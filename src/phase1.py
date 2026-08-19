"""Phase 1: 정책 추출(피평가 모델) + 유형 분류(심판 모델).
원 논문 방식 (2026-08-13 수정):
- 추출을 3회 반복 실행 (gpt-5.4-mini)
- 3회 중 "가장 긴 non-error 응답" 1개만 대표로 선택
- 그 대표 응답 1개만 분류 실행 (gemini-3.5-flash-lite) -> rule_type 확정.
"""
import json
import re
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


def _select_representative(extraction_runs: list[dict]) -> dict:
    """논문 방식: 3회 추출 중 '가장 긴 non-error 응답'을 대표로 선택한다.

    non-error 판정: 응답이 비어있지 않고, 토큰 한도에 걸려 잘리지도(finish_reason
    == "length") 않은 것. API 오류는 llm_client가 재시도 후 예외를 던지므로 여기까지
    오지 않는다.

    3회 전부 잘렸거나 비어있는 극단적인 경우엔 조건을 순서대로 완화해서 최소한
    하나는 반환한다 (분류 자체가 불가능해지는 것을 막기 위함).
    """
    candidates = [r for r in extraction_runs
                  if r["content"].strip() and r["finish_reason"] != "length"]
    if not candidates:
        candidates = [r for r in extraction_runs if r["content"].strip()]
    if not candidates:
        candidates = extraction_runs
    return max(candidates, key=lambda r: len(r["content"]))


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
            # 제공자 필터에 막히면 content가 빈 문자열이라 _select_representative가
            # 자동으로 제외한다("가장 긴 non-error 응답"). 기록만 남긴다.
            "provider_filter_blocked": resp.get("provider_filter_blocked", False),
        })

    representative_extraction = _select_representative(extraction_runs)

    sys_cls, user_cls = load_phase1_classification(category_name, representative_extraction["content"])
    resp = chat_completion(judge_model_id, sys_cls, user_cls, max_tokens_classification, temperature)
    try:
        parsed = _extract_json(resp["content"])
        parse_ok = True
    except (json.JSONDecodeError, AttributeError):
        parsed = {"type": "OPAQUE", "confidence": None, "conditions_for_compliance": [],
                  "framing_changes": [], "predicate": None, "rationale": "JSON parse failed"}
        parse_ok = False
    classification = {
        "run_id": representative_extraction["run_id"],
        "parsed": parsed,
        "raw": resp["content"],
        "finish_reason": resp["finish_reason"],
        "parse_ok": parse_ok,
    }

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
        "rule_type": parsed.get("type", "OPAQUE"),
        "confidence": parsed.get("confidence"),
        "rationale": parsed.get("rationale"),
        "extraction_run_ids": [r["run_id"] for r in extraction_runs],
        "_debug_qa_parse_status": qa_fields.get("_parse_status"),
        "_debug_representative_run_id": representative_extraction["run_id"],
        "_debug_extraction_lengths": [len(r["content"]) for r in extraction_runs],
        "_debug_extraction_runs": extraction_runs,
        "_debug_classification": classification,
        "_debug_judge_model": judge_model_id,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{eval_model_id}_{category_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
