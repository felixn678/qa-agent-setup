# Knowledge: swallow docs and the codebase once, query cheaply later

Why: big specs and large codebases do not fit in context. Ingest once into a searchable digest;
read the small map first; pull only the passages a task needs.

## Ingest (setup step 2; re-run when docs change)

```
kb=<setup skill dir>/runner/scripts/kb.py   # in a generated agent: <agent dir>/scripts/kb.py
python3 $kb ingest <file|dir|glob> ...     # .md .mdx .txt .rst (+ .pdf if pdftotext exists). Prefer .md.
python3 $kb code .                         # codebase map + code search entries
python3 $kb status                         # indexed / stale
```

Docs: split by heading (<= 400 words/chunk), hashed (unchanged files skipped), 100k-word files take
~0.1s. Output in `.qa/knowledge/`: `index.md` (map), `rules.md`, `glossary.md`, `codebase-map.md`,
`chunks.jsonl` (git-ignore). PDFs/Word/Confluence/Notion: ask the user to export to `.md`.

## What the agent does after ingest

1. Read `index.md` (small), `glossary.md`, `rules.md` (skim), `codebase-map.md` (skim). NEVER open a big
   raw doc whole.
2. For each open question, `kb.py search "<topic>" --kind doc -n 5`; open `--full` only for the top hit.
3. Write `.qa/knowledge/overview.md`, <= 60 lines, facts only, each with its source:
   purpose and users, main flows, glossary (top 15 terms), rules that matter for testing, environments
   and how to run, known gotchas, where things live (routes, API prefixes, flags).
4. Use it to prefill the config profile; ask the user only what stays unknown. Put verified facts into
   `project-context.md`.

## How QA and implementers use it

- Terms in a task -> `glossary.md` / `kb.py search`. Screen or endpoint location -> `codebase-map.md`.
- Expected behavior when a task has no acceptance criteria -> the docs are an oracle (after the task
  text and design image). Cite `source:line` in the report.
- `knowledge.code_use: locate` (default): code only finds where things are; it never decides
  pass/fail. Set `oracle` only if the user wants code to define expected behavior.
- Implementation work: search the same index for conventions and rules before writing code.

## Hygiene

- Rule-like sentences in `rules.md` are candidates, not facts: verify before relying on them.
- Docs contradict each other or the live app -> report under "Needs decision", do not pick silently.
- Stale index (`kb.py status`) -> re-ingest before relying on it.
- No secrets in docs you ingest; if one shows up, tell the user and do not copy it anywhere.
