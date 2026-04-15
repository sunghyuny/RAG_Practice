# HWP Table Enrichment Results

## 작업 범위

- HWP 표 파싱 결과를 QA 친화적인 표 표현으로 보강
- 이미지 OCR이 필요한 경우 Windows OCR fallback 경로 추가
- 표 중심 질문 평가셋과 context dump 스크립트 추가
- Group B/C 질문 기준으로 재적재 및 재평가 수행

## 적용한 보강

- `STRUCTURAL_TABLE` 블록에 `DOC_TITLE`, `TABLE_INDEX`, `SECTION_HEADER` 추가
- 표에서 추정 가능한 `KEY_VALUE_SUMMARY`, `ROW_SUMMARY` 생성
- 표 유형 추정 로직 추가
  - `equipment_region`
  - `service_status`
  - `ai_requirement`
  - `requirement_table`
  - `score_table`
  - `schedule_table`
- 표 제목과 비교형 요약 추가
  - `TABLE_TITLE`
  - `TABLE_TYPE`
  - `TYPE_TEMPLATE_SUMMARY`
  - `COMPARISON_SUMMARY`
- 원본 표 내용은 `RAW_TABLE_TEXT`로 유지

## 실행 결과

- 벡터 DB 재구축 완료
  - `Stored 23528 chunks`
- 평가 실행
  - `python -m rag_system.eval_questions_table_runner --groups TB TC --retrieval-mode mmr --k 5`
  - `python -m rag_system.dump_eval_questions_table_context --groups TB TC --retrieval-mode mmr --k 3`
- 현재 결과
  - `Top1 9/10`
  - `Top3 9/10`

## 관찰 사항

- `TB-02`는 `COMPARISON_SUMMARY`에 장비 축 요약이 추가되어 장비 관련 표 맥락이 더 잘 드러남
- `TB-05`는 기존 서비스 구성 관련 문장이 더 잘 노출되지만, 탑재 앱 목록 표를 직접 끌어오는 부분은 추가 보강 여지 있음
- `TC-05`는 여전히 다른 문서가 끼어드는 경우가 있어 표 제목 추출 정확도와 표 유형 규칙을 더 다듬을 필요가 있음

## 남은 과제

- 표 제목 추출 정확도 개선
- 표 유형 판별 규칙 보강
- 비교형/문제-해결형 표에 대한 브리지 문장 강화
