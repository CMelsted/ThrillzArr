import os
from pathlib import Path

from django.conf import settings


def input_dir() -> str:
    # Input location comes from the deploy-time bind mount, not settings.
    # The mount is guaranteed to exist under Docker; the ~/input fallback
    # (running outside Docker) is not, so create it on first use.
    if Path('/input').is_dir():
        return '/input'
    path = Path.home() / 'input'
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def output_dir() -> str:
    # Output location comes from the deploy-time bind mount, not settings
    if Path('/output').is_dir():
        return '/output'
    path = Path.home() / 'output'
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def uploads_dir() -> str:
    # Files uploaded through the browser instead of dropped into the
    # input mount. Stored under CONFIG_DIR so they survive container
    # restarts (same persistent volume as secret_key.txt/db.sqlite3).
    path = Path(settings.CONFIG_DIR) / 'uploads'
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def tracked_paths() -> set:
    """
        Every src_path with a live Book record, regardless of status
        (pending review, processing, done, error, abandoned). A path
        only ever leaves this set once its Book is actually deleted
        (Discard, Clear Entry, Clear all).
    """
    from importer.models import Book
    return set(Book.objects.values_list('src_path', flat=True))


def excluded_input_paths() -> set:
    """
        Locations that must never be offered for import: the output
        location, if it happens to live inside the input tree.
    """
    excluded = set()
    for path in [Path(output_dir())]:
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
