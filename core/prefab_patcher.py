"""
core/prefab_patcher.py

Safely reads and patches Unity YAML prefab and asset files.
Supports:
- Setting Inspector field references (fileID + guid)
- Setting primitive values (colors, strings, ints, bools)
- Finding MonoBehaviour components by script GUID
- Validating YAML structure after patching
"""

import re
import shutil
from pathlib import Path
from datetime import datetime


# Unity object reference format
def make_object_ref(file_id: str, guid: str = "", asset_type: int = 0) -> str:
    """
    Build a Unity object reference string.
    For scene-local references: {fileID: 12345}
    For asset references: {fileID: 11400000, guid: abc123, type: 2}
    For sprite references: {fileID: 21300000, guid: abc123, type: 3}
    """
    if guid:
        return f"{{fileID: {file_id}, guid: {guid}, type: {asset_type}}}"
    return f"{{fileID: {file_id}}}"


SPRITE_FILE_ID = "21300000"   # Unity fileID for Sprite sub-asset
TEXTURE_FILE_ID = "2800000"   # Unity fileID for Texture2D
ASSET_FILE_ID = "11400000"    # Unity fileID for ScriptableObject assets


def make_color(r: float, g: float, b: float, a: float = 1.0) -> str:
    return f"{{r: {r}, g: {g}, b: {b}, a: {a}}}"


def backup_file(file_path: str) -> str:
    """Create a timestamped backup of the file before patching."""
    path = Path(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".{timestamp}.bak")
    shutil.copy2(file_path, backup_path)
    return str(backup_path)


def read_unity_yaml(file_path: str) -> str:
    """Read a Unity YAML file."""
    return Path(file_path).read_text(encoding="utf-8")


def write_unity_yaml(file_path: str, content: str):
    """Write patched content back to a Unity YAML file."""
    Path(file_path).write_text(content, encoding="utf-8")


def find_component_block(yaml_text: str, script_guid: str) -> tuple[int, int] | None:
    """
    Find the start and end line indices of a MonoBehaviour block
    that uses the given script GUID.
    Returns (start_line, end_line) or None if not found.
    """
    lines = yaml_text.splitlines()
    block_start = None

    for i, line in enumerate(lines):
        # Look for MonoBehaviour blocks
        if line.strip() == "MonoBehaviour:":
            block_start = i

        # Look for the script GUID within the current block
        if block_start is not None and f"guid: {script_guid}" in line:
            # Found the right block — now find where it ends
            # The block ends at the next "--- " separator or EOF
            for j in range(block_start, len(lines)):
                if j > block_start and lines[j].startswith("---"):
                    return (block_start, j - 1)
            return (block_start, len(lines) - 1)

    return None


def find_field_in_block(lines: list[str], block_start: int, block_end: int,
                        field_name: str) -> int | None:
    """
    Find the line index of a field within a component block.
    Returns the line index or None if not found.
    """
    for i in range(block_start, block_end + 1):
        stripped = lines[i].strip()
        if stripped.startswith(f"{field_name}:"):
            return i
    return None


def set_field_in_component(
    yaml_text: str,
    script_guid: str,
    field_name: str,
    field_value: str,
) -> str | None:
    """
    Set a field value in the MonoBehaviour component identified by script_guid.
    Returns the modified YAML text, or None if the component wasn't found.
    """
    lines = yaml_text.splitlines()
    block = find_component_block(yaml_text, script_guid)

    if block is None:
        return None

    block_start, block_end = block
    field_line = find_field_in_block(lines, block_start, block_end, field_name)

    if field_line is not None:
        # Replace existing field
        indent = len(lines[field_line]) - len(lines[field_line].lstrip())
        lines[field_line] = " " * indent + f"{field_name}: {field_value}"
    else:
        # Insert new field after the last known field in the block
        # Find the insertion point — after m_EditorClassIdentifier or last field
        insert_after = block_start
        for i in range(block_start, block_end + 1):
            if lines[i].strip().startswith("m_EditorClassIdentifier:"):
                insert_after = i
                break
            if lines[i].strip() and not lines[i].startswith("---"):
                insert_after = i

        lines.insert(insert_after + 1, f"  {field_name}: {field_value}")

    return "\n".join(lines)


def set_asset_field(
    yaml_text: str,
    field_name: str,
    field_value: str,
) -> str:
    """
    Set a field in a standalone .asset file (single MonoBehaviour block).
    """
    lines = yaml_text.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{field_name}:"):
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + f"{field_name}: {field_value}"
            return "\n".join(lines)

    # Field not found — insert after m_EditorClassIdentifier
    for i, line in enumerate(lines):
        if "m_EditorClassIdentifier:" in line:
            lines.insert(i + 1, f"  {field_name}: {field_value}")
            return "\n".join(lines)

    return "\n".join(lines)


def validate_unity_yaml(yaml_text: str) -> tuple[bool, list[str]]:
    """
    Basic validation of Unity YAML structure.
    Returns (is_valid, errors).
    """
    errors = []

    if not yaml_text.strip().startswith("%YAML"):
        errors.append("Missing YAML header — file may be corrupted.")

    if "MonoBehaviour:" not in yaml_text:
        errors.append("No MonoBehaviour block found.")

    # Check for obviously broken field references
    broken_refs = re.findall(r"\{fileID:\s*\}", yaml_text)
    if broken_refs:
        errors.append(f"Found {len(broken_refs)} empty fileID reference(s).")

    return (len(errors) == 0, errors)


def patch_prefab_field(
    prefab_path: str,
    script_guid: str,
    field_name: str,
    field_value: str,
    make_backup: bool = True,
) -> tuple[bool, str]:
    """
    High-level function to patch a single field in a prefab component.

    Args:
        prefab_path: Path to the .prefab file
        script_guid: GUID of the script whose component to patch
        field_name: Name of the Inspector field
        field_value: New value (use make_object_ref() or make_color() helpers)
        make_backup: Whether to create a backup before patching

    Returns:
        (success, message)
    """
    if make_backup:
        backup_file(prefab_path)

    yaml_text = read_unity_yaml(prefab_path)
    patched = set_field_in_component(yaml_text, script_guid, field_name, field_value)

    if patched is None:
        return False, f"Component with guid {script_guid} not found in {prefab_path}"

    is_valid, errors = validate_unity_yaml(patched)
    if not is_valid:
        return False, f"Validation failed: {'; '.join(errors)}"

    write_unity_yaml(prefab_path, patched)
    return True, f"Patched {field_name} in {Path(prefab_path).name}"


def patch_asset_field(
    asset_path: str,
    field_name: str,
    field_value: str,
    make_backup: bool = True,
) -> tuple[bool, str]:
    """
    High-level function to patch a single field in a .asset file.

    Returns:
        (success, message)
    """
    if make_backup:
        backup_file(asset_path)

    yaml_text = read_unity_yaml(asset_path)
    patched = set_asset_field(yaml_text, field_name, field_value)

    is_valid, errors = validate_unity_yaml(patched)
    if not is_valid:
        return False, f"Validation failed: {'; '.join(errors)}"

    write_unity_yaml(asset_path, patched)
    return True, f"Patched {field_name} in {Path(asset_path).name}"


def get_field_value(yaml_text: str, field_name: str) -> str | None:
    """Read the current value of a field from a YAML file."""
    for line in yaml_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{field_name}:"):
            return stripped.split(":", 1)[1].strip()
    return None
