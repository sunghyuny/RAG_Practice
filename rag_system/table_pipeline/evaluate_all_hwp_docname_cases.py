import argparse
import re
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from rag_system.table_pipeline.all_hwp_docname_cases import ALL_HWP_DOCNAME_CASES
from rag_system.qa import load_vectorstore, run_search


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\.[a-z0-9]+$", "", value)
    value = re.sub(r"[^0-9a-z가-힣]+", "", value)
    return value


def title_matches(expected_doc: str, doc_title: str, doc_source: str) -> bool:
    expected = normalize_text(expected_doc)
    title = normalize_text(doc_title or "")
    source = normalize_text(doc_source or "")
    return bool(expected and (expected in title or expected in source or title in expected or source in expected))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate using all HWP document titles with fixed question templates.")
    parser.add_argument(
        "--retrieval-mode",
        choices=["baseline", "mmr"],
        default="mmr",
        help="Retrieval strategy to evaluate",
    )
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument(
        "--limit-docs",
        type=int,
        default=0,
        help="Optional limit for the number of HWP documents to test. 0 means all.",
    )
    args = parser.parse_args()

    cases = ALL_HWP_DOCNAME_CASES
    if args.limit_docs > 0:
        allowed_docs = []
        for case in cases:
            title = case["doc_title"]
            if title not in allowed_docs:
                allowed_docs.append(title)
            if len(allowed_docs) >= args.limit_docs:
                break
        allowed_set = set(allowed_docs)
        cases = [case for case in cases if case["doc_title"] in allowed_set]

    vectorstore = load_vectorstore()
    output_path = Path(f"all_hwp_docname_cases_{args.retrieval_mode}.txt")
    started_at = perf_counter()
    top1_hits = 0
    top3_hits = 0
    per_doc = defaultdict(lambda: {"total": 0, "top1": 0, "top3": 0, "misses": []})

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("All HWP doc-title retrieval evaluation\n")
        handle.write(f"Retrieval mode: {args.retrieval_mode}\n")
        handle.write(f"Top-k: {args.k}\n")
        handle.write(f"Document count: {len({case['doc_title'] for case in cases})}\n")
        handle.write(f"Case count: {len(cases)}\n")
        handle.write("=" * 80 + "\n\n")

        for index, case in enumerate(cases, start=1):
            query_started_at = perf_counter()
            docs = run_search(vectorstore, case["query"], args.k, retrieval_mode=args.retrieval_mode)
            elapsed = perf_counter() - query_started_at

            matched_ranks = []
            for rank, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "")
                source = doc.metadata.get("source", "")
                if title_matches(case["expected_title_contains"], title, source):
                    matched_ranks.append(rank)

            top1_hit = bool(matched_ranks and matched_ranks[0] == 1)
            top3_hit = bool(matched_ranks and matched_ranks[0] <= 3)

            doc_summary = per_doc[case["doc_title"]]
            doc_summary["total"] += 1
            if top1_hit:
                top1_hits += 1
                doc_summary["top1"] += 1
            if top3_hit:
                top3_hits += 1
                doc_summary["top3"] += 1
            else:
                doc_summary["misses"].append(
                    {
                        "template_id": case["template_id"],
                        "query": case["query"],
                        "matched_ranks": matched_ranks[:],
                        "top_titles": [doc.metadata.get("title", "N/A") for doc in docs[:3]],
                    }
                )

            handle.write(f"[Case {index}] {case['template_id']} | {case['doc_title']}\n")
            handle.write(f"Query: {case['query']}\n")
            handle.write(f"Elapsed: {elapsed:.2f}s\n")
            handle.write(f"Top1 hit: {'Y' if top1_hit else 'N'}\n")
            handle.write(f"Top3 hit: {'Y' if top3_hit else 'N'}\n")
            handle.write(f"Matched ranks: {matched_ranks or 'None'}\n")
            handle.write("Results:\n")

            for rank, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "N/A")
                source = doc.metadata.get("source", "N/A")
                snippet = doc.page_content[:240].replace("\n", " / ")
                handle.write(f"  {rank}. {title} ({source})\n")
                handle.write(f"     {snippet}\n")

            handle.write("\n" + "-" * 80 + "\n\n")

        total_docs = len(per_doc)
        total_elapsed = perf_counter() - started_at
        ranked_docs = sorted(
            per_doc.items(),
            key=lambda item: (
                item[1]["top3"] / item[1]["total"] if item[1]["total"] else 0,
                item[1]["top1"] / item[1]["total"] if item[1]["total"] else 0,
                item[0],
            ),
        )

        handle.write("=" * 80 + "\n")
        handle.write("Summary\n")
        handle.write(f"Top1 hits: {top1_hits}/{len(cases)}\n")
        handle.write(f"Top3 hits: {top3_hits}/{len(cases)}\n")
        handle.write(f"Total elapsed: {total_elapsed:.2f}s\n\n")
        handle.write("Weak docs (sorted by lowest Top3/Top1 rate):\n")

        for title, stats in ranked_docs[:20]:
            top1_rate = stats["top1"] / stats["total"] if stats["total"] else 0.0
            top3_rate = stats["top3"] / stats["total"] if stats["total"] else 0.0
            handle.write(
                f"- {title} | Top1 {stats['top1']}/{stats['total']} ({top1_rate:.0%}) | "
                f"Top3 {stats['top3']}/{stats['total']} ({top3_rate:.0%})\n"
            )
            for miss in stats["misses"][:3]:
                handle.write(f"  * {miss['template_id']} miss | matched ranks: {miss['matched_ranks'] or 'None'}\n")
                handle.write(f"    query: {miss['query']}\n")
                handle.write(f"    top titles: {', '.join(miss['top_titles'])}\n")

        handle.write("\nStrong docs (sorted by highest Top3/Top1 rate):\n")
        for title, stats in reversed(ranked_docs[-20:]):
            top1_rate = stats["top1"] / stats["total"] if stats["total"] else 0.0
            top3_rate = stats["top3"] / stats["total"] if stats["total"] else 0.0
            handle.write(
                f"- {title} | Top1 {stats['top1']}/{stats['total']} ({top1_rate:.0%}) | "
                f"Top3 {stats['top3']}/{stats['total']} ({top3_rate:.0%})\n"
            )

    print(f"Saved all-HWP retrieval evaluation to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
