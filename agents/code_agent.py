from pathlib import Path

from core.unity_scanner import find_relevant_files
from core.file_preview import read_preview
from core.unity_log_reader import read_unity_log, read_filtered_unity_log
from core.project_search import search_project_code
from core.search_formatter import format_search_results
from core.unity_asset_search import search_unity_assets
from core.asset_search_formatter import format_asset_search
from core.unity_hierarchy_inspector import inspect_scene_context
from core.hierarchy_formatter import format_hierarchy_results
from core.proposal_store import add_proposal
from core.diff_preview import build_diff_preview
from core.llm_client import is_llm_available, generate_patch_proposal
from core.scene_context_helper import get_scene_context_for_task
from core.proposal_validator import validate_patch_for_file


def extract_keywords(title: str):
    words = title.lower().split()

    ignore = {
        "the",
        "a",
        "fix",
        "add",
        "update",
        "bug",
        "investigate",
        "when",
        "find",
        "who",
        "calls",
        "search",
        "for",
        "where",
        "used",
        "is",
        "appears",
    }

    return [w for w in words if w not in ignore]


def _contains_strong_log_signal(log_text: str) -> bool:
    lower_log = log_text.lower()
    strong_signals = [
        "nullreferenceexception",
        "missingreferenceexception",
        "argumentnullexception",
        "indexoutofrangeexception",
        "exception",
        "error",
    ]
    return any(signal in lower_log for signal in strong_signals)


def _task_explicitly_requests_patch(lower_title: str) -> bool:
    return (
        "results" in lower_title
        or "null reference" in lower_title
        or "nullreference" in lower_title
        or "hide gameplay ui" in lower_title
    )


def _gather_patch_evidence(task: dict, best_file: str, file_content: str, filtered_log: str) -> tuple[bool, list[str]]:
    lower_title = task["title"].lower()
    reasons = []

    if _task_explicitly_requests_patch(lower_title):
        reasons.append("task title matches patchable issue pattern")

    if _contains_strong_log_signal(filtered_log):
        reasons.append("unity log contains strong error signal")

    if "persistentinvasives" in lower_title and "PersistentInvasives" in file_content:
        reasons.append("task mentions PersistentInvasives and symbol exists in target file")

    if "resultspanel" in lower_title and "ResultsPanel" in file_content:
        reasons.append("task mentions ResultsPanel and symbol exists in target file")

    if "scoresummarytext" in lower_title and "ScoreSummaryText" in file_content:
        reasons.append("task mentions ScoreSummaryText and symbol exists in target file")

    return (len(reasons) > 0, reasons)


def _proposal_matches_evidence(new_content: str, original_content: str, task_title: str) -> tuple[bool, str]:
    lower_title = task_title.lower()

    # If the patch introduces a PersistentInvasives null guard, require that
    # the task or original file gave us evidence this symbol is relevant.
    if "PersistentInvasives" in new_content and "PersistentInvasives" not in original_content:
        return False, "Patch introduced PersistentInvasives even though the original file did not contain that symbol."

    if "PersistentInvasives" in new_content and "persistentinvasives" not in lower_title and "PersistentInvasives" not in original_content:
        return False, "Patch appears to address PersistentInvasives without task or file evidence."

    return True, ""


