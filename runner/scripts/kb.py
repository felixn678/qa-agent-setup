"""Project knowledge base for QA: swallow big docs and the codebase once, search them cheaply later.

Never loads a whole large file into the agent's context: docs are split by heading into chunks,
indexed (BM25, no dependencies), and queried by topic. Output lives in <knowledge dir>
(default .qa/knowledge/):
  chunks.jsonl    every doc chunk + one entry per source file (derived, git-ignore it)
  index.md        map of every source: headings + first sentence (small; read this first)
  rules.md        sentences that state rules (must/only/never/...) with their source
  glossary.md     defined terms
  codebase-map.md routes, API paths, feature flags, env vars, test ids, state, pages
  sources.json    hashes for incremental re-ingest
The agent then writes overview.md (<= 60 lines) from index.md + codebase-map.md.

Commands (run from the project root, or set QA_CONFIG):
  kb.py ingest <path|dir|glob> ... [--out DIR] [--max-words 400] [--force]   docs: .md .mdx .markdown .txt .rst (+ .pdf via pdftotext)
  kb.py code [root] [--out DIR]                                              codebase map + code search entries
  kb.py search "<query>" [-n 5] [--kind doc|code] [--full]                   top chunks with source#heading
  kb.py status                                                               what is indexed, what is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

DOC_EXT = {".md", ".mdx", ".markdown", ".txt", ".rst"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "venv", ".venv", "__pycache__", "coverage", "target", ".qa", "vendor", ".idea", ".vscode"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".py", ".java", ".kt", ".go", ".rs", ".cs", ".rb", ".php"}
STOP = set("a an the and or of to in on for with is are be as at by it this that from not no can will should must may if then else when which who what we you your our".split())
NOT_TERMS = {"example", "examples", "note", "notes", "warning", "tip", "usage", "important", "returns", "default", "type", "description", "see also"}
RULE = re.compile(r"\b(must|shall|should|only|never|always|cannot|can't|required|not allowed|forbidden|at least|at most|maximum|minimum|default)\b", re.I)


# ------------------------------------------------------------------ paths and config

def knowledge_dir(cli_out: str | None) -> pathlib.Path:
    if cli_out:
        return pathlib.Path(cli_out)
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        import qa_config
        cfg, root = qa_config.load()
        return root / ((cfg.get("knowledge") or {}).get("dir") or ".qa/knowledge")
    except SystemExit:
        return pathlib.Path(".qa/knowledge")


def project_root(kdir: pathlib.Path) -> pathlib.Path:
    return kdir.resolve().parent.parent if kdir.parent.name == ".qa" else pathlib.Path.cwd()


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9]{1,}|\d{2,}", text.lower()) if t not in STOP]


def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]


def read_text(path: pathlib.Path) -> str:
    if path.suffix == ".pdf":
        if not shutil.which("pdftotext"):
            print(f"skip {path}: pdftotext not installed (convert the PDF to .md)", file=sys.stderr)
            return ""
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout
    return path.read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------ doc chunking

def strip_front_matter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)


def chunk_markdown(text: str, max_words: int) -> list[dict]:
    """Split by headings (H1-H4), keep the heading path, split oversize sections by paragraph."""
    out, stack, buf, in_code = [], [], [], False
    start_line = 1

    def flush(end_line: int) -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        heading = " > ".join(h for _, h in stack) or "(top)"
        words = body.split()
        if len(words) <= max_words:
            out.append({"heading": heading, "text": body, "line": start_line})
            return
        paras, cur, count = re.split(r"\n\s*\n", body), [], 0
        for para in paras:
            n = len(para.split())
            if cur and count + n > max_words:
                out.append({"heading": heading, "text": "\n\n".join(cur), "line": start_line})
                cur, count = [], 0
            cur.append(para)
            count += n
        if cur:
            out.append({"heading": heading, "text": "\n\n".join(cur), "line": start_line})

    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,4})\s+(.*\S)\s*#*$", line)
        if m:
            flush(lineno)
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
            start_line = lineno
        else:
            buf.append(line)
    flush(len(text.splitlines()))
    return out


def chunk_plain(text: str, max_words: int) -> list[dict]:
    return chunk_markdown(re.sub(r"^([A-Z][^\n]{2,80})\n[=\-~]{3,}\s*$", r"# \1", text, flags=re.M), max_words)


def first_sentence(text: str) -> str:
    clean = re.sub(r"[`*_>#|\-]+", " ", re.sub(r"\s+", " ", re.sub(r"```.*?```", " ", text, flags=re.S))).strip()
    m = re.match(r"(.{20,200}?[.!?])(\s|$)", clean)
    return (m.group(1) if m else clean[:160]).strip()


def gather_docs(inputs: list[str], root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for item in inputs:
        p = pathlib.Path(item)
        if not p.is_absolute():
            p = root / p
        if p.is_dir():
            for dirpath, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                files += [pathlib.Path(dirpath) / n for n in names if pathlib.Path(n).suffix.lower() in DOC_EXT | {".pdf"}]
        elif p.is_file():
            files.append(p)
        else:
            files += [f for f in root.glob(item) if f.is_file()]
    return sorted(set(files))


def load_chunks(kdir: pathlib.Path) -> list[dict]:
    path = kdir / "chunks.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_chunks(kdir: pathlib.Path, chunks: list[dict]) -> None:
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "chunks.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n", encoding="utf-8")


def cmd_ingest(args) -> None:
    kdir = knowledge_dir(args.out)
    root = project_root(kdir)
    files = gather_docs(args.paths, root)
    if not files:
        sys.exit("no documents found for: " + " ".join(args.paths))
    sources_path = kdir / "sources.json"
    sources = json.loads(sources_path.read_text()) if sources_path.is_file() else {}
    chunks = [c for c in load_chunks(kdir)]
    kept = {c["source"] for c in chunks if c["kind"] == "doc"}
    changed = 0
    for f in files:
        rel = str(f.relative_to(root)) if f.is_relative_to(root) else str(f)
        text = read_text(f)
        digest = sha(text)
        if not args.force and sources.get(rel, {}).get("hash") == digest and rel in kept:
            continue
        chunks = [c for c in chunks if c["source"] != rel]
        body = strip_front_matter(text)
        pieces = chunk_markdown(body, args.max_words) if f.suffix.lower() in (".md", ".mdx", ".markdown") else chunk_plain(body, args.max_words)
        for i, piece in enumerate(pieces):
            chunks.append({"id": f"{rel}#{i}", "kind": "doc", "source": rel, "heading": piece["heading"], "line": piece["line"], "text": piece["text"]})
        sources[rel] = {"hash": digest, "words": len(text.split()), "chunks": len(pieces), "mtime": f.stat().st_mtime}
        changed += 1
    gone = [s for s in sources if not (root / s).exists() and not pathlib.Path(s).exists()]
    for s in gone:
        chunks = [c for c in chunks if c["source"] != s]
        sources.pop(s)
    save_chunks(kdir, chunks)
    sources_path.write_text(json.dumps(sources, indent=1), encoding="utf-8")
    write_doc_outputs(kdir, chunks, sources)
    docs = [c for c in chunks if c["kind"] == "doc"]
    print(f"ingested {changed}/{len(files)} changed docs -> {len(docs)} chunks, {sum(s['words'] for s in sources.values())} words total")
    print(f"read first: {kdir / 'index.md'} (map), then rules.md / glossary.md; query with: kb.py search \"<topic>\"")


def write_doc_outputs(kdir: pathlib.Path, chunks: list[dict], sources: dict) -> None:
    docs = [c for c in chunks if c["kind"] == "doc"]
    by_source: dict[str, list[dict]] = defaultdict(list)
    for c in docs:
        by_source[c["source"]].append(c)
    idx = ["# Knowledge index", "", "Map of ingested documents. Search for detail: `kb.py search \"<topic>\"`.", ""]
    for src, items in by_source.items():
        meta = sources.get(src, {})
        idx.append(f"## {src}  ({meta.get('words', '?')} words, {len(items)} chunks)")
        seen = set()
        for c in items:
            top = c["heading"].split(" > ")[:2]
            key = " > ".join(top)
            if key in seen:
                continue
            seen.add(key)
            idx.append(f"- {key}: {first_sentence(c['text'])}")
            if len(seen) >= 40:
                idx.append("- ...")
                break
        idx.append("")
    (kdir / "index.md").write_text("\n".join(idx), encoding="utf-8")

    rules, seen_rules = [], set()
    for c in docs:
        for sent in re.split(r"(?<=[.!?])\s+|\n[-*]\s+", c["text"]):
            s = re.sub(r"\s+", " ", sent).strip(" -*>")
            norm = re.sub(r"\d+", "#", s.lower())
            if 25 <= len(s) <= 260 and RULE.search(s) and norm not in seen_rules and not s.startswith(("```", "|")):
                seen_rules.add(norm)
                rules.append(f"- {s}  [{c['source']}:{c['line']}]")
    (kdir / "rules.md").write_text("# Rule-like statements (verify before relying on them)\n\n" + "\n".join(rules[:150]) + "\n", encoding="utf-8")

    glossary, seen_terms = [], set()
    pattern = re.compile(r"^\s*(?:[-*]\s+)?\*\*([^*\n]{2,40})\*\*\s*[:–—-]\s*(.{10,200})$|^\s*([A-Z][\w /]{1,35}):\s+(.{20,200})$", re.M)
    for c in docs:
        for m in pattern.finditer(c["text"]):
            term = (m.group(1) or m.group(3)).strip()
            if term.lower() not in seen_terms and term.lower() not in NOT_TERMS:
                seen_terms.add(term.lower())
                glossary.append(f"- **{term}**: {(m.group(2) or m.group(4)).strip()}  [{c['source']}]")
    (kdir / "glossary.md").write_text("# Terms defined in the docs\n\n" + "\n".join(glossary[:120]) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ codebase map

def walk_code(root: pathlib.Path, cap: int = 6000):
    n = 0
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in names:
            if pathlib.Path(name).suffix in CODE_EXT:
                n += 1
                if n > cap:
                    return
                yield pathlib.Path(dirpath) / name


def cmd_code(args) -> None:
    kdir = knowledge_dir(args.out)
    root = pathlib.Path(args.root).resolve()
    routes, apis, flags, envs, testids, slices, pages = set(), defaultdict(set), set(), set(), Counter(), set(), set()
    symbols_by_file: dict[str, list[str]] = {}
    dirs_count: Counter = Counter()
    for path in walk_code(root):
        rel = str(path.relative_to(root))
        parts = rel.split(os.sep)
        dirs_count["/".join(parts[:2]) if len(parts) > 2 else parts[0]] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
        except OSError:
            continue
        syms = [m.group(4) for m in re.finditer(r"(?m)^\s*export\s+(default\s+)?(async\s+)?(function|class|const|enum|interface|type)\s+(\w+)", text)]
        syms += [m.group(2) for m in re.finditer(r"(?m)^(def|class|func|fn)\s+(\w+)", text)]
        if syms:
            symbols_by_file[rel] = syms[:30]
        routes.update(m.group(1) or m.group(2) for m in re.finditer(r"""path:\s*["'`](/[^"'`\s]*)["'`]|<Route[^>]*path=["'`](/[^"'`\s]*)["'`]""", text))
        routes.update(m.group(2) for m in re.finditer(r"""@(\w*(?:Get|Post|Put|Patch|Delete|Request)Mapping|app\.(?:get|post|put|patch|delete)|router\.(?:get|post|put|patch|delete)|\w+\.(?:get|post|put|patch|delete))\(\s*["'`](/[^"'`]*)["'`]""", text))
        if re.search(r"(endpoint|api|service|client|request|http)", path.name, re.I):
            for m in re.finditer(r"""["'`](/[\w\-/{}:$.]{3,})["'`]""", text):
                apis[m.group(1)].add(rel)
        flags.update(m.group(1) for m in re.finditer(r"""(?:useFeatureFlagEnabled|isFeatureEnabled|featureFlag|useFlag|variation)\(\s*["'`]([\w.\-]+)["'`]""", text))
        for m in re.finditer(r"(?:process\.env|import\.meta\.env)\.(\w+)|os\.environ(?:\.get)?[\[(]\s*[\"'](\w+)", text):
            envs.add(m.group(1) or m.group(2))
        testids.update(re.findall(r"""data-test-?id=["'{`]+([\w\-:.]+)""", text))
        slices.update(re.findall(r"createSlice\(\{\s*name:\s*[\"'](\w+)", text))
        if re.search(r"(^|/)(pages|screens|views|routes|app)/", rel) and path.suffix in (".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js"):
            pages.add(rel)

    out = ["# Codebase map (generated; use to LOCATE things and learn terms, not as the source of expected behavior)", "",
           f"Root: {root.name}. Source files scanned: {sum(dirs_count.values())}.", "", "## Main folders (files)"]
    out += [f"- {d}: {n}" for d, n in dirs_count.most_common(25)]
    for title, items in (("Routes / endpoints defined", sorted(routes)), ("Feature flags read", sorted(flags)), ("Env vars referenced", sorted(envs)), ("State slices", sorted(slices))):
        out += ["", f"## {title} ({len(items)})"] + [f"- {i}" for i in items[:80]]
    out += ["", f"## API paths used by client code ({len(apis)})"] + [f"- {p}  <- {sorted(f)[0]}" for p, f in sorted(apis.items())[:100]]
    out += ["", f"## Screens / page files ({len(pages)})"] + [f"- {p}" for p in sorted(pages)[:80]]
    out += ["", f"## Test ids ({len(testids)})"] + [f"- {t} x{n}" for t, n in testids.most_common(40)]
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "codebase-map.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    chunks = [c for c in load_chunks(kdir) if c["kind"] != "code"]
    for rel, syms in symbols_by_file.items():
        chunks.append({"id": f"code:{rel}", "kind": "code", "source": rel, "heading": rel, "line": 1, "text": rel + " " + " ".join(syms)})
    save_chunks(kdir, chunks)
    print(f"wrote {kdir / 'codebase-map.md'}: {len(routes)} routes, {len(apis)} api paths, {len(flags)} flags, {len(pages)} page files, {len(symbols_by_file)} files indexed")


# ------------------------------------------------------------------ search (BM25)

def bm25(chunks: list[dict], query: str, k1: float = 1.4, b: float = 0.75) -> list[tuple[float, dict]]:
    docs = [tokens(c["heading"]) * 3 + tokens(c["text"]) for c in chunks]
    avg = sum(map(len, docs)) / max(len(docs), 1)
    df: Counter = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    q = tokens(query)
    scored = []
    for chunk, d in zip(chunks, docs):
        tf = Counter(d)
        score = 0.0
        for term in q:
            if term in tf:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(d) / avg))
        if score > 0:
            scored.append((score, chunk))
    return sorted(scored, key=lambda x: -x[0])


