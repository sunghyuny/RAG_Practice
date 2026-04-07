import argparse
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from rag_system.config import SETTINGS, require_env
from rag_system.rag_utils import TAG_KEYWORDS, build_embeddings


class SearchPlan(BaseModel):
    search_query: str = Field(description="Query rewritten for semantic search")
    agency: Optional[str] = Field(default=None, description="Issuing agency if present")
    project_name: Optional[str] = Field(default=None, description="Project or bid name if present")


ANSWER_PROMPT = ChatPromptTemplate.from_template(
    """당신은 공공입찰 RFP 분석을 돕는 어시스턴트입니다.
아래 검색 결과만 근거로 답변하세요.

규칙:
1. 문서에 없는 내용은 추측하지 말고 "문서에서 확인되지 않았습니다"라고 답하세요.
2. 여러 사업이 섞여 있으면 사업명을 구분해서 답하세요.
3. 예산, 기관명, 제출 방식, 마감일, 요구사항 번호가 보이면 그대로 인용해 요약하세요.
4. 답변 마지막에 근거 문서 제목 목록을 짧게 덧붙이세요.

[검색 문서]
{context}

[질문]
{question}

답변:"""
)


def load_vectorstore() -> Chroma:
    return Chroma(
        persist_directory=str(SETTINGS.db_path),
        embedding_function=build_embeddings(),
    )


def load_titles(vectorstore: Chroma) -> List[str]:
    metadata = vectorstore._collection.get(include=["metadatas"])
    return sorted({item.get("title", "") for item in metadata["metadatas"] if item.get("title")})


def fuzzy_filter_titles(all_titles: List[str], agency: Optional[str] = None, project_name: Optional[str] = None) -> List[str]:
    if not agency and not project_name:
        return []

    matched = []
    for title in all_titles:
        lowered = title.lower()
        agency_ok = not agency or agency.lower() in lowered
        project_ok = not project_name or project_name.lower() in lowered
        if agency_ok and project_ok:
            matched.append(title)
    return matched


def build_models():
    require_env("OPENAI_API_KEY")
    answer_llm = ChatOpenAI(model=SETTINGS.chat_model, temperature=SETTINGS.answer_temperature)
    planner = ChatOpenAI(model=SETTINGS.chat_model, temperature=0).with_structured_output(SearchPlan)
    return answer_llm, planner


def infer_query_tags(query: str) -> List[str]:
    matched = []
    lowered = query.lower()
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matched.append(tag)
    return matched


def retrieve_documents(user_query: str, vectorstore: Chroma, planner, all_titles: List[str], k: int):
    search_query = user_query
    agency = None
    project_name = None

    try:
        plan = planner.invoke(user_query)
        search_query = plan.search_query or user_query
        agency = plan.agency
        project_name = plan.project_name
    except Exception:
        pass

    matched_titles = fuzzy_filter_titles(all_titles, agency, project_name)
    query_tags = infer_query_tags(user_query)

    filters = []
    if matched_titles:
        filters.append({"title": {"$in": matched_titles}})
    if query_tags:
        filters.append({"primary_tag": {"$in": query_tags}})

    if len(filters) == 2:
        docs = vectorstore.similarity_search(
            query=search_query,
            k=k,
            filter={"$and": filters},
        )
        if docs:
            return docs

    if query_tags:
        docs = vectorstore.similarity_search(
            query=search_query,
            k=k,
            filter={"primary_tag": {"$in": query_tags}},
        )
        if docs:
            return docs

    if matched_titles:
        return vectorstore.similarity_search(
            query=search_query,
            k=k,
            filter={"title": {"$in": matched_titles}},
        )

    return vectorstore.similarity_search(query=search_query, k=k)


def format_docs(docs) -> str:
    blocks = []
    for index, doc in enumerate(docs, start=1):
        title = doc.metadata.get("title", "N/A")
        source = doc.metadata.get("source", "N/A")
        blocks.append(f"[문서 {index}] 사업명: {title} | 파일: {source}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def answer_query(question: str, k: int = SETTINGS.retrieval_k) -> dict:
    vectorstore = load_vectorstore()
    all_titles = load_titles(vectorstore)
    answer_llm, planner = build_models()
    docs = retrieve_documents(question, vectorstore, planner, all_titles, k)
    chain = ANSWER_PROMPT | answer_llm | StrOutputParser()
    answer = chain.invoke({"context": format_docs(docs), "question": question})
    return {"question": question, "answer": answer, "documents": docs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question about the indexed RFP corpus.")
    parser.add_argument("query", help="Question to ask")
    parser.add_argument("--k", type=int, default=SETTINGS.retrieval_k, help="Number of chunks to retrieve")
    args = parser.parse_args()

    result = answer_query(args.query, k=args.k)
    print(result["answer"])

    print("\n[Retrieved documents]")
    seen = set()
    for doc in result["documents"]:
        title = doc.metadata.get("title", "N/A")
        source = doc.metadata.get("source", "N/A")
        key = (title, source)
        if key in seen:
            continue
        seen.add(key)
        print(f"- {title} ({source})")


if __name__ == "__main__":
    main()
