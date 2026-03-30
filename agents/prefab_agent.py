"""
agents/prefab_agent.py

Handles tasks that involve Unity prefab and asset files:
- Wiring Inspector field references in prefabs
- Setting field values in ScriptableObject assets
- Assigning artwork/sprites to cards
- Changing colors, values, and references in prefabs
"""

import json
from pathlib import Path

from core.unity_meta_reader import (
    build_script_guid_map,
    build_asset_guid_map,
    find_relevant_prefabs,
    find_relevant_assets,
)
from core.prefab_patcher import (
    patch_prefab_field,
    patch_asset_field,
    make_object_ref,
    make_color,
    get_field_value,
    read_unity_yaml,
)
from core.llm_client import get_client, extract_json, ANTHROPIC_MODEL as OPENAI_MODEL
from integrations.git_manager import git_commit_files
from integrations.discord_notifier import notify_discord


# Task keywords that suggest prefab/asset work
PREFAB_SIGNALS = [
    "assign", "wire", "reference", "inspector",
    "prefab", "artwork", "sprite", "image",
    "background color", "card color", "set color",
]

ASSET_SIGNALS = [
    "card data", "scriptable", "asset",
    "points", "base points", "card type",
    "effect", "description",
]


def is_prefab_task(task_title: str) -> bool:
    lower = task_title.lower()
    return any(s in lower for s in PREFAB_SIGNALS)


def is_asset_task(task_title: str) -> bool:
    lower = task_title.lower()
    return any(s in lower for s in ASSET_SIGNALS)


def generate_prefab_plan(
    task_title: str,
    prefab_contents: dict[str, str],
    asset_contents: dict[str, str],
    script_guids: dict[str, str],
    asset_guids: dict[str, str],
) -> list[dict]:
    """
    Ask the LLM to generate a plan for patching prefabs/assets.

    Returns a list of patch operations:
    [
        {
            "target_type": "prefab" | "asset",
            "file_path": str,
            "script_guid": str,       # for prefab patches
            "field_name": str,
            "field_value": str,
            "description": str,
        }
    ]
    """
    client = get_client()

    prefab_block = "\n\n".join(
        f"--- PREFAB: {path} ---\n{content[:3000]}"
        for path, content in prefab_contents.items()
    )

    asset_block = "\n\n".join(
        f"--- ASSET: {path} ---\n{content[:1000]}"
        for path, content in list(asset_contents.items())[:10]
    )

    script_guid_block = json.dumps(script_guids, indent=2)
    asset_guid_block = json.dumps(
        {k: v for k, v in asset_guids.items() if "." in k or k[0].isupper()},
        indent=2
    )

    system_prompt = """
You are a Unity engineer who specializes in editing Unity YAML prefab and asset files.

You will be given:
- A task description
- Prefab file contents (YAML)
- Asset file contents (YAML)
- A map of script names to GUIDs
- A map of asset paths to GUIDs

Your job is to generate a list of field patch operations to accomplish the task.

Rules:
- Return VALID JSON only. No markdown.
- Return a JSON object with a "patches" array.
- For prefab patches: include target_type="prefab", file_path, script_guid, field_name, field_value, description.
- For asset patches: include target_type="asset", file_path, field_name, field_value, description.
- field_value must be a valid Unity YAML value string, e.g.:
  - Object reference: {fileID: 11400000, guid: abc123, type: 2}
  - Color: {r: 0, g: 1, b: 0, a: 1}
  - Integer: 5
  - String: Hello
- script_guid must come from the provided script GUID map.
- Asset GUIDs must come from the provided asset GUID map.
- file_path must be the FULL ABSOLUTE path to the file (e.g. /Users/.../Assets/ScriptableObjects/...). Use the exact path shown in the asset contents headers above.
- If no changes are needed, return an empty patches array.
"""

    user_prompt = f"""
Task: {task_title}

Script GUIDs:
{script_guid_block}

Asset GUIDs:
{asset_guid_block}

Prefab contents:
{prefab_block}

Asset contents:
{asset_block}

Return a JSON object with a "patches" array.
"""

    response = client.messages.create(
        model=OPENAI_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ]
    )

    raw_text = response.content[0].text.strip()
    json_text = extract_json(raw_text)
    data = json.loads(json_text)
    return data.get("patches", [])


