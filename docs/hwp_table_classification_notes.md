# HWP Table Classification Notes

## 목적

`ocr/extract_hwp_artifacts.py`에서 HWP 표 블록을 다음 네 가지로 나눈다.

- `cover`
- `toc`
- `data_table`
- `uncertain`

이번 수정의 핵심은 `data_table` 단일 분류를 없애고, 아래 두 단계로 쪼갠 것이다.

- `sure_table`
- `review_needed`

## 이전 방식

이전에는 `row_hint_count >= 3` 같은 구조 신호가 `data_score`에 가산점으로만 들어갔다.

예시:

- `row_hint_count >= 3` 이면 `data_score += 1`
- 숫자 줄이 많으면 `data_score += 1`
- `구분`, `항목`, `내용`, `비고`가 있으면 `data_score += 2`

문제점:

- 설명형 블록도 `예산`, `기간`, `구분`, `내용` 같은 단어가 있으면 쉽게 `data_table`로 분류됐다.
- 즉 구조가 약한 블록도 키워드만 맞으면 실제 표로 오인되었다.

## 새 방식

이제 표 분류는 아래 네 단계를 가진다.

- `cover`
- `toc`
- `sure_table`
- `review_needed`
- `uncertain`

### 헤더 그룹

헤더는 단일 키워드 개수보다, 3개짜리 그룹이 얼마나 맞는지로 본다.

예시:

- `구분`, `항목`, `내용`
- `구분`, `내용`, `비고`
- `요구사항`, `ID`, `명칭`
- `요구사항`, `분류`, `명칭`
- `평가`, `배점`, `기준`
- `평가항목`, `배점`, `평가기준`
- `일정`, `기간`, `비고`
- `예산`, `금액`, `합계`
- `수량`, `단가`, `금액`
- `구분`, `역할`, `비고`

각 표 블록마다 위 그룹 중 가장 많이 맞은 개수를 `header_group_hits`로 둔다.

### 1. sure_table 조건

- `row_hint_count >= 5`
- `paragraph_count >= 4`
- `header_group_hits >= 3`
- `data_score >= 4`
- 설명형 bullet 블록이 아니어야 함

의미:

- 구조와 헤더가 모두 강하게 맞는 표만 `sure_table`로 인정한다.

### 2. review_needed 조건

- `row_hint_count >= 3`
- `paragraph_count >= 3`
- `header_group_hits >= 2`
- `data_score >= 4`

의미:

- 표일 가능성이 높지만 구조나 헤더가 완전히 강하지 않은 경우 `review_needed`로 남긴다.

## 설명형 블록 억제

다음 조건이면 설명형 블록으로 보고 `data_table`을 막는다.

- bullet 줄이 2개 이상
- 긴 줄이 2개 이상
- 헤더형 키워드가 2개 미만

의미:

- `□`, `○`, `-`, `◈`, `※`, `ㆍ` 등으로 시작하는 설명문 위주 블록은 표보다 본문형 리스트일 가능성이 높다.

## 최종 분류 순서

1. `toc_score >= 4` 이면 `toc`
2. `cover_score >= 4 and data_score <= 3` 이면 `cover`
3. 강한 구조 + 3/3 헤더 그룹 매칭이면 `sure_table`
4. 구조는 있지만 2/3 헤더 그룹 매칭이면 `review_needed`
5. 나머지는 `uncertain`

## 기대 효과

- `사업개요`, `추진배경`, `추진방안` 같은 설명형 블록의 과검출 감소
- `요구사항 정의표`, `평가표`, `배점표`, `적용계획표` 같은 실제 표를 `sure_table`로 우선 보존
- 애매한 표는 `review_needed`로 남겨 후속 규칙 보강이나 수동 검토 대상으로 사용
