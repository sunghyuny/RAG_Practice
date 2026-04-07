from pathlib import Path

from langchain_community.callbacks import get_openai_callback

from rag_system.qa import answer_query


TEST_QUERIES = [
    "이 사업의 주요 요구사항을 요약해줘",
    "발주기관과 제출 방식이 무엇인지 알려줘",
    "예산이나 사업 목적이 문서에 있으면 정리해줘",
]


def main() -> None:
    output_path = Path("llm_answer.txt")
    results = []

    with get_openai_callback() as cb:
        for query in TEST_QUERIES:
            result = answer_query(query)
            titles = sorted({doc.metadata.get("title", "") for doc in result["documents"]})
            results.append(
                {
                    "query": query,
                    "answer": result["answer"],
                    "titles": titles,
                    "docs_count": len(result["documents"]),
                }
            )

        with output_path.open("w", encoding="utf-8") as handle:
            handle.write("RAG evaluation snapshot\n")
            handle.write("=" * 60 + "\n\n")
            for index, item in enumerate(results, start=1):
                handle.write(f"[Test {index}] {item['query']}\n")
                handle.write(f"Retrieved chunks: {item['docs_count']}\n")
                handle.write(f"Projects: {', '.join(item['titles']) or 'N/A'}\n")
                handle.write(f"Answer:\n{item['answer']}\n")
                handle.write("\n" + "-" * 60 + "\n\n")

            handle.write(f"Prompt tokens: {cb.prompt_tokens}\n")
            handle.write(f"Completion tokens: {cb.completion_tokens}\n")
            handle.write(f"Total tokens: {cb.total_tokens}\n")
            handle.write(f"Successful requests: {cb.successful_requests}\n")
            handle.write(f"Estimated cost: ${cb.total_cost:.6f}\n")

    print(f"Saved evaluation results to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
