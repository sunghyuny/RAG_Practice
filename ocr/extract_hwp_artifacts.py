import argparse
import json
import struct
import sys
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

import olefile

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


TABLE_CONTROL_ID = "tbl "
GRAPHIC_CONTROL_ID = "gso "
TABLE_RELATED_TYPES = {66, 67, 68, 69, 72, 77}

TOC_KEYWORDS = (
    "목차",
    "차례",
    "추진개요",
    "추진방안",
    "추진내용",
    "입찰관련사항",
    "제안요청내용",
    "제안서작성요령",
    "별지서식",
    "붙임",
)

COVER_KEYWORDS = (
    "제안요청서",
    "제안서",
    "용역사업",
    "사업명",
    "사업개요",
    "재단",
    "협회",
    "공사",
    "대학교",
    "주식회사",
)

DATA_TABLE_KEYWORDS = (
    "구분",
    "항목",
    "내용",
    "비고",
    "금액",
    "예산",
    "평가",
    "배점",
    "일정",
    "기간",
    "제출",
    "자격",
    "요구사항",
    "기능",
    "수량",
    "단가",
    "합계",
)

HEADER_KEYWORDS = (
    "구분",
    "항목",
    "내용",
    "비고",
    "금액",
    "배점",
    "평가기준",
    "요구사항",
    "요구사항 ID",
    "요구사항 명칭",
    "수량",
    "단가",
    "합계",
)

BULLET_MARKERS = ("□", "○", "-", "◈", "※", "ㆍ")

HEADER_GROUPS = (
    ("구분", "항목", "내용"),
    ("구분", "내용", "비고"),
    ("요구사항", "ID", "명칭"),
    ("요구사항", "분류", "명칭"),
    ("평가", "배점", "기준"),
    ("평가항목", "배점", "평가기준"),
    ("일정", "기간", "비고"),
    ("예산", "금액", "합계"),
    ("수량", "단가", "금액"),
    ("구분", "역할", "비고"),
)


@dataclass
class HwpTableArtifact:
    table_index: int
    section: str
    record_start_index: int
    row_hint_count: int
    paragraph_count: int
    text_length: int
    classification: str
    toc_score: int
    cover_score: int
    data_score: int
    header_group_hits: int
    text: str


@dataclass
class HwpImageArtifact:
    name: str
    ext: str
    size_bytes: int
    saved_path: str | None


def decode_para_text(payload: bytes) -> str:
    chars: list[str] = []
    j = 0
    while j < len(payload) - 1:
        code = struct.unpack_from("<H", payload, j)[0]

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

    text = "".join(chars)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def count_keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(text.count(keyword) for keyword in keywords)


