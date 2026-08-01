#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"

PUBLIC_AUTH = {
    "apps/web/app/login/page.tsx",
    "apps/web/app/auth/callback/page.tsx",
}


def add_named_import(text: str, module: str, name: str) -> str:
    pattern = re.compile(rf'import \{{([^}}]+)\}} from "{re.escape(module)}";')
    match = pattern.search(text)
    if match:
        names = [item.strip() for item in match.group(1).split(",") if item.strip()]
        if name not in names:
            names.append(name)
            replacement = f'import {{ {", ".join(sorted(names))} }} from "{module}";'
            text = text[: match.start()] + replacement + text[match.end() :]
        return text

    anchor = '"use client";\n\n'
    import_line = f'import {{ {name} }} from "{module}";\n'
    if anchor in text:
        return text.replace(anchor, anchor + import_line, 1)
    return import_line + text


def remove_unused_api_base(text: str) -> str:
    if "API_BASE" in text:
        return text
    text = re.sub(r'^const API_BASE = process\.env\.NEXT_PUBLIC_API_BASE[^\n]*\n\n?', "", text, flags=re.MULTILINE)
    text = re.sub(r'import \{\s*API_BASE\s*\} from "@/lib/api-client";\n?', "", text)
    text = re.sub(r'import \{\s*API_BASE\s*\} from "@/lib/api";\n?', "", text)
    return text


def transform(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    original = path.read_text(encoding="utf-8")
    text = original

    if rel not in PUBLIC_AUTH and "fetch(`${API_BASE}" in text:
        # Static API_BASE template calls become authenticated path calls.
        text, count = re.subn(
            r'fetch\(`\$\{API_BASE\}([^`]*)`',
            lambda match: f'apiFetch(`{match.group(1)}`',
            text,
        )
        if count:
            text = add_named_import(text, "@/lib/api-client", "apiFetch")
            text = remove_unused_api_base(text)

    if "new Date().toISOString().slice(0, 10)" in text:
        text = text.replace("new Date().toISOString().slice(0, 10)", "localOperationalDate()")
        text = add_named_import(text, "@/lib/operational-date", "localOperationalDate")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(rel)
        return True
    return False


changed = [path for path in WEB.rglob("*.tsx") if transform(path)]
print(f"V31_CODEMOD_CHANGED={len(changed)}")
