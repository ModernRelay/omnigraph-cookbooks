# agent-ops seed: Harbor Labs

An invented engineering team, Harbor Labs, runs four agents on six workflows
around one repository, `harbor/ledger`. Every name, link, session id and
figure is made up; links use `.example` hosts. The runs fall between
20 October and 23 November 2026.

`seed.jsonl` holds 141 nodes and 316 edges:

| Type | Count | What |
|---|---|---|
| `Agent` | 4 | Runner (Claude Code), Support desk (a LangGraph service), Judge, Tuner |
| `Skill` | 7 | Code review, GitHub, reproducing a bug, support routing, Slack, judging a run, the agent-ops record |
| `Workflow` | 6 | `wf-review-pr`, `wf-reproduce-issue`, `wf-triage-support`, `wf-judge-runs`, `wf-tune-prompts`, `wf-weekly-report` |
| `Revision` | 8 | One active per workflow; `wf-review-pr-r1` retired; `wf-reproduce-issue-r2` rejected |
| `Trigger` | 7 | Two events (pull request, bug label), one manual, four schedules |
| `Criterion` | 5 | Two for reviews, two for reproductions, one for triage |
| `Run` | 27 | 25 succeeded, 1 failed, 1 still running |
| `Trace` | 25 | 21 from Claude Code, 4 from LangSmith |
| `Output` | 21 | 15 comments, 4 triage batches, 2 Slack messages |
| `Evaluation` | 31 | 30 by the Judge agent, 1 by a person |

## The story

**Pull request review.** Revision 1 ran on pull requests 401 to 406. The
Judge failed four of its six reviews on "Cites file and line", and a person
failed pull request 404 on "No style nits". On 10 November the Tuner proposed
revision 2, citing the line failures on 401, 403 and 404; a person activated
it on 11 November with the note "Matches how we review by hand." Revision 2
ran on 410 to 414: every judged review cites its lines, and 412 fails "No
style nits". Pull request 414 is not judged yet. The run for 415 started on 22
November and was never closed.

**Bug reproduction.** Revision 1 ran on issues 88 to 91. Issue 89 did not
reproduce because of a cached build, and the Tuner proposed a fresh container
per issue as revision 2. A person rejected it: a container adds six minutes
to every issue, and a clean worktree already avoids the cached build. The
first run for issue 90 failed on a missing tag and has no trace; its retry
succeeded. Issue 91's comment names "latest main" with no commit, a partial
on "Names the version".

**Support triage.** Hourly runs at 06:00 to 09:00 on 23 November, each
covering the hour before it, traced in LangSmith. The 08:00 run sent a refund
question to Platform; Billing owns refunds. The 09:00 run is not judged yet.
The next run is due at 10:00.

**Judging, tuning and reporting.** The Judge ran on 21 and 22 November and is
due again at 06:00 on 23 November. The Tuner ran on 10 and 17 November, which
produced the two proposals, and is next due on 30 November. The weekly report
was posted to Slack on 14 and 21 November and is next due on 27 November.

## What the featured questions return

| Question | Read | Rows |
|---|---|---|
| Did the last change to its instructions make a workflow better? | `revision_scorecard` with `{"workflow":"wf-review-pr"}` | Revision 1 (retired): 5 fail over 4 runs, 7 pass over 5 runs. Revision 2 (active): 1 fail over 1 run, 7 pass over 4 runs |
| Which criteria does each workflow fail under its current instructions? | `criterion_failures` | Four rows of one failure each: `crit-repro-script` and `crit-repro-version` (reproduction r1), `crit-review-no-style-nits` (review r2), `crit-triage-routes-owner` (triage r1) |
| What has each revision of each workflow cost to run? | `revision_cost` | Seven rows. Review r1: 6 runs, $2.38. Review r2: 5 runs, $2.57. Reproduction r1: 4 runs, $2.89. Judging: 2 runs, $3.16. Tuning: 2 runs, $3.09. Weekly report: 2 runs, $0.42. Triage: 4 runs, $0.152 |
| Which workflows are due to run? | `due_workflows` with `{"as_of":"2026-11-23T12:00:00Z"}` | `wf-judge-runs` (due 06:00) and `wf-triage-support` (due 10:00) |
| Which finished runs has nobody judged yet? | `runs_to_judge` | `wf-review-pr@pr-414` and `wf-triage-support@2026-11-23T09` |

## The other reads

With the parameters the `CLAUDE.md` examples use:

| Read | Rows |
|---|---|
| `workflows` | 6; `wf-review-pr` at revision 2, the rest at 1 |
| `workflow_triggers` (`wf-review-pr`) | 2: the manual trigger and the pull request event |
| `active_revision` (`wf-review-pr`) | `wf-review-pr-r2` |
| `workflow_skills` (`wf-review-pr`) | 2: code review, GitHub |
| `workflow_criteria` (`wf-review-pr`) | 2 |
| `agent_skills` (`agent-runner`) | 5 |
| `skill_users` (`skill-agent-ops`) | 3: judging, tuning, the weekly report |
| `recent_runs` (`wf-review-pr`) | 12, newest the running 415 |
| `run_traces`, `run_outputs`, `run_skills` (`wf-review-pr@pr-404`) | 1 Claude Code session at $0.44; 1 comment; 2 skills |
| `run_evaluations` (`wf-review-pr@pr-404`) | 2 fails: lines by the Judge, style nits by a person |
| `output_at` (pull request 412's link) | 1 comment, from `wf-review-pr@pr-412` |
| `failed_runs` (since 2026-11-16) | 1: `wf-reproduce-issue@issue-90`, `executor-error` |
| `stuck_runs` (before 2026-11-23) | 1: `wf-review-pr@pr-415` |
| `runs_without_trace` | 1: `wf-reproduce-issue@issue-90` |
| `last_covered` (`wf-triage-support`) | through 2026-11-23T09:00, over 4 runs |
| `workflow_scorecard` | 8 rows: 25 succeeded, 1 failed, 1 running |
| `agent_runs` (`agent-runner`) | 5 rows over review, reproduction and the report |
| `failures_to_answer` (`wf-review-pr`) | 1: style nits on 412 |
| `revision_history` (`wf-review-pr`) | 2: r1 retired, r2 active with its rationale and note |
| `revision_instructions` (`wf-review-pr-r2`) | r1's and r2's instructions side by side |
| `revision_evidence` (`wf-review-pr-r2`) | 3: the line failures on 401, 403, 404 |
| `proposed_revisions` | none on `main`; a proposal is read on its branch |
| `workflows_without_active_revision`, `workflows_with_several_active_revisions` | none |
