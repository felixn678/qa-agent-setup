# Backend validation (API calls)

Config used: `backend.services.*` (base_url, swagger_url, versions), `backend.auth`,
`backend.test_data`, `environments.*.mutation`, `workstreams.module_from`. Call through
`scripts/api.py <service> <env> <path> [--method M] [--data JSON|--data-file f] [--save f]`: it
resolves the host and secret itself and never prints the token. Show the equivalent `curl` in the
plan with the secret redacted (`Authorization: Bearer [REDACTED]`).

## 1. Extract the endpoint

From the task, in order: an "Example API Call" block (method, path, request/response payloads:
strongest signal), a Deliverables/parameters section, any inline `METHOD /path`. Nothing clear ->
ask the user; never infer a path from the title. Also collect parameters (type, required),
response fields and the Edge Cases section.

## 2. Criteria, derived cases, business rules

Always design the set with `scenario-design.md` (no AC, bug reports, risk cap, test charter); the notes below add the backend specifics.

Each distinct testable statement of the acceptance criteria is one criterion. No criteria ->
derive happy path + the edges the contract exposes (missing/invalid param, bad type, not-found id,
empty result, pagination/filter boundary, duplicate/conflict for writes), labelled `Derived (no AC)`;
an undefined expectation (400 vs 422, empty vs unfiltered list) is recorded as FLAGGED for the
product owner, not FAIL. Also collect every observable business rule the description states that
no criterion covers one-to-one ("only active records", "case-insensitive", "sorted desc"), label
them `Business rule (description)`, and test them when data allows; if not, report inconclusive.
Rules only verifiable internally are noted as `needs code review`.

## 3. Confirm against the OpenAPI/Swagger

Fetch `backend.services.<svc>.swagger_url.<env>` (or the OpenAPI JSON) and find the operation
(allow path-parameter naming differences). Compare parameters and response schema with the task.
- Several `versions`: check each version's Swagger; exactly one has it -> use it and say so; more
  than one -> ask; none -> say so and ask for the right path.
- No Swagger URL configured -> say it is missing and ask the user to confirm the contract.
- No matching operation -> report that fact first (the endpoint is not deployed in this
  environment): the criteria that need it are NOT COVERED/PENDING, and a real call showing the
  actual status (for example 404) is the evidence. Do not guess a path.
- Task and Swagger disagree -> flag it; trust Swagger (it reflects what is deployed) unless the
  user says otherwise, and say so out loud.
- Before calling ANY operation (under test, reference, regression) read its required query/path
  parameters from Swagger and fill them with valid values: a 422 from an omitted parameter is a
  planning mistake. Swagger's response docs are often incomplete (file downloads documented as
  JSON, missing error codes): validate against the task, do not report those gaps.

## 4. Scenarios

Per criterion/derived case/rule: label; the full command (method, URL from `base_url`, headers,
body); the expected status and shape in terms of what the criterion says. Happy path with realistic
values (from the example payload when present), plus each edge/error case the task implies
(invalid/missing param, not-found, auth failure, empty result, limit boundary, conflict). With
written criteria do not invent rules the task never stated. Use `[placeholder]` for values nobody
supplied.

## 4a. File responses

Save the body (`--save`), check `Content-Type`, `Content-Disposition`, filename. Parse it (for
example `openpyxl` for xlsx): sheets, headers, row counts, values, number formats. What a viewer
displays (locale-dependent formats, "opens without repair") is a visual criterion: ask the user to
open it, never pass/fail from the format code alone.

## 4b. Cross-check values against read endpoints

When criteria are about returned values (exports, reports, aggregates), compare cell by cell with
an existing GET that shows the same data. Calibrate first with 2-3 known values (scale 0.9 vs 90,
which id the path wants). Categorize mismatches (value / status / formatting) with one example each.
No reference endpoint -> that part is NOT COVERED.

## 4c. Regression criteria

"Same responses as before" needs the same read-only GETs with the same params in the previous-version
environment (usually `stg`) compared with the tested one. GET only; if unavailable or the data
differs too much, report partially verified.

## 5. Writes need a retrieve companion

For POST/PUT/PATCH/DELETE add a read scenario after the write that uses the id from the write's
response (placeholder `[id from create response]` while only planning) and asserts the fields
actually persisted. No GET exists -> say so and ask how to confirm; never skip silently.

## 5a. Criteria that need writes to be observed

Do not leave them PENDING by default: find the write operations in Swagger, read their required
params/body schema, and plan them as setup scenarios each followed by its read. Allowed only where
`mutation` is `allow` (or after separate confirmation for `ask`); in `forbid` environments report
PENDING (needs a write). Use `backend.test_data.sandbox` when the criterion needs no specific
entity and prefix created records with `backend.test_data.marker`. No documented request body or
an impossible precondition -> NOT COVERED with what is missing; never invent a body. List every
record created/changed/deleted (endpoint + id) in the report's Test data section.

## 6. Base URL and auth

`local` has no backend of its own: use `environments.local.backend_env`. Empty/`TODO` `base_url`
or a missing env var -> tell the user and stop before executing (a plan can still be shown).
Load `backend.auth.env_file` only to check the variable is set; never print the file or the value.
