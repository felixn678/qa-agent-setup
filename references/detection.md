# Reading the detection output

`detect_project.py` prints facts. Convert each into a *proposal* with a confidence, then let the
user confirm. High = state it and move on; medium = recommended option; low = ask open.

| Signal in the output | Proposal | Confidence | Verify by |
|---|---|---|---|
| `git.remote_host` = azure-devops / github / gitlab / bitbucket | tracker type azure-devops / github / (gitlab issues: manual) / (jira likely) | medium | ticket pattern counts, user answer |
| `ticket_pattern_counts.azure_ab > 0` or numeric ids in branch names | Azure DevOps ids (numeric) | high | |
| `jira_like` high | Jira keys `ABC-123` | high (Linear also uses this shape: ask) | remote host, README |
| `clickup_cu > 0` | ClickUp | high | |
| `node.scripts.start/dev` + `ports_in_scripts` / `docker_compose.ports` / `.env` PORT | local frontend URL `http://localhost:<port>` and start command `<pm> run <script>` | medium | open the dev-server config (vite/webpack/next) for the real port |
| `.env*` url-like keys (`*_URL`, `*_HOST`, `*_API*`) | candidate backend base URLs per environment | low-medium | match host names across `.env.development`/`.env.production` |
| `.env.local` untracked + a TOKEN-like key | the project already keeps secrets in a git-ignored file: reuse its name as `env_file` and the key as `env_var` | medium | `git check-ignore .env.local` |
| `node.auth_libs` msal / auth0 / next-auth / keycloak / okta / clerk / firebase | SSO login, so use the profile-copy or manual login; never script credentials | high | README login section |
| `node.feature_flags` posthog / launchdarkly / growthbook | flag provider; ask what QA may do when a flag is off | high | grep the flag hook name used in code |
| `node.ui_test_tools` playwright / cypress | existing e2e tooling: mention it, still use the QA agent's CDP flow; reuse its base URL/auth storage if present | medium | `playwright.config.*` baseURL |
| `openapi_files` or `swagger_route_hints` | OpenAPI exists: backend scenarios can be checked against it. Route hints like `/docs` mean `<base>/docs` | medium | fetch it |
| `python_backend` fastapi -> `/docs` and `/openapi.json`; django (drf-spectacular) -> `/api/schema/`; spring -> `/v3/api-docs`, `/swagger-ui.html`; nest -> `/api` or `/docs` | candidate Swagger URL per service | low-medium | request it once reachable |
| no backend code, only a client calling a remote API | `project.kinds: [frontend]`; the backend is a remote service: ask for its dev URL and Swagger | high | |
| `file_based_routing_dirs` / `routes_sample` | list of screens for mapping task text to routes (used by QA to ask the user, not to guess) | low | the live app |
| `vpn_hints` non-empty, or an internal host in env urls (`*.internal`, corp domains) | VPN likely | medium | ask; setup verifies reachability |
| `tools_on_path.az` / `gh` / `jira` | task CLI available | high | `az account show`, `gh auth status` |
| `browsers` | default to an installed Chromium browser (Edge or Chrome) | high | |
| `tools_on_path.claude` / `codex` / `gemini`, `agent_files` (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursor`) | agent runtime(s) in use | medium | ask when more than one |
| `ci` pipelines | environment names (`dev`/`stage`/`prod`), deploy branches | medium | confirm names |
| `default_branches` includes `stage`/`staging` | a staging environment probably exists | low | ask |
| `existing_qa_config` true | update mode, not a fresh setup | high | |
| `playwright_global_or_local` null | tell the user Playwright is installed globally on first QA run (persistent change: say so before) | high | |

## Things code never tells you (always ask, never infer)

VPN requirement, SSO/MFA and which account to use, which environments QA may write to, the
sandbox entity, how tasks are classified, where acceptance criteria are written, the user's
preferred browser profile, the AI agent they run, and project-specific "known data" facts.

## Facts to put in `project-context.md`

Only facts someone verified (the user said it, or you observed it). Examples: "The backend has no
per-user access control: any valid token reads any entity", "Sandbox entity `0000` is for writes",
"Dates in dev are frozen at 2026-02-20", "Success and error messages are blocking dialogs". Keep it
under ~30 lines, one bullet per fact, no instructions.

## Docs beat guesses

After `kb.py ingest`, search before asking: `kb.py search "how to run locally"`, `"login"`, `"environments"`,
`"VPN"`, `"test accounts"`. A documented answer is a medium-high confidence proposal; still show it for
one-reply confirmation.
