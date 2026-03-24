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


def handle_patch_proposal(task: dict, project_config: dict):

    lower_title = task["title"].lower()
    keywords = extract_keywords(task["title"])
    files = find_relevant_files(project_config, keywords)

    if not files:
        return None

    best_file = files[0]
    best_preview = read_preview(best_file, max_lines=220)

    filtered_log = read_filtered_unity_log(
        keywords=[
            "ResultsUI",
            "Error",
            "Exception",
            "NullReference",
            "ShowResults",
            "Hide",
        ]
    )

    scene_context = get_scene_context_for_task(project_config, task["title"])

    llm_task_match = (
        "results" in lower_title
        or "null reference" in lower_title
        or "hide gameplay ui" in lower_title
    )

    if not llm_task_match:
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
            file_content=Path(best_file).read_text(encoding="utf-8"),
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

    # -------------------------------
    # VALIDATE PATCH BEFORE STORING
    # -------------------------------

    original_content = Path(best_file).read_text(encoding="utf-8")

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
        },
    )

    diff_text = build_diff_preview(best_file, new_content)

    warnings_text = ""

    if validation.warnings:
        warnings_text = "\nWarnings:\n" + "\n".join(
            f"- {w}" for w in validation.warnings
        )

    return {
        "changed_files": [],
        "summary": (
            f"Patch proposed.\n"
            f"Proposal ID: {proposal['id']}\n"
            f"Task ID: {task['id']}\n"
            f"Target file: {best_file}\n"
            f"Diagnosis: {diagnosis}\n"
            f"Summary: {summary}\n"
            f"{warnings_text}\n\n"
            f"Diff preview:\n```diff\n{diff_text}\n```\n\n"
            f"Use /approve {proposal['id']} to apply.\n"
            f"Use /reject {proposal['id']} to discard."
        ),
    }


def handle_reference_search(task: dict, project_config: dict):

    lower_title = task["title"].lower()

    if "find who calls showresults" in lower_title:

        pattern = "ShowResults("
        results = search_project_code(project_config, pattern)

        return {
            "changed_files": [],
            "summary": format_search_results(
                f"Project-wide references for {pattern}", results
            ),
        }

    if "find who calls hide" in lower_title:

        pattern = "Hide("
        results = search_project_code(project_config, pattern)

        return {
            "changed_files": [],
            "summary": format_search_results(
                f"Project-wide references for {pattern}", results
            ),
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
                f"Unity scene/prefab references for '{target}'", results
            ),
        }

    return None


def handle_hierarchy_inspection(task: dict, project_config: dict):

    title = task["title"].lower()

    if "inspect scene context for" in title:

        target = task["title"].split("for", 1)[1].strip()

        results = inspect_scene_context(project_config, target)

        return {
            "changed_files": [],
            "summary": format_hierarchy_results(
                f"Scene context for '{target}'", results
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
        keywords=["ResultsUI", "Error", "Exception", "NullReference"]
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