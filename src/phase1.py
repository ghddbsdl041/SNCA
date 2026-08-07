"""Phase 1: 정책 추출(피평가 모델) + 유형 분류(심판 모델).

확정된 반복 방식 (사용자 확정, 2026-08-07):
- 추출을 3회 반복 실행 (gpt-5.4-mini)
- 각 추출 결과마다 분류를 1회씩 실행 (gemini-3.5-flash-lite) -> 3개 type 라벨
- 3개 type 라벨을 다수결로 최종 rule_type 결정
- confidence/rationale 등 단일값 필드는 다수결과 일치하는 첫 분류 실행의 값을 대표로 사용
"""
import json
import re
from collections import Counter
from pathlib import Path

from llm_client import chat_completion
from prompts import load_phase1_extraction, load_phase1_classification
from qa_parser import parse_qa_response

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "phase1_rules"


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def run_phase1_category(category_id: str, category_name: str,
                         eval_model_id: str, judge_model_id: str,
                         max_tokens_extraction: int, max_tokens_classification: int,
                         temperature: float = 0.0) -> dict:
    sys_ext, user_ext = load_phase1_extraction(category_name)

    extraction_runs = []
    for i in range(3):
        resp = chat_completion(eval_model_id, sys_ext, user_ext, max_tokens_extraction, temperature)
        extraction_runs.append({
            "run_id": i,
            "content": resp["content"],
            "finish_reason": resp["finish_reason"],
        })

    classification_runs = []
    for run in extraction_runs:
        sys_cls, user_cls = load_phase1_classification(category_name, run["content"])
        resp = chat_completion(judge_model_id, sys_cls, user_cls, max_tokens_classification, temperature)
        try:
            parsed = _extract_json(resp["content"])
            parse_ok = True
        except (json.JSONDecodeError, AttributeError):
            parsed = {"type": "OPAQUE", "confidence": None, "conditions_for_compliance": [],
                      "framing_changes": [], "predicate": None, "rationale": "JSON parse failed"}
            parse_ok = False
        classification_runs.append({
            "run_id": run["run_id"],
            "parsed": parsed,
            "raw": resp["content"],
            "finish_reason": resp["finish_reason"],
            "parse_ok": parse_ok,
        })

    types = [c["parsed"].get("type", "OPAQUE") for c in classification_runs]
    majority_type = Counter(types).most_common(1)[0][0]
    representative = next(c for c in classification_runs if c["parsed"].get("type") == majority_type)
    representative_extraction = extraction_runs[representative["run_id"]]

    qa_fields = parse_qa_response(representative_extraction["content"])

    result = {
        "model": eval_model_id,
        "category_id": category_id,
        "category_name": category_name,
        "q1_default": qa_fields["q1_default"],
        "q2_refusal_conditions": qa_fields["q2_refusal_conditions"],
        "q3_compliance_conditions": qa_fields["q3_compliance_conditions"],
        "q4_framing_sensitivity": qa_fields["q4_framing_sensitivity"],
        "q5_policy_statement": qa_fields["q5_policy_statement"],
        "rule_type": majority_type,
        "confidence": representative["parsed"].get("confidence"),
        "rationale": representative["parsed"].get("rationale"),
        "extraction_run_ids": [r["run_id"] for r in extraction_runs],
        "_debug_qa_parse_status": qa_fields.get("_parse_status"),
        "_debug_type_votes": dict(Counter(types)),
        "_debug_extraction_runs": extraction_runs,
        "_debug_classification_runs": classification_runs,
        "_debug_judge_model": judge_model_id,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{eval_model_id}_{category_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
