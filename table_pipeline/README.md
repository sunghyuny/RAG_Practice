# Table Pipeline

`table_pipeline/`은 HWP/PDF 기반 문서를 읽고, HWP 표를 분석하고, semantic text를 만들고, 평가하는 실행 핵심만 모아둔 폴더다.

## 핵심 코드

### 실행 코어

- `rag_system/ingest.py`
  - 전체 적재 실행 진입점
  - `files/` 아래 문서를 순회
  - 최종적으로 Chroma 벡터 DB에 적재

- `rag_system/qa.py`
  - 검색 및 질문 처리
  - 벡터 DB에서 관련 chunk를 찾고 답변 체인을 구성

- `rag_system/config.py`
  - 입력 경로, DB 경로, chunk 설정, 모델 설정 관리

### table_pipeline 본체

- `table_pipeline/rag_utils.py`
  - 문서 읽기
  - HWP/PDF 텍스트 추출
  - semantic text 조립
  - chunk 생성
  - `make_documents()`를 통해 적재 직전 `Document` 리스트 생성

- `table_pipeline/table_enrichment.py`
  - 표 분석 본체
  - 표를 키-값, 행 요약, 비교 요약, 문맥 보강 형태로 재구성

- `table_pipeline/launcher.py`
  - 메뉴 기반 실행 진입점
  - 재적재, 평가, context dump를 커맨드 직접 입력 없이 실행

### HWP/OCR 지원

- `table_pipeline/ocr_support/extract_hwp_artifacts.py`
  - HWP 입력 처리의 시작점
  - HWP 내부 구조를 읽어서 표, 설명문, 섹션 헤더, 이미지 후보를 분리
  - HWP 기반 파이프라인은 이 파일이 없으면 시작되지 않음

- `table_pipeline/ocr_support/run_hwp_ocr_pipeline.py`
  - 이미지 OCR 실행
  - RapidOCR 또는 Windows OCR fallback 사용

- `table_pipeline/ocr_support/windows_ocr_fallback.ps1`
  - Windows 기본 OCR 호출 스크립트

### 평가/테스트

- `table_pipeline/evaluation/eval_questions_table_runner.py`
  - `eval_questions_table_v1` 기준 retrieval 평가

- `table_pipeline/evaluation/dump_eval_questions_table_context.py`
  - LLM 없이 retrieval context만 덤프

- `table_pipeline/evaluation/evaluate_table_retrieval.py`
  - 표 중심 retrieval 점검

- `table_pipeline/evaluation/evaluate_table_retrieval_cases.py`
  - 수동 정의한 표 질문 케이스 평가

- `table_pipeline/evaluation/evaluate_additional_table_cases.py`
  - 추가 문서 기준 표 질문 케이스 평가

- `table_pipeline/evaluation/evaluate_all_hwp_docname_cases.py`
  - 전체 HWP 문서명 기준 자동 평가

- `table_pipeline/evaluation/table_retrieval_cases.py`
  - 표 retrieval용 질문 케이스

- `table_pipeline/evaluation/additional_table_cases.py`
  - 문서명만 바꿔서 확장한 질문 케이스

- `table_pipeline/evaluation/all_hwp_docname_cases.py`
  - 전체 HWP 문서명 기반 자동 생성 케이스

## 폴더 구조

- `table_pipeline/`
  - 실행 핵심
- `table_pipeline/ocr_support/`
  - HWP 읽기, 이미지 OCR, OCR fallback
- `table_pipeline/evaluation/`
  - retrieval 평가 및 테스트 케이스

## 실행 흐름

1. `rag_system/ingest.py`가 `files/` 아래 문서를 순회한다.
2. HWP 문서는 `table_pipeline/ocr_support/extract_hwp_artifacts.py`가 먼저 읽어서 표, 설명문, 섹션 헤더, 이미지 후보를 분리한다.
3. `table_pipeline/rag_utils.py`가 추출 결과를 받아 semantic text를 만든다.
4. HWP 표가 있으면 `table_pipeline/table_enrichment.py`가 표를 구조화한다.
5. 이미지가 있으면 `table_pipeline/ocr_support/run_hwp_ocr_pipeline.py`가 OCR 텍스트를 만든다.
6. `table_pipeline/rag_utils.py`가 최종 chunk를 만든다.
7. `rag_system/ingest.py`가 Chroma 벡터 DB에 적재한다.

## HWP 입력 시작점

- `extract_hwp_artifacts.py`
  - HWP 파일을 직접 읽는 앞단
  - 표는 `structural_table` 계열로 추출
  - 설명문은 `explanatory_block`, 헤더는 `section_header_block`으로 분리
  - 이미지 후보는 OCR 후보로 분리

- `run_hwp_ocr_pipeline.py`
  - HWP에서 분리된 이미지 후보에 OCR 적용
  - 현재 이미지는 OCR 텍스트 블록으로 적재되고, 표는 parser-first 방식으로 처리

## 표 분석 핵심 함수

- `TABLE_FIELD_HINTS`
  - 표 라벨 후보 키워드

- `extract_key_value_pairs(table_text)`
  - 표 텍스트에서 `라벨 -> 값` 추출

- `build_table_row_summary_lines(table_text)`
  - 행 단위 의미 요약 생성

- `detect_table_type(table, table_text, pairs)`
  - 표 유형 판별

- `infer_table_title(table, doc_title, table_type)`
  - 표 제목 추정

- `build_type_template_summary(table_type, table_text, pairs)`
  - 유형별 핵심 요약 생성

- `build_comparison_summary(table_type, table_text)`
  - 비교형 질문 대응 요약 생성

- `DOC_CONTEXT_HINTS`
  - 문서 설명 블록에서 잡을 힌트 키워드

- `extract_doc_context_hints(payload)`
  - 설명문/헤더에서 표 관련 힌트 추출

- `build_doc_context_blocks(doc_title, payload)`
  - 문서 문맥 힌트를 semantic text 블록으로 생성

- `build_table_block(table, doc_title, hint_map)`
  - 최종 표 블록 생성

- `build_hwp_semantic_text(file_path)`
  - HWP 전체 semantic text 조립

## 새 HWP 문서에도 재사용 가능한가

가능하다. 이 파이프라인은 특정 문서명을 하드코딩하지 않고 아래 흐름으로 동작한다.

1. `extract_hwp_artifacts()`로 HWP 구조 추출
2. `table_enrichment.py`로 규칙 기반 표 분석
3. semantic text 조립
4. chunking
5. 벡터 DB 적재

다만 아래 경우는 추가 보강이 필요할 수 있다.

- 이미지형 표 비중이 높은 문서
- 병합 셀이 많은 표
- 표 구조가 매우 특이한 문서
- 같은 기관의 유사 사업 문서처럼 제목 구분력이 약한 경우

## 실행 방법

직접 모듈 경로를 입력하지 않으려면 루트의 `launch_table_pipeline.bat`를 사용한다.

메뉴에서 실행 가능한 작업:

- 벡터 DB 재적재
- `eval_questions_table` TB/TC 평가
- 전체 HWP 문서명 평가
- retrieval context dump
