"""파일럿 이전 단계의 소규모 smoke test: 카테고리당 base 1문항씩, 총 3문항.
Phase 1(12회 호출) + Phase 2 행동수집(9회 호출) + Tier2(가변)를 실행한다.

Phase 1 호출 내역: 카테고리당 추출 3회 + 분류 1회(가장 긴 추출만 분류, 논문 방식) = 4회.
"""
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase1 import run_phase1_category
from phase2 import run_phase2_item

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "config" / "models.yaml", "r", encoding="utf-8") as f:
    MODELS = yaml.safe_load(f)

EVAL_MODEL = MODELS["models"]["phase1_evaluated"]["model_id"]
JUDGE_MODEL = MODELS["models"]["phase1_judge"]["model_id"]
MAX_TOKENS = MODELS["max_tokens"]

CATEGORIES = [
    ("4-A-1", "Personal Identifiable Information"),
    ("4-B-1", "Libelous Words"),
    ("4-B-2", "Intellectual Property Infringement"),
]


def load_smoke_items():
    path = PROJECT_ROOT / "data" / "processed" / "pilot_direct3.csv"
    items_by_cat = {}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["prompt_style"] != "base":
                continue
            cat = row["our_category_id"]
            if cat not in items_by_cat:
                items_by_cat[cat] = row
    return [items_by_cat[cid] for cid, _ in CATEGORIES]


def main():
    print(f"eval_model={EVAL_MODEL} judge_model={JUDGE_MODEL}")

    print("\n=== Phase 1 ===")
    phase1_results = {}
    for cat_id, cat_name in CATEGORIES:
        print(f"  running phase1 for {cat_id} ({cat_name})...")
        result = run_phase1_category(
            cat_id, cat_name, EVAL_MODEL, JUDGE_MODEL,
            MAX_TOKENS["phase1_extraction"], MAX_TOKENS["phase1_classification"],
        )
        phase1_results[cat_id] = result
        print(f"    rule_type={result['rule_type']} "
              f"representative=run{result['_debug_representative_run_id']} "
              f"lengths={result['_debug_extraction_lengths']} "
              f"qa_parse={result['_debug_qa_parse_status']}")

    print("\n=== Phase 2 ===")
    items = load_smoke_items()
    phase2_results = []
    for item in items:
        print(f"  running phase2 for item {item['question_id']} ({item['our_category_id']})...")
        result = run_phase2_item(
            item, EVAL_MODEL, JUDGE_MODEL,
            MAX_TOKENS["phase2_behavior"], MAX_TOKENS["phase2_tier2_judge"],
        )
        phase2_results.append(result)
        n_escalated = sum(1 for l in result["tier1_labels"] if l == "PARTIAL")
        n_truncated = sum(result["_debug_truncated"])
        print(f"    final_label={result['final_label']} tier1={result['tier1_labels']} "
              f"escalated={n_escalated} truncated={n_truncated}")

    print("\n=== Summary ===")
    total_truncated = sum(sum(r["_debug_truncated"]) for r in phase2_results)
    total_responses = sum(len(r["responses"]) for r in phase2_results)
    total_escalated = sum(sum(1 for l in r["tier1_labels"] if l == "PARTIAL") for r in phase2_results)
    print(f"phase1 categories: {len(phase1_results)}, rule_types: "
          f"{ {k: v['rule_type'] for k, v in phase1_results.items()} }")
    print(f"phase2 items: {len(phase2_results)}, responses: {total_responses}, "
          f"truncated(finish_reason=length): {total_truncated}/{total_responses} "
          f"({100*total_truncated/total_responses:.1f}%), "
          f"tier2_escalated: {total_escalated}/{total_responses}")


if __name__ == "__main__":
    main()
