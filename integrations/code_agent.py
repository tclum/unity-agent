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
from core.risk_classifier import classify_risk
from core.proposal_applier import apply_proposal_file
from integrations.git_manager import git_commit_files
from integrations.discord_notifier import notify_discord

MAX_RETRIES = 3


def extract_keywords(title: str):
    words = title.lower().split()

    ignore = {
        "the", "a", "fix", "add", "update", "bug", "investigate", "when",
        "find", "who", "calls", "search", "for", "where", "used", "is",
        "appears", "auto:",
    }

    return [w for w in words if w not in ignore]


def _contains_strong_log_signal(log_text: str) -> bool:
    lower_log = log_text.lower()
    strong_signals = [
        "nullreferenceexception", "missingreferenceexception",
        "argumentnullexception", "indexoutofrangeexception",
        "exception", "error",
    ]
    return any(signal in lower_log for signal in strong_signals)


def _task_explicitly_requests_patch(lower_title: str) -> bool:
    return (
        "results" in lower_title
        or "null reference" in lower_title
        or "nullreference" in lower_title
        or "hide gameplay ui" in lower_title
        or "auto:" in lower_title
    )


def _gather_patch_evidence(task, best_file, file_content, filtered_log):
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


def _proposal_matches_evidence(new_content, original_content, task_title):
    lower_title = task_title.lower()

    if "PersistentInvasives" in new_content and "PersistentInvasives" not in original_content:
        return False, "Patch introduced PersistentInvasives even though the original file did not contain that symbol."

    if "PersistentInvasives" in new_content and "persistentinvasives" not in lower_title and "PersistentInvasives" not in original_content:
        return False, "Patch appears to address PersistentInvasives without task or file evidence."

    return True, ""


