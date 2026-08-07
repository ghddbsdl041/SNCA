"""피평가 모델의 Q1~Q5 자유 서술 응답을 스키마 필드로 최대한 분리한다.
모델이 정확히 'Q1. ...' 형식으로 응답한다는 보장이 없으므로 best-effort 파싱이며,
실패 시 원문 전체를 q1_default에 보존해 정보 손실을 막는다.
"""
import re

_Q_PATTERN = re.compile(r"Q([1-5])[\.:\)]?\s*[A-Z ]*[:\-]?\s*", re.IGNORECASE)


def parse_qa_response(text: str) -> dict:
    matches = list(_Q_PATTERN.finditer(text))
    fields = {
        "q1_default": "",
        "q2_refusal_conditions": "",
        "q3_compliance_conditions": "",
        "q4_framing_sensitivity": "",
        "q5_policy_statement": "",
    }
    key_by_num = {
        "1": "q1_default",
        "2": "q2_refusal_conditions",
        "3": "q3_compliance_conditions",
        "4": "q4_framing_sensitivity",
        "5": "q5_policy_statement",
    }

    if not matches:
        fields["q1_default"] = text.strip()
        fields["_parse_status"] = "failed_no_markers"
        return fields

    for i, m in enumerate(matches):
        num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        key = key_by_num.get(num)
        if key:
            fields[key] = text[start:end].strip()

    fields["_parse_status"] = "ok" if len(matches) == 5 else f"partial_{len(matches)}_of_5"
    return fields
