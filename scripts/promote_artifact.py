#!/usr/bin/env python3
"""Turn docs/artifact/staging.html into a promotable copy of the main Real Estate Tool artifact.

Dry run by default: strips the staging banner/title, checks the approved layout survived, prints the
result. With --write it overwrites docs/artifact/real-estate-tool.html (git keeps the previous
approved copy). Publishing to the main artifact URL is a separate step that needs the user's explicit
approval; this script never touches the network.
"""
import re
import sys
from pathlib import Path

ART = Path(__file__).resolve().parent.parent / "docs" / "artifact"
REQUIRED = ['data-t="ov"', 'data-t="cf"', 'data-t="st"', 'data-t="as"', "Pick a world", "Glass Box Underwriting"]


def main() -> int:
    html = (ART / "staging.html").read_text()
    html = re.sub(r"<!--STAGING-BANNER-->.*?<!--/STAGING-BANNER-->\n?", "", html, flags=re.S)
    html = html.replace("<title>Real Estate Tool Staging</title>", "<title>Real Estate Tool</title>")
    missing = [r for r in REQUIRED if r not in html]
    if "STAGING" in html or missing:
        print("NOT promotable:", missing or "staging marker still present")
        return 1
    print(f"promotable: all {len(REQUIRED)} layout checks pass, {len(html)} bytes")
    if "--write" in sys.argv:
        (ART / "real-estate-tool.html").write_text(html)
        print("wrote docs/artifact/real-estate-tool.html (review the git diff, then ask to publish to main)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
