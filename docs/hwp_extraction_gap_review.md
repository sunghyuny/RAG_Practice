# HWP Extraction Gap Review

## 목적

이 문서는 `parsed.json` 기준이 아니라, 현재 프로젝트에서 직접 구현한 HWP 파서 결과를 기준으로 표/그림 정보 손실 지점을 정리한 검토 문서다.

검토 기준은 아래 3가지다.

1. HWP 파서가 원문에서 표/이미지 후보를 얼마나 잡는가
2. 그 결과가 현재 RAG 적재 경로에서 실제로 활용 가능한 텍스트로 이어지는가
3. 어떤 문서를 먼저 OCR 또는 추가 구조 복구 대상으로 잡아야 하는가

## 기준 코드

- HWP 표/이미지 추출: [extract_hwp_artifacts.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\extract_hwp_artifacts.py)
- HWP OCR payload 생성: [build_hwp_ocr_payload.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\build_hwp_ocr_payload.py)
- OCR 실행 파이프라인: [run_hwp_ocr_pipeline.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\run_hwp_ocr_pipeline.py)
- RAG 포맷 변환: [format_hwp_ocr_for_rag.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\format_hwp_ocr_for_rag.py)
- 현재 HWP 적재 경로: [rag_utils.py](C:\Users\zerax\Desktop\RAG_Practice\rag_system\rag_utils.py)

## 핵심 결론

1. HWP 파서는 표/이미지 존재 자체는 충분히 잘 잡고 있다.
2. 표는 `structural_table`로 일부 복구되지만, 복잡한 표는 여전히 `table_ocr_candidate`로 많이 남는다.
3. 이미지는 HWP 파서에서 `image_count`로 잡히더라도 현재 RAG 적재 경로에서는 거의 활용되지 않는다.
4. 현재 부족한 부분은 "HWP에서 못 뽑는다"가 아니라 "뽑은 결과를 QA에 쓰기 좋은 텍스트로 끝까지 연결하지 못한 부분"이다.

## 검토 문서 5개

| 문서 | 선정 이유 | HWP 파서 기준 수치 | 현재 판단 |
| --- | --- | --- | --- |
| `(사)벤처기업협회_2024년 벤처확인종합관리시스템 기능 고도화 용역사업 .hwp` | 현재 샘플 OCR 결과가 이미 있고 복잡한 흐름형 표가 많음 | `table_count=221`, `structural_table_count=179`, `table_ocr_candidate_count=85`, `image_count=9`, `image_ocr_candidate_count=5` | 표 중요 + 그림 중요 |
| `(사）한국대학스포츠협의회_KUSF 체육특기자 경기기록 관리시스템 개발.hwp` | 평가표, 사업범위표, 보안표가 많고 이미지도 존재 | `table_count=148`, `structural_table_count=131`, `table_ocr_candidate_count=71`, `image_count=6`, `image_ocr_candidate_count=3` | 표 중요 + 그림 중요 |
| `(재)예술경영지원센터_통합 정보시스템 구축 사전 컨설팅.hwp` | 일정표, 산출물표, 보안특약 표가 많음 | `table_count=93`, `structural_table_count=54`, `table_ocr_candidate_count=41`, `image_count=6`, `image_ocr_candidate_count=5` | 표 중요 + 일부 그림 중요 |
| `(사)부산국제영화제_2024년 BIFF & ACFM 온라인서비스 재개발 및 행사지원시.hwp` | 작업유형표, 일정표, 신청서형 표가 많음 | `table_count=91`, `structural_table_count=75`, `table_ocr_candidate_count=30`, `image_count=17`, `image_ocr_candidate_count=0` | 표 중요 + 일부 그림 중요 |
| `2025 구미 아시아육상경기선수권대회 조직위원회_2025 구미아시아육상경.hwp` | 종목표, 보고 일정표, 신청 양식표가 명확함 | `table_count=87`, `structural_table_count=77`, `table_ocr_candidate_count=43`, `image_count=2`, `image_ocr_candidate_count=0` | 표 중요 |

## 현재 상태 정리

### 1. 표 추출

현재 HWP 파서는 표를 아래 단계로 나눈다.

- `final_sure_table`
- `final_review_table`
- `structural_table`
- `table_ocr_candidate`