def _attempt_patch(task, best_file, original_content, filtered_log, scene_context, attempt):
    try:
        proposal_data = generate_patch_proposal(
            task_title=task["title"],
            file_path=best_file,
            file_content=original_content,
            filtered_log=filtered_log[:3000],
            scene_context=scene_context[:3000],
            attempt=attempt,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

    new_content = proposal_data.get("new_content", "").strip()
    diagnosis = proposal_data.get("diagnosis", "No diagnosis provided.")
    summary = proposal_data.get("summary", "No summary provided.")

    if not new_content:
        return {"status": "empty", "message": f"LLM returned no file content. Diagnosis: {diagnosis}"}

    diagnosis_lower = diagnosis.lower()
    speculative_phrases = [
        "usually happens", "more likely", "likely", "in some cases",
        "appears to be", "might be", "may be",
    ]

    if any(phrase in diagnosis_lower for phrase in speculative_phrases) and not _contains_strong_log_signal(filtered_log):
        return {"status": "speculative", "diagnosis": diagnosis}

    evidence_match, evidence_error = _proposal_matches_evidence(new_content, original_content, task["title"])
    if not evidence_match:
        return {"status": "evidence_mismatch", "message": evidence_error}

    validation = validate_patch_for_file(
        file_path=best_file,
        original_text=original_content,
        proposed_text=new_content,
    )

    if not validation.is_valid:
        return {
            "status": "invalid",
            "errors": validation.errors,
            "new_content": new_content,
            "diagnosis": diagnosis,
            "summary": summary,
        }

    return {
        "status": "ok",
        "new_content": new_content,
        "diagnosis": diagnosis,
        "summary": summary,
        "validation": validation,
    }


def handle_patch_proposal(task, project_config):
    keywords = extract_keywords(task["title"])
    files = find_relevant_files(project_config, keywords)

    if not files:
        return None

    best_file = files[0]
    best_preview = read_preview(best_file, max_lines=220)
    original_content = Path(best_file).read_text(encoding="utf-8")

    filtered_log = read_filtered_unity_log(
        keywords=[
            "ResultsUI", "Error", "Exception", "NullReference",
            "ShowResults", "Hide", "ScoreSummaryText", "ResultsPanel",
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
                f"Target file:\n{best_file}\n\nTop file preview:\n{best_preview[:3000]}"
            ),
        }

    # --- Retry loop ---
    last_result = None

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[CodeAgent] Patch attempt {attempt}/{MAX_RETRIES} for task #{task['id']}")
        result = _attempt_patch(task, best_file, original_content, filtered_log, scene_context, attempt)
        last_result = result

        if result["status"] == "ok":
            break

        if result["status"] == "speculative" and attempt == MAX_RETRIES:
            return {
                "changed_files": [],
                "summary": (
                    "Patch rejected after max retries — diagnosis remained too speculative.\n\n"
                    f"Target file: {best_file}\nDiagnosis: {result.get('diagnosis', '')}\n\n"
                    "Evidence found:\n" + "\n".join(f"- {r}" for r in evidence_reasons)
                ),
            }

        if result["status"] == "evidence_mismatch":
            return {
                "changed_files": [],
                "summary": (
                    "Patch rejected — did not match gathered evidence.\n\n"
                    f"Target file: {best_file}\nReason: {result.get('message', '')}\n\n"
                    "Evidence found:\n" + "\n".join(f"- {r}" for r in evidence_reasons)
                ),
            }

        if result["status"] in ("error", "empty") and attempt == MAX_RETRIES:
            notify_discord(
                f"🚨 Patch failed after {MAX_RETRIES} attempts for task #{task['id']} — needs your input.\n"
                f"Target file: `{best_file}`\nLast error: {result.get('message', 'unknown')}"
            )
            return {
                "changed_files": [],
                "summary": (
                    f"LLM proposal generation failed after {MAX_RETRIES} attempts.\n\n"
                    f"Target file:\n{best_file}\n\nTop file preview:\n{best_preview[:3000]}"
                ),
            }

        if result["status"] == "invalid" and attempt == MAX_RETRIES:
            notify_discord(
                f"🚨 Patch failed validation after {MAX_RETRIES} attempts for task #{task['id']} — needs your input.\n"
                f"Target file: `{best_file}`\nErrors: {', '.join(result.get('errors', []))}"
            )
            return {
                "changed_files": [],
                "summary": (
                    f"Patch rejected by validator after {MAX_RETRIES} attempts.\n\n"
                    f"Target file: {best_file}\n\nErrors:\n"
                    + "\n".join(f"- {e}" for e in result.get("errors", []))
                ),
            }

        print(f"[CodeAgent] Attempt {attempt} failed ({result['status']}), retrying...")

    if not last_result or last_result["status"] != "ok":
        return {"changed_files": [], "summary": "Patch could not be generated after all retries."}

    # --- Good patch — classify risk and route ---
    new_content = last_result["new_content"]
    diagnosis = last_result["diagnosis"]
    summary = last_result["summary"]
    validation = last_result["validation"]

    risk = classify_risk(original_text=original_content, proposed_text=new_content, file_path=best_file)

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
    warnings_text = ("\nWarnings:\n" + "\n".join(f"- {w}" for w in validation.warnings)) if validation.warnings else ""
    evidence_text = ("\nEvidence:\n" + "\n".join(f"- {r}" for r in evidence_reasons)) if evidence_reasons else ""

    # Auto-apply low risk patches
    if risk.level == "low":
        backup_path = apply_proposal_file(best_file, new_content)
        git_commit_files(project_config, [best_file], f"agent auto-patch proposal {proposal['id']} (task #{task['id']})")

        from core.proposal_store import update_proposal_status
        update_proposal_status(proposal["id"], "applied")

        notify_discord(
            f"✅ Auto-patched `{Path(best_file).name}` (task #{task['id']})\n"
            f"Summary: {summary}\nProposal ID: {proposal['id']}"
        )

        return {
            "changed_files": [best_file],
            "summary": (
                f"Patch auto-applied (low risk).\n"
                f"Proposal ID: {proposal['id']}\nTask ID: {task['id']}\n"
                f"Target file: {best_file}\nDiagnosis: {diagnosis}\nSummary: {summary}"
                f"{evidence_text}{warnings_text}"
            ),
        }

    # High risk — send to Discord for approval
    risk_reasons_text = "\nRisk reasons:\n" + "\n".join(f"- {r}" for r in risk.reasons)

    notify_discord(
        f"⚠️ High-risk patch ready for task #{task['id']}\n"
        f"File: `{Path(best_file).name}`\nSummary: {summary}\n"
        f"Risk: {', '.join(risk.reasons)}\n"
        f"Use `/approve {proposal['id']}` to apply or `/reject {proposal['id']}` to discard."
    )

    return {
        "changed_files": [],
        "summary": (
            f"Patch proposed (high risk — approval required).\n"
            f"Proposal ID: {proposal['id']}\nTask ID: {task['id']}\n"
            f"Target file: {best_file}\nDiagnosis: {diagnosis}\nSummary: {summary}"
            f"{evidence_text}{risk_reasons_text}{warnings_text}\n\n"
            f"Diff preview:\n```diff\n{diff_text}\n```\n\n"
            f"Use /approve {proposal['id']} to apply.\n"
            f"Use /reject {proposal['id']} to discard."
        ),
    }


def handle_reference_search(task, project_config):
    lower_title = task["title"].lower()

    if "find who calls showresults" in lower_title or "find who calls show results" in lower_title:
        pattern = "ShowResults("
        results = search_project_code(project_config, pattern)
        return {"changed_files": [], "summary": format_search_results(f"Project-wide references for {pattern}", results)}

    if "find who calls hide" in lower_title:
        pattern = "Hide("
        results = search_project_code(project_config, pattern)
        return {"changed_files": [], "summary": format_search_results(f"Project-wide references for {pattern}", results)}

    if "find where setactive(false) is used" in lower_title or "find where setactive(false) is referenced" in lower_title:
        pattern = "SetActive(false)"
        results = search_project_code(project_config, pattern)
        return {"changed_files": [], "summary": format_search_results(f"Project-wide references for {pattern}", results)}

    if "find where resultspanel is referenced" in lower_title or "find resultspanel references" in lower_title:
        pattern = "ResultsPanel"
        results = search_project_code(project_config, pattern)
        return {"changed_files": [], "summary": format_search_results(f"Project-wide references for {pattern}", results)}

    return None


def handle_asset_search(task, project_config):
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
            "summary": format_asset_search(f"Unity scene/prefab references for '{target}'", results),
        }

    return None


def handle_hierarchy_inspection(task, project_config):
    title = task["title"].lower()

    if "inspect ui cluster for" in title:
        target = task["title"].split("for", 1)[1].strip()
        results = inspect_scene_context(project_config, target)
        return {"changed_files": [], "summary": format_hierarchy_results(f"Scene context for '{target}'", results)}

    if "inspect scene context for" in title:
        target = task["title"].split("for", 1)[1].strip()
        results = inspect_scene_context(project_config, target)
        return {"changed_files": [], "summary": format_hierarchy_results(f"Scene context for '{target}'", results)}

    return None


def handle_task(task, project_config):
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
            "summary": f"No likely Unity scripts found.\n\nRecent filtered Unity log:\n{filtered_log[:4000]}",
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
