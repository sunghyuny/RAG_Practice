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

## 7-1. 개선사항 및 성능 향상 요약

### 지금까지 반영한 개선사항

- 전처리, 적재, QA, 평가를 모듈형 구조로 분리함
- `pipeline.py`, `test.py`를 얇은 진입점으로 정리함
- 단순 문자 분할 대신 섹션 기반 청킹 적용
- chunk metadata에 태그를 부여하도록 개선
- 태그 추론 방식을 단순 키워드 포함 검사에서 `strong/weak keyword + threshold` 방식으로 고도화함
- retrieval 실험을 위해 `baseline`과 `mmr`를 분리 실행할 수 있도록 구성함
- 평가 결과를 `llm_answer_baseline.txt`, `llm_answer_mmr.txt`처럼 모드별 파일로 저장하도록 변경함
- `langchain_community.callbacks` 의존성을 제거해 `test.py` 실행 안정성을 높임
- `uv` 가상환경 기반 실행 흐름 정리
- `data_list.csv` 기반 메타데이터를 문서와 매핑하여 chunk metadata에 저장하도록 변경함
- 발주기관을 질문에서 감지해 metadata filter로 retrieval에 반영하는 구조를 추가함

### 현재까지 확인된 성능 향상

- 요구사항 중심 추출형 질문은 이전보다 더 안정적으로 동작함
- MMR 실험 결과, 현재 샘플 질문 기준으로는 baseline보다 최종 답변 품질이 더 좋은 경향을 보임
- 특히 `발주기관 + 제출 방식` 질문에서 baseline보다 더 구체적인 제출 방식 문구를 끌어오는 경우가 있었음
- `예산 + 목적` 같은 복합 질문에서도 baseline보다 답변 정보량이 더 많아지는 경향이 있었음
- CSV 메타데이터를 활용할 수 있게 되면서 발주기관, 사업명, 예산, 마감일, 사업 요약 같은 구조 정보를 retrieval에 직접 활용할 기반이 생김
- 이제 기관명 질문은 본문 검색뿐 아니라 `issuer` metadata를 활용하는 방향으로 확장 가능해짐

### 아직 남아 있는 한계

- broad query에서는 서로 다른 사업 문서가 섞이는 문제가 여전히 있음
- 복합 질문은 intent별 근거를 함께 안정적으로 가져오는 부분이 더 필요함
- metadata filter를 추가했지만 기관명 질문의 실제 top-k 품질은 추가 검증이 필요함
- 후속 질문 맥락 유지, hybrid retrieval, reranking은 아직 본격 적용 전 단계임

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

## 10. 2026-04-08 작업 정리

### 오늘 한 작업

- generation 옵션 실험
  - `temperature`, `top_p`, `max_tokens`를 generation 옵션 후보로 검토
  - `gpt-5-mini`와의 호환성을 확인하는 과정에서 `top_p`를 그대로 넣는 방식은 적절하지 않음을 확인
  - 최종적으로는 generation 옵션 실험은 보류하고, 안정적인 기본 호출 형태를 유지
- retrieval 개선
  - CSV 메타데이터를 ingestion 단계에 연결하여 문서별 `issuer`, `project_name`, `bid_amount`, `project_summary` 등을 metadata로 저장할 수 있게 정리
  - 질문에서 발주기관을 추론하는 로직을 추가하고 `issuer_filter`를 retrieval 과정에 반영
  - `title_filter`, `issuer_filter`, `tag_filter`를 조합해 여러 retrieval 결과를 만들고 병합하는 구조로 개선
- hybrid retrieval 실험
  - semantic retrieval 결과에 lexical 신호를 결합하는 hybrid search를 시험적으로 구현
  - 평가 결과를 비교한 뒤, 현재 버전에서는 precision 저하 가능성이 있어 최종 반영 범위에서는 제외
- 커밋 정리
  - 최종 커밋은 `baseline` / `mmr` retrieval 개선만 남기고 생성 옵션 실험, hybrid search, 임베딩 관련 실험 변경은 제외

### 오늘 얻은 인사이트

- 현재 프로젝트에서는 generation 파라미터 튜닝보다 retrieval 품질 개선이 전체 답변 품질에 더 큰 영향을 준다.
- RFP처럼 형식이 비슷한 문서 집합에서는 단순 similarity retrieval만으로는 서로 다른 사업 문서가 쉽게 섞인다.
- `issuer` 같은 구조화된 metadata는 retrieval precision을 높이는 데 유용하다.
- hybrid retrieval은 "semantic + lexical"을 무조건 섞는다고 좋아지는 것이 아니라, lexical 가중치가 너무 강하면 precision이 오히려 떨어질 수 있다.
- generation 옵션은 품질 자체보다도 모델 호환성 여부를 먼저 확인해야 한다.

### 문제점 / 보완점

- multi-intent 질문(`발주기관 + 제출방식`, `예산 + 사업 목적`)에 대해서는 retrieval precision이 아직 충분히 안정적이지 않다.
- `예산`, `마감일`, `제출방식`, `사업 목적` 같은 핵심 정보를 구조화된 필드로 직접 추출하는 단계가 아직 부족하다.
- retrieval 성능 비교를 위한 정량 평가 기준이 더 필요하다.
- hybrid retrieval은 다시 시도하더라도 semantic 중심, lexical 보조 신호 형태로 더 보수적으로 설계할 필요가 있다.
- 후속 질문 문맥 유지와 reranking은 이후 단계에서 추가 검토가 필요하다.

### 설명용 한 줄 요약

- 오늘은 generation 옵션 실험을 통해 모델별 파라미터 호환성 이슈를 확인했고, retrieval 쪽에서는 CSV metadata와 발주기관 필터를 결합해 `baseline` / `mmr` 검색 품질을 개선했다.
