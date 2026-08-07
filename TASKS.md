# 파일럿 작업 지시문

CLAUDE.md와 SPEC.md는 클로드코드가 세션 시작 시 자동으로 읽는다.
아래 내용을 클로드코드 채팅창 첫 메시지로 그대로 붙여넣어 사용한다.

---

```
지금은 본실험 전 파이프라인 검증 단계다. 아래 범위로만 한정해서 작업하고,
범위를 벗어나는 작업은 하지 마라. CLAUDE.md와 SPEC.md를 먼저 확인해라.

[파일럿 범위]
- 데이터셋: sorry-bench/sorry-bench-202503 (HuggingFace, gated — 접근 승인 필요)
- 카테고리: config/category_mapping.csv에서 status=active, pilot=true 인
  아래 3개만 이번 파일럿에서 실행한다.
  - 4-A-1 Personal Identifiable Information
  - 4-B-1 Libelous Words
  - 4-B-2 Intellectual Property Infringement
  전부 SorryBench 원본과 direct 매핑이므로 원본 프롬프트를 그대로 재사용한다.
  카테고리 필터링은 번호가 아니라 카테고리 이름(name) 필드로 매칭해라.
- status=pending인 카테고리(new 유형, 16개)는 이번 파일럿과 무관하다.
  config/categories.yaml에 정의만 남겨두고 건드리지 마라.
- XSTest, OR-Bench는 이번 파일럿에서 제외한다.
- 모델: config/models.yaml 참고 (Phase 1·2 피평가 모델 = GPT-5.4 mini 동일,
  심판 모델 = Gemini 3.5 Flash-Lite 동일). model_id가 "CONFIRM_ME"로 되어
  있으니 0단계에서 실제 값으로 채워야 한다.

[0-A단계: 모델 목록 확인 — 반드시 가장 먼저 수행]
GET /v1/gateway/models/ 를 호출해서 사용 가능한 모델 전체 목록을 출력해라.
그 목록에서 "GPT-5.4 mini"와 "Gemini 3.5 Flash-Lite"에 정확히 대응하는 모델
id를 찾아서, config/models.yaml의 "CONFIRM_ME" 부분을 실제 값으로 채워라.
정확히 일치하는 항목이 없으면 코드를 진행하지 말고 후보들을 나에게 보여주고
확인받아라.

[0-B단계: HuggingFace 인증 확인]
sorry-bench/sorry-bench-202503은 gated 데이터셋이다. huggingface-cli login이
이미 되어 있는지, 이 계정이 해당 데이터셋 접근 승인을 받은 상태인지 먼저
확인해라. 인증이 안 되어 있으면 코드를 진행하지 말고 나에게 알려라.

[0-C단계: 데이터셋 구조 확인 및 버전 고정 — 필터링 전 승인 필요]
아래 코드를 실행해서 데이터셋 구조와 커밋 해시를 확인하고 결과를 나에게
보여줘라. "Personal Identifiable Information", "Libelous Words",
"Intellectual Property Infringement"가 실제로 어느 컬럼의 어떤 값과
정확히 일치하는지(철자, 대소문자까지) 확인받기 전에는 필터링 코드를
작성하지 마라. 확인된 커밋 해시는 data/raw/sorrybench/DATASET_VERSION.json에
저장해라.

from huggingface_hub import dataset_info
info = dataset_info("sorry-bench/sorry-bench-202503")
print("commit sha:", info.sha)

from datasets import load_dataset
ds = load_dataset("sorry-bench/sorry-bench-202503", revision=info.sha)
print(ds)
split = list(ds.keys())[0]
print(ds[split].column_names)
print(ds[split].features)
for col in ds[split].column_names:
    if "categ" in col.lower() or "topic" in col.lower() or "cat" in col.lower():
        print(col, "->", sorted(set(ds[split][col])))

[1단계: 카테고리 3개 필터링]
0-C단계에서 확인받은 컬럼/값 기준으로 위 3개 카테고리에 해당하는 항목만
필터링해서 data/processed/pilot_direct3.csv로 저장해라. 필터링 후 카테고리별
항목 수(기본 프롬프트 수, mutation 포함 여부와 개수)를 출력해서 보고해라.

[2단계: Phase 1 (규칙 추출 + 분류)]
prompts/phase1_extraction.txt, prompts/phase1_classification.txt 원문을
그대로 사용해서, config/models.yaml에 지정된 모델로 3개 카테고리에 대해
정책을 추출하고 심판 모델로 유형 분류해라. config/models.yaml의 decoding,
max_tokens 설정을 그대로 적용해라. 실행 전 예상 API 호출 횟수를 계산해서
보여주고 승인받은 뒤 실행해라. 결과는 SPEC.md 11번 항목 JSON 스키마 그대로
results/phase1_rules/에 저장해라.

[3단계: Phase 2 (행동 테스트)]
data/processed/pilot_direct3.csv의 모든 항목에 대해 prompts/phase2_system.txt
시스템 프롬프트로 응답을 수집하고, config/refusal_keywords.yaml의 Tier 1
키워드와 prompts/phase2_judge.txt Tier 2 판정 프롬프트로 REFUSE/COMPLY/PARTIAL을
분류해라. 실행 전 예상 API 호출 횟수를 계산해서 보여주고 승인받은 뒤
실행해라. 응답이 max_tokens에 걸려 잘린 경우(finish_reason == "length")가
있으면 로그로 남기고 비율을 보고해라. 결과는 results/phase2_responses/에
저장해라.

[4단계: Phase 3 (SNCS 계산)]
SPEC.md 10번 항목의 예측 로직과 계산식을 그대로 구현해서 카테고리별 SNCS와
위반 유형(Abs-Comply, Cond-Leak, Frame-Mismatch)을 계산해라. LLM 호출 없이
결정론적으로만 수행한다. 결과는 results/phase3_scores/에 저장해라.

[결과 취급 주의사항]
PII, 명예훼손, 지적재산권 카테고리는 실제 개인정보 유사 텍스트나 명예훼손성
문구가 프롬프트/응답에 담길 수 있다. results/ 하위 파일은 팀 내부 저장소에만
두고(.gitignore로 이미 제외됨), 공유 문서에는 원문 대신 통계치만 사용해라.

각 단계 완료 후 다음을 보고해라:
- 이번 단계에서 SPEC.md/CLAUDE.md의 어느 항목을 참조했는지
- 판단이 필요했던 지점이 있었는지, 있었다면 무엇을 질문했는지
- 생성/수정된 파일 목록과 항목 수
```
