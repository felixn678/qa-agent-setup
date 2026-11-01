# Agent entry points

The QA playbook is the generated skill `<skill dir>/SKILL.md` (flow) and its `references/*.md`;
`<skill dir>` = `.claude/skills/<agent_name>` by default (`generate_agent.py --out` changes it). What differs per agent is only how it is *invoked* and how it *asks the user*.
Write the entry point for the runtime chosen in the interview (more than one is fine).

| Runtime | Invoke | What the setup writes | Asking the user |
|---|---|---|---|
| claude | `/<agent_name> <task>` (generated project skill in `.claude/skills/`) | nothing extra; optionally add a 3-line "QA" section to `CLAUDE.md` pointing at `.qa/qa.config.yaml` | `AskUserQuestion` |
| codex | "run QA on <task>" | `AGENTS.md` section (below); symlink or copy the skill folders into the agent's skills dir if it supports skills (`~/.codex/skills/`) | plain-text question, wait for the reply |
| gemini | "run QA on <task>" | `GEMINI.md` section (below) | plain-text question |
| cursor | rule | `.cursor/rules/qa.mdc` with the section below, `alwaysApply: false`, description "QA a task" | plain-text question |
| other | paste the section into whatever instruction file the agent reads | the section below | plain-text question |

## Section to write (AGENTS.md / GEMINI.md / rule file)

```markdown
## QA (task validation)
To validate a task against the running app, follow `<skill dir>/SKILL.md` and its
`references/` using this project's `.qa/qa.config.yaml` and `.qa/project-context.md`.
Scripts: `<skill dir>/scripts/` (fetch_task.py, api.py, frontend/browser.sh, lib.js).
Read-only against the tracker; never write secrets; ask before any write to a non-dev environment.
If `.qa/qa.config.yaml` is missing, run the `qa-agent-setup` skill first.
```

The generated skill folder is self-contained (scripts included): commit it and teammates need only
Python 3.9+ with PyYAML and Node with Playwright. For agents without a skills dir, pass
`generate_agent.py --out <dir>` and point the section above at that folder.

Set `agent.runtime` and `agent.ask_user_tool` in the config so the QA flow knows how to ask.
