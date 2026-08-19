"""category_mapping.csv 기준으로 SorryBench에서 실험용 CSV를 만든다.

filter_pilot_categories.py를 일반화한 것. 달라진 점:
- pilot=true 로 고정하지 않고, 매핑이 있는 카테고리를 전부 대상으로 한다
- prompt_style 을 골라서 뽑을 수 있다 (기본 base)
- 제외할 our_category_id 를 지정할 수 있다
- 같은 SorryBench 카테고리가 서로 다른 our_category_id 에 중복 매핑되면 중단한다
  (Phase 2 출력 파일명이 {model}_sorrybench_{question_id}_{style}.json 이라
   카테고리가 달라도 같은 문항이면 파일이 덮어써진다)

2026-08-19 랩미팅 결정: SorryBench 변형 프롬프트가 원본의 유해성을 보존하지
않는 사례가 다수 확인되어, 당분간 base 프롬프트만 사용한다.

사용 예:
    python src/build_dataset.py                      # 계획만 출력
    python src/build_dataset.py --write              # base 전체를 base_all.csv 로
    python src/build_dataset.py --styles base,question --write
    python src/build_dataset.py --exclude-categories 6-D-1,6-D-2 --write
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_NAME = "sorry-bench/sorry-bench-202503"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATUS_COL = "status(데이터셋 유무)"

# category_mapping.csv 에서 SorryBench 대응이 없음을 뜻하는 값
NO_MAPPING = {"", "SorryBench 대응 없음"}

# 랩미팅 결정으로 기본 제외하는 카테고리.
# 6-D-1 / 6-D-2 는 둘 다 "Child-related Crimes" 하나에 매핑돼 있어 문항이 겹친다.
# 팀이 매핑을 정리한 뒤에 다시 넣는다.
DEFAULT_EXCLUDE = ["6-D-1", "6-D-2"]

FIELDNAMES = ["our_category_id", "our_category_name", "sorrybench_category_num",
              "question_id", "prompt_style", "prompt", "n_turns"]

PLACEHOLDER = "the mutated text here"


def get_pinned_sha() -> str:
    path = PROJECT_ROOT / "data" / "raw" / "sorrybench" / "DATASET_VERSION.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["commit_sha"]


def load_taxonomy(sha: str) -> dict[str, str]:
    """SorryBench 공식 카테고리명 -> 번호(문자열) 매핑을 meta_info.py에서 만든다."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(DATASET_NAME, "meta_info.py", repo_type="dataset", revision=sha)
    namespace: dict = {}
    with open(path, "r", encoding="utf-8") as f:
        exec(f.read(), namespace)
    return {name: str(i + 1) for i, name in enumerate(namespace["category_descriptions"])}


def load_mapping(exclude: list[str]) -> list[dict]:
    """매핑이 실제로 존재하고 제외 대상이 아닌 행만 돌려준다."""
    path = PROJECT_ROOT / "config" / "category_mapping.csv"
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    kept = []
    for r in rows:
        sb_name = r["sorrybench_category_name"].strip()
        if sb_name in NO_MAPPING:
            continue
        if r["our_category_id"].strip() in exclude:
            continue
        kept.append(r)
    return kept


def build_category_map(mapping_rows: list[dict], taxonomy: dict[str, str]) -> dict[str, dict]:
    """SorryBench 카테고리 번호 -> our 카테고리 정보. 중복 매핑이면 중단한다."""
    owner: dict[str, str] = {}   # sb_num -> our_category_id
    cat_map: dict[str, dict] = {}

    for r in mapping_rows:
        sb_name = r["sorrybench_category_name"].strip()
        our_id = r["our_category_id"].strip()
        if sb_name not in taxonomy:
            raise ValueError(
                f"category_mapping.csv의 sorrybench_category_name '{sb_name}'이 "
                f"meta_info.py taxonomy에 없다 - 철자/데이터셋 버전을 확인할 것"
            )
        num = taxonomy[sb_name]
        if num in owner and owner[num] != our_id:
            raise ValueError(
                f"SorryBench 카테고리 '{sb_name}'(#{num})이 "
                f"'{owner[num]}'과 '{our_id}' 두 곳에 매핑돼 있다.\n"
                f"같은 문항이 두 번 실행되고 Phase 2 출력 파일이 덮어써진다. "
                f"--exclude-categories 로 한쪽을 빼거나 매핑을 정리할 것."
            )
        owner[num] = our_id
        cat_map[num] = {"our_category_id": our_id,
                        "our_category_name": r["our_category_name"].strip(),
                        "status": r[STATUS_COL].strip()}
    return cat_map


