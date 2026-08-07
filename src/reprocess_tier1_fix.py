"""아포스트로피 정규화 버그 수정 후, 이미 수집된 Phase 2 응답을 재API호출 없이
재분류한다. Tier1이 PARTIAL로 바뀐 run만 Tier2 심판을 새로 호출한다.
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_client import chat_completion
from prompts import load_phase2_judge
from tier1 import classify_tier1
from phase2 import _parse_tier2_letter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "phase2_responses"

with open(PROJECT_ROOT / "config" / "models.yaml", "r", encoding="utf-8") as f:
    MODELS = yaml.safe_load(f)

JUDGE_MODEL = MODELS["models"]["phase2_judge"]["model_id"]
MAX_TOKENS_TIER2 = MODELS["max_tokens"]["phase2_tier2_judge"]


def reprocess_file(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    old_tier1 = d["tier1_labels"]
    old_final = d["final_label"]

    new_tier1 = [classify_tier1(r) for r in d["responses"]]
    new_tier2 = [None, None, None]
    tier2_parsed = [None, None, None]
    tier2_calls = 0

    for i, label in enumerate(new_tier1):
        if label == "PARTIAL":
            judge_prompt = load_phase2_judge(d["prompt"], d["responses"][i])
            resp = chat_completion(JUDGE_MODEL, "", judge_prompt, MAX_TOKENS_TIER2, temperature=0.0)
            new_tier2[i] = resp["content"]
            tier2_parsed[i] = _parse_tier2_letter(resp["content"])
            tier2_calls += 1

    final_per_run = []
    for i, label in enumerate(new_tier1):
        if label == "PARTIAL" and tier2_parsed[i] is not None:
            final_per_run.append(tier2_parsed[i])
        elif label == "PARTIAL":
            final_per_run.append("PARTIAL")
        else:
            final_per_run.append(label)

    new_final = Counter(final_per_run).most_common(1)[0][0]

    d["tier1_labels"] = new_tier1
    d["tier2_labels"] = new_tier2
    d["final_label"] = new_final
    d["_debug_final_per_run"] = final_per_run
    d["_debug_reprocessed_note"] = "apostrophe-normalization fix applied 2026-08-07"
    d["_debug_previous_tier1_labels"] = old_tier1
    d["_debug_previous_final_label"] = old_final

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    return old_final, new_final, tier2_calls


def main():
    total_tier2_calls = 0
    for path in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        p = Path(path)
        old_final, new_final, calls = reprocess_file(p)
        total_tier2_calls += calls
        changed = " (CHANGED)" if old_final != new_final else ""
        print(f"{p.name}: {old_final} -> {new_final}{changed}  [tier2 calls: {calls}]")
    print(f"\ntotal tier2 calls made: {total_tier2_calls}")


if __name__ == "__main__":
    main()
