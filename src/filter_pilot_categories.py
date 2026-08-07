"""config/category_mapping.csv에서 pilot=true인 카테고리만 필터링해서
data/processed/pilot_direct3.csv로 저장한다 (TASKS.md 1단계).

SorryBench 원본 데이터셋의 category 컬럼은 이름이 아니라 숫자 코드(1~44)뿐이라,
HF 저장소의 meta_info.py(taxonomy 리스트)를 받아서 이름 -> 번호로 변환한다.
"""
import csv
import json
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import hf_hub_download

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_NAME = "sorry-bench/sorry-bench-202503"


def get_pinned_sha() -> str:
    version_path = PROJECT_ROOT / "data" / "raw" / "sorrybench" / "DATASET_VERSION.json"
    with open(version_path, "r", encoding="utf-8") as f:
        return json.load(f)["commit_sha"]


def load_taxonomy(sha: str) -> dict[str, str]:
    """SorryBench 공식 카테고리명 -> 번호(문자열) 매핑을 meta_info.py에서 만든다."""
    path = hf_hub_download(DATASET_NAME, "meta_info.py", repo_type="dataset", revision=sha)
    namespace = {}
    with open(path, "r", encoding="utf-8") as f:
        exec(f.read(), namespace)
    descriptions = namespace["category_descriptions"]
    return {name: str(i + 1) for i, name in enumerate(descriptions)}


def load_pilot_mapping() -> list[dict]:
    """category_mapping.csv에서 pilot=true인 행만 추출."""
    path = PROJECT_ROOT / "config" / "category_mapping.csv"
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["pilot"].strip().lower() == "true"]


def main():
    sha = get_pinned_sha()
    print(f"dataset sha: {sha}")

    taxonomy = load_taxonomy(sha)
    pilot_rows = load_pilot_mapping()

    pilot_map = {}
    for row in pilot_rows:
        sb_name = row["sorrybench_category_name"]
        if sb_name not in taxonomy:
            raise ValueError(
                f"category_mapping.csv의 sorrybench_category_name '{sb_name}'이 "
                f"meta_info.py taxonomy에 없음 - 철자/버전을 다시 확인할 것"
            )
        num = taxonomy[sb_name]
        pilot_map[num] = {
            "our_category_id": row["our_category_id"],
            "our_category_name": row["our_category_name"],
        }

    print("pilot categories (number -> our category):")
    for num, m in pilot_map.items():
        print(f"  #{num} -> {m['our_category_id']} {m['our_category_name']}")

    ds = load_dataset(DATASET_NAME, revision=sha)["train"]

    rows = []
    for ex in ds:
        if ex["category"] in pilot_map:
            m = pilot_map[ex["category"]]
            rows.append({
                "our_category_id": m["our_category_id"],
                "our_category_name": m["our_category_name"],
                "sorrybench_category_num": ex["category"],
                "question_id": ex["question_id"],
                "prompt_style": ex["prompt_style"],
                "prompt": ex["turns"][0] if len(ex["turns"]) == 1 else " ||NEXT_TURN|| ".join(ex["turns"]),
                "n_turns": len(ex["turns"]),
            })

    out_path = PROJECT_ROOT / "data" / "processed" / "pilot_direct3.csv"
    fieldnames = ["our_category_id", "our_category_name", "sorrybench_category_num",
                  "question_id", "prompt_style", "prompt", "n_turns"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"\nwrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
