# Step 0: the brief

Ask ONE open question first, before detection or any specific question. Let the user write
everything in one message; every part is optional and they can paste docs, links or notes.

## The prompt (keep it this short)

> Tell me about this project in your own words. Anything you know helps, skip what you don't:
> - what it is and who uses it
> - tech stack (frontend / backend / mobile / data)
> - how to run it locally, and which environments exist (dev, stage, prod)
> - where tasks live (Azure DevOps, Jira, ClickUp, GitHub, ... or just text + screenshots)
> - how you log in (SSO, VPN, test accounts)
> - what kinds of tasks you QA (features with acceptance criteria, bug reports, ...)
> - anything that usually goes wrong when testing
> - docs I should read first: a big `.md` spec, a `docs/` folder, notes (paths or paste), or "scan the repo"

If the user answers "just scan it", go straight to ingest + detection. Docs the user names go to
`knowledge.docs` and are ingested with `kb.py` (`knowledge.md`): their content then prefills the profile.

## Then: how-to-test notes

Right after the brief, ask once: "Describe how to test this project in as much detail as you like (flows,
accounts/data, expected results, known traps). Long is fine. Paste anything, or `skip`." Save verbatim to
`.qa/how-to-test.md` (strip secrets). It is the QA agent's first oracle for what "correct" means.

## Parse the brief into a profile

Map statements onto config keys. Mark each value `source: brief`. Detection fills the rest
(`source: code`). On conflict the brief wins; mention it in one line ("brief says port 3000, code
says 5173: using 3000").

| The user says | Sets |
|---|---|
| "React app, Python API" | `project.kinds`, framework notes in project-context |
| "run with `npm start`", port, URL | `environments.list.local.start`, `frontend_url` |
| "dev / stage / prod" | `environments.list.*`, mutation defaults (dev allow, stage ask, prod forbid) |
| "tasks in Jira / ADO / ..." | `task_source.type` + details |
| "we log in with Microsoft SSO", "needs VPN" | `frontend.login.*`, `network.vpn_required` |
| "bug reports, no acceptance criteria" | `project.task_style: [bug-reports]` and a rule: use `scenario-design.md` |
| "the table is virtualized", "toasts block the page" | `frontend.app_notes` |
| "backend has no per-user access control" | a fact in `project-context.md` |

## Save it

Write the user's words (trimmed, no secrets) under `## Project brief` at the top of
`.qa/project-context.md`. Later QA runs read it for context.

## Then ask only the gaps

After merging brief + detection, list what is still unknown and ask exactly those, grouped, with a
recommended option each (see `interview.md`). Never re-ask something the brief or the code answered.
Show the merged profile in <= 10 lines and let the user correct it in one reply.