def handle_patch_proposal(task: dict, project_config: dict):
    lower_title = task["title"].lower()
    keywords = extract_keywords(task["title"])
    files = find_relevant_files(project_config, keywords)

    if not files:
        return None

    best_file = files[0]
    best_preview = read_preview(best_file, max_lines=220)
    original_content = Path(best_file).read_text(encoding="utf-8")

    filtered_log = read_filtered_unity_log(
        keywords=[
            "ResultsUI",
            "Error",
            "Exception",
            "NullReference",
            "ShowResults",
            "Hide",
            "ScoreSummaryText",
            "ResultsPanel",
        ]
    )

    scene_context = get_scene_context_for_task(project_config, task["title"])

    should_patch, evidence_reasons = _gather_patch_evidence(
        task=task,
        best_file=best_file,
        file_content=original_content,
        filtered_log=filtered_log,
    )

    if not should_patch:
        return None

    if not is_llm_available():
        return {
            "changed_files": [],
            "summary": (
                "LLM proposal requested, but OPENAI_API_KEY is not configured.\n\n"
                f"Target file:\n{best_file}\n\n"
                f"Top file preview:\n{best_preview[:3000]}"
            ),
        }

    try:
        proposal_data = generate_patch_proposal(
            task_title=task["title"],
            file_path=best_file,
            file_content=original_content,
            filtered_log=filtered_log[:3000],
            scene_context=scene_context[:3000],
        )

    except Exception as e:
        return {
            "changed_files": [],
            "summary": (
                f"LLM proposal generation failed: {e}\n\n"
                f"Target file:\n{best_file}\n\n"
                f"Top file preview:\n{best_preview[:3000]}"
            ),
        }

    new_content = proposal_data.get("new_content", "").strip()
    diagnosis = proposal_data.get("diagnosis", "No diagnosis provided.")
    summary = proposal_data.get("summary", "No summary provided.")

    if not new_content:
        return {
            "changed_files": [],
            "summary": (
                f"LLM returned no file content.\nDiagnosis: {diagnosis}\nSummary: {summary}"
            ),
        }

    diagnosis_lower = diagnosis.lower()
    speculative_phrases = [
        "usually happens",
        "more likely",
        "likely",
        "in some cases",
        "appears to be",
        "might be",
        "may be",
    ]

    if any(phrase in diagnosis_lower for phrase in speculative_phrases) and not _contains_strong_log_signal(filtered_log):
        return {
            "changed_files": [],
            "summary": (
                "Patch rejected before proposal creation because the diagnosis was too speculative "
                "and no strong Unity log error signal was found.\n\n"
                f"Target file: {best_file}\n"
                f"Diagnosis: {diagnosis}\n\n"
                "Evidence found:\n"
                + "\n".join(f"- {reason}" for reason in evidence_reasons)
            ),
        }

    evidence_match, evidence_error = _proposal_matches_evidence(
        new_content=new_content,
        original_content=original_content,
        task_title=task["title"],
    )

    if not evidence_match:
        return {
            "changed_files": [],
            "summary": (
                "Patch rejected before proposal creation because it did not match the gathered evidence.\n\n"
                f"Target file: {best_file}\n"
                f"Reason: {evidence_error}\n\n"
                "Evidence found:\n"
                + "\n".join(f"- {reason}" for reason in evidence_reasons)
            ),
        }

    validation = validate_patch_for_file(
        file_path=best_file,
        original_text=original_content,
        proposed_text=new_content,
    )

    if not validation.is_valid:
        return {
            "changed_files": [],
            "summary": (
                "Patch rejected by validator.\n\n"
                f"Target file: {best_file}\n\n"
                "Errors:\n"
                + "\n".join(f"- {e}" for e in validation.errors)
            ),
        }

    proposal = add_proposal(
        task_id=task["id"],
        project_id=task["project_id"],
        file_path=best_file,
        new_content=new_content,
        summary=summary,
        validation={
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "evidence_reasons": evidence_reasons,
        },
    )

    diff_text = build_diff_preview(best_file, new_content)

    warnings_text = ""
    if validation.warnings:
        warnings_text = "\nWarnings:\n" + "\n".join(f"- {w}" for w in validation.warnings)

    evidence_text = ""
    if evidence_reasons:
        evidence_text = "\nEvidence:\n" + "\n".join(f"- {reason}" for reason in evidence_reasons)

    return {
        "changed_files": [],
        "summary": (
            f"Patch proposed.\n"
            f"Proposal ID: {proposal['id']}\n"
            f"Task ID: {task['id']}\n"
            f"Target file: {best_file}\n"
            f"Diagnosis: {diagnosis}\n"
            f"Summary: {summary}"
            f"{evidence_text}"
            f"{warnings_text}\n\n"
            f"Diff preview:\n```diff\n{diff_text}\n```\n\n"
            f"Use /approve {proposal['id']} to apply.\n"
            f"Use /reject {proposal['id']} to discard."
        ),
    }