def apply_patches(patches: list[dict]) -> tuple[list[str], list[str]]:
    """
    Apply a list of patch operations.
    Returns (changed_files, errors).
    """
    changed = []
    errors = []

    for patch in patches:
        target_type = patch.get("target_type", "")
        file_path = patch.get("file_path", "")
        field_name = patch.get("field_name", "")
        field_value = patch.get("field_value", "")
        description = patch.get("description", "")

        if not file_path or not field_name:
            errors.append(f"Invalid patch — missing file_path or field_name: {patch}")
            continue

        if not Path(file_path).exists():
            errors.append(f"File not found: {file_path}")
            continue

        if target_type == "prefab":
            script_guid = patch.get("script_guid", "")
            if not script_guid:
                errors.append(f"Prefab patch missing script_guid: {patch}")
                continue

            success, msg = patch_prefab_field(
                prefab_path=file_path,
                script_guid=script_guid,
                field_name=field_name,
                field_value=str(field_value),
            )

        elif target_type == "asset":
            success, msg = patch_asset_field(
                asset_path=file_path,
                field_name=field_name,
                field_value=str(field_value),
            )

        else:
            errors.append(f"Unknown target_type: {target_type}")
            continue

        if success:
            print(f"[PrefabAgent] ✓ {description or msg}")
            if file_path not in changed:
                changed.append(file_path)
        else:
            print(f"[PrefabAgent] ✗ {msg}")
            errors.append(msg)

    return changed, errors


def assign_artwork_to_all_cards(
    project_config: dict,
    task: dict,
) -> dict:
    """
    Special handler for bulk artwork assignment.
    Matches each card asset to its PNG by name and patches directly
    without going through the LLM — faster and more reliable for bulk ops.
    """
    asset_guids = build_asset_guid_map(project_config)
    card_assets = [
        p for p in find_relevant_assets(project_config, [], ".asset")
        if "ScriptableObjects" in p
    ]

    changed_files = []
    summaries = []
    errors = []

    for asset_path in card_assets:
        stem = Path(asset_path).stem

        # Check if a matching PNG exists
        png_guid = asset_guids.get(stem)
        if not png_guid:
            # Try case-insensitive match
            for key, guid in asset_guids.items():
                if key.lower() == stem.lower() and not key.endswith(".asset"):
                    png_guid = guid
                    break

        if not png_guid:
            print(f"[PrefabAgent] No PNG found for {stem} — skipping")
            continue

        # Check if Artwork is already assigned
        try:
            yaml_text = Path(asset_path).read_text(encoding="utf-8")
            current = None
            for line in yaml_text.splitlines():
                if line.strip().startswith("Artwork:"):
                    current = line.strip()
                    break

            if current and png_guid in current:
                print(f"[PrefabAgent] {stem} artwork already assigned — skipping")
                continue
        except Exception:
            pass

        field_value = f"{{fileID: 21300000, guid: {png_guid}, type: 3}}"
        success, msg = patch_asset_field(
            asset_path=asset_path,
            field_name="Artwork",
            field_value=field_value,
        )

        if success:
            print(f"[PrefabAgent] ✓ Assigned artwork to {stem}")
            changed_files.append(asset_path)
            summaries.append(f"Assigned {stem}.png → {stem} card")
        else:
            print(f"[PrefabAgent] ✗ {msg}")
            errors.append(msg)

    if not changed_files:
        return {
            "changed_files": [],
            "summary": (
                "No artwork assignments made — all cards may already have artwork, "
                "or no matching PNG files were found.\n\n"
                + ("\n".join(f"- {e}" for e in errors) if errors else "")
            ),
        }

    git_commit_files(
        project_config,
        changed_files,
        f"agent bulk artwork assignment task #{task['id']}"
    )

    notify_discord(
        f"✅ Artwork assigned to {len(changed_files)} card(s) (task #{task['id']})\n"
        + "\n".join(f"- {s}" for s in summaries)
    )

    return {
        "changed_files": changed_files,
        "summary": (
            f"Bulk artwork assignment complete.\n"
            f"Task ID: {task['id']}\n"
            f"Cards updated: {len(changed_files)}\n\n"
            + "\n".join(f"- {s}" for s in summaries)
            + ("\n\nErrors:\n" + "\n".join(f"- {e}" for e in errors) if errors else "")
        ),
    }


