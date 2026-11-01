# Scenario design (with or without acceptance criteria)

Goal: the smallest set of scenarios that catches the most risk. Not exhaustive. Cap: **<= 8** for a
small task, <= 15 for a big one. Say what was left out in one line.

## 1. Task kind (decides the method)

| Kind | Signs | Method |
|---|---|---|
| Feature with AC | numbered/Gherkin criteria | 1 scenario per AC + risks (step 4) |
| Feature, no AC | description/objective only | extract claims (step 2) -> derived AC |
| Bug report | "X happens, should be Y", repro steps, screenshot, error text | bug method (step 3) |
| Fix / regression | "fix", "no longer", links to a bug | bug method + regression neighbors |
| UI tweak | screenshot/mock, copy or style change | visual checks + states |
| One-liner / image only | a sentence, a screenshot | extract claims from the image + sentence; ask once |

## 2. Extract claims (no AC)

Read title, description, comments, images, linked items. Write each observable promise as one line:
`<actor> can/sees/gets <outcome> when <condition>`. Sources: verbs in the title, "should/must/can't",
UI text in images, field names, error text. Each claim = a derived criterion `D1, D2...`.
Mark the source (`title`, `description`, `image`, `comment`). A claim with no stated expected result is
`FLAGGED`, not a failure.

## 3. Bug method

1. **Pin the report:** steps, actual, expected, environment/version, account/data, frequency. Missing
   expected -> infer (oracles below) and mark `FLAGGED`.
2. **Reproduce first** on the target environment with the reported steps. Outcomes:
   - reproduced -> the bug still exists: the fix scenario FAILS with evidence (before-state).
   - not reproduced -> the fix works or data/version differs: continue, and note the data used.
   - cannot attempt (needs data/role you lack) -> NOT COVERED + what is needed.
3. **Verify the fix:** the original steps now give the expected result.
4. **Variants** (2-4): same bug at other inputs: boundary values, other role/entity, empty vs full,
   other browser width, after reload, repeat/double action.
5. **Regression neighbors** (1-3): the nearest feature sharing the same code path/screen/endpoint.
6. **Root-cause hint:** if it fails, record the exact request/response or console error. No guessing.

## 4. Risk ranking (add edge scenarios)

For each claim/AC ask: what breaks most likely and hurts most? Pick from this checklist, only items
that apply, highest risk first:

happy path - boundaries (0, 1, max, max+1) - empty/none - invalid input - repeat / double submit -
state change and reload (persists?) - cancel / back / refresh mid-flow - error path (4xx/5xx/network) -
permissions/roles - large data / slow - dependent data (filters, hidden items) - formats (dates,
numbers, long text, unicode) - responsive width - keyboard/focus basics.

Score each candidate impact x likelihood (H/M/L). Keep the top ones within the cap. Merge near-duplicates.

## 5. Oracles: what is "expected" when nobody wrote it

In order: 0) the user's testing notes (`how_to_test`, notes pasted with the request), 1) task text and comments, 2) design image/mock, 3) project docs (`kb.py search --kind doc`; cite
`source:line`), 4) the same behavior elsewhere in the app (consistency), 5) API contract (Swagger/OpenAPI,
schema), 6) platform/UI conventions, 7) ask the user. Source code is not an oracle unless
`knowledge.code_use: oracle`. Use 1-5 silently. For 6-7, collect all open points into ONE question with a recommended answer.
Unconfirmed -> `Needs decision`, never FAIL.

## 6. Output: the test charter (show before running, <= 1 screen)

```
ID    Source        Scenario                          Expected                     Pri
AC1   AC            ...                               ...                          H
D1    claim:title   ...                               ...                          H
B1    bug-repro     steps from report                 <expected, FLAGGED if inferred>  H
V1    bug-variant   same at boundary 0                ...                          M
R1    regression    neighbor feature X                unchanged                    M
Left out: <one line>
```

Then the pre-run review (contradictions, data coverage) and one go-ahead question. Report labels:
`ACn` for written criteria; `D1`, `B1`, `V1`, `R1` for derived ones (report-format.md).

## 7. Image-only or one-line tasks

Read the image: list every UI element, text and state it shows as claims. Compare the live screen to
it (structure, copy, states, colors, sizes). Ask once: "Expected result for X is not stated: is Y
right?" with Y as the recommended answer.
