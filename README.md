# RFP RAG Prototype

Minimal RAG project for Korean RFP documents.

Included files:
- `rag_system/`: ingestion, retrieval, QA, and evaluation modules
- `pipeline.py`: ingestion entrypoint
- `test.py`: evaluation entrypoint

Notes:
- Source documents in `files/` are ignored by git.
- Vector DB in `my_rfp_vectordb/` is ignored by git.
- Secrets must stay in a local `.env` file and must not be committed.

Basic usage:

```bash
python -m rag_system.ingest --rebuild
python -m rag_system.qa "질문"
python test.py
```
