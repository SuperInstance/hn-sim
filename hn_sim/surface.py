"""Repo surface: the only thing hn-sim reads.

DESIGN LAW 5: simulation on inference. Input is README + title + Show-HN draft
(+ optional first-screen file). No network. No real HN. Ever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

README_CANDIDATES = ("README.md", "README", "readme.md", "Readme.md")
FIRST_SCREEN_CANDIDATES = ("docs/SCREENSHOTS.md", "SCREENSHOTS.md", "docs/DEMO.md")


@dataclass
class SurfaceDoc:
    """One document of the repo surface."""

    file: str
    text: str

    def sections(self) -> dict[str, str]:
        """Split text into {heading_line: body} so triggers can cite sections."""
        parts: dict[str, list[str]] = {"(top)": []}
        current = "(top)"
        for line in self.text.splitlines():
            if line.startswith("#"):
                current = line.strip().lstrip("#").strip() or "(top)"
                parts.setdefault(current, [])
            else:
                parts[current].append(line)
        return {h: "\n".join(body) for h, body in parts.items()}

    def section_for_offset(self, offset: int) -> str:
        """Heading of the section containing character offset (nearest preceding)."""
        section = "(top)"
        pos = 0
        for line in self.text.splitlines(keepends=True):
            if line.startswith("#"):
                heading = line.strip().lstrip("#").strip() or "(top)"
                if pos <= offset:
                    section = heading
                else:
                    break
            pos += len(line)
        return section


@dataclass
class Surface:
    """The full surface a forecast runs against."""

    title: str
    docs: list[SurfaceDoc] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return all(not d.text.strip() for d in self.docs) and not self.title.strip()

    def all_text(self) -> str:
        return "\n\n".join([self.title, *[d.text for d in self.docs]])


def load_surface(repo: Path, title: str, show_hn_draft: Path | None = None) -> Surface:
    """Load README (+ optional draft + optional first-screen doc) from repo."""
    docs: list[SurfaceDoc] = []
    readme_found = False
    for name in README_CANDIDATES:
        p = repo / name
        if p.is_file():
            docs.append(SurfaceDoc(file=name, text=p.read_text(encoding="utf-8", errors="replace")))
            readme_found = True
            break
    # first-screen doc: best-effort, never fatal
    for name in FIRST_SCREEN_CANDIDATES:
        p = repo / name
        if p.is_file():
            docs.append(SurfaceDoc(file=name, text=p.read_text(encoding="utf-8", errors="replace")))
            break
    if show_hn_draft is not None and show_hn_draft.is_file():
        docs.append(
            SurfaceDoc(file=show_hn_draft.name, text=show_hn_draft.read_text(encoding="utf-8", errors="replace"))
        )
    elif show_hn_draft is not None:
        raise FileNotFoundError(f"Show-HN draft not found: {show_hn_draft}")
    if not readme_found and title.strip():
        # title-only surface is thin but not empty; forecaster will flag low signal
        pass
    return Surface(title=title, docs=docs)


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
