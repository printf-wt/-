"""Check local Markdown links and saved evidence hashes without changing files.

Run from any directory: python tools/validate_layout.py
Historical code blocks and immutable offline packages are intentionally not rewritten.
"""

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]\n]*\]\(([^\n]*?)\)')


def main():
    errors = []
    links = 0
    documents = [ROOT / "README.md"]
    for directory in ["writeups", "tools", "output"]:
        documents.extend((ROOT / directory).rglob("*.md"))
    for path in sorted(documents):
        fenced = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
                continue
            if fenced:
                continue
            for match in LINK.finditer(line):
                target = match[1].strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                resolved = path.parent / unquote(parsed.path)
                links += 1
                if not resolved.exists():
                    errors.append(f"{path.relative_to(ROOT)}:{number}: missing {target}")
    manifest_path = ROOT / "writeups/check7/data/sha256-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, expected in manifest.items():
        path = ROOT / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"Evidence hash mismatch: {relative}")
    images = {".jpg", ".jpeg", ".png"}
    for n in range(8):
        directory = ROOT / f"writeups/check{n}"
        if not (directory / "report.md").is_file():
            errors.append(f"Missing report for check{n}")
        for path in (directory / "screenshots").glob("*"):
            if path.is_file() and path.suffix.lower() not in images:
                errors.append(f"Non-image in screenshots: {path.relative_to(ROOT)}")
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print(json.dumps({"status": "passed", "documents": len(documents),
                      "local_links": links, "evidence_hashes": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