즉, 표는 완전히 못 뽑는 상태가 아니라 아래 두 부류로 나뉜다.

- 이미 구조 텍스트로 어느 정도 쓸 수 있는 표
- 구조는 잡혔지만 OCR이나 추가 복구가 필요한 표

### 2. 이미지 추출

HWP 파서는 `BinData` 이미지를 직접 뽑고 `image_count`, `image_ocr_candidate_count`까지 계산한다.

하지만 현재 적재 경로를 보면 [rag_utils.py](C:\Users\zerax\Desktop\RAG_Practice\rag_system\rag_utils.py)의 `build_hwp_semantic_text()`는 아래만 RAG에 넣는다.

- `structural_table`
- `explanatory_block`
- `section_header_block`

즉, 이미지가 HWP에서 추출되더라도 지금 기본 적재 경로에서는 거의 반영되지 않는다.

### 3. OCR 연결 상태

[run_hwp_ocr_pipeline.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\run_hwp_ocr_pipeline.py) 기준으로 표는 아직 실제 crop OCR이 연결되지 않았다.

- 표 결과 상태: `ready_for_table_ocr`
- 표 `ocr_text`: 비어 있음
- 실제 chunk는 [format_hwp_ocr_for_rag.py](C:\Users\zerax\Desktop\RAG_Practice\ocr\format_hwp_ocr_for_rag.py) 에서 `source_text` fallback으로 적재

즉, 표는 "HWP 구조 추출까지만 완료, crop OCR은 미연결" 상태다.

## 문서별 체크리스트

| 문서 | 중요도 | 빠진 정보 예시 | 필요한 질문 유형 | OCR/구조 복구 필요도 | 메모 |
| --- | --- | --- | --- | --- | --- |
| 벤처기업협회 | 표 중요 / 그림 중요 | 메뉴 흐름형 표, 제출서류/요건 매핑, 화면형 이미지 | 기능 범위, 제출서류, 처리 흐름, 요건 확인 | 최상 | 샘플 OCR 결과가 있어 전후 비교가 가장 쉬움 |
| KUSF | 표 중요 / 그림 중요 | 평가표, 사업범위표, 보안 위규 처리기준, 일부 이미지 | 평가기준, 사업 범위, 보안 요구사항 | 상 | 표는 많이 살아 있지만 이미지 반영은 약함 |
| 예술경영지원센터 | 표 중요 / 일부 그림 중요 | 일정표, 산출물 제출표, 보안특약 표 | 일정, 산출물, 보안 특약 | 상 | `final_review_table`와 OCR 후보가 많음 |
| BIFF | 표 중요 / 일부 그림 중요 | 서비스별 작업유형표, 월별 일정표, 신청서형 표 | 범위, 일정, 제출서류 | 중상 | 이미지 수는 많지만 OCR 후보로 강하게 연결되지는 않음 |
| 구미 아시아육상 | 표 중요 | 종목 구성표, 보고 일정표, 위임 양식표 | 참가 종목, 일정, 신청 양식 | 중상 | figure 비중은 낮고 표 질의 영향이 큼 |

## 대표 사례 4개

### 1. 표 사례: 벤처기업협회 메뉴/업무 흐름형 표

- HWP 파서 결과에서 `table_index=23`은 `ocr_candidate_score=20`으로 가장 높은 우선순위를 가진 표다.
- 현재 추출 텍스트는 `관리기능 / 대민 제도안내(CMS) / 담당자 알림 설정 / 연계 모니터링 / 제출서류 원본 ...` 형태로 남아 있다.
- 이 표는 내용 일부는 추출됐지만, 박스형 관계와 메뉴 흐름 구조는 여전히 평면 텍스트로 눌려 있다.
- 영향 질문: "관리 기능은 어떤 하위 메뉴로 구성되는가", "제도 요건과 제출서류는 어떤 흐름으로 연결되는가"

### 2. 표 사례: KUSF 평가기준표

- HWP 파서 기준 고우선순위 표 중 하나는 `table_index=124`이고 `ocr_candidate_score=11`이다.
- 현재 추출 텍스트는 `평가부문 / 평가항목 / 평가기준 / 배점 / 전략 및 방법론 ...` 형태로 남아 있다.
- 기본 내용은 살아 있으나, 셀 경계가 약해져 항목-배점-설명 관계를 정밀하게 묻는 질의에는 불안 요소가 있다.
- 영향 질문: "평가 항목별 배점은 얼마인가", "평가기준은 어떤 항목으로 나뉘는가"

