# 프로젝트 지시사항

이 프로젝트는 SNCA(Symbolic-Neural Consistency Audit) 논문의 방법론을 재현하는
연구다. 원 논문: "Do LLMs Follow Their Own Rules? A Reflexive Audit of
Self-Stated Safety Policies"

## 절대 규칙

- 이 저장소의 **SPEC.md가 유일한 진실 공급원(single source of truth)**이다.
  모든 구현은 SPEC.md에 명시된 내용만 따른다.
- SPEC.md에 없는 내용을 스스로 판단해서 구현하지 마라. 애매하거나 빈칸인
  지점을 발견하면 코드를 작성하지 말고 먼저 질문해라.
- SPEC.md에서 `[TEAM DECISION NEEDED]`로 표시된 항목은 아직 미확정이다.
  해당 항목이 필요한 작업은 진행하지 말고 먼저 확인을 받아라.
- 프롬프트 원문(prompts/ 폴더), 카테고리 매핑(config/category_mapping.csv),
  거부 키워드 리스트(SPEC.md 9번)는 절대 임의로 다듬거나 수정하지 마라.
  "더 나은 프롬프트"로 개선하려는 시도도 금지.
- `config/category_mapping.csv`에서 `status=active`인 카테고리만 실제로
  처리한다. `status=pending`인 카테고리는 정의만 존재하며 아직 실행 대상이
  아니다.
- API를 실제로 호출하는 작업(Phase 1, Phase 2) 전에는 반드시 예상 호출
  횟수와 비용을 계산해서 보여주고 승인을 받은 뒤 실행한다.
- API 키는 `.env`에서만 읽는다. 코드나 로그에 하드코딩하거나 출력하지 않는다.

## 프로젝트 구조

- `SPEC.md` — 전체 스펙 (모델, 카테고리, 프롬프트, 계산식, 출력 스키마)
- `config/` — categories.yaml, category_mapping.csv, models.yaml
- `prompts/` — Phase 1·2 프롬프트 원문 (.txt, {CATEGORY} placeholder 포함)
- `data/raw/` — 원본 데이터셋 (가공 금지)
- `data/processed/` — 매핑 적용 후 실험용 데이터
- `src/` — 파이프라인 코드
- `results/` — Phase 1/2/3 출력
- `logs/` — API 호출 로그

## 현재 단계: 파일럿 (본실험 전 파이프라인 검증)

지금은 아래 3개 카테고리로만 파이프라인이 끝까지 도는지 검증하는 단계다:
- 4-A-1 Personal Identifiable Information
- 4-B-1 Libelous Words
- 4-B-2 Intellectual Property Infringement

각 단계 완료 후 다음을 보고할 것:
- SPEC.md의 어느 항목을 참조했는지
- 판단이 필요했던 지점이 있었는지, 있었다면 무엇을 질문했는지
- 생성/수정된 파일 목록
