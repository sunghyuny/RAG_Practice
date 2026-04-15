import csv
import re
import struct
import sys
import warnings
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    import olefile
except ImportError:  # pragma: no cover
    olefile = None

try:
    import pymupdf4llm
except ImportError:  # pragma: no cover
    pymupdf4llm = None
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_system.config import SETTINGS

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocr.extract_hwp_artifacts import extract_hwp_artifacts
from ocr.run_hwp_ocr_pipeline import run_image_ocr


warnings.filterwarnings("ignore")

SECTION_PATTERNS = [
    re.compile(r"^\s*제?\s*\d+\s*장\b.*$"),
    re.compile(r"^\s*\d+(\.\d+){0,3}[\.\)]\s+.+$"),
    re.compile(r"^\s*[가-힣][\.\)]\s+.+$"),
    re.compile(r"^\s*[A-Z][\.\)]\s+.+$"),
    re.compile(
        r"^\s*(사업개요|사업 목적|추진 배경|추진 목적|제안 요청 내용|제안요청내용|제안 범위|과업 내용|과업내용|제출 서류|입찰 참가 자격|평가 기준|평가기준|사업 예산|예산|추진 일정|일정)\s*$"
    ),
]

TAG_RULES = {
    "budget": {
        "strong": ["예산", "사업비", "예산액", "기초금액", "추정금액", "총사업비", "배정예산"],
        "weak": ["금액", "원", "vat", "부가세"],
        "threshold": 2,
    },
    "submission": {
        "strong": ["제출", "제안서 제출", "접수", "제출서류", "제출방법", "방문접수", "전자제출"],
        "weak": ["우편", "이메일", "usb", "마감"],
        "threshold": 2,
    },
    "evaluation": {
        "strong": ["평가", "평가기준", "배점", "기술평가", "정량평가", "정성평가", "종합평가"],
        "weak": ["심사", "점수"],
        "threshold": 2,
    },
    "purpose": {
        "strong": ["목적", "사업목적", "추진목적", "추진배경", "사업개요", "사업목표"],
        "weak": ["배경", "필요성", "기대효과"],
        "threshold": 2,
    },
    "deadline": {
        "strong": ["마감", "마감일", "기한", "제출기한", "접수기간", "공고기간", "제안서 제출일시"],
        "weak": ["일정", "일시", "기간"],
        "threshold": 2,
    },
    "requirement": {
        "strong": ["요구사항", "과업내용", "과업범위", "기능요건", "기술요건", "상세요건"],
        "weak": ["요건", "기능", "성능", "범위", "구현"],
        "threshold": 2,
    },
    "qualification": {
        "strong": ["자격", "참가자격", "입찰참가자격", "제안자격", "자격요건"],
        "weak": ["실적", "인력", "면허", "등록", "인증"],
        "threshold": 2,
    },
}

TAG_KEYWORDS = {tag: rules["strong"] + rules["weak"] for tag, rules in TAG_RULES.items()}

CSV_METADATA_FIELDS = {
    "공고 번호": "notice_id",
    "공고 차수": "notice_round",
    "사업명": "project_name",
    "사업 금액": "bid_amount",
    "발주 기관": "issuer",
    "공개 일자": "posted_at",
    "입찰 참여 시작일": "bid_start_at",
    "입찰 참여 마감일": "bid_end_at",
    "사업 요약": "project_summary",
    "파일형식": "listed_extension",
    "파일명": "listed_filename",
}
def build_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=SETTINGS.embedding_model,
        model_kwargs={
            "device": SETTINGS.embedding_device,
            "local_files_only": True,
        },
    )


def build_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " "],
        chunk_size=SETTINGS.chunk_size,
        chunk_overlap=SETTINGS.chunk_overlap,
    )


