"""Keep the latest release in README and preserve versioned release history."""

import argparse
from pathlib import Path
import re


START = "<!-- whats-new:start -->"
END = "<!-- whats-new:end -->"
GENERATED = "<!-- generated-release-notes -->"
VERSION = r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
LEGACY_HEADING = re.compile(rf"(?m)^## (?:🆕 )?What's New in ({VERSION})[ \t]*$")
REPOSITORY = "Ghostshadowplays/Ghosty-Tools"


def notes_body(notes: str) -> str:
    notes = notes.replace(GENERATED, "").strip()
    return re.sub(r"\A# What's New in v\d+\.\d+\.\d+[^\n]*(?:\n|$)", "", notes).strip()


def nested_headings(body: str) -> str:
    """Keep note subsections inside the README/changelog version heading."""
    result = []
    fence = ""
    for line in body.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            value = marker.group(1)
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = ""
        if not fence:
            line = re.sub(r"^#{1,2} ", "### ", line)
        result.append(line)
    return "\n".join(result)


def version_key(version: str) -> tuple[int, ...]:
    return tuple(map(int, version[1:].split(".")))


def update_release_docs(root: Path, version: str, incoming_notes: str, repository: str = REPOSITORY,
                        commit_notes: str = "") -> None:
    if not re.fullmatch(VERSION, version):
        raise ValueError(f"Invalid release version: {version}")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Invalid repository name")
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    starts, ends = readme.count(START), readme.count(END)
    if (starts, ends) not in ((0, 0), (1, 1)):
        raise ValueError("README must have one matching pair of What's New markers, or neither")
    if starts and readme.index(END) < readme.index(START):
        raise ValueError("README What's New markers are reversed")
    if starts:
        heading = LEGACY_HEADING.search(readme[readme.index(START):readme.index(END)])
        if heading and version_key(version) < version_key(heading.group(1)):
            raise ValueError("An older release cannot replace the newer README version")

    folder = root / "config/release_notes"
    articles = {path.stem: path.read_text(encoding="utf-8")
                for path in folder.glob("v*.md") if re.fullmatch(VERSION, path.stem)}
    writes = {}
    if not starts:
        # Migrate the original hand-written README entries before replacing them.
        sections = []
        for heading in LEGACY_HEADING.finditer(readme):
            following = re.search(r"(?m)^## ", readme[heading.end():])
            stop = heading.end() + following.start() if following else len(readme)
            old_version = heading.group(1)
            body = readme[heading.end():stop].strip()
            # One historical entry linked to a different version's comparison.
            def keep_matching_comparison(match: re.Match[str]) -> str:
                return match.group(0) if match.group(1) == old_version else ""

            body = re.sub(
                r"(?m)^\[Full (v\d+\.\d+\.\d+) changelog]\([^\n]*\)[ \t]*$",
                keep_matching_comparison, body,
            ).strip()
            if old_version not in articles:
                articles[old_version] = f"# What's New in {old_version}\n\n{body}\n"
                writes[folder / f"{old_version}.md"] = articles[old_version]
            sections.append((heading.start(), stop))
        position = sections[0][0] if sections else readme.find("\n## ")
        if position < 0:
            position = len(readme)
        for begin, stop in reversed(sections):
            readme = readme[:begin] + readme[stop:]
        readme = readme[:position].rstrip() + f"\n\n{START}\n{END}\n\n" + readme[position:].lstrip()

    existing = articles.get(version, "")
    # Hand-written notes win. Generated notes can refresh when a retry adds fixes.
    if existing and GENERATED not in existing:
        current = existing
    else:
        body = notes_body(incoming_notes)
        if not re.search(r"(?m)^[-*] ", body) and commit_notes.strip():
            body = f"## Changes\n\n{commit_notes.strip()}\n\n{body}"
        if not body:
            raise ValueError("Release notes are empty; README was not updated")
        current = f"# What's New in {version}\n\n{GENERATED}\n\n{body}\n"
        writes[folder / f"{version}.md"] = current
    body = notes_body(current)
    if not body:
        raise ValueError("Release notes are empty; README was not updated")
    if START in body or END in body:
        raise ValueError("Release notes must not contain README control markers")
    articles[version] = current
    release_url = f"https://github.com/{repository}/releases/tag/"
    block = (f"{START}\n## 🆕 What's New in {version}\n\n{nested_headings(body)}\n\n"
             f"[Release details]({release_url}{version}) · [Release history](CHANGELOG.md)\n{END}")
    begin, stop = readme.index(START), readme.index(END) + len(END)
    writes[readme_path] = readme[:begin] + block + readme[stop:]
    history = ["# Changelog\n\nRelease notes are preserved here as the README moves to each new version.\n"]
    for tag in sorted(articles, key=version_key, reverse=True):
        history.append(f"## {tag}\n\n{nested_headings(notes_body(articles[tag]))}\n\n"
                       f"[GitHub release]({release_url}{tag})\n")
    writes[root / "CHANGELOG.md"] = "\n".join(history)
    for path, content in writes.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes-file", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--commits-file", type=Path)
    args = parser.parse_args()
    try:
        commits = args.commits_file.read_text(encoding="utf-8") if args.commits_file else ""
        update_release_docs(args.root, args.version, args.notes_file.read_text(encoding="utf-8"),
                            args.repository, commits)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Release documentation update failed: {error}\n")


if __name__ == "__main__":
    main()
