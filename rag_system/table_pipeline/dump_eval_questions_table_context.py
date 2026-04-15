import argparse
from pathlib import Path

from rag_system.table_pipeline.eval_questions_table_runner import DEFAULT_QUESTION_FILE, parse_eval_questions
from rag_system.qa import load_vectorstore, run_search


def main():
    parser = argparse.ArgumentParser(description="Dump retrieval context for eval_questions_table cases without LLM answers.")
    parser.add_argument(
        "--question-file",
        type=Path,
        default=DEFAULT_QUESTION_FILE,
        help="Path to eval_questions_table_v1.txt",
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        default=["TB", "TC"],
        help="Groups to run, e.g. TA TB TC",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=["baseline", "mmr"],
        default="baseline",
        help="Retrieval strategy to evaluate",
    )
    parser.add_argument("--k", type=int, default=3, help="Number of chunks to retrieve")
    args = parser.parse_args()

    all_cases = parse_eval_questions(args.question_file)
    selected_groups = {group.upper() for group in args.groups}
    cases = [case for case in all_cases if case["group"] in selected_groups]

    vectorstore = load_vectorstore()
    output_path = Path(f"eval_questions_table_context_{args.retrieval_mode}_{'-'.join(sorted(selected_groups))}.txt")

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("eval_questions_table retrieval context dump\n")
        handle.write(f"Question file: {args.question_file}\n")
        handle.write(f"Groups: {', '.join(sorted(selected_groups))}\n")
        handle.write(f"Retrieval mode: {args.retrieval_mode}\n")
        handle.write("=" * 80 + "\n\n")

        for case in cases:
            docs = run_search(vectorstore, case["question"], k=args.k, retrieval_mode=args.retrieval_mode)
            handle.write(f"[{case['id']}] {case['question']}\n")
            handle.write(f"Ground truth doc: {case['ground_truth_doc']}\n")
            handle.write(f"Ground truth hint: {case['ground_truth_hint']}\n")
            handle.write(f"Eval focus: {case['eval_focus']}\n")
            handle.write("Retrieved contexts:\n")

            for rank, doc in enumerate(docs, start=1):
                title = doc.metadata.get("title", "N/A")
                source = doc.metadata.get("source", "N/A")
                section = doc.metadata.get("section", "N/A")
                handle.write(f"\n  [{rank}] {title} ({source})\n")
                handle.write(f"  Section: {section}\n")
                handle.write("  Content:\n")
                for line in doc.page_content.splitlines():
                    handle.write(f"    {line}\n")

            handle.write("\n" + "-" * 80 + "\n\n")

    print(f"Saved retrieval context dump to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
