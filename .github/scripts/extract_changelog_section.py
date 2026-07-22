"""Extract one version's release notes from CHANGELOG.md.

Usage: python extract_changelog_section.py <version> [output_path]

Finds the "## [<version>] ..." heading and returns everything up to (but not
including) the next "## [" heading. Used by the release workflow to build
GitHub Release notes straight from the changelog instead of duplicating them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"


def extract_section(changelog_text: str, version: str) -> str:
    """Return the body of the "## [<version>]" section, excluding its heading.

    Stops at the next "## [" heading, or at the trailing block of Markdown
    reference-style links (e.g. "[Unreleased]: https://...") that Keep a
    Changelog puts at the end of the file, whichever comes first — the
    section is otherwise unbounded when it's the last (or only) version.
    """
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\n\[[^\]]+\]:|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(changelog_text)

    if match is None:
        raise ValueError(f"No CHANGELOG.md section found for version {version!r}.")

    return match.group(1).strip() + "\n"


def main() -> None:
    """Extract the requested version's section and print or write it."""
    if len(sys.argv) < 2:
        print(
            "Usage: extract_changelog_section.py <version> [output_path]",
            file=sys.stderr,
        )
        sys.exit(2)

    version = sys.argv[1]
    section = extract_section(CHANGELOG_PATH.read_text(), version)

    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(section)
    else:
        print(section)


if __name__ == "__main__":
    main()
