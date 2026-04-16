# Table Pipeline 수정사항

## 1. 구조 정리

- `rag_system/table_pipeline/` 아래에 있던 표 분석 관련 코드를 루트 1계층인 `table_pipeline/`으로 이동
- 실행 핵심과 보조 파일을 다음처럼 분리
  - `table_pipeline/`
    - `rag_utils.py`
    - `table_enrichment.py`
    - `launcher.py`
    - `README.md`
  - `table_pipeline/evaluation/`
    - 평가 스크립트
    - 질문 케이스 파일
  - `table_pipeline/ocr_support/`
    - `extract_hwp_artifacts.py`
    - `run_hwp_ocr_pipeline.py`
    - `windows_ocr_fallback.ps1`

## 2. import / 실행 경로 수정

- `rag_system/ingest.py`
  - `table_pipeline.rag_utils`를 직접 import 하도록 변경
- `rag_system/qa.py`
  - `table_pipeline.rag_utils`를 직접 import 하도록 변경
- `launch_table_pipeline.bat`
  - `python -m table_pipeline.launcher`를 실행하도록 변경
- `table_pipeline/launcher.py`
  - 평가 모듈 경로를 `table_pipeline.evaluation.*` 기준으로 수정

## 3. OCR / HWP 지원 경로 정리

- HWP 입력 시작점인 `extract_hwp_artifacts.py`를 `table_pipeline/ocr_support/`로 이동
- 이미지 OCR 실행 파일인 `run_hwp_ocr_pipeline.py`를 `table_pipeline/ocr_support/`로 이동
- 기존 `ocr/` 경로는 바로 깨지지 않도록 얇은 래퍼 파일만 유지

## 4. README 정리

- `table_pipeline/README.md`를 다시 작성
- 아래 내용을 명시적으로 추가
  - 핵심 코드 목록
  - 실행 흐름
  - HWP 입력 시작점
  - 표 분석 핵심 함수
  - 새 HWP 문서 재사용 가능 여부

## 5. LLM 평가 질문셋 복구

- `table_pipeline/evaluation/evaluate_table_focus.py`
  - 깨져 있던 질문 문자열을 정상 한글로 복구
  - 벤처기업협회 4개 질문
  - 국방과학연구소 2개 질문

## 6. 코드 정리

### `table_pipeline/table_enrichment.py`

- `Pair = tuple[str, str]` 타입 별칭 추가
- `extract_key_value_pairs()`가 `extract_table_lines()`를 재사용하도록 정리
- `build_table_key_value_lines()`가 이미 계산한 `pairs`를 재사용할 수 있게 수정
- `build_table_row_summary_lines()`가 이미 계산한 `pairs`를 재사용할 수 있게 수정
- `append_if_value()` 헬퍼 추가
- `build_type_template_summary()` 내부 반복 패턴 정리
- `build_table_block()`에서 key-value/row-summary 중복 계산 제거

### `table_pipeline/rag_utils.py`

- `table_enrichment` import를 상단으로 정리
- 빠져 있던 `extract_doc_context_hints` import 추가
- OCR 관련 매직넘버를 상수로 분리
  - `MIN_OCR_LINE_LENGTH`
  - `MIN_IMAGE_BLOCK_LENGTH`
- `append_labeled_block()` 헬퍼 추가
- explanatory/header 블록 추가 로직 중복 축소

## 7. 동작 검증

- import 정상 확인
  - `table_pipeline.table_enrichment`
  - `table_pipeline.rag_utils`
  - `table_pipeline.ocr_support.extract_hwp_artifacts`
  - `table_pipeline.ocr_support.run_hwp_ocr_pipeline`
  - `table_pipeline.evaluation.eval_questions_table_runner`
  - `table_pipeline.evaluation.evaluate_all_hwp_docname_cases`
  - `rag_system.ingest`
  - `rag_system.qa`
  - `ocr.extract_hwp_artifacts`
  - `ocr.run_hwp_ocr_pipeline`

- 런처 정상 확인
  - `table_pipeline.launcher` 실행 시 워크스페이스와 메뉴 출력 정상

## 8. 현재 판단

- 문서 추출, 표 분석, semantic text 조립, chunk 생성, 벡터 DB 적재는 안정화됨
- retrieval 기준 문서 hit도 높은 수준
- 남은 품질 이슈는 retrieval보다는 LLM의 근거 조합 및 답변 구성 단계에 가까움
