# SNCA 재현 연구 (파일럿)

"Do LLMs Follow Their Own Rules? A Reflexive Audit of Self-Stated Safety
Policies" 논문의 SNCA 방법론을 팀 자체 카테고리 체계로 재현하는 연구.

## 처음 셋업하는 방법 (한 번만)

```bash
# 1. 압축 풀고 폴더 진입
cd snca-replication

# 2. 파이썬 가상환경 생성 (선택이지만 권장)
python -m venv .venv
source .venv/bin/activate        # Windows는 .venv\Scripts\activate

# 3. 필요한 패키지 설치
pip install openai python-dotenv datasets huggingface_hub pyyaml pandas httpx langsmith

# 4. .env 파일 만들고 실제 API 키 채우기
cp .env.example .env
# .env 파일을 열어서 MINDLOGIC_API_KEY=실제키값 으로 수정

# 5. HuggingFace 로그인 (SorryBench가 gated 데이터셋이라 필요)
huggingface-cli login
# 토큰 입력 후, https://huggingface.co/datasets/sorry-bench/sorry-bench-202503
# 페이지에서 접근 승인을 받아야 함 (승인 안 됐으면 미리 신청)

# 6. git 저장소 초기화 (아직 안 했다면)
git init
git add .
git commit -m "Initial SNCA pilot project scaffold"
```

## 클로드코드 실행

```bash
claude
```

세션이 시작되면 `CLAUDE.md`와 `SPEC.md`를 자동으로 읽습니다.
그 다음 `TASKS.md`에 있는 파일럿 지시문을 채팅창에 그대로 붙여넣어 시작하세요.

## 폴더 구조

```
snca-replication/
├── CLAUDE.md              # 클로드코드가 세션마다 자동으로 읽는 규칙
├── SPEC.md                # 전체 스펙 (단일 진실 공급원)
├── TASKS.md                # 파일럿 작업 지시문 (첫 메시지로 붙여넣기)
├── .env                   # 실제 API 키 (git 추적 안 됨, 직접 만들어야 함)
├── .env.example            # 키 값 없는 템플릿
├── config/
│   ├── categories.yaml           # 카테고리 29개 전체 정의
│   ├── category_mapping.csv      # SorryBench ↔ 우리 카테고리 매핑
│   ├── models.yaml                # 모델·API·디코딩 설정
│   └── refusal_keywords.yaml      # Tier 1 거부 키워드 초안
├── prompts/                # Phase 1·2 프롬프트 원문 (수정 금지)
├── data/
│   ├── raw/                # 원본 데이터셋 (가공 금지)
│   └── processed/          # 매핑 적용 후 실험용 데이터
├── src/                    # 파이프라인 코드 (클로드코드가 생성)
├── results/                 # Phase 1/2/3 출력 (git 추적 안 됨)
└── logs/                    # API 호출 로그
```

## 현재 파일럿 범위

- 카테고리 3개 (SorryBench와 direct 매핑): Personal Identifiable Information,
  Libelous Words, Intellectual Property Infringement
- 피평가 모델: GPT-5.4 mini (Phase 1·2 동일)
- 심판 모델: Gemini 3.5 Flash-Lite (Phase 1·2 동일)
- 게이트웨이: mindlogic (`https://factchat-cloud.mindlogic.ai/v1/gateway`)

자세한 내용은 `SPEC.md` 참고.
