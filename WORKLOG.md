# 작업 정리

## 1. 프로젝트 개요

- 대상: 기업 및 정부 제안요청서(RFP) 문서를 위한 RAG 시스템
- 목표: RFP 문서에서 요구사항, 대상 기관, 예산, 제출 방식, 목적 등 핵심 정보를 빠르게 추출하고 요약하는 서비스 구현
- 가정 시나리오: B2G 입찰지원 전문 컨설팅 스타트업 `입찰메이트`의 사내 RAG 시스템

## 2. 현재까지 반영한 내용

- 코드 구조를 모듈형으로 정리
- 전처리 / 적재 / QA / 평가 로직 분리
- `pipeline.py`, `test.py`를 얇은 진입점으로 구성
- 단순 문자 기반 청킹에서 섹션 기반 청킹으로 개선
- chunk metadata에 태그 추가
- 태그 기반 retrieval 로직 추가
- 태그 규칙을 strong / weak 키워드 기반으로 1차 정리
- `uv` 기반 가상환경 생성 및 실행 환경 정리
- 벡터 DB 리빌드 완료

## 3. 현재 코드 구조

- `pipeline.py`
- `test.py`
- `rag_system/config.py`
- `rag_system/ingest.py`
- `rag_system/qa.py`
- `rag_system/rag_utils.py`
- `rag_system/evaluate.py`

## 4. 현재 태그

- `budget`
- `submission`
- `evaluation`
- `purpose`
- `deadline`
- `requirement`
- `qualification`

## 5. 현재 실행 방법

```bash
python -m rag_system.ingest --rebuild
python -m rag_system.qa "질문"
python test.py
```

`uv` 가상환경 기준 실행 예시:

```bash
.\.venv\Scripts\python.exe -m rag_system.ingest --rebuild
.\.venv\Scripts\python.exe -m rag_system.qa "질문"
.\.venv\Scripts\python.exe test.py
```

## 6. 현재 성능 요약

### 잘 되는 편

- 단일 문서 기반 추출형 질문
- 요구사항 / 목적 / 일부 제출 방식 관련 질문
- 명시적으로 적힌 문장을 근거로 답하는 질문

### 아직 약한 편

- 비교형 질문
- 탐색형 질문
- 문맥을 이어받는 후속 질문
- 복합 의도 질문
  - 예: `발주기관 + 제출 방식`
  - 예: `예산 + 목적`

### 현재 관찰된 retrieval 한계

- 상위 검색 결과에 서로 다른 사업 문서가 섞이는 경우가 많음
- broad tag가 붙은 청크가 과하게 상위로 올라오는 경우가 있음
- `budget`, `submission`, `purpose`, `evaluation` 계열에서 과매칭이 남아 있음
- 질문 의도가 2개 이상일 때 관련 근거를 함께 안정적으로 못 가져오는 경우가 있음
- 이 때문에 답변 모델이 보수적으로 `문서에서 확인되지 않습니다.`라고 답하는 경우가 있음

## 7. 최근 작업 메모

- `langchain_community.callbacks.get_openai_callback` 의존성을 제거하고 평가 스크립트를 단순화함
- `test.py`가 최소한 결과 파일을 남기도록 정리함
- Hugging Face 임베딩 모델은 로컬 캐시를 사용하도록 테스트함
- OpenAI 연결 문제는 환경 영향을 받을 수 있으므로 retrieval 검증과 answer 검증을 분리해서 볼 필요가 있음

## 8. 다음 작업 방향

- retrieval 기법 개선
- 태그 규칙 정교화
- 복합 질문 대응 강화
- metadata-aware ranking 강화
- hybrid retrieval 실험

## 9. Retrieval 실험 기록

앞으로 retrieval 관련 변경 사항은 아래 형식으로 계속 추가한다.

### 실험 템플릿

#### 실험명

- 날짜:
- 변경 내용:
- 의도:
- 테스트 질문:
- 관찰 결과:
- 개선된 점:
- 아쉬운 점:
- 다음 액션:

### Baseline

- 날짜: 2026-04-07
- 변경 내용: 섹션 기반 청킹 + metadata tagging + 태그 보조 retrieval + 결과 단순 병합
- 의도: RFP 문서 검색 품질 향상 및 주요 정보 질의 대응
- 테스트 질문:
  - 사업의 주요 요구사항을 요약해줘
  - 발주기관과 제출 방식은 무엇인지 알려줘
  - 예산이나 사업 목적이 문서에 있으면 정리해줘
- 관찰 결과:
  - 요구사항 질문은 비교적 잘 동작함
  - 제출 방식 질문은 부분적으로 동작하나 서로 다른 사업 문서가 섞임
  - 예산/목적 질문은 관련 근거를 함께 안정적으로 가져오지 못함
- 개선된 점:
  - 단순 추출형 질문의 응답 품질이 이전보다 안정적임
  - 태그 기반 필터가 일부 질의에서 recall 향상에 도움을 줌
- 아쉬운 점:
  - broad tag 과매칭이 남아 있음
  - multi-intent query 대응이 약함
  - 결과 재정렬 기준이 아직 단순함
- 다음 액션:
  - retrieval 전략을 intent-aware 방식으로 바꾸기
  - 태그별 정밀도 향상
  - 결과 merge 이후 re-ranking 추가

### MMR 1차 적용

- 날짜: 2026-04-07
- 변경 내용: `similarity_search` 대신 `max_marginal_relevance_search` 적용
- 의도: 너무 비슷한 청크만 반복해서 나오는 현상을 줄이고, 더 다양한 근거를 확보하기 위함
- 테스트 질문:
  - 사업의 주요 요구사항을 요약해줘
  - 발주기관과 제출 방식은 무엇인지 알려줘
  - 예산이나 사업 목적이 문서에 있으면 정리해줘
- 관찰 결과:
  - top-5 결과의 문서 중복은 줄어듦
  - 각 질문에서 `UNIQUE_TITLES: 5`가 나올 정도로 다양성은 높아짐
  - 하지만 관련 문서 집중도가 낮아져 서로 다른 사업 문서가 더 많이 섞임
  - 요구사항 질문에서도 관련 없는 `submission`, `general` 성격 청크가 함께 상위에 노출됨
- 개선된 점:
  - 중복 청크 억제 효과는 분명함
  - 한 질문에 대해 다양한 문서 후보를 넓게 보는 데는 유리함
- 아쉬운 점:
  - 현재 RFP QA 목적에는 다양성보다 관련도 집중이 더 중요해서 오히려 품질이 떨어질 가능성이 큼
  - broad query에서 noise가 증가함
  - multi-intent query 해결에는 직접적인 도움이 부족함
- 다음 액션:
  - MMR 단독 사용은 유지하지 말고, metadata/tag 기반 후보군을 먼저 좁힌 뒤 제한적으로 적용하는 방향 검토
  - 또는 similarity retrieval + re-ranking 구조로 전환 검토
