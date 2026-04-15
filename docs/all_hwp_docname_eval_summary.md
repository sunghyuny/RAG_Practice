# All HWP Docname Retrieval Summary

## Test setup

- 대상 문서: `files/` 아래 HWP 96개
- 질문 방식: 문서명만 바꾸고 동일한 표 중심 질문 템플릿 5개 적용
- 총 케이스 수: 480개
- 실행 스크립트:
  - `rag_system/all_hwp_docname_cases.py`
  - `rag_system/evaluate_all_hwp_docname_cases.py`

## Question templates

1. 기능 목록 / 모듈 구성
2. 표 기반 주요 요구사항 / 핵심 기능 항목
3. 도입 장비 / 시스템 구성 / 연계 대상
4. 일정 / 평가항목 / 배점 / 산출물 / 제출서류
5. 기존 현황 / 서비스 구성 / 개선 대상 / 신규 도입

## Results

### MMR

- 결과 파일: `all_hwp_docname_cases_mmr.txt`
- Top1: `479/480`
- Top3: `480/480`

### Baseline

- 결과 파일: `all_hwp_docname_cases_baseline.txt`
- Top1: `479/480`
- Top3: `480/480`

## Weak case

### Missed document

- `축산물품질평가원_꿀 품질평가 전산시스템 기능개선 사업`

### Missed template

- `T04`
- 질문:
  - `축산물품질평가원_꿀 품질평가 전산시스템 기능개선 사업 문서에서 일정, 평가항목, 배점, 산출물, 제출서류처럼 표로 정리된 핵심 정보가 뭐야?`

### Retrieval behavior

- Top1 miss, Top3 hit
- 실제 상위 문서:
  1. `축산물품질평가원_축산물이력관리시스템 개선(정보화 사업)`
  2. `축산물품질평가원_꿀 품질평가 전산시스템 기능개선 사업`
  3. `축산물품질평가원_축산물이력관리시스템 개선(정보화 사업)`

## Interpretation

- 전체 HWP 문서 기준으로 문서명 anchoring은 매우 안정적이다.
- 남은 약점은 문서명이 매우 비슷하고 기관/도메인이 같은 문서끼리 경쟁할 때 발생한다.
- 특히 `평가항목`, `배점`, `산출물`, `제출서류`처럼 범용 표 키워드 질문에서 유사 문서가 먼저 뜰 수 있다.

## Follow-up from table/OCR side

- 표 제목에 도메인 고유어를 더 강하게 포함시키기
  - 예: `꿀 품질평가`, `축산물이력관리`
- 문서별 컨텍스트 힌트에 사업 고유 목적어 추가
- 평가/배점형 표 요약 시 문서 고유 명사를 반복 삽입
- 같은 기관 내 유사 문서 쌍을 우선 검수 대상으로 삼기
