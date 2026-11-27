"""Versioned release notes shared by the Info page and the update popup."""

import hashlib
from pathlib import Path
import re

from src.utils.helpers import get_resource_path


def bundled_release_notes(version):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        return ""
    path = Path(get_resource_path(f"config/release_notes/{version}.md"))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def notes_revision(version):
    notes = bundled_release_notes(version)
    return hashlib.sha256(notes.encode("utf-8")).hexdigest() if notes else ""