### 3. 표 사례: 구미 아시아육상 종목 구성표

- HWP 파서 결과 `table_index=2`는 `ocr_candidate_score=12`, `final_review_table`로 남아 있다.
- 현재 추출 텍스트는 `구분 / 종목명 / 남자 / 100m, 200m ... / 여자 ...` 형태로 복구돼 있다.
- 종목 목록 자체는 보이지만, 남녀 구분과 셀 경계가 완전히 안정적이지 않아 정밀 질의 시 오류 가능성이 있다.
- 영향 질문: "남자 종목과 여자 종목이 각각 무엇인가", "총 종목 수는 어떻게 되는가"

### 4. 이미지 사례: 벤처기업협회 embedded image OCR

- 샘플 OCR 결과 [sample_hwp_ocr_results.json](C:\Users\zerax\Desktop\RAG_Practice\ocr\sample_hwp_ocr_results.json) 에서 image 후보는 존재하지만 OCR 결과 품질이 낮다.
- 예를 들어 `BIN0002.jpg`, `BIN0007.jpg`, `BIN0009.jpg`는 OCR이 수행되지만 결과 문자열이 깨져 있어 RAG 근거로 쓰기 어렵다.
- 즉, 이미지는 "추출은 됨 -> OCR도 시도함 -> 하지만 현재 품질이 낮아 활용도는 낮음" 상태다.
- 영향 질문: 화면 구성, 도식 흐름, 제출 양식 이미지 설명 계열 질의

## 우선순위 목록

### 1순위 문서 3개

1. `(사)벤처기업협회_2024년 벤처확인종합관리시스템 기능 고도화 용역사업 .hwp`
   이유: 표 OCR 후보 수가 가장 많고 현재 샘플 OCR 결과가 이미 존재해 복구 전후 효과를 검증하기 가장 좋다.

2. `(사）한국대학스포츠협의회_KUSF 체육특기자 경기기록 관리시스템 개발.hwp`
   이유: 평가표, 사업범위표, 보안표가 많고 이미지도 함께 존재해 표/그림 복구 효과를 동시에 보기 좋다.

3. `(재)예술경영지원센터_통합 정보시스템 구축 사전 컨설팅.hwp`
   이유: 일정표, 산출물표, 보안특약 표가 핵심 질의에 직접 연결되고 OCR 후보 수도 높다.

### 2순위 문서 5개

1. `(사)부산국제영화제_2024년 BIFF & ACFM 온라인서비스 재개발 및 행사지원시.hwp`
   이유: 범위표와 일정표가 중요하고 신청서형 표도 포함돼 있다.

2. `2025 구미 아시아육상경기선수권대회 조직위원회_2025 구미아시아육상경.hwp`
   이유: 종목표와 보고 일정표가 명확해 QA 영향이 크다.

3. `KOICA 전자조달_[긴급] [지문] [국제] 우즈베키스탄 열린 의정활동 상하원 .hwp`
   이유: 우선순위 점수가 높고 문서 규모가 크다.

4. `문화체육관광부 국립민속박물관_2024년 국립민속박물관 민속아카이브 자.hwp`
   이유: 일정/평가/금액 관련 신호가 강해 표 손실 시 영향이 크다.

5. `경기도 평택시_2024년도 평택시 버스정보시스템(BIS) 구축사업.hwp`
   이유: 표 구조 신호가 강하고 범위/평가/일정 질의가 많을 가능성이 높다.

## 최종 판단

- 네가 만든 HWP 파서는 표/이미지 탐지와 1차 구조 복구까지는 이미 상당 부분 해냈다.
- 지금 부족한 것은 "HWP를 못 읽는 문제"가 아니라 "복잡한 표와 이미지가 QA에 바로 쓰일 수준까지 연결되지 않은 문제"다.
- 그래서 다음 단계는 새 파서를 만드는 것이 아니라, 1순위 문서 3개를 대상으로 `table_ocr_candidate`와 `image_ocr_candidate`를 실제 crop/OCR 또는 후처리로 연결하는 것이다.