def clean_text(text: str) -> str:
    text = re.sub(r"\*\*==>.*?<==\*\*", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[^\S\r\n]{3,}", " ", text)
    text = re.sub(r"\.{4,}", " ", text)
    text = re.sub(r"\n\s*-\d+-\s*\n", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^\|[-|\s]+\|\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|[\s|]*\|\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if len(stripped) < 4:
        return False
    if len(stripped) > 70 and not stripped.startswith("제"):
        return False
    if stripped.endswith((".", ",")):
        return False
    if len(stripped.split()) > 12:
        return False
    return any(pattern.match(stripped) for pattern in SECTION_PATTERNS)


def split_into_sections(text: str) -> List[dict]:
    sections: List[dict] = []
    current_header = "문서 개요"
    current_lines: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        if is_section_header(line):
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append({"header": current_header, "body": body})
            current_header = line
            current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append({"header": current_header, "body": body})

    if not sections:
        return [{"header": "문서 개요", "body": text}]
    return sections


def chunk_section(section: dict, splitter: RecursiveCharacterTextSplitter) -> List[dict]:
    header = section["header"].strip()
    body = section["body"].strip()
    combined = f"{header}\n{body}" if body else header

    if len(combined) <= SETTINGS.chunk_size:
        return [{"section": header, "content": combined}]

    chunks = splitter.split_text(body)
    results = []
    for index, chunk in enumerate(chunks, start=1):
        chunk = chunk.strip()
        if not chunk:
            continue
        label = header if len(chunks) == 1 else f"{header} (part {index})"
        results.append({"section": header, "content": f"{header}\n{chunk}", "subchunk_label": label})
    return results


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def normalize_filename(text: str) -> str:
    lowered = normalize_text(text)
    return re.sub(r"[^0-9a-z가-힣]", "", lowered)


def match_keywords(text: str, keywords: List[str]) -> List[str]:
    normalized = normalize_text(text)
    return [keyword for keyword in keywords if normalize_text(keyword) in normalized]


def score_tags(text: str, section: Optional[str] = None) -> dict[str, dict]:
    body = text or ""
    section_text = section or ""
    scored = {}

    for tag, rules in TAG_RULES.items():
        strong_hits = match_keywords(body, rules["strong"])
        weak_hits = match_keywords(body, rules["weak"])
        section_hits = match_keywords(section_text, rules["strong"] + rules["weak"])
        score = len(strong_hits) * 2 + len(weak_hits) + len(section_hits) * 2

        if score >= rules["threshold"]:
            scored[tag] = {
                "score": score,
                "strong_hits": strong_hits,
                "weak_hits": weak_hits,
                "section_hits": section_hits,
            }

    return scored


def infer_tags(text: str, section: Optional[str] = None) -> dict:
    scored_tags = score_tags(text=text, section=section)
    matched_tags = sorted(scored_tags, key=lambda tag: (-scored_tags[tag]["score"], tag))
    primary_tag = matched_tags[0] if matched_tags else "general"
    return {
        "primary_tag": primary_tag,
        "tags": ", ".join(matched_tags) if matched_tags else "",
        "has_budget": "budget" in matched_tags,
        "has_submission": "submission" in matched_tags,
        "has_evaluation": "evaluation" in matched_tags,
        "has_purpose": "purpose" in matched_tags,
        "has_deadline": "deadline" in matched_tags,
        "has_requirement": "requirement" in matched_tags,
        "has_qualification": "qualification" in matched_tags,
    }


def load_csv_metadata(csv_path: Path = SETTINGS.metadata_csv_path) -> Dict[str, dict]:
    if not csv_path.exists():
        return {}

    metadata_by_filename: Dict[str, dict] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            filename = (row.get("파일명") or "").strip()
            if not filename:
                continue

            mapped = {}
            for source_key, target_key in CSV_METADATA_FIELDS.items():
                value = (row.get(source_key) or "").strip()
                if value:
                    mapped[target_key] = value

            metadata_by_filename[normalize_filename(filename)] = mapped

    return metadata_by_filename


def get_document_metadata(file_path: Path, metadata_by_filename: Optional[Dict[str, dict]] = None) -> dict:
    metadata_by_filename = metadata_by_filename or {}
    return metadata_by_filename.get(normalize_filename(file_path.name), {}).copy()


def extract_pdf_text(file_path: Path) -> str:
    if pymupdf4llm is None:
        raise RuntimeError("pymupdf4llm is required to read PDF files.")
    return pymupdf4llm.to_markdown(str(file_path))


def extract_hwp_text(file_path: Path) -> str:
    if olefile is None:
        raise RuntimeError("olefile is required to read HWP files.")
    try:
        hwp = olefile.OleFileIO(str(file_path))
        if not hwp.exists("FileHeader"):
            hwp.close()
            return ""

        header_data = hwp.openstream("FileHeader").read()
        is_compressed = (header_data[36] & 1) == 1
        text_parts: List[str] = []

        for entry in hwp.listdir():
            if not entry or entry[0] != "BodyText":
                continue

            data = hwp.openstream("/".join(entry)).read()
            if is_compressed:
                try:
                    data = zlib.decompress(data, -15)
                except zlib.error:
                    continue

            i = 0
            size = len(data)
            while i < size:
                if i + 4 > size:
                    break

                header = struct.unpack_from("<I", data, i)[0]
                rec_type = header & 0x3FF
                rec_len = (header >> 20) & 0xFFF

                if rec_len == 0xFFF:
                    if i + 8 > size:
                        break
                    rec_len = struct.unpack_from("<I", data, i + 4)[0]
                    i += 4

                if rec_type == 67:
                    rec_data = data[i + 4 : i + 4 + rec_len]
                    chars: List[str] = []
                    j = 0
                    while j < len(rec_data) - 1:
                        code = struct.unpack_from("<H", rec_data, j)[0]

                        if code in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23):
                            j += 14
                            continue
                        if code in (4, 5, 6, 7, 8, 9, 19, 20):
                            j += 10
                            continue
                        if code in (10, 13):
                            chars.append("\n")
                            j += 2
                            continue
                        if code == 24:
                            chars.append("\t")
                            j += 14
                            continue
                        if code == 0 or 0xD800 <= code <= 0xDFFF:
                            j += 2
                            continue

                        chars.append(chr(code))
                        j += 2

                    line = "".join(chars).strip()
                    if line:
                        text_parts.append(line)

                i += 4 + rec_len

        if not text_parts and hwp.exists("PrvText"):
            preview = hwp.openstream("PrvText").read().decode("utf-16-le", errors="ignore").strip()
            if preview:
                text_parts.append(preview)

        hwp.close()
        return "\n".join(text_parts)
    except Exception:
        return ""


def normalize_ocr_lines(lines: List[str]) -> List[str]:
    cleaned_lines: List[str] = []
    for line in lines:
        normalized = re.sub(r"\s+", " ", line).strip()
        if len(normalized) < 2:
            continue
        cleaned_lines.append(normalized)
    return cleaned_lines


TABLE_FIELD_HINTS = (
    "요구사항",
    "요구",
    "사항",
    "분류",
    "고유번호",
    "ID",
    "명칭",
    "정의",
    "설명",
    "세부",
    "내용",
    "산출정보",
    "관련",
    "사용자",
    "기능",
    "구분",
    "내역",
    "수량",
    "비고",
    "장비",
    "지역",
    "대상",
    "기간",
    "일정",
    "금액",
    "배점",
    "기준",
)


def normalize_table_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def looks_like_table_label(line: str) -> bool:
    stripped = normalize_table_line(line)
    if not stripped:
        return False
    compact = re.sub(r"\s+", "", stripped)
    if len(compact) <= 10:
        return True
    if any(hint in stripped for hint in TABLE_FIELD_HINTS):
        return True
    if re.fullmatch(r"[A-Z]{2,5}[-_ ]?\d{2,4}", stripped):
        return True
    return False


def join_table_value_lines(lines: List[str]) -> str:
    normalized = [normalize_table_line(line) for line in lines if normalize_table_line(line)]
    return " / ".join(normalized)


def extract_key_value_pairs(table_text: str) -> List[tuple[str, str]]:
    lines = [normalize_table_line(line) for line in table_text.splitlines() if normalize_table_line(line)]
    pairs: List[tuple[str, str]] = []
    index = 0

    while index < len(lines) - 1:
        label = lines[index]
        if not looks_like_table_label(label):
            index += 1
            continue

        value_lines: List[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if value_lines and looks_like_table_label(candidate):
                break
            if not value_lines and candidate == label:
                break
            value_lines.append(candidate)
            cursor += 1
            if len(value_lines) >= 6:
                break

        value = join_table_value_lines(value_lines)
        if value and value != label:
            pairs.append((label, value))
            index = cursor
            continue

        index += 1

    deduped: List[tuple[str, str]] = []
    seen = set()
    for label, value in pairs:
        key = (label, value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((label, value))
    return deduped


def build_table_key_value_lines(table_text: str) -> List[str]:
    pairs = extract_key_value_pairs(table_text)
    return [f"{label}: {value}" for label, value in pairs[:8]]


def build_table_row_summary_lines(table_text: str) -> List[str]:
    pairs = extract_key_value_pairs(table_text)
    summaries: List[str] = []

    current: List[str] = []
    for label, value in pairs:
        current.append(f"{label}={value}")
        if len(current) == 3:
            summaries.append(" / ".join(current))
            current = []

    if current:
        summaries.append(" / ".join(current))

    return summaries[:4]


def extract_table_lines(table_text: str) -> List[str]:
    return [normalize_table_line(line) for line in table_text.splitlines() if normalize_table_line(line)]


def find_pair_value(pairs: List[tuple[str, str]], *keywords: str) -> Optional[str]:
    for label, value in pairs:
        if any(keyword in label for keyword in keywords):
            return value
    return None


def detect_table_type(table: dict, table_text: str, pairs: List[tuple[str, str]]) -> str:
    parent_text = normalize_table_line(table.get("linked_parent_text") or "")
    body = f"{parent_text}\n{table_text}"

    if any(keyword in body for keyword in ["장비", "교환기", "CTI", "IP녹취", "대상지역", "대상 지역"]):
        return "equipment_region"
    if any(keyword in body for keyword in ["모바일오피스", "업무지원 앱", "업무전용앱", "탑재 앱", "앱 목록", "서비스 구성"]):
        return "service_status"
    if any(keyword in body for keyword in ["AI", "삭제지원", "피해촬영물", "검출", "일치율", "판별"]):
        return "ai_requirement"
    if any(keyword in body for keyword in ["요구사항 고유번호", "요구사항 ID", "요구사항 명칭"]) or find_pair_value(pairs, "요구사항 고유번호", "요구사항 ID"):
        return "requirement_table"
    if any(keyword in body for keyword in ["배점", "평가기준", "평가항목"]):
        return "score_table"
    if any(keyword in body for keyword in ["일정", "기간", "제출", "마감"]):
        return "schedule_table"
    return "general_table"


def infer_table_title(table: dict, doc_title: str, table_type: str) -> str:
    parent_text = normalize_table_line(table.get("linked_parent_text") or "")
    if parent_text:
        return parent_text

    title_by_type = {
        "equipment_region": "도입 장비 및 대상 지역",
        "service_status": "기존 기능 및 서비스 구성 현황",
        "ai_requirement": "AI 기반 기능 요구사항",
        "requirement_table": "요구사항 상세 표",
        "score_table": "평가 및 배점 표",
        "schedule_table": "일정 및 기간 표",
        "general_table": f"{doc_title} 구조형 표",
    }
    return title_by_type.get(table_type, f"{doc_title} 구조형 표")


def collect_matching_lines(table_text: str, keywords: List[str], limit: int = 3) -> List[str]:
    matches: List[str] = []
    for line in extract_table_lines(table_text):
        if any(keyword in line for keyword in keywords):
            matches.append(line)
        if len(matches) >= limit:
            break
    return matches


def summarize_terms(table_text: str, terms: List[str], limit: int = 6) -> str:
    found: List[str] = []
    for term in terms:
        if term in table_text and term not in found:
            found.append(term)
        if len(found) >= limit:
            break
    return ", ".join(found)


def build_type_template_summary(table_type: str, table_text: str, pairs: List[tuple[str, str]]) -> List[str]:
    lines: List[str] = []

    if table_type == "equipment_region":
        id_value = find_pair_value(pairs, "요구사항 고유번호", "요구사항 ID")
        name_value = find_pair_value(pairs, "요구사항 명칭", "명칭")
        equipment_terms = summarize_terms(table_text, ["CTI", "교환기", "IP녹취", "IP전화기", "게이트웨이", "서버", "SIP", "PSTN"])
        region_terms = summarize_terms(table_text, ["중앙", "서울", "대전", "대구", "광주"])
        if id_value:
            lines.append(f"요구사항 ID: {id_value}")
        if name_value:
            lines.append(f"요구사항 명칭: {name_value}")
        if equipment_terms:
            lines.append(f"장비 목록: {equipment_terms}")
        if region_terms:
            lines.append(f"대상 지역: {region_terms}")
        return lines

    if table_type == "service_status":
        service_terms = summarize_terms(table_text, ["모바일오피스", "업무전용앱", "업무지원 앱", "VPN", "MDM", "메신저", "그룹채팅", "전화걸기"])
        purpose_lines = collect_matching_lines(table_text, ["통합", "이관", "폐지", "사용", "기능"], limit=2)
        if service_terms:
            lines.append(f"주요 서비스/앱: {service_terms}")
        lines.extend(f"현황 요약: {line}" for line in purpose_lines)
        return lines

    if table_type == "ai_requirement":
        feature_lines = collect_matching_lines(table_text, ["AI", "삭제지원", "검출", "검색", "판별", "일치율"], limit=4)
        lines.extend(f"AI 요구사항: {line}" for line in feature_lines)
        return lines

    if table_type == "requirement_table":
        id_value = find_pair_value(pairs, "요구사항 고유번호", "요구사항 ID")
        name_value = find_pair_value(pairs, "요구사항 명칭", "명칭")
        user_value = find_pair_value(pairs, "사용자")
        detail_value = find_pair_value(pairs, "세부", "내용", "정의")
        if id_value:
            lines.append(f"요구사항 ID: {id_value}")
        if name_value:
            lines.append(f"요구사항 명칭: {name_value}")
        if user_value:
            lines.append(f"대상 사용자: {user_value}")
        if detail_value:
            lines.append(f"핵심 내용: {detail_value[:220]}")
        return lines

    return []


def build_comparison_summary(table_type: str, table_text: str) -> List[str]:
    lines: List[str] = []

    if table_type == "equipment_region":
        equipment_terms = summarize_terms(table_text, ["CTI", "교환기", "IP녹취", "IP전화기", "게이트웨이", "호처리 서버", "SIP", "PSTN"])
        region_terms = summarize_terms(table_text, ["중앙", "서울", "대전", "대구", "광주"])
        if equipment_terms:
            lines.append(f"도입 장비 축: {equipment_terms}")
        if region_terms:
            lines.append(f"지역 축: {region_terms}")

    if table_type == "service_status":
        current_lines = collect_matching_lines(table_text, ["기존", "현황", "이관", "통합", "폐지"], limit=3)
        lines.extend(f"서비스 구성 축: {line}" for line in current_lines)

    if table_type == "ai_requirement":
        problem_lines = collect_matching_lines(table_text, ["검색", "검출", "삭제지원", "판별", "일치율"], limit=3)
        lines.extend(f"해결 기능 축: {line}" for line in problem_lines)

    return lines[:4]


def build_table_bridge_line(doc_title: str, table: dict) -> str | None:
    parent_text = normalize_table_line(table.get("linked_parent_text") or "")
    if parent_text:
        return f"이 표는 {doc_title} 문서의 '{parent_text}' 관련 내용을 구조적으로 정리한 것이다."
    return f"이 표는 {doc_title} 문서에서 추출한 구조형 표이다."


def build_table_block(table: dict, doc_title: str) -> str | None:
    body = (table.get("text") or "").strip()
    if not body:
        return None
    pairs = extract_key_value_pairs(body)
    table_type = detect_table_type(table, body, pairs)
    table_title = infer_table_title(table, doc_title, table_type)

    prefixes: List[str] = ["[STRUCTURAL_TABLE]"]
    final_classification = table.get("final_classification")
    if final_classification:
        prefixes.append(f"[{final_classification}]")
    if table.get("ocr_candidate_priority") in {"high", "medium"}:
        prefixes.append(f"[OCR_CANDIDATE:{table['ocr_candidate_priority']}]")

    header = " ".join(prefixes)
    lines = [
        header,
        f"[DOC_TITLE] {doc_title}",
        f"[TABLE_INDEX] {table['table_index']}",
        f"[TABLE_TITLE] {table_title}",
        f"[TABLE_TYPE] {table_type}",
    ]

    if table.get("linked_parent_text"):
        lines.append(f"[SECTION_HEADER] {table['linked_parent_text']}")

    bridge_line = build_table_bridge_line(doc_title, table)
    if bridge_line:
        lines.append(f"[TABLE_CONTEXT] {bridge_line}")

    type_template_lines = build_type_template_summary(table_type, body, pairs)
    if type_template_lines:
        lines.append("[TYPE_TEMPLATE_SUMMARY]")
        lines.extend(type_template_lines)

    comparison_lines = build_comparison_summary(table_type, body)
    if comparison_lines:
        lines.append("[COMPARISON_SUMMARY]")
        lines.extend(comparison_lines)

    key_value_lines = [f"{label}: {value}" for label, value in pairs[:8]]
    if key_value_lines:
        lines.append("[KEY_VALUE_SUMMARY]")
        lines.extend(key_value_lines)

    row_summary_lines = build_table_row_summary_lines(body)
    if row_summary_lines:
        lines.append("[ROW_SUMMARY]")
        lines.extend(row_summary_lines)

    lines.append("[RAW_TABLE_TEXT]")
    lines.append(body)
    return "\n".join(lines).strip()


def build_image_blocks(payload: dict) -> List[str]:
    blocks: List[str] = []

    for image in payload.get("image_ocr_candidates", []):
        saved_path = image.get("saved_path")
        if not saved_path:
            continue

        ocr_result = run_image_ocr(Path(saved_path))
        cleaned_lines = normalize_ocr_lines(ocr_result.get("ocr_lines", []))
        if not cleaned_lines:
            continue

        joined_text = "\n".join(cleaned_lines)
        if len(joined_text) < 20:
            continue

        block_lines = [
            "[IMAGE_OCR]",
            f"[IMAGE_NAME] {image['name']}",
            f"[OCR_PRIORITY] {image.get('ocr_candidate_priority', 'low')}",
            joined_text,
        ]
        blocks.append("\n".join(block_lines).strip())

    return blocks


def build_hwp_semantic_text(file_path: Path) -> str:
    payload = extract_hwp_artifacts(file_path, save_images=True, output_dir=ROOT_DIR / "ocr")

    blocks: List[str] = []
    doc_title = file_path.stem

    for table in payload.get("structural_tables", []):
        table_block = build_table_block(table, doc_title)
        if table_block:
            blocks.append(table_block)

    for block in payload.get("explanatory_blocks", []):
        body = block.get("text", "").strip()
        if body:
            blocks.append(f"[EXPLANATORY_BLOCK]\n{body}")

    for header in payload.get("section_header_blocks", []):
        if header.get("linked_child_table_indices"):
            child_labels = ", ".join(str(idx) for idx in header["linked_child_table_indices"])
            body = header.get("text", "").strip()
            if body:
                blocks.append(f"[SECTION_HEADER] children={child_labels}\n{body}")

    blocks.extend(build_image_blocks(payload))

    return "\n\n".join(blocks).strip()


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(file_path)
    if suffix == ".hwp":
        semantic_text = build_hwp_semantic_text(file_path)
        if semantic_text:
            return semantic_text
        return extract_hwp_text(file_path)
    return ""


def make_documents(
    file_path: Path,
    splitter: RecursiveCharacterTextSplitter,
    metadata_by_filename: Optional[Dict[str, dict]] = None,
) -> List[Document]:
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        return []

    cleaned = clean_text(raw_text)
    sections = split_into_sections(cleaned)
    title = file_path.stem
    mapped_metadata = get_document_metadata(file_path, metadata_by_filename)
    docs: List[Document] = []

    chunk_index = 0
    for section in sections:
        for chunk_info in chunk_section(section, splitter):
            chunk = chunk_info["content"].strip()
            if len(chunk) < 20:
                continue
            section_name: Optional[str] = chunk_info.get("section")
            docs.append(
                Document(
                    page_content=f"[사업명: {title}]\n[섹션: {section_name or '문서 개요'}]\n---\n{chunk}",
                    metadata={
                        "title": title,
                        "source": file_path.name,
                        "file_path": str(file_path.resolve()),
                        "chunk_id": chunk_index,
                        "extension": file_path.suffix.lower(),
                        "section": section_name or "문서 개요",
                        **mapped_metadata,
                        **infer_tags(chunk, section_name),
                    },
                )
            )
            chunk_index += 1
    return docs


def iter_source_files(base_dir: Path) -> Iterable[Path]:
    for pattern in ("*.pdf", "*.hwp"):
        yield from sorted(base_dir.glob(pattern))
