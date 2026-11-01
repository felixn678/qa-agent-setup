# Report format

ASCII only (`-`, `->`, no arrows, smart quotes or em dashes). Plain text: no markdown tables, no
bold. Omit a section that is empty; keep the order. Ready to paste into the tracker (QA never posts it).

```
QA - <Frontend|Backend> <test|re-test> (<env>)
Screen: <area> > <screen> (<route>), <control used> -> <what opens>.        (backend: Endpoint: <METHOD> <path>, service/version)
Environment: <env> (<base url>); for local also "backend: <backend_env>". <entity used and its id>. <flags/roles/window widths>.
Scope: <what was tested; for a re-test, which earlier points it re-checks>.
Overall result: <PASS|FAIL|PENDING> - <one sentence: what failed / what still needs the user's review or decision>.

Failed                                   (a re-test uses "Previously failed - now fixed" for fixed items)
<AC/D/B/V/R id>. <criterion short name> - FAIL.
- <evidence: request sent, value observed vs expected, entity/row> [NN-name.png]

Passed / Re-checked
<AC no>. <criterion short name> - PASS.
- <evidence: exact request + params, measured values (px, counts), first row> [NN-name.png]
<criterion short name> - PENDING - visual review.
- <what was measured> [NN-name.png]

Needs decision                           (contradictions, undefined rules, behavior for the product owner)
- <item and what was observed>

N/A / Out of scope
- <criterion> - <why>

Not re-tested (passed on <date>, nothing indicates a change)      (re-tests only)
<criterion>.

Not covered
- <criterion/case> (<why: no data, backend not deployed, flag not switchable, needs a write>)

Notes
- <observations that are not criteria: data issues, visual oddities, environment problems>

Test data
- None. Read-only validation.            (or: every record created/changed/deleted: endpoint + id)

Screenshots
<folder path>
NN-name.png                              (one per line, same names as cited above)

OVERALL: <PASS|FAIL|PENDING>
AC1: <PASS|FAIL|PENDING|N/A|NOT COVERED>
AC2: <...>
```

Rules:
- Be brief: one line per evidence item, numbers over prose, no repeated context. The report must fit one screen when possible.
- Number each criterion with its acceptance-criterion number; derived or business-rule items use
  their ID from the test charter (`D1`, `B1` bug repro, `V1` bug variant, `R1` regression neighbor). Edge cases get their own short names.
- Every PASS/FAIL line carries concrete evidence, never just "works".
- The last lines are the verdict block, nothing after it. Per-criterion value: FAIL if any scenario
  failed; PENDING if nothing failed but it still needs the user's visual review or a decision;
  NOT COVERED if it could not be tested; N/A if the user marked it not applicable; PASS only when
  every scenario passed with evidence. OVERALL: FAIL if any FAIL, else PENDING if any PENDING or
  NOT COVERED, else PASS (N/A ignored). Keep the lines and the sections consistent.
- Screenshots are copied to `NN-short-slug.png` (00 = the page before any action) in one folder
  under the scratch dir and cited in square brackets right after the evidence they support.
- State the window width(s) used (frontend) or the exact host and API version (backend).
- Mocked responses, forced errors and flag overrides used in the browser are stated in Scope.
- A custom template (`report.format` = a path) replaces this layout but must still end with the
  OVERALL/ACn verdict block.
