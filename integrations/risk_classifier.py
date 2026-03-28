from dataclasses import dataclass


@dataclass
class RiskResult:
    level: str          # "low" | "high"
    reasons: list[str]


# Methods that are high-risk to add, remove, or rename
_HIGH_RISK_METHODS = {
    "Start", "OnEnable", "OnDisable", "OnDestroy",
    "Update", "FixedUpdate", "LateUpdate",
}

# Patterns that suggest structural rewrites
_HIGH_RISK_PATTERNS = [
    "MonoBehaviour",
    ": MonoBehaviour",
    "SceneManager.LoadScene",
    "Destroy(",
    "Instantiate(",
    "GetComponent<",
    "AddComponent<",
    "Resources.Load",
    "PlayerPrefs",
]


def classify_risk(
    original_text: str,
    proposed_text: str,
    file_path: str = "",
) -> RiskResult:
    reasons = []

    original_lines = len(original_text.strip().splitlines())
    proposed_lines = len(proposed_text.strip().splitlines())

    if original_lines > 0:
        change_ratio = abs(proposed_lines - original_lines) / original_lines
        if change_ratio > 0.40:
            reasons.append(
                f"Large change: {change_ratio:.0%} of lines modified"
            )

    if "MonoBehaviour" in original_text and "MonoBehaviour" not in proposed_text:
        reasons.append("MonoBehaviour inheritance removed")

    original_classes = _find_class_names(original_text)
    proposed_classes = _find_class_names(proposed_text)
    for cls in original_classes:
        if cls not in proposed_classes:
            reasons.append(f"Class removed or renamed: {cls}")

    for method in _HIGH_RISK_METHODS:
        was_present = f"{method}(" in original_text
        now_present = f"{method}(" in proposed_text
        if was_present and not now_present:
            reasons.append(f"Unity lifecycle method removed: {method}()")

    for pattern in _HIGH_RISK_PATTERNS:
        was_present = pattern in original_text
        now_present = pattern in proposed_text
        if was_present and not now_present:
            reasons.append(f"Significant pattern removed: {pattern}")

    using_original = set(_find_usings(original_text))
    using_proposed = set(_find_usings(proposed_text))
    removed_usings = using_original - using_proposed
    if removed_usings:
        reasons.append(f"Using directives removed: {', '.join(removed_usings)}")

    level = "high" if reasons else "low"
    return RiskResult(level=level, reasons=reasons)


def _find_class_names(text: str) -> list[str]:
    import re
    return re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)


def _find_usings(text: str) -> list[str]:
    import re
    return re.findall(r"^using\s+([\w.]+);", text, re.MULTILINE)
