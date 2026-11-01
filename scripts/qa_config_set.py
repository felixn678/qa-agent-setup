"""Set ONE scalar value in .qa/qa.config.yaml by dotted path, keeping comments and layout.

Usage: python qa_config_set.py <dotted.path> <value> [--config file]
  python qa_config_set.py environments.list.local.frontend_url http://localhost:5173
Values: true/false/numbers stay unquoted; anything else is quoted. Handles block-style mappings and
inline `{ a: b }` maps one level deep. Anything else (lists, new keys) -> exit 2 with the line to edit
by hand. Never accepts a value for a key whose name looks like a secret.
"""
from __future__ import annotations

import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE if (_HERE / "qa_config.py").exists() else _HERE.parent / "runner" / "scripts"))
import qa_config  # noqa: E402

SECRET = re.compile(r"(token|secret|password|passwd|credential)$", re.I)


def fmt(value: str) -> str:
    if re.fullmatch(r"(true|false|null|-?\d+(\.\d+)?)", value):
        return value
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def set_value(text: str, dotted: str, value: str) -> str:
    keys = dotted.split(".")
    if SECRET.search(keys[-1]):
        sys.exit("refusing to store a secret value: put it in the git-ignored env file")
    lines = text.splitlines()
    parent_indent, start = -1, 0
    for level, key in enumerate(keys):
        found, child_indent = None, None
        for i in range(start, len(lines)):
            raw = lines[i]
            stripped = raw.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(stripped)
            if indent <= parent_indent:
                break  # left the parent block
            if child_indent is None:
                child_indent = indent  # first line inside the parent fixes the child level
            if indent == child_indent and re.match(rf"{re.escape(key)}\s*:", stripped):
                found = (i, indent)
                break
        if not found:
            sys.exit(f"key '{key}' not found under '{'.'.join(keys[:level]) or 'root'}': add it by hand in .qa/qa.config.yaml")
        i, indent = found
        if level == len(keys) - 1:
            m = re.match(rf"^(\s*{re.escape(key)}\s*:\s*)(\"[^\"]*\"|'[^']*'|[^#\n]*?)(\s*(#.*)?)$", lines[i])
            if not m or m.group(2).strip().startswith(("[", "{")) or not m.group(2).strip():
                sys.exit(f"'{dotted}' is not a plain scalar: edit line {i + 1} by hand")
            lines[i] = f"{m.group(1)}{fmt(value)}{m.group(3)}"
            return "\n".join(lines) + "\n"
        inline = re.match(rf"^(\s*{re.escape(key)}\s*:\s*)\{{(.*)\}}(\s*(#.*)?)$", lines[i])
        if inline and level == len(keys) - 2:
            leaf = keys[-1]
            body = inline.group(2)
            existing = re.search(rf"\b{re.escape(leaf)}\s*:\s*(\S)", body)
            if existing and existing.group(1) in "[{":
                sys.exit(f"'{dotted}' holds a list/map: edit line {i + 1} by hand")
            if existing:
                body = re.sub(rf"(\b{re.escape(leaf)}\s*:\s*)(\"[^\"]*\"|'[^']*'|[^,}}]+)", lambda mm: mm.group(1) + fmt(value), body, count=1)
            else:
                sys.exit(f"'{leaf}' missing in the inline map on line {i + 1}: edit it by hand")
            lines[i] = f"{inline.group(1)}{{{body}}}{inline.group(3)}"
            return "\n".join(lines) + "\n"
        parent_indent, start = indent, i + 1
    sys.exit("unreachable")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("value")
    parser.add_argument("--config")
    args = parser.parse_args()
    config = pathlib.Path(args.config) if args.config else qa_config.find_config()
    new = set_value(config.read_text(encoding="utf-8"), args.path, args.value)
    qa_config.yaml.safe_load(new)  # must still parse
    config.write_text(new, encoding="utf-8")
    print(f"set {args.path} = {fmt(args.value)}")


if __name__ == "__main__":
    main()
