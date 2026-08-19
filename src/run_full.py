"""전체 데이터셋 실행 스크립트 (Phase 1 규칙 추출 + Phase 2 행동 테스트).

run_smoke_test.py / run_mutation_test.py를 대체한다. 달라진 점:
- 돌릴 항목을 코드에 하드코딩하지 않고 CSV에서 읽는다
- SorryBench 원본 결함 행(플레이스홀더/빈 프롬프트)을 자동으로 건너뛴다
- 이미 결과 JSON이 있는 항목은 건너뛴다 -> 중단 후 이어서 실행 가능
- 항목 하나가 실패해도 전체가 죽지 않고 계속 진행한다
- --yes 를 붙이지 않으면 계획만 출력하고 API를 호출하지 않는다
  (CLAUDE.md: API 호출 전 예상 횟수를 보여주고 승인받을 것)

사용 예:
    python src/run_full.py                                   # 계획만 출력, API 호출 없음
    python src/run_full.py --phase2 --yes                    # Phase 2 전체 실행
    python src/run_full.py --phase1 --phase2 --yes           # 둘 다
    python src/run_full.py --phase2 --styles base --yes      # base 스타일만
    python src/run_full.py --phase2 --categories 4-A-1 --limit 10 --yes
    python src/run_full.py --phase2 --data data/processed/full.csv --yes
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase1 import run_phase1_category
from phase2 import run_phase2_item

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "config" / "models.yaml", "r", encoding="utf-8") as f:
    MODELS = yaml.safe_load(f)

MAX_TOKENS = MODELS["max_tokens"]
PHASE1_EVAL = MODELS["models"]["phase1_evaluated"]["model_id"]
PHASE1_JUDGE = MODELS["models"]["phase1_judge"]["model_id"]
PHASE2_EVAL = MODELS["models"]["phase2_evaluated"]["model_id"]
PHASE2_JUDGE = MODELS["models"]["phase2_judge"]["model_id"]
REPETITIONS = MODELS["decoding"]["repetitions"]

DEFAULT_DATA = PROJECT_ROOT / "data" / "processed" / "pilot_direct3.csv"
PHASE1_DIR = PROJECT_ROOT / "results" / "phase1_rules"
PHASE2_DIR = PROJECT_ROOT / "results" / "phase2_responses"

# SorryBench 원본에서 mutation 생성이 누락된 행에 들어있는 템플릿 문구.
# 원본 9,240개 중 8건이 이 문구이고, 4건은 turns가 NULL이라 빈 문자열이 된다.
PLACEHOLDER = "the mutated text here"


def is_defective(prompt: str) -> bool:
    """SorryBench 원본 데이터 결함 행인지 판정한다."""
    p = (prompt or "").strip()
    return not p or p.lower() == PLACEHOLDER


def phase1_output_path(category_id: str) -> Path:
    return PHASE1_DIR / f"{PHASE1_EVAL}_{category_id}.json"


def phase2_output_path(item: dict) -> Path:
    item_id = f"{item['question_id']}_{item['prompt_style']}"
    return PHASE2_DIR / f"{PHASE2_EVAL}_sorrybench_{item_id}.json"


def load_rows(data_path: Path) -> list[dict]:
    with open(data_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def select_items(rows: list[dict], styles: list[str] | None,
                 categories: list[str] | None, limit: int | None) -> tuple[list[dict], dict]:
    """돌릴 항목을 고르고, 왜 제외됐는지 집계해서 함께 돌려준다."""
    stats = {"total": len(rows), "style": 0, "category": 0, "defective": 0, "done": 0}

    selected = []
    for r in rows:
        if styles and r["prompt_style"] not in styles:
            stats["style"] += 1
            continue
        if categories and r["our_category_id"] not in categories:
            stats["category"] += 1
            continue
        if is_defective(r["prompt"]):
            stats["defective"] += 1
            continue
        if phase2_output_path(r).exists():
            stats["done"] += 1
            continue
        selected.append(r)

    if limit is not None:
        selected = selected[:limit]

    return selected, stats


def select_categories(rows: list[dict], categories: list[str] | None) -> tuple[list[tuple], int]:
    """Phase 1 대상 카테고리 목록. 이미 결과가 있는 카테고리는 제외한다."""
    seen, todo, done = {}, [], 0
    for r in rows:
        cid, cname = r["our_category_id"], r["our_category_name"]
        if categories and cid not in categories:
            continue
        if cid in seen:
            continue
        seen[cid] = cname
        if phase1_output_path(cid).exists():
            done += 1
        else:
            todo.append((cid, cname))
    return todo, done


def print_plan(p1_todo, p1_done, p2_items, p2_stats, do_phase1, do_phase2):
    print("=" * 70)
    print("실행 계획")
    print("=" * 70)
    print(f"피평가 모델: {PHASE2_EVAL}    심판 모델: {PHASE2_JUDGE}")
    print(f"반복 횟수  : {REPETITIONS}회 (다수결)")
    print()

    p1_calls = p2_gpt = p2_judge_max = 0

    if do_phase1:
        p1_calls = len(p1_todo) * (REPETITIONS + 1)
        print(f"[Phase 1] 대상 카테고리 {len(p1_todo)}개 (이미 완료된 {p1_done}개 제외)")
        for cid, cname in p1_todo[:10]:
            print(f"    {cid}  {cname}")
        if len(p1_todo) > 10:
            print(f"    ... 외 {len(p1_todo) - 10}개")
        print(f"  호출: 카테고리당 추출 {REPETITIONS}회 + 분류 1회 = {p1_calls}회")
        print(f"  토큰 상한: 추출 {MAX_TOKENS['phase1_extraction']} / 분류 {MAX_TOKENS['phase1_classification']}")
        print()

    if do_phase2:
        p2_gpt = len(p2_items) * REPETITIONS
        p2_judge_max = p2_gpt
        s = p2_stats
        print(f"[Phase 2] 대상 항목 {len(p2_items)}개")
        print(f"  CSV 전체 {s['total']}행")
        print(f"    - 스타일 필터로 제외 : {s['style']}")
        print(f"    - 카테고리 필터로 제외: {s['category']}")
        print(f"    - 원본 데이터 결함    : {s['defective']}")
        print(f"    - 이미 완료됨         : {s['done']}")
        print(f"  호출: 피평가 {p2_gpt}회 + 심판 최대 {p2_judge_max}회")
        print(f"        (심판은 Tier1이 PARTIAL인 응답만 호출. 파일럿에선 100%가 escalate였음)")
        print(f"  토큰 상한: 행동 {MAX_TOKENS['phase2_behavior']} / 심판 {MAX_TOKENS['phase2_tier2_judge']}")
        print()

    total_max = p1_calls + p2_gpt + p2_judge_max
    print("-" * 70)
    print(f"총 API 호출: 최소 {p1_calls + p2_gpt}회, 최대 {total_max}회")
    print("-" * 70)


def run(args):
    data_path = Path(args.data) if args.data else DEFAULT_DATA
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path
    if not data_path.exists():
        sys.exit(f"데이터 파일이 없다: {data_path}")

    rows = load_rows(data_path)
    styles = args.styles.split(",") if args.styles else None
    categories = args.categories.split(",") if args.categories else None

    do_phase1, do_phase2 = args.phase1, args.phase2
    if not do_phase1 and not do_phase2:
        do_phase1 = do_phase2 = True

    p1_todo, p1_done = select_categories(rows, categories) if do_phase1 else ([], 0)
    p2_items, p2_stats = select_items(rows, styles, categories, args.limit) if do_phase2 else ([], {})

    print(f"데이터: {data_path.relative_to(PROJECT_ROOT)}")
    print()
    print_plan(p1_todo, p1_done, p2_items, p2_stats, do_phase1, do_phase2)

    if not args.yes:
        print()
        print("계획만 출력했다. 실제로 실행하려면 --yes 를 붙여라.")
        return

    if not p1_todo and not p2_items:
        print("\n실행할 항목이 없다.")
        return

    failures = []
    started = time.time()

    if do_phase1 and p1_todo:
        print(f"\n=== Phase 1 시작 ({len(p1_todo)}개) ===")
        for i, (cid, cname) in enumerate(p1_todo, 1):
            try:
                r = run_phase1_category(
                    cid, cname, PHASE1_EVAL, PHASE1_JUDGE,
                    MAX_TOKENS["phase1_extraction"], MAX_TOKENS["phase1_classification"],
                )
                print(f"  [{i}/{len(p1_todo)}] {cid} -> {r['rule_type']} "
                      f"(대표 run{r['_debug_representative_run_id']}, conf={r['confidence']})")
            except KeyboardInterrupt:
                print("\n중단됨. 여기까지 저장된 결과는 남아있고, 다시 실행하면 이어서 진행된다.")
                return
            except Exception as e:
                failures.append(("phase1", cid, repr(e)))
                print(f"  [{i}/{len(p1_todo)}] {cid} 실패: {e}")

    if do_phase2 and p2_items:
        n = len(p2_items)
        print(f"\n=== Phase 2 시작 ({n}개) ===")
        labels = {"REFUSE": 0, "COMPLY": 0, "PARTIAL": 0}
        for i, item in enumerate(p2_items, 1):
            item_id = f"{item['question_id']}_{item['prompt_style']}"
            try:
                r = run_phase2_item(
                    item, PHASE2_EVAL, PHASE2_JUDGE,
                    MAX_TOKENS["phase2_behavior"], MAX_TOKENS["phase2_tier2_judge"],
                )
                labels[r["final_label"]] = labels.get(r["final_label"], 0) + 1
                if i % args.progress_every == 0 or i == n:
                    elapsed = time.time() - started
                    rate = i / elapsed if elapsed else 0
                    eta = (n - i) / rate if rate else 0
                    print(f"  [{i}/{n}] {item['our_category_id']} {item_id} -> {r['final_label']}"
                          f"   경과 {elapsed/60:.1f}분, 남은 예상 {eta/60:.1f}분, 누적 {labels}")
            except KeyboardInterrupt:
                print(f"\n중단됨 ({i-1}/{n} 완료). 다시 실행하면 이어서 진행된다.")
                return
            except Exception as e:
                failures.append(("phase2", item_id, repr(e)))
                print(f"  [{i}/{n}] {item_id} 실패: {e}")

        print(f"\nPhase 2 최종 라벨 집계: {labels}")

    print(f"\n총 소요 {(time.time() - started)/60:.1f}분")
    if failures:
        print(f"\n실패 {len(failures)}건 (다시 실행하면 재시도된다):")
        for phase, ident, err in failures[:20]:
            print(f"  {phase}  {ident}  {err}")
        if len(failures) > 20:
            print(f"  ... 외 {len(failures) - 20}건")


def main():
    ap = argparse.ArgumentParser(
        description="SNCA 전체 실행 (--yes 없이는 계획만 출력한다)")
    ap.add_argument("--phase1", action="store_true", help="Phase 1 규칙 추출 실행")
    ap.add_argument("--phase2", action="store_true", help="Phase 2 행동 테스트 실행")
    ap.add_argument("--data", help=f"입력 CSV 경로 (기본: {DEFAULT_DATA.relative_to(PROJECT_ROOT)})")
    ap.add_argument("--styles", help="prompt_style 필터, 쉼표 구분 (예: base,role_play)")
    ap.add_argument("--categories", help="our_category_id 필터, 쉼표 구분 (예: 4-A-1,4-B-1)")
    ap.add_argument("--limit", type=int, help="Phase 2 실행 항목 수 상한")
    ap.add_argument("--progress-every", type=int, default=10, help="진행 상황 출력 간격 (기본 10)")
    ap.add_argument("--yes", action="store_true", help="실제로 API를 호출한다")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
