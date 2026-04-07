import re
import struct
import warnings
import zlib
from pathlib import Path
from typing import Iterable, List, Optional

import olefile
import pymupdf4llm
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_system.config import SETTINGS


warnings.filterwarnings("ignore")

SECTION_PATTERNS = [
    re.compile(r"^\s*제\s*\d+\s*(장|절|조)\b.*$"),
    re.compile(r"^\s*\d+(\.\d+){0,3}[\.\)]\s+.+$"),
    re.compile(r"^\s*[가-하][\.\)]\s+.+$"),
    re.compile(r"^\s*[A-Z][\.\)]\s+.+$"),
    re.compile(r"^\s*(사업개요|사업 목적|추진 배경|추진 목적|제안 요청 내용|제안요청내용|제안 범위|과업 내용|과업내용|제출 서류|입찰 참가 자격|평가 기준|평가기준|사업 예산|예산|추진 일정|일정)\s*$"),
]

TAG_KEYWORDS = {
    "budget": ["예산", "사업비", "총액", "금액", "추정가격", "기초금액", "원", "억원"],
    "submission": ["제출", "제안서", "접수", "제출장소", "제출서류", "우편", "방문접수", "전자제출", "나라장터", "usb"],
    "evaluation": ["평가", "배점", "기술평가", "가격평가", "평가기준", "종합평가", "점수"],
    "purpose": ["목적", "배경", "필요성", "추진배경", "추진목적", "사업목표", "기대효과"],
    "deadline": ["마감", "기한", "제출기한", "접수기간", "공고기간", "일정", "제안서 제출일", "입찰일시"],
    "requirement": ["요구사항", "기능", "구축", "개발", "연계", "성능", "테스트", "과업", "범위"],
    "qualification": ["자격", "참가자격", "입찰참가", "실적", "인력", "면허", "인증", "등록"],
}


def build_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=SETTINGS.embedding_model,
        model_kwargs={"device": SETTINGS.embedding_device},
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
    text = re.sub(r"[·•▪■]{3,}", " ", text)
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


def infer_tags(text: str, section: Optional[str] = None) -> dict:
    search_space = f"{section or ''}\n{text}"
    matched_tags = []

    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword.lower() in search_space.lower() for keyword in keywords):
            matched_tags.append(tag)

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


def extract_pdf_text(file_path: Path) -> str:
    return pymupdf4llm.to_markdown(str(file_path))


def extract_hwp_text(file_path: Path) -> str:
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


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(file_path)
    if suffix == ".hwp":
        return extract_hwp_text(file_path)
    return ""


def make_documents(file_path: Path, splitter: RecursiveCharacterTextSplitter) -> List[Document]:
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        return []

    cleaned = clean_text(raw_text)
    sections = split_into_sections(cleaned)
    title = file_path.stem
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
                        **infer_tags(chunk, section_name),
                    },
                )
            )
            chunk_index += 1
    return docs


def iter_source_files(base_dir: Path) -> Iterable[Path]:
    for pattern in ("*.pdf", "*.hwp"):
        yield from sorted(base_dir.glob(pattern))
