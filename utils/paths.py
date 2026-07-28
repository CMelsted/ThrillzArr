import os
from pathlib import Path

from importer.models import Setting


def input_dir() -> str:
    # Input location comes from the deploy-time bind mount, not settings
    if Path('/input').is_dir():
        return '/input'
    return str(Path.home() / 'input')


def output_dir() -> str:
    # Output location comes from the deploy-time bind mount, not settings
    if Path('/output').is_dir():
        return '/output'
    return str(Path.home() / 'output')


def excluded_input_paths() -> set:
    """
        Locations that must never be offered for import: the folder
        completed originals are moved into, and the output location if it
        happens to live inside the input tree.
    """
    candidates = [Path(output_dir())]

    setting = Setting.objects.first()
    if setting and setting.completed_directory:
        candidates.append(Path(setting.completed_directory))

    excluded = set()
    for path in candidates:
        try:
            excluded.add(path.resolve())
        except OSError:
            continue
    return excluded


def importable_contents(path) -> list:
    """
        Directory listing for the import picker, minus excluded locations.
    """
    excluded = excluded_input_paths()
    contents = sorted(Path(path).iterdir(), key=os.path.getmtime, reverse=True)

    visible = []
    for item in contents:
        try:
            if item.resolve() in excluded:
                continue
        except OSError:
            continue
        visible.append(item)
    return visible
