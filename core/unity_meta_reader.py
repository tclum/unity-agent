"""
core/unity_meta_reader.py

Reads Unity .meta files to build a map of:
- Script name → GUID (for finding MonoBehaviour components in prefabs)
- Asset path → GUID (for referencing assets in prefab/asset fields)
"""

from pathlib import Path


EXCLUDED_PARTS = [
    "TextMesh Pro",
    "Plugins",
    "ThirdParty",
    "Third Party",
    "Packages",
    "Library",
]


def is_excluded(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(excluded in path_str for excluded in EXCLUDED_PARTS)


def read_guid(meta_path: Path) -> str | None:
    """Extract the guid from a .meta file."""
    try:
        for line in meta_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("guid:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def build_script_guid_map(project_config: dict) -> dict[str, str]:
    """
    Returns a map of script name (without .cs) → GUID.
    e.g. {"CardUIButton": "d97197ab7c54f4ff29a1bb877d8d22ce"}
    """
    unity_root = Path(project_config["unity_project_path"])
    assets_dir = unity_root / "Assets"
    result = {}

    for meta_path in assets_dir.rglob("*.cs.meta"):
        if is_excluded(meta_path):
            continue
        guid = read_guid(meta_path)
        if guid:
            script_name = meta_path.stem.replace(".cs", "")
            result[script_name] = guid

    return result


def build_asset_guid_map(project_config: dict) -> dict[str, str]:
    """
    Returns a map of asset path → GUID.
    Includes both absolute paths and stem names for easy lookup.
    e.g. {
        "/full/path/to/Kalo.asset": "4cce1b47...",
        "Kalo": "4cce1b47...",
    }
    """
    unity_root = Path(project_config["unity_project_path"])
    assets_dir = unity_root / "Assets"
    result = {}

    for ext_pattern, asset_ext in [
        ("*.asset.meta", ".asset"),
        ("*.prefab.meta", ".prefab"),
        ("*.png.meta", ".png"),
        ("*.jpg.meta", ".jpg"),
        ("*.jpeg.meta", ".jpeg"),
        ("*.psd.meta", ".psd"),
    ]:
        for meta_path in assets_dir.rglob(ext_pattern):
            if is_excluded(meta_path):
                continue
            guid = read_guid(meta_path)
            if guid:
                asset_path = meta_path.with_suffix("")  # remove .meta
                abs_path = str(asset_path)
                rel_path = str(asset_path.relative_to(assets_dir))
                stem = asset_path.stem

                # Index by absolute path, relative path, and stem name
                result[abs_path] = guid
                result[rel_path] = guid
                result[stem] = guid

    return result


def find_prefabs(project_config: dict) -> list[str]:
    """Returns all non-excluded prefab paths in the project."""
    unity_root = Path(project_config["unity_project_path"])
    assets_dir = unity_root / "Assets"
    results = []

    for path in assets_dir.rglob("*.prefab"):
        if not is_excluded(path):
            results.append(str(path))

    return results


def find_assets(project_config: dict, asset_type: str = ".asset") -> list[str]:
    """Returns all non-excluded asset paths of a given type."""
    unity_root = Path(project_config["unity_project_path"])
    assets_dir = unity_root / "Assets"
    results = []

    for path in assets_dir.rglob(f"*{asset_type}"):
        if not is_excluded(path):
            results.append(str(path))

    return results


def find_relevant_prefabs(project_config: dict, keywords: list[str]) -> list[str]:
    """Find prefabs whose name matches any keyword."""
    all_prefabs = find_prefabs(project_config)
    if not keywords:
        return all_prefabs

    results = []
    for path in all_prefabs:
        name = Path(path).stem.lower()
        if any(k.lower() in name for k in keywords):
            results.append(path)

    return results


def find_relevant_assets(project_config: dict, keywords: list[str],
                         asset_type: str = ".asset") -> list[str]:
    """Find assets whose name matches any keyword."""
    all_assets = find_assets(project_config, asset_type)
    if not keywords:
        return all_assets

    results = []
    for path in all_assets:
        name = Path(path).stem.lower()
        if any(k.lower() in name for k in keywords):
            results.append(path)

    return results
