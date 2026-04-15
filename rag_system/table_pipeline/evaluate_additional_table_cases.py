import argparse
from pathlib import Path
from time import perf_counter

from rag_system.table_pipeline.additional_table_cases import ADDITIONAL_TABLE_CASES
from rag_system.qa import load_vectorstore, run_search


def title_matches(doc_title: str, expected_title_contains: str) -> bool:
    return expected_title_contains.lower() in (doc_title or "").lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate for additional table-focused queries.")
    parser.add_argument(
        "--retrieval-mode",
        choices=["baseline", "mmr"],
        default="mmr",
        help="Retrieval strategy to evaluate",
    )
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve")
    args = parser.parse_args()

    vectorstore = load_vectorstore()
    output_path = Path(f"additional_table_cases_{args.retrieval_mode}.txt")
    started_at = perf_counter()
    top1_hits = 0
    top3_hits = 0

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("Additional table retrieval evaluation\n")
        handle.write(f"Retrieval mode: {args.retrieval_mode}\n")
        handle.write("=" * 60 + "\n\n")

        for index, case in enumerate(ADDITIONAL_TABLE_CASES, start=1):
            query_started_at = perf_counter()
            docs = run_search(vectorstore, case["query"], args.k, retrieval_mode=args.retrieval_mode)
            elapsed = perf_counter() - query_started_at

            matched_ranks = []
            for rank, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "")
                if title_matches(title, case["expected_title_contains"]):
                    matched_ranks.append(rank)

            top1_hit = bool(matched_ranks and matched_ranks[0] == 1)
            top3_hit = bool(matched_ranks and matched_ranks[0] <= 3)
            if top1_hit:
                top1_hits += 1
            if top3_hit:
                top3_hits += 1

            handle.write(f"[Case {index}] {case['query']}\n")
            handle.write(f"Expected title contains: {case['expected_title_contains']}\n")
            handle.write(f"Notes: {case['notes']}\n")
            handle.write(f"Elapsed: {elapsed:.2f}s\n")
            handle.write(f"Top1 hit: {'Y' if top1_hit else 'N'}\n")
            handle.write(f"Top3 hit: {'Y' if top3_hit else 'N'}\n")
            handle.write(f"Matched ranks: {matched_ranks or 'None'}\n")
            handle.write("Results:\n")

            for rank, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "N/A")
                source = doc.metadata.get("source", "N/A")
                snippet = doc.page_content[:300].replace("\n", " / ")
                handle.write(f"  {rank}. {title} ({source})\n")
                handle.write(f"     {snippet}\n")

            handle.write("\n" + "-" * 60 + "\n\n")

        total_cases = len(ADDITIONAL_TABLE_CASES)
        total_elapsed = perf_counter() - started_at
        handle.write(f"Top1 hits: {top1_hits}/{total_cases}\n")
        handle.write(f"Top3 hits: {top3_hits}/{total_cases}\n")
        handle.write(f"Total elapsed: {total_elapsed:.2f}s\n")

    print(f"Saved additional retrieval evaluation to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
