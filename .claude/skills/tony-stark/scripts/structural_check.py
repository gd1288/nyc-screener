#!/usr/bin/env python3
"""Structural sanity check for a ten-part SKILL.md. Stdlib only, no deps.

Requires Python 3.7+ (the `from __future__ import annotations` below covers 3.7-3.9,
where `Path | None`-style annotations aren't otherwise valid).

Usage: python3 structural_check.py <path-to-SKILL.md>

Checks:
  - frontmatter parses, has non-empty name + description
  - description <= 1024 chars
  - body (excluding frontmatter) <= 500 lines
  - all ten numbered section headings present, in order (or an explicit N/A + reason)
  - name doesn't collide with another skill's name under the project's .claude/skills/,
    the user's ~/.claude/skills/, or installed plugin skill directories

Exits 0 if everything passes, 1 otherwise, printing every failure found (not just the first).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SECTION_KEYWORDS = {
    1: ["name"],
    2: ["description"],
    3: ["body", "instruction"],
    4: ["gotcha"],
    5: ["guardrail"],
    6: ["embed", "skill"],
    7: ["memory", "allocation"],
    8: ["frontmatter"],
    9: ["sub-file", "script", "eval"],
    10: ["version", "iteration"],
}


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text, "file does not start with '---' frontmatter delimiter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text, "frontmatter not closed with a second '---'"
    fm_raw, body = parts[1], parts[2]
    fields = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fields, body, None


def check_headings(body: str, failures: list):
    heading_re = re.compile(r"^\s*#{1,3}\s*(\d{1,2})[.)]\s*(.+?)\s*$", re.MULTILINE)
    found = {}
    for m in heading_re.finditer(body):
        num = int(m.group(1))
        if 1 <= num <= 10 and num not in found:
            found[num] = (m.start(), m.end(), m.group(2))

    for n in range(1, 11):
        if n not in found:
            failures.append(f"missing heading for section {n} ({' / '.join(SECTION_KEYWORDS[n])})")
            continue
        title_norm = normalize(found[n][2])
        if not any(kw.replace("-", "") in title_norm for kw in SECTION_KEYWORDS[n]):
            failures.append(
                f"section {n} heading text {found[n][2]!r} doesn't look like "
                f"{'/'.join(SECTION_KEYWORDS[n])} — check numbering/order"
            )

    nums_in_order = sorted(found.keys())
    if nums_in_order != list(range(1, len(nums_in_order) + 1)):
        failures.append(f"section headings out of order or non-contiguous: found {nums_in_order}")

    # check each present section has non-empty content (or a stated N/A reason)
    sorted_by_pos = sorted(found.items(), key=lambda kv: kv[1][0])
    for i, (n, (start, end, _title)) in enumerate(sorted_by_pos):
        next_start = sorted_by_pos[i + 1][1][0] if i + 1 < len(sorted_by_pos) else len(body)
        content = body[end:next_start].strip()
        if not content:
            failures.append(f"section {n} has no content")
        elif content.upper().startswith("N/A"):
            rest = content[3:].lstrip(" -—:")
            if len(rest) < 5:
                failures.append(f"section {n} marked N/A without a stated reason")


def find_skill_files(project_root: Path | None):
    paths = []
    if project_root is not None:
        paths += sorted((project_root / ".claude" / "skills").glob("*/SKILL.md"))
    home = Path.home()
    paths += sorted((home / ".claude" / "skills").glob("*/SKILL.md"))
    plugin_root = home / ".claude" / "plugins"
    if plugin_root.exists():
        paths += sorted(plugin_root.glob("**/skills/*/SKILL.md"))
    # de-dupe while preserving order
    seen = set()
    out = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def check_duplicate_name(target: Path, name: str, failures: list):
    project_root = None
    for anc in target.resolve().parents:
        if anc.name == ".claude":
            project_root = anc.parent
            break
    target_resolved = target.resolve()
    for other in find_skill_files(project_root):
        if other == target_resolved:
            continue
        try:
            other_text = other.read_text(encoding="utf-8")
        except OSError:
            continue
        other_fields, _, err = parse_frontmatter(other_text)
        if err or not other_fields:
            continue
        other_name = other_fields.get("name", "")
        if other_name and other_name.strip().lower() == name.strip().lower():
            failures.append(f"name collides with existing skill at {other}")


def main():
    if len(sys.argv) != 2:
        print("usage: structural_check.py <path-to-SKILL.md>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    if not target.is_file():
        print(f"FAIL: {target} is not a file", file=sys.stderr)
        return 1

    text = target.read_text(encoding="utf-8")
    failures = []

    fields, body, fm_err = parse_frontmatter(text)
    if fm_err:
        failures.append(f"frontmatter: {fm_err}")
        fields = fields or {}

    name = fields.get("name", "") if fields else ""
    description = fields.get("description", "") if fields else ""

    if not name:
        failures.append("frontmatter missing non-empty 'name'")
    if not description:
        failures.append("frontmatter missing non-empty 'description'")
    elif len(description) > 1024:
        failures.append(f"description is {len(description)} chars, over the 1024 limit")

    if name and target.parent.name != name:
        failures.append(f"folder name {target.parent.name!r} doesn't match frontmatter name {name!r}")

    body_lines = [l for l in body.splitlines()]
    if len(body_lines) > 500:
        failures.append(f"body is {len(body_lines)} lines, over the 500-line limit")

    check_headings(body, failures)

    if name:
        check_duplicate_name(target, name, failures)

    if failures:
        print(f"FAIL: {target}")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"PASS: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