def collect_rows(cat_map: dict[str, dict], styles: list[str] | None, sha: str) -> list[dict]:
    from datasets import load_dataset

    ds = load_dataset(DATASET_NAME, revision=sha)["train"]
    out = []
    for ex in ds:
        num = ex["category"]
        if num not in cat_map:
            continue
        if styles and ex["prompt_style"] not in styles:
            continue
        turns = ex["turns"]
        prompt = turns[0] if len(turns) == 1 else " ||NEXT_TURN|| ".join(turns)
        m = cat_map[num]
        out.append({
            "our_category_id": m["our_category_id"],
            "our_category_name": m["our_category_name"],
            "sorrybench_category_num": num,
            "question_id": ex["question_id"],
            "prompt_style": ex["prompt_style"],
            "prompt": prompt,
            "n_turns": len(turns),
        })
    return out


def is_defective(prompt: str) -> bool:
    p = (prompt or "").strip()
    return not p or p.lower() == PLACEHOLDER


def report(cat_map: dict[str, dict], rows: list[dict], styles: list[str] | None,
           exclude: list[str]) -> None:
    by_cat = defaultdict(set)
    for num, m in cat_map.items():
        by_cat[m["our_category_id"]].add(num)

    print("=" * 70)
    print("데이터셋 구성 계획")
    print("=" * 70)
    print(f"스타일 : {', '.join(styles) if styles else '전체'}")
    print(f"제외   : {', '.join(exclude) if exclude else '없음'}")
    print()
    print(f"우리 카테고리 {len(by_cat)}개  <-  SorryBench 카테고리 {len(cat_map)}개")
    for cid in sorted(by_cat):
        nums = sorted(by_cat[cid], key=int)
        names = [m["our_category_name"] for n, m in cat_map.items() if n == nums[0]]
        st = cat_map[nums[0]]["status"] or "(빈칸)"
        n_items = sum(1 for r in rows if r["our_category_id"] == cid)
        print(f"  {cid:8} [{st:12}] SB #{','.join(nums):12} {n_items:4}건  {names[0]}")

    defective = [r for r in rows if is_defective(r["prompt"])]
    print()
    print(f"수집 행수      : {len(rows)}")
    print(f"원본 결함 행   : {len(defective)}  (run_full.py 가 실행 시 건너뛴다)")
    print(f"실행 대상 예상 : {len(rows) - len(defective)}")


def main():
    ap = argparse.ArgumentParser(
        description="category_mapping.csv 기준으로 SorryBench 실험용 CSV 생성")
    ap.add_argument("--styles", default="base",
                    help="쉼표 구분 prompt_style (기본 base, 'all' 이면 전체)")
    ap.add_argument("--exclude-categories", default=",".join(DEFAULT_EXCLUDE),
                    help=f"제외할 our_category_id (기본 {','.join(DEFAULT_EXCLUDE)})")
    ap.add_argument("--out", default="data/processed/base_all.csv", help="출력 CSV 경로")
    ap.add_argument("--write", action="store_true", help="실제로 파일을 쓴다")
    args = ap.parse_args()

    styles = None if args.styles.strip().lower() == "all" else \
        [s.strip() for s in args.styles.split(",") if s.strip()]
    exclude = [c.strip() for c in args.exclude_categories.split(",") if c.strip()]

    sha = get_pinned_sha()
    print(f"dataset: {DATASET_NAME}  sha={sha}\n")

    taxonomy = load_taxonomy(sha)
    mapping_rows = load_mapping(exclude)
    cat_map = build_category_map(mapping_rows, taxonomy)
    rows = collect_rows(cat_map, styles, sha)

    report(cat_map, rows, styles, exclude)

    if not args.write:
        print("\n계획만 출력했다. 실제로 쓰려면 --write 를 붙여라.")
        return

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)}행을 {out_path.relative_to(PROJECT_ROOT)} 에 저장했다.")


if __name__ == "__main__":
    main()
