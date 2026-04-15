# Table Pipeline

이 폴더는 HWP 표 분석, 표 enrichment, semantic text 조립, 표 중심 평가를 한 곳에 모아둔 패키지입니다.

## 역할 분리

- `table_enrichment.py`
  - 표 분석 본체
  - 표를 구조적으로 읽고 QA 친화적인 텍스트 블록으로 변환
- `rag_utils.py`
  - 문서 읽기
  - HWP artifact 추출 결과와 표 enrichment 결과를 합쳐 semantic text 조립
  - chunk 생성용 `make_documents()` 제공
- `eval_*.py`, `*_cases.py`
  - 표 중심 retrieval 테스트와 평가
- `launcher.py`
  - 메뉴 기반 실행 진입점

## 핵심 분석 함수

### `TABLE_FIELD_HINTS`
- 표 라벨처럼 보이는 키워드 모음
- 예: `요구사항`, `고유번호`, `명칭`, `장비`, `지역`, `배점`
- 키-값 추출 시 "이 줄이 항목명인지" 판단하는 기준으로 사용

### `extract_key_value_pairs(table_text)`
- 표 텍스트에서 `라벨 -> 값` 쌍을 추출
- 예:
  - `요구사항 ID -> SFR-007`
  - `요구사항 명칭 -> 병원선정`
  - `사용자 -> 광역상황실`

### `build_table_row_summary_lines(table_text)`
- 추출한 키-값을 행 단위 의미 묶음으로 재구성
- 예:
  - `요구사항 ID=SFR-007 / 요구사항 명칭=병원선정 / 사용자=광역상황실`

### `detect_table_type(table, table_text, pairs)`
- 표 유형 분류
- 현재 주요 타입:
  - `equipment_region`
  - `service_status`
  - `ai_requirement`
  - `requirement_table`
  - `score_table`
  - `schedule_table`
  - `general_table`

### `infer_table_title(table, doc_title, table_type)`
- 표 제목 추정
- 상위 문맥이 있으면 상위 문맥 사용
- 없으면 표 타입과 문서명으로 제목 생성
- 문서 고유어를 붙여 유사 문서 간 구분력을 높이도록 보강됨

### `build_type_template_summary(table_type, table_text, pairs)`
- 표 타입별 핵심 항목 요약
- 예:
  - 장비 표: `장비 목록`, `대상 지역`
  - 서비스 현황 표: `주요 서비스/앱`
  - 요구사항 표: `요구사항 ID`, `명칭`, `대상 사용자`

### `build_comparison_summary(table_type, table_text)`
- 비교/목록형 질문 대응용 요약
- 예:
  - `도입 장비 축: CTI, 교환기, IP녹취`
  - `지역 축: 중앙, 서울, 대전, 대구, 광주`

### `DOC_CONTEXT_HINTS`
- 문서 설명 블록에서 잡을 문맥 힌트 키워드 정의
- 예:
  - 장비/지역 관련
  - 서비스 현황 관련
  - AI 요구사항 관련

### `extract_doc_context_hints(payload)`
- `explanatory_blocks`, `section_header_blocks`에서 표와 연결될 설명 문장 추출

### `build_doc_context_blocks(doc_title, payload)`
- 문서 설명 힌트를 semantic text용 블록으로 생성

### `build_table_block(table, doc_title, hint_map)`
- 표 1개를 최종 RAG 입력 블록으로 생성
- 포함 정보:
  - `DOC_TITLE`
  - `TABLE_TITLE`
  - `TABLE_TYPE`
  - `TABLE_CONTEXT`
  - `TYPE_TEMPLATE_SUMMARY`
  - `COMPARISON_SUMMARY`
  - `DOC_HINT_SUMMARY`
  - `DOC_FOCUS_SUMMARY`
  - `KEY_VALUE_SUMMARY`
  - `ROW_SUMMARY`
  - `RAW_TABLE_TEXT`

### `build_hwp_semantic_text(file_path)`
- HWP 문서 전체 기준으로 아래를 합쳐 semantic text 구성
  - 문서 설명 힌트 블록
  - 구조 표 블록
  - explanatory block
  - section header block
  - image OCR block

## 새 HWP 문서에도 재사용 가능한가?

가능합니다. 이 파이프라인은 특정 문서 하나에 고정된 하드코딩이 아니라:

1. `extract_hwp_artifacts()`로 HWP 구조를 추출하고
2. 추출된 표 텍스트를 규칙 기반으로 분석한 뒤
3. semantic text로 조립해서
4. chunking 및 벡터 DB 적재로 넘기는 방식입니다.

즉 새로운 HWP가 들어와도 같은 흐름으로 처리할 수 있습니다.

다만 아래 경우에는 추가 보강이 필요할 수 있습니다.

- 표 구조가 매우 특이한 경우
- 이미지형 표 비중이 높은 경우
- 병합 셀이 많아 키-값 추출이 약한 경우
- 같은 기관의 유사 사업 문서처럼 문서 구분력이 약한 경우

## 실행 방식

커맨드 직접 입력 대신 아래 진입점 사용:

- `launch_table_pipeline.bat`

이 파일을 실행하면 메뉴에서 다음 작업을 선택할 수 있습니다.

- 벡터 DB 재적재
- `eval_questions_table` TB/TC 평가
- 전체 HWP 문서명 평가
- context dump
