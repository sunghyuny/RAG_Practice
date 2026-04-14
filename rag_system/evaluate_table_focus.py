import argparse
from pathlib import Path
from time import perf_counter

from rag_system.qa import answer_query


TABLE_FOCUSED_QUERIES = [
    "(사)벤처기업협회 문서의 사업기간과 소요예산은 얼마야?",
    "(사)벤처기업협회 문서의 기술평가와 가격평가 배점은 각각 몇 점이야?",
    "(사)벤처기업협회 문서의 제출서류 목록을 알려줘.",
    "(사)벤처기업협회 문서에서 요구사항 고유번호 SFR-001의 명칭과 세부내용을 알려줘.",
    "국방과학연구소 기록관리시스템 문서의 평가항목과 배점 기준을 알려줘.",
    "국방과학연구소 기록관리시스템 문서에서 수행실적 평가등급별 평점을 알려줘.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run table-focused evaluation queries against the RAG system.")
    parser.add_argument(
        "--retrieval-mode",
        choices=["baseline", "mmr"],
        default="baseline",
        help="Retrieval strategy to evaluate",
    )
    args = parser.parse_args()

    retrieval_mode = args.retrieval_mode
    output_path = Path(f"llm_answer_table_focus_{retrieval_mode}.txt")
    results = []
    started_at = perf_counter()

    for query in TABLE_FOCUSED_QUERIES:
        query_started_at = perf_counter()
        try:
            result = answer_query(query, retrieval_mode=retrieval_mode)
            titles = sorted({doc.metadata.get("title", "") for doc in result["documents"]})
            results.append(
                {
                    "query": query,
                    "answer": result["answer"],
                    "titles": titles,
                    "docs_count": len(result["documents"]),
                    "elapsed_seconds": perf_counter() - query_started_at,
                    "status": "success",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "query": query,
                    "answer": f"ERROR: {exc}",
                    "titles": [],
                    "docs_count": 0,
                    "elapsed_seconds": perf_counter() - query_started_at,
                    "status": "failed",
                }
            )

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("RAG table-focused evaluation snapshot\n")
        handle.write(f"Retrieval mode: {retrieval_mode}\n")
        handle.write("=" * 60 + "\n\n")
        for index, item in enumerate(results, start=1):
            handle.write(f"[Test {index}] {item['query']}\n")
            handle.write(f"Status: {item['status']}\n")
            handle.write(f"Elapsed: {item['elapsed_seconds']:.2f}s\n")
            handle.write(f"Retrieved chunks: {item['docs_count']}\n")
            handle.write(f"Projects: {', '.join(item['titles']) or 'N/A'}\n")
            handle.write(f"Answer:\n{item['answer']}\n")
            handle.write("\n" + "-" * 60 + "\n\n")

        total_elapsed = perf_counter() - started_at
        success_count = sum(1 for item in results if item["status"] == "success")
        handle.write(f"Successful tests: {success_count}/{len(results)}\n")
        handle.write(f"Total elapsed: {total_elapsed:.2f}s\n")

    print(f"Saved table-focused evaluation results to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
