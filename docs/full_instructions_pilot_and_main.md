# 클로드코드 초기 지시문

아래 내용을 SPEC.md와 함께 VSCode의 클로드코드 채팅창에 그대로 붙여넣어 사용한다.
SPEC.md의 [TEAM DECISION NEEDED] 항목을 전부 채운 뒤에만 본 프롬프트(전체 실험용)를
사용할 것.

전체 실험 전에 파이프라인 검증이 필요하면, 아래 "파일럿용 지시문"을 먼저 사용한다.

---

## 파일럿용 지시문 (direct 매핑 3개 카테고리, 본실험 전 파이프라인 검증)

```
지금은 본실험 전 파이프라인 검증 단계다. 아래 범위로만 한정해서 작업하고,
범위를 벗어나는 작업은 하지 마라.

[파일럿 범위]
- 데이터셋: sorry-bench/sorry-bench-202503 (HuggingFace, gated — 접근 승인 필요)
- 카테고리: config/category_mapping.csv에서 status=active 인 항목 중
  아래 3개만 이번 파일럿에서 실행한다. 전부 SorryBench 원본과 direct
  매핑이라 원본 프롬프트를 그대로 재사용한다
  - 4-A-1 Personal Identifiable Information ↔ SorryBench "Personal Identifiable Information"
  - 4-B-1 Libelous Words ↔ SorryBench "Libelous Words"
  - 4-B-2 Intellectual Property Infringement ↔ SorryBench "Intellectual Property Infringement"
  카테고리 필터링은 번호가 아니라 카테고리 이름(name) 필드로 매칭해라 —
  0-B단계에서 실제 컬럼값을 확인한 뒤 정확한 이름 문자열로 필터링해라.
- status=pending 인 카테고리(new 유형, 16개)는 이번 파일럿과 무관하다.
  config/categories.yaml에 정의만 남겨두고, Phase 1~3 어느 것도 실행하지 마라.
  이 카테고리들은 아직 SorryBench 대응 데이터가 없어서 "제외할지 자체 제작
  프롬프트를 추가할지"가 팀 결정 대기 중이다. 코드가 이 카테고리들을
  임의로 처리하려고 시도하면 안 된다.
- XSTest, OR-Bench는 이번 파일럿에서 제외한다
- Phase 1 피평가 모델: GPT-5.4 mini
- Phase 2 피평가 모델: GPT-5.4 mini (Phase 1과 동일 — 자기일관성 측정 조건 유지)
- Phase 1 심판 모델: Gemini 3.5 Flash-Lite
- Phase 2 Tier 2 심판 모델: Gemini 3.5 Flash-Lite (Phase 1 심판과 동일)

[API 연결 정보 — mindlogic 게이트웨이]
- Base URL: https://factchat-cloud.mindlogic.ai/v1/gateway
- 엔드포인트: POST /v1/gateway/chat/completions/ (OpenAI 호환 Chat Completions)
- 인증: Authorization: Bearer {API_KEY} 헤더 사용. API 키는 .env 파일에
  MINDLOGIC_API_KEY=실제키값 형태로 저장하고 python-dotenv로 읽어와라.
  .env는 .gitignore에 반드시 등록하고, 값이 비어있는 .env.example을
  별도로 커밋해라. 코드나 로그에 키 값이 그대로 출력되지 않게 해라.
- 디코딩 설정: temperature=0, 반복 횟수=3회(다수결로 최종 라벨 결정)
- max_tokens는 호출 종류마다 다르게 설정해라:
  - Phase 1 추출(피평가 모델): 1024
  - Phase 1 분류(심판 모델): 512
  - Phase 2 행동 테스트(피평가 모델): 1024
  - Phase 2 Tier 2 판정(심판 모델): 200
  이 값을 임의로 통일하거나 바꾸지 마라. 특히 Phase 2 행동 테스트 응답이
  max_tokens에 걸려 잘리면 Tier 1 키워드 분류기가 COMPLY를 REFUSE로
  오판할 수 있으니, 실제 실행 중 응답이 max_tokens에 도달해 잘린 경우가
  있는지(finish_reason == "length") 로그로 남기고 비율을 보고해라.
- openai 파이썬 SDK를 그대로 쓰되 base_url만 위 값으로 지정해라. GPT-5.4 mini와
  Gemini 3.5 Flash-Lite 둘 다 이 게이트웨이의 동일한 OpenAI 호환 엔드포인트로
  호출한다:
  client = OpenAI(api_key=os.environ["MINDLOGIC_API_KEY"],
                   base_url="https://factchat-cloud.mindlogic.ai/v1/gateway")
- 코드 작성 전에 GET /v1/gateway/models/ 를 먼저 호출해서 "GPT-5.4 mini"와
  "Gemini 3.5 Flash-Lite"에 대응하는 정확한 모델 문자열(model id)을 확인하고
  결과를 나에게 보여줘라. 목록에서 이름이 정확히 일치하지 않으면 임의로
  비슷한 걸 골라 쓰지 말고 나에게 확인받아라.
- Gemini 계열 모델은 OpenAI/Anthropic 모델과 JSON 강제 출력, system 메시지
  처리 방식이 다를 수 있다. 심판 모델 소규모 테스트 호출을 먼저 해보고
  SPEC.md 6, 8번 항목의 JSON 스키마가 그대로 파싱되는지 확인한 뒤 본격
  구현에 들어가라. 파싱이 깨지면 임의로 프롬프트를 고치지 말고 나에게
  먼저 보고해라.

[0-A단계: 모델 목록 확인 — 반드시 가장 먼저 수행]
GET /v1/gateway/models/ 를 호출해서 사용 가능한 모델 전체 목록을 출력해라.
그 목록에서 "GPT-5.4 mini"와 "Gemini 3.5 Flash-Lite"에 정확히 대응하는 모델 id를
찾아서 config/models.yaml 초안으로 정리해 보여줘라. 정확히 일치하는 항목이
없으면 코드를 진행하지 말고 후보들을 나에게 보여주고 확인받아라.

[0-B단계: HuggingFace 인증 확인]
sorry-bench/sorry-bench-202503은 gated 데이터셋이다. huggingface-cli login이
이미 되어 있는지, 그리고 이 계정이 해당 데이터셋 접근 승인을 받은 상태인지
먼저 확인해라. 인증이 안 되어 있으면 코드를 진행하지 말고 나에게 알려라.

[0-C단계: 데이터셋 구조 확인 및 버전 고정 — 반드시 먼저 수행, 필터링 전 승인 필요]
아래 코드를 실행해서 데이터셋 구조와 커밋 해시를 확인하고 결과를 나에게 보여줘라.
이 결과를 보여주고 "Personal Identifiable Information", "Libelous Words",
"Intellectual Property Infringement"가 실제로 어느 컬럼의 어떤 값과 정확히
일치하는지(철자, 대소문자까지) 나에게 확인받기 전에는 필터링 코드를 작성하지 마라.

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

확인된 커밋 해시는 data/raw/sorrybench/DATASET_VERSION.json에
{"dataset": "sorry-bench/sorry-bench-202503", "commit_sha": "...", "downloaded_at": "..."}
형태로 저장해라. 이후 모든 다운로드는 이 revision을 고정해서 받아라.

[1단계: 3개 카테고리 필터링]
0-C단계에서 확인받은 컬럼/값 기준으로 4-A-1(PII), 4-B-1(Libelous Words),
4-B-2(IP Infringement) 세 카테고리에 해당하는 항목만 필터링해서
data/processed/pilot_direct3.csv로 저장해라. 우리 카테고리 코드(4-A-1 등)를
컬럼으로 추가해서 원본 라벨과 함께 남겨라. 필터링 후 카테고리별 항목 수를
출력해서 나에게 보고해라.

[2단계: Phase 1 (규칙 추출 + 분류)]
SPEC.md 5, 6번 항목의 프롬프트 원문을 그대로 사용해서, 3개 카테고리 각각에
대해 정책을 추출하고 심판 모델로 유형 분류해라. 프롬프트 문구는 본실험과 동일하게
한 글자도 바꾸지 마라. 실행 전 예상 API 호출 횟수(카테고리 수 × 반복 횟수)를
계산해서 보여주고 승인받은 뒤 실행해라.

[3단계: Phase 2 (행동 테스트)]
pilot_direct3.csv의 모든 항목에 대해 SPEC.md 7번 항목 시스템 프롬프트로 응답을
수집하고, SPEC.md 9번 항목 Tier 1 키워드 리스트와 SPEC.md 8번 항목 Tier 2 판정
프롬프트로 REFUSE/COMPLY/PARTIAL을 분류해라. 실행 전 예상 API 호출 횟수(항목 수 ×
반복 횟수)를 계산해서 보여주고 승인받은 뒤 실행해라.

[4단계: Phase 3 (SNCS 계산)]
SPEC.md 10번 항목의 예측 로직과 계산식을 그대로 구현해서 3개 카테고리 각각의
SNCS와 위반 유형(Abs-Comply, Cond-Leak, Frame-Mismatch)을 계산해라. 이 단계는
LLM 호출 없이 결정론적으로만 수행한다. 로직을 간소화하거나 본실험과 다르게
구현하지 마라 — 파일럿의 목적은 본실험과 동일한 로직이 끝까지 에러 없이
도는지 확인하는 것이다.

[결과 취급 주의사항]
PII, 명예훼손, 저작권 침해 카테고리는 실제 개인정보나 명예훼손성 표현이
프롬프트/응답에 포함될 수 있다. 프롬프트 원문과 모델 응답 원문이 담긴
results/ 하위 파일은 팀 내부 저장소에만 두고, git에 커밋하거나 공유 문서에
원문을 그대로 붙여넣지 마라. 요약 시에는 통계치(SNCS 점수, 위반 유형 카운트)만
사용해라.

각 단계 완료 후 다음을 보고해라:
- 이번 단계에서 SPEC.md의 어느 항목을 참조했는지
- 판단이 필요했던 지점이 있었는지, 있었다면 무엇을 질문했는지
- 생성/수정된 파일 목록과 항목 수
```

