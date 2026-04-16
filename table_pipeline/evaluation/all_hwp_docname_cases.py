from pathlib import Path

from rag_system.config import SETTINGS


QUESTION_TEMPLATES = [
    "{doc} 문서에서 구축 대상 기능 목록이나 모듈 구성이 어떻게 돼? 표나 기능 분류가 있으면 정리해줘.",
    "{doc} 문서에서 표로 정리된 주요 요구사항이나 핵심 기능 항목을 정리해줘.",
    "{doc} 문서에서 도입 장비, 시스템 구성, 연계 대상 같은 항목이 있으면 표 기준으로 알려줘.",
    "{doc} 문서에서 일정, 평가항목, 배점, 산출물, 제출서류처럼 표로 정리된 핵심 정보가 뭐야?",
    "{doc} 문서에서 기존 현황, 서비스 구성, 개선 대상이나 신규 도입 내용이 있으면 표 기준으로 설명해줘.",
]


def list_hwp_doc_titles(base_dir: Path | None = None) -> list[str]:
    root = Path(base_dir or SETTINGS.base_dir)
    titles = [path.stem for path in sorted(root.glob("*.hwp"))]
    return titles


def build_cases(base_dir: Path | None = None) -> list[dict]:
    cases: list[dict] = []
    for title in list_hwp_doc_titles(base_dir=base_dir):
        for template_index, template in enumerate(QUESTION_TEMPLATES, start=1):
            cases.append(
                {
                    "doc_title": title,
                    "template_id": f"T{template_index:02d}",
                    "query": template.format(doc=title),
                    "expected_title_contains": title,
                }
            )
    return cases


ALL_HWP_DOCNAME_CASES = build_cases()
