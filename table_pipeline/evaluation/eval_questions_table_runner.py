import argparse
import re
from pathlib import Path
from time import perf_counter

from rag_system.qa import load_vectorstore, run_search


DEFAULT_QUESTION_FILE = Path(r"C:\Users\zerax\Desktop\AI_07_Intermidiate\evaluation\eval_questions_table_v1.txt")


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\.[a-z0-9]+$", "", value)
    value = re.sub(r"[^0-9a-z가-힣]+", "", value)
    return value


def parse_eval_questions(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    cases = []
    blocks = re.split(r"(?=T[ABC]-\d{2}\n)", text)
    for block in blocks:
        lines = block.splitlines()
        if not lines or not re.fullmatch(r"T[ABC]-\d{2}", lines[0].strip()):
            continue

        case_id = lines[0].strip()
        group = case_id.split("-")[0]
        fields = {}
        current_key = None

        for raw_line in lines[1:]:
            line = raw_line.rstrip()
            matched = re.match(r"\s*(question|answer_type|ground_truth_doc|ground_truth_hint|enrichment_needed|eval_focus)\s*:\s*(.*)", line)
            if matched:
                current_key = matched.group(1)
                fields[current_key] = matched.group(2).strip()
                continue
            if current_key and line.strip():
                fields[current_key] = f"{fields[current_key]} {line.strip()}".strip()

        if not {"question", "answer_type", "ground_truth_doc", "ground_truth_hint", "enrichment_needed", "eval_focus"} <= fields.keys():
            continue

        cases.append(
            {
                "id": case_id,
                "group": group,
                "question": fields["question"],
                "answer_type": fields["answer_type"],
                "ground_truth_doc": fields["ground_truth_doc"],
                "ground_truth_hint": fields["ground_truth_hint"],
                "enrichment_needed": fields["enrichment_needed"],
                "eval_focus": fields["eval_focus"],
            }
        )
    return cases


def title_matches(expected_doc: str, doc_title: str, doc_source: str) -> bool:
    expected = normalize_text(expected_doc)
    title = normalize_text(doc_title or "")
    source = normalize_text(doc_source or "")
    return bool(expected and (expected in title or expected in source or title in expected or source in expected))


def evaluate_cases(cases, retrieval_mode: str, k: int):
    vectorstore = load_vectorstore()
    results = []

    for case in cases:
        started_at = perf_counter()
        docs = run_search(vectorstore, case["question"], k=k, retrieval_mode=retrieval_mode)
        elapsed = perf_counter() - started_at

        matched_ranks = []
        for rank, doc in enumerate(docs, start=1):
            title = doc.metadata.get("title", "")
            source = doc.metadata.get("source", "")
            if title_matches(case["ground_truth_doc"], title, source):
                matched_ranks.append(rank)

        results.append(
            {
                "case": case,
                "elapsed": elapsed,
                "docs": docs,
                "matched_ranks": matched_ranks,
                "top1_hit": bool(matched_ranks and matched_ranks[0] == 1),
                "top3_hit": bool(matched_ranks and matched_ranks[0] <= 3),
            }
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Run retrieval evaluation using eval_questions_table_v1 cases.")
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
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve")
    args = parser.parse_args()

    all_cases = parse_eval_questions(args.question_file)
    selected_groups = {group.upper() for group in args.groups}
    cases = [case for case in all_cases if case["group"] in selected_groups]

    results = evaluate_cases(cases, retrieval_mode=args.retrieval_mode, k=args.k)
    output_name = f"eval_questions_table_{args.retrieval_mode}_{'-'.join(sorted(selected_groups))}.txt"
    output_path = Path(output_name)

    top1_hits = sum(1 for item in results if item["top1_hit"])
    top3_hits = sum(1 for item in results if item["top3_hit"])

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("eval_questions_table retrieval evaluation\n")
        handle.write(f"Question file: {args.question_file}\n")
        handle.write(f"Groups: {', '.join(sorted(selected_groups))}\n")
        handle.write(f"Retrieval mode: {args.retrieval_mode}\n")
        handle.write("=" * 60 + "\n\n")

        for item in results:
            case = item["case"]
            handle.write(f"[{case['id']}] {case['question']}\n")
            handle.write(f"Group: {case['group']}\n")
            handle.write(f"Ground truth doc: {case['ground_truth_doc']}\n")
            handle.write(f"Enrichment needed: {case['enrichment_needed']}\n")
            handle.write(f"Eval focus: {case['eval_focus']}\n")
            handle.write(f"Elapsed: {item['elapsed']:.2f}s\n")
            handle.write(f"Top1 hit: {'Y' if item['top1_hit'] else 'N'}\n")
            handle.write(f"Top3 hit: {'Y' if item['top3_hit'] else 'N'}\n")
            handle.write(f"Matched ranks: {item['matched_ranks'] or 'None'}\n")
            handle.write("Results:\n")

            for rank, doc in enumerate(item["docs"], start=1):
                title = doc.metadata.get("title", "N/A")
                source = doc.metadata.get("source", "N/A")
                snippet = doc.page_content[:300].replace("\n", " / ")
                handle.write(f"  {rank}. {title} ({source})\n")
                handle.write(f"     {snippet}\n")

            handle.write("\n" + "-" * 60 + "\n\n")

        handle.write(f"Top1 hits: {top1_hits}/{len(results)}\n")
        handle.write(f"Top3 hits: {top3_hits}/{len(results)}\n")

    print(f"Saved eval_questions_table retrieval results to {output_path.resolve()}.")


if __name__ == "__main__":
    main()
