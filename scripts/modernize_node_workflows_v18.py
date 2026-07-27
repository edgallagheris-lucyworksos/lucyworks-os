#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
changed = []
for path in sorted([*root.glob("*.yml"), *root.glob("*.yaml")]):
    text = path.read_text()
    updated = text.replace('node-version: "20"', 'node-version: "22"').replace("node-version: '20'", "node-version: '22'")
    if updated != text:
        path.write_text(updated)
        changed.append(str(path.relative_to(root.parents[1])))
if not changed:
    raise SystemExit("No Node 20 workflow pins remained")
print("Modernised Node workflow pins:")
print("\n".join(changed))