def count_outline_lines(lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("Ⅰ.", "Ⅱ.", "Ⅲ.", "Ⅳ.", "Ⅴ.", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            count += 1
    return count


def count_numeric_lines(lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(char.isdigit() for char in stripped):
            count += 1
    return count


def classify_table_text(text: str, row_hint_count: int, paragraph_count: int) -> tuple[str, int, int, int]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    toc_score = count_keyword_hits(text, TOC_KEYWORDS)
    cover_score = count_keyword_hits(text, COVER_KEYWORDS)
    data_score = count_keyword_hits(text, DATA_TABLE_KEYWORDS)

    outline_lines = count_outline_lines(lines)
    numeric_lines = count_numeric_lines(lines)
    header_hit_count = sum(1 for keyword in HEADER_KEYWORDS if keyword in text)
    bullet_line_count = sum(1 for line in lines if line.startswith(BULLET_MARKERS))
    long_line_count = sum(1 for line in lines if len(line) >= 40)
    header_group_hits = max(sum(1 for keyword in group if keyword in text) for group in HEADER_GROUPS)

    if outline_lines >= 3:
        toc_score += 2
    if any(line == "목차" or line == "차례" for line in lines):
        toc_score += 3

    if paragraph_count <= 4 and row_hint_count <= 5 and text.count("제안요청서") > 0:
        cover_score += 2
    if paragraph_count <= 4 and any("2024." in line or "2025." in line or "2026." in line for line in lines):
        cover_score += 1

    if row_hint_count >= 3:
        data_score += 1
    if numeric_lines >= max(3, len(lines) // 2):
        data_score += 1
    if any(keyword in text for keyword in ("구분", "항목", "내용", "비고")):
        data_score += 2

    if toc_score >= 4:
        return "toc", toc_score, cover_score, data_score, header_group_hits
    if cover_score >= 4 and data_score <= 3:
        return "cover", toc_score, cover_score, data_score, header_group_hits

    # Gate-based table classification:
    # - sure_table: strong structural signals + a full 3-of-3 header group match.
    # - review_needed: enough structure + a 2-of-3 header group match.
    passes_structure_gate = row_hint_count >= 3 and paragraph_count >= 3
    passes_strict_structure_gate = row_hint_count >= 5 and paragraph_count >= 4
    passes_content_gate = data_score >= 4
    looks_like_explanatory_block = bullet_line_count >= 2 and long_line_count >= 2 and header_hit_count < 2

    if (
        passes_strict_structure_gate
        and header_group_hits >= 3
        and passes_content_gate
        and not looks_like_explanatory_block
    ):
        return "sure_table", toc_score, cover_score, data_score, header_group_hits

    if passes_structure_gate and header_group_hits >= 2 and passes_content_gate:
        return "review_needed", toc_score, cover_score, data_score, header_group_hits

    return "uncertain", toc_score, cover_score, data_score, header_group_hits


def iter_hwp_records(file_path: Path):
    ole = olefile.OleFileIO(str(file_path))
    header_data = ole.openstream("FileHeader").read()
    is_compressed = (header_data[36] & 1) == 1

    try:
        for entry in ole.listdir():
            if not entry or entry[0] != "BodyText":
                continue

            section_name = "/".join(entry)
            data = ole.openstream(section_name).read()
            if is_compressed:
                data = zlib.decompress(data, -15)

            i = 0
            record_index = 0
            while i + 4 <= len(data):
                header = struct.unpack_from("<I", data, i)[0]
                rec_type = header & 0x3FF
                rec_len = (header >> 20) & 0xFFF
                if rec_len == 0xFFF:
                    if i + 8 > len(data):
                        break
                    rec_len = struct.unpack_from("<I", data, i + 4)[0]
                    i += 4

                payload = data[i + 4 : i + 4 + rec_len]
                control_id = ""
                if rec_type in (71, 76):
                    control_id = payload[:4].decode("ascii", errors="ignore")[::-1]

                yield {
                    "section": section_name,
                    "record_index": record_index,
                    "type": rec_type,
                    "length": rec_len,
                    "control_id": control_id,
                    "payload": payload,
                }

                i += 4 + rec_len
                record_index += 1
    finally:
        ole.close()


def extract_hwp_tables(file_path: Path) -> list[HwpTableArtifact]:
    tables: list[HwpTableArtifact] = []
    active_table: dict | None = None

    for record in iter_hwp_records(file_path):
        rec_type = record["type"]
        control_id = record["control_id"]

        if rec_type == 71 and control_id == TABLE_CONTROL_ID:
            if active_table and active_table["paragraphs"]:
                text = "\n".join(active_table["paragraphs"]).strip()
                classification, toc_score, cover_score, data_score, header_group_hits = classify_table_text(
                    text=text,
                    row_hint_count=active_table["row_hints"],
                    paragraph_count=len(active_table["paragraphs"]),
                )
                tables.append(
                    HwpTableArtifact(
                        table_index=len(tables) + 1,
                        section=active_table["section"],
                        record_start_index=active_table["record_start_index"],
                        row_hint_count=active_table["row_hints"],
                        paragraph_count=len(active_table["paragraphs"]),
                        text_length=len(text),
                        classification=classification,
                        toc_score=toc_score,
                        cover_score=cover_score,
                        data_score=data_score,
                        header_group_hits=header_group_hits,
                        text=text,
                    )
                )

            active_table = {
                "section": record["section"],
                "record_start_index": record["record_index"],
                "row_hints": 0,
                "paragraphs": [],
            }
            continue

        if active_table is None:
            continue

        # Table-related records continue the current table body. Any other
        # control header usually means the next object started, so we flush.
        if rec_type == 71 and control_id != TABLE_CONTROL_ID:
            if active_table["paragraphs"]:
                text = "\n".join(active_table["paragraphs"]).strip()
                classification, toc_score, cover_score, data_score, header_group_hits = classify_table_text(
                    text=text,
                    row_hint_count=active_table["row_hints"],
                    paragraph_count=len(active_table["paragraphs"]),
                )
                tables.append(
                    HwpTableArtifact(
                        table_index=len(tables) + 1,
                        section=active_table["section"],
                        record_start_index=active_table["record_start_index"],
                        row_hint_count=active_table["row_hints"],
                        paragraph_count=len(active_table["paragraphs"]),
                        text_length=len(text),
                        classification=classification,
                        toc_score=toc_score,
                        cover_score=cover_score,
                        data_score=data_score,
                        header_group_hits=header_group_hits,
                        text=text,
                    )
                )
            active_table = None
            continue

        if rec_type not in TABLE_RELATED_TYPES:
            if active_table["paragraphs"]:
                text = "\n".join(active_table["paragraphs"]).strip()
                classification, toc_score, cover_score, data_score, header_group_hits = classify_table_text(
                    text=text,
                    row_hint_count=active_table["row_hints"],
                    paragraph_count=len(active_table["paragraphs"]),
                )
                tables.append(
                    HwpTableArtifact(
                        table_index=len(tables) + 1,
                        section=active_table["section"],
                        record_start_index=active_table["record_start_index"],
                        row_hint_count=active_table["row_hints"],
                        paragraph_count=len(active_table["paragraphs"]),
                        text_length=len(text),
                        classification=classification,
                        toc_score=toc_score,
                        cover_score=cover_score,
                        data_score=data_score,
                        header_group_hits=header_group_hits,
                        text=text,
                    )
                )
            active_table = None
            continue

        if rec_type == 72:
            active_table["row_hints"] += 1
        elif rec_type == 67:
            text = decode_para_text(record["payload"])
            if text:
                active_table["paragraphs"].append(text)

    if active_table and active_table["paragraphs"]:
        text = "\n".join(active_table["paragraphs"]).strip()
        classification, toc_score, cover_score, data_score, header_group_hits = classify_table_text(
            text=text,
            row_hint_count=active_table["row_hints"],
            paragraph_count=len(active_table["paragraphs"]),
        )
        tables.append(
            HwpTableArtifact(
                table_index=len(tables) + 1,
                section=active_table["section"],
                record_start_index=active_table["record_start_index"],
                row_hint_count=active_table["row_hints"],
                paragraph_count=len(active_table["paragraphs"]),
                text_length=len(text),
                classification=classification,
                toc_score=toc_score,
                cover_score=cover_score,
                data_score=data_score,
                header_group_hits=header_group_hits,
                text=text,
            )
        )

    return tables


def extract_hwp_images(file_path: Path, save_dir: Path | None = None) -> list[HwpImageArtifact]:
    ole = olefile.OleFileIO(str(file_path))
    images: list[HwpImageArtifact] = []

    try:
        for entry in ole.listdir(streams=True, storages=False):
            if not entry or entry[0] != "BinData":
                continue

            stream_name = "/".join(entry)
            name = entry[-1]
            ext = Path(name).suffix.lower().lstrip(".") or "bin"
            data = ole.openstream(stream_name).read()

            saved_path: str | None = None
            if save_dir is not None:
                save_dir.mkdir(parents=True, exist_ok=True)
                image_path = save_dir / name
                image_path.write_bytes(data)
                saved_path = str(image_path.resolve())

            images.append(
                HwpImageArtifact(
                    name=name,
                    ext=ext,
                    size_bytes=len(data),
                    saved_path=saved_path,
                )
            )
    finally:
        ole.close()

    return images


def extract_hwp_artifacts(file_path: Path, save_images: bool = False, output_dir: Path | None = None) -> dict:
    image_dir = output_dir / "hwp_images" if save_images and output_dir is not None else None
    tables = extract_hwp_tables(file_path)
    images = extract_hwp_images(file_path, save_dir=image_dir)

    return {
        "source_path": str(file_path.resolve()),
        "source_name": file_path.name,
        "file_type": ".hwp",
        "status": "ok",
        "table_count": len(tables),
        "toc_table_count": sum(1 for table in tables if table.classification == "toc"),
        "cover_table_count": sum(1 for table in tables if table.classification == "cover"),
        "sure_table_count": sum(1 for table in tables if table.classification == "sure_table"),
        "review_needed_count": sum(1 for table in tables if table.classification == "review_needed"),
        "uncertain_table_count": sum(1 for table in tables if table.classification == "uncertain"),
        "image_count": len(images),
        "tables": [asdict(table) for table in tables],
        "images": [asdict(image) for image in images],
    }


def summarize(payload: dict) -> str:
    lines = [
        f"source: {payload['source_name']}",
        f"tables: {payload['table_count']}",
        f"  sure_table: {payload['sure_table_count']}",
        f"  review_needed: {payload['review_needed_count']}",
        f"  toc: {payload['toc_table_count']}",
        f"  cover: {payload['cover_table_count']}",
        f"  uncertain: {payload['uncertain_table_count']}",
        f"images: {payload['image_count']}",
        "",
    ]

    for table in payload["tables"][:3]:
        lines.append(
            f"table {table['table_index']}: class={table['classification']} "
            f"section={table['section']} row_hints={table['row_hint_count']} "
            f"paragraphs={table['paragraph_count']} text_length={table['text_length']} "
            f"(toc={table['toc_score']}, cover={table['cover_score']}, data={table['data_score']}, header_hits={table['header_group_hits']})"
        )
        preview = table["text"][:200].replace("\n", " / ")
        lines.append(f"   preview: {preview}")

    for index, image in enumerate(payload["images"][:5], start=1):
        lines.append(
            f"image {index}: {image['name']} ext={image['ext']} size={image['size_bytes']} saved={image['saved_path']}"
        )

    return "\n".join(lines)


def safe_console(text: str) -> str:
    return text.encode("cp949", errors="replace").decode("cp949")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract table and image artifacts directly from an HWP file.")
    parser.add_argument("--file", type=Path, required=True, help="HWP file path.")
    parser.add_argument("--json", type=Path, default=None, help="Optional output JSON path.")
    parser.add_argument("--save-images", action="store_true", help="Save BinData images to disk.")
    args = parser.parse_args()

    output_dir = args.json.parent if args.json is not None else Path("ocr/output")
    payload = extract_hwp_artifacts(args.file, save_images=args.save_images, output_dir=output_dir)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(safe_console(summarize(payload)))


if __name__ == "__main__":
    main()
