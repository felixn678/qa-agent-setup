---
name: qa-agent-setup
description: Set up (and repair) a QA agent for ANY project, and generate it as a project-specific skill with a name the user picks (default qa-agent-<project>). Starts by asking for a free-form project brief, scans the codebase, asks only the remaining specific questions (task tracker, login/VPN, environments, browser, AI agent), writes .qa/qa.config.yaml + .qa/project-context.md, then self-verifies and self-repairs until a QA run can start. Use when the user wants QA set up for a project, QA fails because setup is missing or broken, or tracker/login/environment settings change. Run before qa-agent in a project without .qa/qa.config.yaml.
---

Goal: a working, project-named QA agent skill for this project with the fewest user steps. This is the only
skill to install: it generates the runner skill into the project.

## Style (hard rule)

Short and plain. Outcome first. No preamble, no recap, no "I will now...". One idea per line. At
most ~8 lines per message unless showing a checklist. Questions: one clear sentence + options. Say
what you did and what you need, nothing else.

## Output

```
.claude/skills/<agent_name>/  the generated QA agent: SKILL.md + scripts + references   (commit)
.qa/qa.config.yaml     what to run, where, how to log in, where tasks live   (commit, no secrets)
.qa/project-context.md brief + verified facts                                 (commit)
.qa/how-to-test.md     the user's own notes on how to test                    (commit)
.qa/knowledge/         doc + codebase digest (index, rules, glossary, map,    (commit all but chunks.jsonl)
                        overview.md)
.qa/extensions/        optional project helpers                               (commit)
.qa/runs/              scratch, screenshots                                   (git-ignored)
```

Schema: `assets/qa.config.template.yaml`. Scripts (`check_prereqs.py`, `detect_project.py`, `verify_setup.py`, `qa_config_set.py`, `generate_agent.py`): `scripts/` (python3 + PyYAML). Runner template: `runner/`.

## Flow

**Prerequisites first (before step 0/1).** Ask one question: "Do you already have python3 + PyYAML,
Node + Playwright and Edge/Chrome? **All OK** / **Not sure or missing: check and install for me**."
All OK -> continue. Otherwise run `scripts/check_prereqs.py` (read-only), show the result in <= 8 lines,
and ask once before changing the machine: "Install the missing ones?" Yes -> `check_prereqs.py --install`
(only PyYAML and the Playwright package; both are global/user-level, say so). Anything else it cannot
install (Python, Node, browser): show the exact command from its output and wait for "done". Re-run
until `READY`. Skip the question when the user already ran the check this session.

0. **Existing config?** If `.qa/qa.config.yaml` exists: run step 6 first, show the result, ask what to
   change. Never overwrite silently.
**Terminal tip (print this first, as is):**
```
TIP: the more detail you give, the better your QA agent. Write freely:
  - what the app does, who uses it, how to run and log in
  - HOW YOU TEST IT: main flows, test accounts/data, things that often break
  - paste long notes or a .md file path. No need to be neat.
```

1. **Brief + docs first.** Ask ONE open question (`references/brief.md`): what the project is, stack,
   how to run, environments, where tasks live, login/VPN, what tasks look like, known problems, and
   **any docs to swallow** (a big `.md` spec, `docs/` folder, notes; or "scan the repo docs").
   Save their words to `project-context.md` (no secrets).
   **How-to-test notes (one open question):** "Describe how to test this project in as much detail as
   you like: main flows, which account/data to use, expected results, known traps. Long is fine, paste
   anything, or `skip`." Save their words verbatim (no secrets) to `.qa/how-to-test.md`, set
   `project.how_to_test`, add the file to `knowledge.docs`. Skipped -> say once they can add it later
   (`verify_setup.py` shows a tip until the file has ~30 words).
2. **Ingest knowledge** (`references/knowledge.md`). `kb.py ingest <docs...>` (user's files + README,
   `docs/`, other `*.md`), `kb.py code .`. Read `index.md`, `codebase-map.md`, `rules.md`,
   `glossary.md` (never the raw big files), write `.qa/knowledge/overview.md` (<= 60 lines), and
   use what you learned to prefill the profile (stack, run command, login, environments, flags).
3. **Detect + merge.** Read `CLAUDE.md`/`AGENTS.md`, CI. Run `scripts/detect_project.py .`. Merge
   brief > docs > code (note conflicts in one line). See `references/detection.md`. Show the merged
   profile in <= 10 lines for one-reply correction.
4. **Ask only the gaps.** Specific questions (`references/interview.md`), grouped, max 4 per call,
   detected value first and marked "(Recommended)". Groups: task source; environments; access (VPN,
   login, **API token: required / optional / not needed**, with the token guide if required); tooling (browser, AI agent, flags); **agent name** (see below). Skip any group already answered.
5. **Write.** Fill the template from the profile; delete blocks the project does not need. Unknown
   -> `""`. Set `knowledge.docs`. Write `project-context.md`, create `.qa/runs/`, git-ignore
   `.qa/knowledge/chunks.jsonl`, write the agent entry point
   (`references/agent-entrypoints.md`). **Generate the agent:**
   `scripts/generate_agent.py --name <agent_name>` (copies `runner/` + checks into
   `.claude/skills/<agent_name>/`, records `project.agent_name`). Re-run it to update the agent.
6. **Verify and repair (loop, `references/repair.md`).**
   `scripts/verify_setup.py [--fix]`. It lists failing checks with a fix each:
   auto -> `--fix`; config -> ask the user (batched) then `scripts/qa_config_set.py <path> <value>`;
   user -> exact steps, wait for "done". Re-run until `READY` (max 4 rounds). Stale docs: `kb.py ingest` again.
7. **Live check.** `verify_setup.py --live` (opens the browser, checks it is logged in) and
   `--task <real id>` (reads a real task). Fix what fails the same way.
8. **Hand over (<= 6 lines).** Ready or not; how to run QA (`/<agent_name> <task>`); anything still open.
   Offer to commit `.claude/skills/<agent_name>/` and `.qa/` (never `runs/`, never secrets).

## Agent name

Ask in the same call as the tooling group: "What should we name this project's QA agent?" Options:
`qa-agent-<project-slug>` (Recommended; slug from `project.name` or the repo folder), `qa-<project-slug>`,
other. It becomes the folder and the slash command. Rules: lowercase, digits, dashes, 3-48 chars; never
`qa-agent` or `qa-agent-setup`. Changing it later: re-run `generate_agent.py --name <new>` and delete the old folder.

## Rules

- Never write, read aloud or ask for a secret value. Config holds only the env var NAME.
- Never invent a URL, port, login step or tracker field. Unknown stays `""` and is reported.
- Never start the user's app, log in for them, or touch project source. Only `.qa/`, `.gitignore`,
  the generated agent folder and the agent entry-point file.
- The user's answer beats detection. Ask each fact once.
- Auto-fix only safe things (mkdir, .gitignore, stub). Anything else needs the user.
- Missing capability (new tracker, custom login) -> add a helper in `.qa/extensions/` and say so.
