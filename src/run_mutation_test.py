"""smoke test 2단계: 카테고리당 mutation 2종(role_play, expert_endorsement) 추가 실행.
4-A-1의 role_play(question_id=161)는 SorryBench 원본 데이터 결함("the mutated text
here" 플레이스홀더)이라 같은 카테고리의 다른 question_id(162, 정상 텍스트 확인됨)로 대체.
"""
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase2 import run_phase2_item

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "config" / "models.yaml", "r", encoding="utf-8") as f:
    MODELS = yaml.safe_load(f)

EVAL_MODEL = MODELS["models"]["phase2_evaluated"]["model_id"]
JUDGE_MODEL = MODELS["models"]["phase2_judge"]["model_id"]
MAX_TOKENS = MODELS["max_tokens"]

# (category_id, prompt_style, question_id)
TARGETS = [
    ("4-A-1", "expert_endorsement", "161"),
    ("4-A-1", "role_play", "162"),  # 161 role_play는 깨진 데이터라 대체
    ("4-B-1", "expert_endorsement", "41"),
    ("4-B-1", "role_play", "41"),
    ("4-B-2", "expert_endorsement", "151"),
    ("4-B-2", "role_play", "151"),
]


def load_items():
    path = PROJECT_ROOT / "data" / "processed" / "pilot_direct3.csv"
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    items = []
    for cat, style, qid in TARGETS:
        match = next(r for r in rows if r["our_category_id"] == cat
                     and r["prompt_style"] == style and r["question_id"] == qid)
        items.append(match)
    return items


def main():
    print(f"eval_model={EVAL_MODEL} judge_model={JUDGE_MODEL}")
    items = load_items()
    for item in items:
        print(f"\n  running phase2 for {item['question_id']}_{item['prompt_style']} "
              f"({item['our_category_id']})...")
        result = run_phase2_item(
            item, EVAL_MODEL, JUDGE_MODEL,
            MAX_TOKENS["phase2_behavior"], MAX_TOKENS["phase2_tier2_judge"],
        )
        n_escalated = sum(1 for l in result["tier1_labels"] if l == "PARTIAL")
        n_truncated = sum(result["_debug_truncated"])
        print(f"    final_label={result['final_label']} tier1={result['tier1_labels']} "
              f"escalated={n_escalated} truncated={n_truncated}")


if __name__ == "__main__":
    main()
