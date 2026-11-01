# Interview question bank

Run AFTER the brief (`brief.md`) and detection. Ask only what both could not settle. Put the detected value first and mark it
"(Recommended)". One `AskUserQuestion` call = up to 4 questions. Questions marked [skip-if] are
omitted when the condition holds; confirm the value in your summary instead.

## 1. Task source

| Question | Options | Maps to |
|---|---|---|
| Where do tasks live? [skip-if git remote host + ticket pattern agree and user did not mention otherwise: still confirm in one line] | Azure DevOps / Jira / ClickUp / GitHub Issues / Linear / No tracker: I paste a description (+ images) | `task_source.type` |
| How should QA read a task? | CLI already logged in (`az`, `gh`) / API token in an env var / The tracker's MCP server in this agent / I will paste it | `task_source.auth.method`; for env-token ask the variable NAME and file (`env_file`) |
| What identifies a task in your requests? | Numeric id / `KEY-123` / full URL / free text | `task_source.id_pattern` |
| Tracker details: org + project (Azure), site url (Jira), team id (ClickUp), repo (GitHub) | free text, prefilled from the git remote | `task_source.*` |
| How are tasks classified into frontend/backend work? | Labels/tags / title prefixes like `[FE]` `[BE]` / Area/component field / I will say it each time | `workstreams.*` |
| Which task types or labels must QA refuse and stop on? (e.g. data engineering) | free text / none | `workstreams.unsupported` |
| What do your tasks look like? | Features with acceptance criteria / bug reports / screenshots or one-liners only / mixed | `project.task_style` (drives `scenario-design.md`) |
| Where are acceptance criteria written? | A dedicated field / a heading in the description / not written (derive them) | `task_source.acceptance_field` or heading rule |

QA is read-only against the tracker by default. Only change `read_only` if the user asks explicitly.

## 2. Environments

| Question | Options | Maps to |
|---|---|---|
| Which environments exist? | multi-select: local, dev, test/stg, prod, other (name them) | `environments.list.*` |
| Which is the default when the request names none? | recommended: local if it exists, else the lowest shared one | `environments.default` |
| For each environment: frontend URL (and how to start local) | prefilled from `.env*`/dev-server config | `<env>.frontend_url`, `local.start` |
| What does "local" use as its backend? | The dev backend (Recommended when no backend code is in the repo) / a local backend I run / mocked API | `local.backend_env` |
| May QA create/update/delete data? per env | Yes / Ask each time / Never. Recommend: dev yes, stg ask, prod never | `<env>.mutation` |
| Is there a safe sandbox entity for writes? | id/name / none | `backend.test_data.sandbox` |
| Backend services and where Swagger/OpenAPI lives, per env | urls / "code only: no OpenAPI" | `backend.services.*` |
| Only a frontend task description and images, no backend calls? | frontend-only project (drop `backend`) | `project.kinds` |

## 3. Access

| Question | Options | Maps to |
|---|---|---|
| Is a VPN needed to reach the app/API/tracker? | Yes / No / Only for some environments | `network.vpn_required` |
| A URL that only answers on the VPN (for the check)? | url / none | `network.vpn_check_url` |
| How do you log in to the app? | SSO (Microsoft/Okta/Google), with MFA / email+password / magic link / none | `frontend.login.sso` |
| How should QA get a logged-in browser? | Copy my logged-in browser profile (Recommended: no typing credentials) / I log in by hand each run / stored auth state file | `frontend.login.mode`, profile name |
| Any notice/dialog that appears after login or reload? (terms, cookie banner, tour) | button text / none | `frontend.post_login_steps` |
| How does the backend authenticate API calls? | Bearer token in a header / API key header / cookie / none | `backend.auth` |
| Is an API token needed for QA? | Required (API checks matter) / Optional (screen-only testing is fine) / Not needed (public or no auth) | `backend.auth.type`: `header` / `optional` / `none` |
| Required or optional: name of the env var that holds it, and the git-ignored file | e.g. `API_TOKEN`, `.env.local` | `backend.auth.env_var`, `env_file` |

### API token (guide the user)

Optional -> set `type: optional`, tell them: "QA tests on screen only; API/Swagger checks are marked
NOT COVERED. Add a token later any time." Do not block setup on it.

Required (or they want API checks) -> ask which kind they have, then give the steps (<= 4 lines):
- Personal/service token from the system's settings (Azure DevOps: User settings > Personal access
  tokens; GitHub: Settings > Developer settings > tokens; Jira/Atlassian: id.atlassian.com > API tokens).
- Bearer token the app itself uses (short-lived): log in, DevTools > Network > any API call >
  Request Headers > `Authorization`, copy the part after `Bearer `. Say it expires; ask how to refresh.
- Unknown: ask the backend team for a dev token, or read the project docs (`kb.py search "token"`).

Store it without echoing it, in a git-ignored file (tell the user to run it themselves with `!`):
`read -rs T && printf 'API_TOKEN=%s\n' "$T" >> .env.local && unset T` (then check `git check-ignore .env.local`).
`verify_setup.py` confirms it is set (never prints it).

Never ask for, accept, or store the secret itself. If the user pastes one, do not repeat it and
tell them to put it in the env file.

## 4. Tooling and conventions

| Question | Options | Maps to |
|---|---|---|
| Which browser? | Edge / Chrome (installed ones first; any Chromium works over CDP) | `frontend.browser` |
| What should we name this project's QA agent? | `qa-agent-<project>` (Recommended) / `qa-<project>` / custom | `project.agent_name`, generated skill folder |
| Which AI agent runs QA? | Claude Code / Codex / Gemini CLI / Cursor / other | `agent.runtime`, entry point files |
| Feature flags: provider, and what may QA do when the needed flag is off? | posthog/launchdarkly/env/none; mock locally only / ask the user / stop | `frontend.feature_flags` |
| Report language and format | default verdict-block format (Recommended) / my template (path) | `report.*` |
| Known traps and project rules? | free text: blocking toasts, virtualized tables, slow data, test accounts... | `frontend.app_notes`, `rules`, `project-context.md` |
| Project facts that change how results are judged? | e.g. "no per-user access control", "month data is stale", "sandbox 0000" | `project-context.md` |

## Question hygiene

- Ask each fact once. Do not re-ask what an earlier answer implies (no VPN -> no probe url).
- If the user says "you decide", take the recommended option and list it in the hand-over.
- When an answer needs a value you cannot verify now (a token not yet exported), write the config
  with the variable NAME, mark it in the hand-over, and let `verify_setup.py` report it.
