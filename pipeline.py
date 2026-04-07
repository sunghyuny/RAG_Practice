from rag_system.ingest import ingest_documents


def build_pipeline(rebuild: bool = False) -> int:
    return ingest_documents(rebuild=rebuild)


if __name__ == "__main__":
    count = build_pipeline(rebuild=False)
    print(f"Pipeline completed safely. Stored {count} chunks.")
