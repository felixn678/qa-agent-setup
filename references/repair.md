# Repair guide: verify -> fix -> re-verify

`verify_setup.py` gives every failing check a `fix`:

| fix.kind | You do |
|---|---|
| `auto` | Run `verify_setup.py --fix`. Safe changes only: mkdir scratch, `.gitignore` lines, context stub. Report in one line. |
| `config` | Ask the user the check's question (offer the detected value first), then `qa_config_set.py <path> <answer>`. Batch all `config` items into ONE ask. |
| `user` | Show the exact steps, numbered, <= 3 lines each. Wait for "done", re-run. Never do these for the user. |
| `ask` | A whole section is missing: redo that interview group only. |

## Loop

1. `verify_setup.py --json` (or text). Read `ready`, `blocking`, checks.
2. Apply `auto` fixes. Batch `config` questions in one ask. List `user` steps together.
3. Re-run. Repeat until `ready: true`. Max 4 rounds; after that report what is left and stop.
4. Run `--live` once (opens the browser, checks login) and `--task <id>` once (reads a real task).
5. `--write` the final status. Tell the user: ready, or the 1-3 remaining items.

## Common failures

| Check | Usual cause | Fix |
|---|---|---|
| `net.vpn` / `net.*` unreachable | VPN off, wrong URL | connect VPN; verify URL |
| `net.local.frontend` | app not running | user runs `environments.local.start` |
| `secret.<VAR>` not set | token not exported | token guide in `interview.md` ("API token"); git-ignored env file or shell; never in chat. WARN when `auth.type: optional`: not blocking |
| `git.secret-not-tracked` | secret file committed | `git rm --cached`, rotate token |
| `auth.task-cli` | CLI not logged in | `az login` / `gh auth login` |
| machine tools missing (python3, PyYAML, node, Playwright, browser) | not installed | `check_prereqs.py` (report) then `--install` after the user agrees |
| `tool.playwright` | not installed | `npm install -g playwright` (ask first, global) |
| `tool.browser` | browser missing | pick another Chromium browser |
| `live.login` | profile not logged in / SSO expired | log in in the window, or set `login.mode: manual`; check `login.profile` (`browser.sh profiles <browser>`) |
| `live.attach` | Playwright missing / port taken | install it; change `debug_port` |
| `task.fetch` | wrong org/project, token, id pattern | fix `task_source`; try another id |
| `value.*` | answer missing | ask, then `qa_config_set.py` |

## During a QA run

Before planning, QA runs `verify_setup.py --quick`. A blocking item -> do the repair loop for that item
only, then continue the run. Do not restart the whole setup.

## Learn from runs

When a run hits a recurring trap (blocking dialog, slow table, flag needed, data missing), propose one
line for `frontend.app_notes` or `project-context.md`. Add it only after the user agrees.
