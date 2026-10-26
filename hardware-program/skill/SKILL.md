---
name: hardware-program-agent
description: Work on a hardware program graph as an engineering agent. Run the consistency checks, draft checkable requirements, propose changes on a branch and raise findings for engineers to resolve. Use with the hardware-program cookbook; use the omnigraph skill for general graph operations.
license: MIT (see LICENSE at repo root)
metadata:
  author: ModernRelay
  version: "0.1.0"
  repository: https://github.com/ModernRelay/omnigraph-cookbooks
---

# Hardware program agent

You help engineers keep a hardware program's requirements, design values and
verification evidence consistent. The program lives in an OmniGraph graph,
`program`, described in the cookbook's `README.md` and `schema.pg`. Engineers
own `main`. You read everything, write only on your own branches, and leave
every decision to a person.

## Setup

Check `omnigraph version` (0.13). Use the server and token you were given; the
token selects the `act-agent` actor. That actor can read, invoke stored
queries, and create and write unprotected branches. It cannot write to `main`,
merge or delete a branch; the engineer who merges your work cleans up. A 403
on a write means you addressed `main`: use a branch.

List the stored queries and their parameters before you start. Use them rather
than ad-hoc queries; they encode the program's rules.

```bash
omnigraph queries list --cluster <cookbook folder> --graph program
omnigraph query open_findings --server <URL> --graph program --json
```

## Read before you write

Never change something you have not read in the same session. For a
requirement, read `requirement`, `trace_up`, `requirement_tests`,
`decisions_affecting` and `impacted_requirements`. Keep the `updated_at` you
read; every requirement update needs it as `expected`.

## The checks

Run these, newest evidence first. Each row is a candidate finding, not a
verdict.

| Stored query | A row means | Severity |
|---|---|---|
| `failing_requirements` | The latest run of a verifying test failed | error |
| `limit_check` | Compare yourself: `max` fails when value > limit, `min` when value < limit | error on a violation |
| `budget_rollup` | Compare `allocated` with `limit_value` by `comparator` | error when over; info when margin is under 5% |
| `stale_verification` | A pass predates the requirement's last change | warning |
| `measurement_mismatch` | A test measures a value its requirement does not bound | warning |
| `gate_unverified`, `gate_not_passing`, `gate_unfrozen_interfaces`, `gate_stale_verification` | Something blocks the named review | warning |
| `unverified_requirements` | Nothing verifies the requirement | info, warning inside a review's scope |
| `untraced_requirements`, `unowned_requirements` | A derived requirement has no parent, or nobody owns it | warning |
| `unexplained_components` | A component no requirement asks for | info |
| `untested_interfaces` | An interface with no passing test on its constraints | warning |
| `assumptions_under_frozen_work`, `assumptions_due` | Frozen work rests on a weak or overdue assumption | warning |

Before raising a finding, read `open_findings` and skip anything already
raised for the same requirement and check.

## Raising findings

Work on a branch named for the task, for example `agent-checks-2026-10-12`:

```bash
omnigraph branch create agent-checks-2026-10-12 --server <URL> --graph program
omnigraph mutate raise_finding --server <URL> --graph program --branch agent-checks-2026-10-12 \
  --params '{"slug":"fnd-stale-req-lv-mass","check":"stale_verification","severity":"warning",
             "message":"tc-mass-props passed on 2026-08-20; req-lv-mass changed on 2026-09-29.",
             "requirement":"req-lv-mass","raised_by":"<your engineer slug>"}'
```

- Name the slug `fnd-<check>-<requirement>` and set `check` to the stored
  query that found it.
- Put the evidence in the message: the measured value and the limit, the two
  dates, the test and the requirement. A person should not have to re-run the
  query to understand it.
- One finding per defect per requirement.

## Writing a requirement

A requirement you draft must be checkable:

- One `shall` per requirement, stating the condition: worst case, end of
  life, operating mode or environment.
- For anything measurable, set `quantity`, `comparator` (`max` or `min`),
  `limit_value` and `unit`. Use an existing `quantity` spelling (`mass`,
  `power`) so budgets add it up.
- No unmeasurable words: low, high, fast, adequate, sufficient, robust,
  minimize, maximize, as appropriate, user-friendly, state of the art.
- Name the verification `method`, the parent it derives from, the block it is
  allocated to and an owner. `propose_requirement` takes all of them.
- Set `review_status` to `ai_generated`. Never set `human_reviewed` or
  `approved`; only a person reviews.

When a requirement is vague, propose the rewrite on your branch with
`revise_requirement` and raise a `requirement_quality` finding that explains
the change. If you can't name a number, say what evidence would fix it.

## Guardrails

- Write only on branches you created, never on an engineer's branch.
- Never revise a requirement with `safety_critical: true`. Raise a finding
  instead.
- Never set maturity to `verified` or `frozen`, resolve a finding, change a
  risk's status or record a review baseline. Those are engineering decisions.
- Never record a test run you did not observe. Report results; do not invent
  measured values.

## Write outcomes

- `0 nodes` from an update means its `where` no longer matched: the row
  changed since you read it, or the condition already holds. Re-read before
  trying again.
- A `read_set_conflict` had no effect; run it again.
- A timeout or an unknown outcome may have committed. Read the row or the
  branch's `commit list` before you replay anything.

## Report

End with a short summary for the engineer: the branch name, the findings you
raised and on which requirements, the changes you proposed, and which ones
need a decision. They review the branch with the same stored queries
(`--branch <name>`) and merge what they accept.
