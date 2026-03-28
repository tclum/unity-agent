import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _extract_class_names(text: str) -> List[str]:
    pattern = r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b"
    return re.findall(pattern, text)


def _contains_method(text: str, method_name: str) -> bool:
    pattern = rf"\b{re.escape(method_name)}\s*\("
    return re.search(pattern, text) is not None


def _contains_field(text: str, field_name: str) -> bool:
    pattern = rf"\b{re.escape(field_name)}\b"
    return re.search(pattern, text) is not None


def _is_balanced(text: str, open_char: str, close_char: str) -> bool:
    depth = 0
    for ch in text:
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _check_setactive_before_null_guard(text: str) -> bool:
    setactive_match = re.search(r"ResultsPanel\.SetActive\(true\)", text)
    null_guard_match = re.search(r"players\s*==\s*null\s*\|\|", text)
    if setactive_match and null_guard_match:
        return setactive_match.start() < null_guard_match.start()
    return False


def _check_public_methods_indented(text: str) -> List[str]:
    unindented = []
    pattern = re.compile(
        r"^(public|private|protected|internal)\s+(?!class\s)(?!static\s+class\s)",
        re.MULTILINE
    )
    for match in pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        col = match.start() - line_start
        if col == 0:
            snippet = text[match.start():match.start() + 80].split("\n")[0]
            unindented.append(snippet.strip()[:60])
    return unindented