def handle_task(task: dict, project_config: dict) -> dict:
    """Main entry point for prefab/asset tasks."""
    title = task["title"]
    lower = title.lower()

    # Route bulk artwork assignment to dedicated fast handler
    if any(phrase in lower for phrase in [
        "assign artwork to all", "assign all artwork",
        "artwork to all cards", "assign artwork to cards",
    ]):
        print(f"[PrefabAgent] Bulk artwork assignment for task #{task['id']}")
        return assign_artwork_to_all_cards(project_config, task)

    # Build GUID maps
    print(f"[PrefabAgent] Building GUID maps...")
    script_guids = build_script_guid_map(project_config)
    asset_guids = build_asset_guid_map(project_config)

    # Find relevant prefabs and assets
    keywords = [w for w in lower.split() if len(w) > 3]
    relevant_prefabs = find_relevant_prefabs(project_config, keywords)

    # For card asset tasks, always load all card assets
    if any(w in lower for w in ["card", "cards", "artwork", "all", "assign"]):
        relevant_assets = find_relevant_assets(project_config, [], ".asset")
    else:
        relevant_assets = find_relevant_assets(project_config, keywords)

    # If no keyword match on prefabs, include all prefabs
    if not relevant_prefabs:
        from core.unity_meta_reader import find_prefabs
        relevant_prefabs = find_prefabs(project_config)

    print(f"[PrefabAgent] Found {len(relevant_prefabs)} prefab(s), {len(relevant_assets)} asset(s)")

    # Read file contents
    prefab_contents = {}
    for path in relevant_prefabs:
        try:
            prefab_contents[path] = Path(path).read_text(encoding="utf-8")
        except Exception:
            pass

    asset_contents = {}
    for path in relevant_assets[:20]:  # cap to avoid huge prompts
        try:
            asset_contents[path] = Path(path).read_text(encoding="utf-8")
        except Exception:
            pass

    if not prefab_contents and not asset_contents:
        return {
            "changed_files": [],
            "summary": "No relevant prefabs or assets found for this task.",
        }

    # Generate patch plan
    print(f"[PrefabAgent] Generating patch plan...")
    try:
        patches = generate_prefab_plan(
            task_title=title,
            prefab_contents=prefab_contents,
            asset_contents=asset_contents,
            script_guids=script_guids,
            asset_guids=asset_guids,
        )
    except Exception as e:
        return {
            "changed_files": [],
            "summary": f"Failed to generate prefab patch plan: {e}",
        }

    if not patches:
        return {
            "changed_files": [],
            "summary": "LLM determined no prefab or asset changes are needed for this task.",
        }

    print(f"[PrefabAgent] Applying {len(patches)} patch(es)...")
    changed_files, errors = apply_patches(patches)

    if not changed_files:
        return {
            "changed_files": [],
            "summary": (
                f"Prefab/asset patch failed.\n\n"
                f"Errors:\n" + "\n".join(f"- {e}" for e in errors)
            ),
        }

    # Commit changes
    git_commit_files(
        project_config,
        changed_files,
        f"agent prefab/asset patch task #{task['id']}"
    )

    summaries = [p.get("description", p.get("field_name", "")) for p in patches if p.get("file_path") in changed_files]

    notify_discord(
        f"✅ Prefab/asset patch applied (task #{task['id']})\n"
        f"Files: {', '.join(Path(f).name for f in changed_files)}\n"
        + "\n".join(f"- {s}" for s in summaries)
    )

    error_text = ""
    if errors:
        error_text = f"\n\nErrors:\n" + "\n".join(f"- {e}" for e in errors)

    return {
        "changed_files": changed_files,
        "summary": (
            f"Prefab/asset patch applied.\n"
            f"Task ID: {task['id']}\n"
            f"Files changed: {len(changed_files)}\n\n"
            + "\n".join(f"- {s}" for s in summaries)
            + error_text
        ),
    }
