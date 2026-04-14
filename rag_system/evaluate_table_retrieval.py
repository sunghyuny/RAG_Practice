import argparse
from pathlib import Path
from time import perf_counter

from rag_system.evaluate_table_focus import TABLE_FOCUSED_QUERIES
from rag_system.qa import load_vectorstore, run_search


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval-only checks for table-focused queries.")
    parser.add_argument(
        "--retrieval-mode",
        choices=["baseline", "mmr"],
        default="baseline",
        help="Retrieval strategy to evaluate",
    )
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve")
    args = parser.parse_args()

    vectorstore = load_vectorstore()
    output_path = Path(f"table_retrieval_{args.retrieval_mode}.txt")
    started_at = perf_counter()

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("Table-focused retrieval snapshot\n")
        handle.write(f"Retrieval mode: {args.retrieval_mode}\n")
        handle.write("=" * 60 + "\n\n")

        for index, query in enumerate(TABLE_FOCUSED_QUERIES, start=1):
            query_started_at = perf_counter()
            docs = run_search(vectorstore, query, args.k, retrieval_mode=args.retrieval_mode)
            elapsed = perf_counter() - query_started_at

            handle.write(f"[Test {index}] {query}\n")
            handle.write(f"Elapsed: {elapsed:.2f}s\n")
            handle.write(f"Retrieved chunks: {len(docs)}\n")
            handle.write("Results:\n")

            for doc_index, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "N/A")
                source = doc.metadata.get("source", "N/A")
                snippet = doc.page_content[:400].replace("\n", " / ")
                handle.write(f"  {doc_index}. {title} ({source})\n")
                handle.write(f"     {snippet}\n")

            handle.write("\n" + "-" * 60 + "\n\n")

        total_elapsed = perf_counter() - started_at
        handle.write(f"Total elapsed: {total_elapsed:.2f}s\n")

    print(f"Saved retrieval-only results to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