def _check_scoring_purity(text: str) -> bool:
    """
    Returns True (invalid) if CalculateRoundScore modifies TotalScore.
    CalculateRoundScore must be a pure calculation — it returns an int
    and must not have side effects on player.TotalScore.
    GameManager.ApplyEndOfRoundScores already applies the returned value.
    """
    pattern = re.compile(r"int\s+CalculateRoundScore\s*\(.*?\{", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return False

    # Find the method body
    body_start = text.find("{", match.start())
    if body_start == -1:
        return False

    depth = 0
    for i, ch in enumerate(text[body_start:], start=body_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = text[body_start:i + 1]
                return "TotalScore" in body

    return False


def _check_totalscore_assignment(text: str) -> bool:
    """
    Returns True (invalid) if TotalScore is directly assigned (=)
    outside the PlayerState constructor.
    Uses brace depth to find the enclosing method and checks its signature.
    """
    for match in re.finditer(r"TotalScore\s*=", text):
        eq_pos = text.index("=", match.start() + len("TotalScore"))
        before_eq = text[:eq_pos].rstrip()
        # Skip +=  -=  ==  !=
        if before_eq[-1] in ("+", "-", "=", "!"):
            continue

        # Walk backwards to find the opening { of the enclosing method
        pos = match.start()
        depth = 0
        method_start = -1
        for i in range(pos, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                if depth == 0:
                    method_start = i
                    break
                depth -= 1

        if method_start == -1:
            return True

        # Get the method signature (text before the opening brace)
        sig_start = max(0, method_start - 200)
        signature = text[sig_start:method_start]

        # Allow if this is the constructor
        if re.search(r"PlayerState\s*\(", signature):
            continue

        return True

    return False


def _check_coroutine_yield(text: str, method_name: str) -> bool:
    if not match:
        return False
    body_start = text.find("{", match.start())
    if body_start == -1:
        return False
    depth = 0
    for i, ch in enumerate(text[body_start:], start=body_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = text[body_start:i + 1]
                return "yield" not in body
    return False


def get_validation_profile(file_path: str) -> dict:
    normalized = file_path.replace("\\", "/")

    if normalized.endswith("ResultsUI.cs"):
        return {
            "required_methods": ["Awake", "ShowResults", "Hide", "PlayAgain", "ReturnToMainMenu"],
            "required_fields": ["ResultsPanel", "TitleText", "ScoreSummaryText", "PlayAgainButton", "MainMenuButton"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": True,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("HumanTurnUI.cs"):
        return {
            "required_methods": ["HandleTurn", "SetupHand", "SelectCard", "ConfirmSelection",
                                  "HideHandUI", "ClearHandUI", "IsSelectionConfirmed", "GetConfirmedSelection"],
            "required_fields": ["HandPanel", "CardButtonPrefab", "SelectedCardText", "ConfirmButton", "LogText"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": ["HandleTurn"],
        }

    if normalized.endswith("RevealUI.cs"):
        return {
            "required_methods": ["Initialize", "ShowReveal", "ClearReveal"],
            "required_fields": ["RevealPanel", "PlayerAreas", "CardButtonPrefab"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": ["ShowReveal"],
        }

    if normalized.endswith("FieldUI.cs"):
        return {
            "required_methods": ["Initialize", "ResetFieldUI", "AddPlantedCards"],
            "required_fields": ["PlayerAreas", "CardButtonPrefab"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("TurnTransitionUI.cs"):
        return {
            "required_methods": ["ShowMessage", "IsContinuePressed", "HideImmediate"],
            "required_fields": ["Panel", "MessageText", "ContinueButton"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("PauseMenuUI.cs"):
        return {
            "required_methods": ["TogglePause", "Show", "Hide", "IsPaused", "ContinueGame", "ReturnToMainMenu"],
            "required_fields": ["PausePanel"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("GameManager.cs"):
        return {
            "required_methods": ["Start", "Update", "CreatePlayers", "GameLoop",
                                  "ApplyEndOfRoundScores", "ShouldShowLocalHandoff"],
            "required_fields": ["RoundManager", "HumanTurnUI", "RevealUI", "FieldUI",
                                 "ResultsUI", "PauseMenuUI", "TurnTransitionUI", "Players"],
            "max_size_change_ratio": 0.50,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": ["GameLoop", "ShowTransitionMessage", "WaitWhilePaused"],
        }

    if normalized.endswith("RoundManager.cs"):
        return {
            "required_methods": ["SetupRound", "IsRoundOver", "HandleAITurns",
                                  "RevealAndResolve", "RotateHandsLeft"],
            "required_fields": ["AllCards"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("PlayerState.cs"):
        return {
            "required_methods": ["ResetRoundData"],
            "required_fields": ["PlayerId", "PlayerName", "IsHuman", "TotalScore",
                                 "Hand", "PlantedThisRound", "PersistentInvasives"],
            "max_size_change_ratio": 0.50,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
            "check_totalscore_assignment": True,
        }

    if normalized.endswith("CardEffectResolver.cs"):
        return {
            "required_methods": ["ApplyEffects"],
            "required_fields": [],
            "max_size_change_ratio": 0.70,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("ScoringSystem.cs"):
        return {
            "required_methods": ["CalculateRoundScore", "ApplyFinalInvasivePenalty"],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
            "check_scoring_purity": True,
        }

    if normalized.endswith("GameSettings.cs"):
        return {
            "required_methods": [],
            "required_fields": ["SoloMode", "SelectedPlayerCount"],
            "max_size_change_ratio": 0.60,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("AlPlayerController.cs"):
        return {
            "required_methods": ["ChooseCardsToPlant"],
            "required_fields": [],
            "max_size_change_ratio": 0.70,
            "check_setactive_order": False,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("CardData.cs"):
        return {
            "required_methods": [],
            "required_fields": ["CardName", "CardType", "BasePoints", "EffectType"],
            "max_size_change_ratio": 0.50,
            "check_setactive_order": False,
            "check_indentation": False,
            "protected_coroutines": [],
        }

    return {
        "required_methods": [],
        "required_fields": [],
        "max_size_change_ratio": 0.80,
        "check_setactive_order": False,
        "check_indentation": False,
        "protected_coroutines": [],
    }


def validate_patch(
    original_text: str,
    proposed_text: str,
    required_methods: Optional[List[str]] = None,
    required_fields: Optional[List[str]] = None,
    max_size_change_ratio: float = 0.80,
    check_setactive_order: bool = False,
    check_indentation: bool = False,
    protected_coroutines: Optional[List[str]] = None,
    check_scoring_purity: bool = False,
    check_totalscore_assignment: bool = False,
) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    required_methods = required_methods or []
    required_fields = required_fields or []
    protected_coroutines = protected_coroutines or []
    original_text = original_text or ""
    proposed_text = proposed_text or ""

    if not proposed_text.strip():
        return ValidationResult(is_valid=False, errors=["Proposed file is empty."])

    if proposed_text.strip() == original_text.strip():
        warnings.append("Proposed patch is identical to the original file.")

    for class_name in _extract_class_names(original_text):
        if class_name not in _extract_class_names(proposed_text):
            errors.append(f"Missing class definition: {class_name}")

    for method_name in required_methods:
        if not _contains_method(proposed_text, method_name):
            errors.append(f"Missing required method: {method_name}()")

    for field_name in required_fields:
        if not _contains_field(proposed_text, field_name):
            errors.append(f"Missing required field/reference: {field_name}")

    if not _is_balanced(proposed_text, "{", "}"):
        errors.append("Unbalanced curly braces detected.")
    if not _is_balanced(proposed_text, "(", ")"):
        errors.append("Unbalanced parentheses detected.")
    if not _is_balanced(proposed_text, "[", "]"):
        warnings.append("Unbalanced square brackets detected.")

    if "MonoBehaviour" in original_text and "MonoBehaviour" not in proposed_text:
        errors.append("MonoBehaviour inheritance appears to have been removed.")

    for using in ["using UnityEngine;", "using TMPro;", "using UnityEngine.UI;",
                  "using System.Collections;", "using System.Collections.Generic;"]:
        if using in original_text and using not in proposed_text:
            warnings.append(f"{using} was removed.")

    for coroutine in protected_coroutines:
        if _check_coroutine_yield(proposed_text, coroutine):
            errors.append(
                f"Coroutine {coroutine}() appears to have lost its yield statements — "
                f"this would break the coroutine execution flow."
            )

    if check_scoring_purity and _check_scoring_purity(proposed_text):
        errors.append(
            "CalculateRoundScore() must be a pure function — it must not modify player.TotalScore. "
            "GameManager.ApplyEndOfRoundScores already applies the returned score; "
            "adding it inside CalculateRoundScore causes doubled scores."
        )

    if check_totalscore_assignment and _check_totalscore_assignment(proposed_text):
        errors.append(
            "TotalScore must not be directly assigned (=) outside the constructor. "
            "Use += or -= to accumulate scores across rounds. "
            "Direct assignment wipes all previously accumulated score."
        )

    if check_setactive_order and _check_setactive_before_null_guard(proposed_text):
        errors.append(
            "ResultsPanel.SetActive(true) must not appear before the players null/empty check. "
            "Activating the panel before validation causes a blank results screen when called with no players."
        )

    if check_indentation:
        unindented = _check_public_methods_indented(proposed_text)
        if unindented:
            errors.append(
                "Unindented method(s) detected (must be indented inside class body): "
                + "; ".join(unindented)
            )

    original_len = len(original_text.strip())
    proposed_len = len(proposed_text.strip())
    if original_len > 0:
        size_change_ratio = abs(proposed_len - original_len) / original_len
        if size_change_ratio > max_size_change_ratio:
            warnings.append(f"Large file size change detected: {size_change_ratio:.2%}")

    original_lines = _line_count(original_text)
    proposed_lines = _line_count(proposed_text)
    if original_lines > 0:
        line_change_ratio = abs(proposed_lines - original_lines) / original_lines
        if line_change_ratio > max_size_change_ratio:
            warnings.append(f"Large line count change detected: {line_change_ratio:.2%}")

    return ValidationResult(is_valid=(len(errors) == 0), errors=errors, warnings=warnings)


def validate_patch_for_file(
    file_path: str, original_text: str, proposed_text: str
) -> ValidationResult:
    profile = get_validation_profile(file_path)
    return validate_patch(
        original_text=original_text,
        proposed_text=proposed_text,
        required_methods=profile.get("required_methods", []),
        required_fields=profile.get("required_fields", []),
        max_size_change_ratio=profile.get("max_size_change_ratio", 0.80),
        check_setactive_order=profile.get("check_setactive_order", False),
        check_indentation=profile.get("check_indentation", False),
        protected_coroutines=profile.get("protected_coroutines", []),
        check_scoring_purity=profile.get("check_scoring_purity", False),
        check_totalscore_assignment=profile.get("check_totalscore_assignment", False),
    )