파일럿이 끝까지 에러 없이 돌고 결과(SNCS, 위반 유형)가 사람이 보기에도 말이 되는
수준이면, 그때 SPEC.md 전체를 마저 채우고 아래 "본실험용 지시문"으로 넘어간다.

---

## 본실험용 지시문 (SPEC.md 전체 확정 후 사용)

```
이 프로젝트는 "Do LLMs Follow Their Own Rules? A Reflexive Audit of Self-Stated Safety
Policies" 논문의 SNCA(Symbolic-Neural Consistency Audit) 방법론을 재현하는 연구다.
카테고리 체계만 우리 팀이 만든 것으로 바꾸고, 나머지 방법론(모델, 프롬프트, 계산식,
데이터셋)은 논문과 동일하게 구현한다.

가장 중요한 규칙: 이 SPEC.md에 명시되지 않은 내용은 절대 스스로 판단해서 구현하지
마라. 스펙에 빈칸이 있거나 애매한 지점을 발견하면, 코드를 작성하지 말고 먼저 나에게
질문해라. 특히 다음 항목들은 절대 임의로 채우지 마라:
- 카테고리 매핑 규칙 (SPEC.md 3번 항목에 이미 확정되어 있음, 없으면 질문할 것)
- 거부 키워드 리스트 (SPEC.md 9번 항목에 이미 확정되어 있음, 없으면 질문할 것)
- 프롬프트 문구 (SPEC.md 5~8번 항목 원문을 토씨 하나 바꾸지 말고 그대로 사용)
- 모델명, temperature, 반복 횟수 등 실험 설정값 (SPEC.md 1번 항목 그대로 사용)
- SNCS 계산식과 예측 로직 (SPEC.md 10번 항목 수식 그대로 구현, 임의 변형 금지)

작업은 아래 순서로 단계별로 진행하고, 각 단계가 끝날 때마다 나에게 결과를 보여주고
다음 단계로 넘어가도 되는지 확인받아라. 여러 단계를 한 번에 몰아서 하지 마라.

[1단계] 폴더 구조 생성
SPEC.md와 이전에 합의한 폴더 구조(config/, prompts/, data/, src/, results/, logs/)를
그대로 만들어라. 빈 디렉토리와 함께 각 폴더의 역할을 README.md로 한 줄씩 남겨라.

[2단계] config 파일 생성
SPEC.md 1, 2, 3번 항목을 그대로 옮겨서 config/models.yaml, config/categories.yaml,
config/category_mapping.csv를 만들어라. 표에 있는 값을 그대로 옮기기만 하고,
누락되거나 [TEAM DECISION NEEDED]로 남아있는 셀이 있으면 파일을 만들지 말고
나에게 먼저 알려라.

[3단계] 프롬프트 파일 생성
SPEC.md 5~8번 항목의 프롬프트 원문을 그대로 prompts/ 폴더의 각 .txt 파일로 저장해라.
{CATEGORY} placeholder는 그대로 남겨두고, 문구를 한 글자도 다듬거나 개선하지 마라.

[4단계] 데이터 다운로드 스크립트
SPEC.md 4번 항목에 명시된 출처에서 SORRY-Bench, XSTest, OR-Bench 원본을
data/raw/ 하위에 각각 받아오는 스크립트를 작성해라. 원본 컬럼 구조를 그대로
보존하고 어떤 필터링도 하지 마라. 다운로드가 끝나면 각 데이터셋의 항목 수를
출력해서 원 논문에 명시된 규모(SORRY-Bench 450+9000, XSTest 450, OR-Bench 1974)와
일치하는지 확인해라. 불일치하면 나에게 알리고 멈춰라.

[5단계] 카테고리 매핑 적용 스크립트
config/category_mapping.csv를 읽어서 data/raw의 원본 프롬프트를 우리 카테고리
ID로 재라벨링한 data/processed/mapped_prompts.csv를 생성해라. mapping_type이
split인 항목은 category_mapping.csv에 이미 확정된 split_criteria를 그대로
적용하고, 그 기준으로 원본 프롬프트를 어느 하위 카테고리로 나눌지 스스로
판단하지 마라 — 이 재라벨링이 이미 사람이 수작업으로 끝낸 상태인지, 아니면
코드가 자동으로 나눠야 하는지 나에게 먼저 확인해라.

[6단계] Tier 1 키워드 분류기 구현
SPEC.md 9번 항목의 키워드 리스트를 src/keyword_classifier.py에 그대로 하드코딩해라.
판정 규칙(길이 기준, 키워드 매칭)도 SPEC.md에 명시된 대로 정확히 구현해라.

[7단계] Phase 1 스크립트 (규칙 추출 + 분류)
src/phase1_extract.py: config와 prompts를 읽어 (모델, 카테고리) 쌍마다 API를
호출하고, 반복 횟수만큼 실행해서 최장 무오류 응답을 저장해라.
src/phase1_classify.py: 심판 모델에 추출된 정책을 보내 SPEC.md 11번 항목
JSON 스키마 그대로 결과를 저장해라.
API 호출 전에 예상 호출 횟수와 예상 비용을 계산해서 먼저 나에게 보여주고
승인을 받아라.

[8단계] Phase 2 스크립트 (행동 테스트)
src/phase2_behavior.py: data/processed/mapped_prompts.csv를 순회하며 중립
시스템 프롬프트로 응답을 수집하고, keyword_classifier와 Tier 2 판정을 거쳐
최종 라벨을 SPEC.md 스키마대로 저장해라. 이 단계도 실행 전 예상 호출 횟수와
비용을 먼저 보여줘라.

[9단계] Phase 3 스크립트 (예측 및 채점)
src/phase3_score.py: SPEC.md 10번 항목의 예측 로직과 SNCS 계산식을 그대로
구현해라. 이 스크립트는 LLM API를 호출하지 않는다 — 만약 구현 중 LLM 호출이
필요해 보이는 지점이 생기면 (예: 조건-프레이밍 일치 판정), 임의로 API를
추가하지 말고 나에게 먼저 알려라.

[10단계] 검증 스크립트
SPEC.md 12번 항목 체크리스트를 코드로 구현해서 결과 재현성을 점검해라.

각 단계 완료 후 다음을 반드시 보고해라:
- 이번 단계에서 SPEC.md의 어느 항목을 참조했는지
- SPEC.md에 없어서 판단이 필요했던 지점이 있었는지 (있었다면 무엇을 질문했는지)
- 생성/수정된 파일 목록
```

---

## 사용 팁

- 한 번에 전체 프롬프트를 붙여넣되, 실제로는 1단계 결과만 먼저 확인하고 "2단계 진행해줘"라고 명시적으로 승인해가며 진행하는 걸 권장합니다. 클로드코드가 알아서 여러 단계를 연달아 처리하게 두면 검토 없이 결정이 누적됩니다.
- Phase 1, 2는 실제 API 비용이 발생하는 단계이므로, 실행 전 반드시 "예상 호출 횟수 계산해서 보여줘"를 먼저 시키고 소규모 파일럿(카테고리 2~3개)으로 먼저 돌려본 뒤 전체 실행하는 걸 추천합니다.
