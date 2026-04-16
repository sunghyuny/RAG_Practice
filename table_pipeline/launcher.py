import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def resolve_python() -> str:
    venv_python = WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_module(module: str, *args: str) -> int:
    python_executable = resolve_python()
    command = [python_executable, "-m", module, *args]
    return subprocess.call(command, cwd=str(WORKSPACE_ROOT))


def print_menu() -> None:
    print("=" * 60)
    print("Table Pipeline Launcher")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print(f"Python: {resolve_python()}")
    print("=" * 60)
    print("1. 벡터 DB 재적재")
    print("2. eval_questions_table TB/TC 평가")
    print("3. 전체 HWP 문서명 평가")
    print("4. eval_questions_table context dump")
    print("5. 종료")
    print()


def main() -> None:
    while True:
        print_menu()
        choice = input("실행할 번호를 입력하세요: ").strip()

        if choice == "1":
            code = run_module("rag_system.ingest", "--rebuild")
            print(f"\n작업 종료 (exit code: {code})\n")
        elif choice == "2":
            code = run_module(
                "table_pipeline.evaluation.eval_questions_table_runner",
                "--groups",
                "TB",
                "TC",
                "--retrieval-mode",
                "mmr",
                "--k",
                "5",
            )
            print(f"\n작업 종료 (exit code: {code})\n")
        elif choice == "3":
            code = run_module(
                "table_pipeline.evaluation.evaluate_all_hwp_docname_cases",
                "--retrieval-mode",
                "mmr",
                "--k",
                "5",
            )
            print(f"\n작업 종료 (exit code: {code})\n")
        elif choice == "4":
            code = run_module(
                "table_pipeline.evaluation.dump_eval_questions_table_context",
                "--groups",
                "TB",
                "TC",
                "--retrieval-mode",
                "mmr",
                "--k",
                "3",
            )
            print(f"\n작업 종료 (exit code: {code})\n")
        elif choice == "5":
            print("런처를 종료합니다.")
            return
        else:
            print("올바른 번호를 입력해 주세요.\n")
            continue

        input("엔터를 누르면 메뉴로 돌아갑니다...")
        print()


if __name__ == "__main__":
    main()
