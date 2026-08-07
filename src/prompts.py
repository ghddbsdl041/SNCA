"""SPEC.md 5/6/7/8번 항목의 프롬프트 원문을 그대로 로드/치환한다.
프롬프트 원문 자체는 수정하지 않는다 (CLAUDE.md 절대 규칙).
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _split_system_user(text: str) -> tuple[str, str]:
    """'System: ...\\n\\nUser: ...' 형식의 원문을 (system, user)로 분리."""
    idx = text.index("User:")
    system_part = text[:idx].split("System:", 1)[1].strip()
    user_part = text[idx + len("User:"):].strip()
    return system_part, user_part


def load_phase1_extraction(category_name: str) -> tuple[str, str]:
    text = (PROMPTS_DIR / "phase1_extraction.txt").read_text(encoding="utf-8")
    system, user = _split_system_user(text)
    user = user.replace("{CATEGORY}", category_name)
    return system, user


def load_phase1_classification(category_name: str, qa_text: str) -> tuple[str, str]:
    text = (PROMPTS_DIR / "phase1_classification.txt").read_text(encoding="utf-8")
    system, user = _split_system_user(text)
    user = user.replace("{CATEGORY}", category_name)
    user = user.replace("[Q1-Q5 responses inserted here]", qa_text)
    return system, user


def load_phase2_system() -> str:
    return (PROMPTS_DIR / "phase2_system.txt").read_text(encoding="utf-8").strip()


def load_phase2_judge(prompt: str, response: str) -> str:
    text = (PROMPTS_DIR / "phase2_judge.txt").read_text(encoding="utf-8")
    text = text.replace("{prompt}", prompt).replace("{response}", response)
    return text.strip()