def handle_reference_search(task: dict, project_config: dict):
    lower_title = task["title"].lower()

    if "find who calls showresults" in lower_title or "find who calls show results" in lower_title:
        pattern = "ShowResults("
        results = search_project_code(project_config, pattern)
        return {
            "changed_files": [],
            "summary": format_search_results(f"Project-wide references for {pattern}", results),
        }

    if "find who calls hide" in lower_title:
        pattern = "Hide("
        results = search_project_code(project_config, pattern)
        return {
            "changed_files": [],
            "summary": format_search_results(f"Project-wide references for {pattern}", results),
        }

    if "find where setactive(false) is used" in lower_title or "find where setactive(false) is referenced" in lower_title:
        pattern = "SetActive(false)"
        results = search_project_code(project_config, pattern)
        return {
            "changed_files": [],
            "summary": format_search_results(f"Project-wide references for {pattern}", results),
        }

    if "find where resultspanel is referenced" in lower_title or "find resultspanel references" in lower_title:
        pattern = "ResultsPanel"
        results = search_project_code(project_config, pattern)
        return {
            "changed_files": [],
            "summary": format_search_results(f"Project-wide references for {pattern}", results),
        }

    return None


def handle_asset_search(task: dict, project_config: dict):
    title = task["title"].lower()

    if "find" in title or "search" in title:
        words = title.split()
        target = None

        for w in words:
            if w.endswith("panel") or w.endswith("button") or w.endswith("ui"):
                target = w
                break

        if target is None:
            return None

        results = search_unity_assets(project_config, target)

        return {
            "changed_files": [],
            "summary": format_asset_search(
                f"Unity scene/prefab references for '{target}'",
                results,
            ),
        }

    return None


def handle_hierarchy_inspection(task: dict, project_config: dict):
    title = task["title"].lower()

    if "inspect ui cluster for" in title:
        target = task["title"].split("for", 1)[1].strip()
        results = inspect_scene_context(project_config, target)
        return {
            "changed_files": [],
            "summary": format_hierarchy_results(
                f"Scene context for '{target}'",
                results,
            ),
        }

    if "inspect scene context for" in title:
        target = task["title"].split("for", 1)[1].strip()
        results = inspect_scene_context(project_config, target)
        return {
            "changed_files": [],
            "summary": format_hierarchy_results(
                f"Scene context for '{target}'",
                results,
            ),
        }

    return None


def handle_task(task: dict, project_config: dict):
    patch_result = handle_patch_proposal(task, project_config)
    if patch_result is not None:
        return patch_result

    reference_result = handle_reference_search(task, project_config)
    if reference_result is not None:
        return reference_result

    asset_result = handle_asset_search(task, project_config)
    if asset_result is not None:
        return asset_result

    hierarchy_result = handle_hierarchy_inspection(task, project_config)
    if hierarchy_result is not None:
        return hierarchy_result

    keywords = extract_keywords(task["title"])
    files = find_relevant_files(project_config, keywords)

    filtered_log = read_filtered_unity_log(
        keywords=["ResultsUI", "Error", "Exception", "NullReference", "ShowResults", "Hide"]
    )
    full_log = read_unity_log(200)

    if not files:
        return {
            "changed_files": [],
            "summary": (
                "No likely Unity scripts found.\n\n"
                f"Recent filtered Unity log:\n{filtered_log[:4000]}"
            ),
        }

    best_file = files[0]
    best_preview = read_preview(best_file, max_lines=140)

    return {
        "changed_files": [],
        "summary": (
            f"Top candidate file:\n{best_file}\n\n"
            f"Top file preview:\n{best_preview[:3000]}\n\n"
            f"Recent filtered Unity log:\n{filtered_log[:3000]}\n\n"
            f"Recent raw Unity log:\n{full_log[:2000]}"
        ),
    }