def cmd_search(args) -> None:
    kdir = knowledge_dir(args.out)
    chunks = [c for c in load_chunks(kdir) if not args.kind or c["kind"] == args.kind]
    if not chunks:
        sys.exit(f"no knowledge at {kdir}: run `kb.py ingest <docs>` / `kb.py code` first")
    hits = bm25(chunks, args.query)[: args.n]
    if not hits:
        print("no match. Try other words from the task or glossary.")
        return
    for score, c in hits:
        body = c["text"] if args.full else re.sub(r"\s+", " ", c["text"])[:380] + ("..." if len(c["text"]) > 380 else "")
        print(f"[{score:.1f}] {c['source']}:{c['line']}  # {c['heading']}\n{body}\n")


def cmd_status(args) -> None:
    kdir = knowledge_dir(args.out)
    root = project_root(kdir)
    sources_path = kdir / "sources.json"
    if not sources_path.is_file():
        print("no knowledge yet")
        return
    sources = json.loads(sources_path.read_text())
    stale = []
    for rel, meta in sources.items():
        p = root / rel if not pathlib.Path(rel).is_absolute() else pathlib.Path(rel)
        if not p.exists():
            stale.append(f"{rel} (deleted)")
        elif sha(read_text(p)) != meta["hash"]:
            stale.append(f"{rel} (changed)")
    chunks = load_chunks(kdir)
    print(f"docs: {len(sources)} sources, {sum(c['kind'] == 'doc' for c in chunks)} chunks; code entries: {sum(c['kind'] == 'code' for c in chunks)}")
    print("codebase map: " + ("yes" if (kdir / "codebase-map.md").is_file() else "no") + "; overview.md: " + ("yes" if (kdir / "overview.md").is_file() else "NO (agent should write it)"))
    print("stale: " + (", ".join(stale) if stale else "none") + (" -> re-run kb.py ingest" if stale else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest"); p.add_argument("paths", nargs="+"); p.add_argument("--out"); p.add_argument("--max-words", type=int, default=400); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("code"); p.add_argument("root", nargs="?", default="."); p.add_argument("--out"); p.set_defaults(fn=cmd_code)
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("-n", type=int, default=5); p.add_argument("--kind", choices=["doc", "code"]); p.add_argument("--full", action="store_true"); p.add_argument("--out"); p.set_defaults(fn=cmd_search)
    p = sub.add_parser("status"); p.add_argument("--out"); p.set_defaults(fn=cmd_status)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
