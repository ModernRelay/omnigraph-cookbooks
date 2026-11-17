# Design: the agent benchmark at scale

Status: built; the pilot runs from `scale-pilot.sh`. Measurements below were
taken on 2026-11-17 on one Mac (18 cores, 48 GiB) with the 0.14.0 `omnigraph`
CLI. `scale.py` builds the repository, graph, reference and questions;
`agent.py --suite vscode` sets up the arms and runs and scores the sessions.

## Why

On hono, an agent with no code graph answered all 24 sessions exactly.
Omnigraph cut cost by 16 to 23% and the other five tools saved nothing. hono
is 25,636 lines in 186 files, and its most shared name has 26 definitions, so
one text search returns a short list the agent can read. That benchmark could
not show what a graph is for: questions that text search answers badly.

## Hypotheses

Stated before any run, with what would refute each:

1. **Correctness.** Without a graph, exact answers fall on questions whose
   target's name has many definitions, that go through an interface, or that
   follow a chain of calls. With Omnigraph they stay exact. Refuted if the
   no-graph arm stays at 90% exact or more on those families.
2. **Cost.** Omnigraph's cost against no graph falls as the number of lines a
   text search returns grows. Refuted if the per-question ratio does not
   correlate with that count.
3. **Name matching.** Tools that resolve calls by name lose exactness on the
   shared-name family faster than Omnigraph.

## Repository: VS Code 1.146.0

MIT-licensed, released 2026-11-11. Its services are interfaces injected into
constructors, so most calls go through a type a name does not reveal, and it
reuses names heavily.

| | hono a10592f3 | VS Code 1.146.0 |
|---|---|---|
| Source files, outside tests | 186 | 7,898 |
| Lines, outside tests | 25,636 | 2,285,009 |
| Definitions in the graph | 3,316 | 817,999 (347,503 outside tests) |
| References | 5,752 | 1,872,018 |
| Most definitions of one name | 26 | 2,187 |
| Names with 50 or more definitions | 0 | 376 |

Text search gets hard fast: a search for `run(` outside tests returns 2,531
lines, `getValue(` 1,077 and `readFile(` 409, against 6, 5 and 246 actual
callers of the methods asked about.

The cookbook's pipeline runs at this size:

| Step | Time | Peak memory | Output |
|---|---|---|---|
| scip-typescript index | 3 min 25 s | 8.7 GB | 1.0 GB index; five oversized test files skipped |
| Convert (`build_seed.py`) | 2 min 5 s | 9.3 GB | 1.2 GB JSONL, 5.2 million rows |
| Load (`overwrite`) | 44 s | 8.4 GB | 0.76 GB graph; needs `--set write_max_bytes=8589934592` |
| Compiler reference (`reference.mjs`) | 1 min 30 s | 8.5 GB | 292,232 definitions, 1,447,942 references |
| `cg callers` on a hub | 0.6 to 1.8 s | | |
| `cg impact`, sixteen hops, on a hub | 2.2 to 14.7 s | | |

Alternatives considered: the TypeScript compiler keeps most of its code in
one closure, whose functions are locals with no symbol; Angular builds with
Bazel; Effect is mostly generic functions; Backstage's repository is 8 GB;
n8n and Grafana are not permissively licensed.

## What changed in the cookbook first

The probe found problems that would have decided answers, not measured them.
All are fixed on the cookbook's branch:

1. **Reads truncated silently.** `callers` stopped at 200 rows, `impact` at
   500 and `symbols_named` at 50, which `cg` then filtered by `--path`.
   `IFileService.readFile` has 246 callers outside tests and `run` has 1,097
   definitions. The limits are now 1,000 to 5,000, `cg` says when a read
   returns exactly its limit, and `symbols_named_in` filters by path inside
   the query.
2. **Loads over 32 MiB were refused** by `write_max_bytes`. `cg load` raises
   it to the file's size for a local graph and refuses such a file for a
   server, whose load request is capped.
3. **Keys did not start with their file's path** when the tsconfig is in a
   subfolder: scip-typescript writes symbol paths relative to the project.
   The converter now puts the project's folder in front of every key.

Two more facts the build turned up: a graph records its own absolute path, so
it cannot be built aside and moved; and the diff between the two releases is
large (84,046 symbols and 201,651 references added; `cg diff` prints 322,000
lines in 175 s), so the Omnigraph arm is told that every read also takes
`--branch v1.145.0`.

## Questions

Six families of four questions each, 24 in all, in `scale-questions.json`.
Every answer is a set of 3 to 40 definitions outside tests, so it fits one
read. `scale.py questions` picks them from the compiler reference with a fixed
seed, by rule, so they are not chosen by hand, and drops a candidate when any
key entry's own source text does not name the target (for a chain, a
definition on the chain). Candidates per family on 1.146.0: shared-name 673,
dispatch 411, transitive 4,503, construction 107, release 446, control 7,001.

| Family | Rule | Example candidate |
|---|---|---|
| Shared-name callers | A callable with 5 to 30 callers whose name has 50 or more definitions (733 candidates) | `AbstractTaskService.run`: 6 callers, 1,097 definitions of `run` |
| Interface dispatch | An interface method with 3 to 15 implementations (2,103 candidates); ask which bodies a named call site can run | `IFileService.readFile` |
| Transitive callers | Definitions reaching a callable through 4 to 8 references, 10 to 40 of them | chosen by the script |
| Constructions | A class constructed in 10 to 40 definitions | chosen by the script |
| Release changes | Definitions that gained or lost a call to a symbol between 1.145.0 and 1.146.0 | Omnigraph answers with `cg diff` |
| Controls | A callable with a unique name and 3 to 10 callers (2,797 candidates) | `deriveLegacyDefaultChat` |

The controls measure each tool's overhead where text search is enough. The
release family is the one only a graph with history answers directly; every
arm gets read-only `git log`, `git diff` and `git show` on a repository holding
both releases as commits.

Keys come from the compiler reference, as on hono. Over the definitions both
model, it and Omnigraph's graph agree on 98.7% of the reference's references
and 98.4% of the graph's, so a key differs from what `cg` reports for about
one reference in 60. A second script checks each
key entry against the source: the caller's text names the target. Every
disagreement between the reference and Omnigraph's graph is read by hand
before the runs.

## Arms

No code graph, Omnigraph, and the tools that index VS Code within 60 minutes
and 32 GB. Each of the five tools gets one indexing attempt first, which costs
no model time; an index that fails or runs over is a result. Agent sessions
run for no graph, Omnigraph and the two tools with the best hono recall that
index (codegraph and Graphify, if they do).

## Protocol

- Claude Code headless, Sonnet 5.5, the hono harness (`agent.py`) generalized
  to a repository, a revision and a question file.
- Five sessions per question and arm. All arms in one shuffled order in one
  window, one session per arm at a time, so API speed is shared.
- Per session: exactness, F1, turns, output tokens, cost, wall time, time on
  the API and output tokens per API second. If throughput drifts by more than
  20% across the run, wall time is reported only alongside it.
- Cost is reported as billed, with each session's cache-write tokens beside
  it. On hono a session that wrote 25k tokens to the cache cost $0.13 and one
  that wrote 4k cost $0.05 for the same answer. A cache-neutral cost cannot be
  derived from fixed price ratios: hono's Sonnet 5.5 sessions fit no single
  per-token price (the implied price ranges from $1.20 to $2.82 per million
  tokens), so it waits for the analysis.
- The per-question grep count, lines a search for the target's name returns,
  is recorded as the covariate for hypothesis 2.

## Analysis

Per family and arm: exact rate, mean F1, median cost and turns. Against no
graph: per question, the ratio of medians; per family and overall, the
geometric mean with a 95% bootstrap interval over questions. Hypothesis 2: the
rank correlation between the grep count and Omnigraph's cost ratio. Every
inexact answer is read and attributed (graph gap, truncated read, agent
error), as on hono.

## Cost and time

Sessions on VS Code will cost more than hono's $0.06 to $0.11. A pilot of the
six control and shared-name questions, one session each in four arms (24
sessions, about $5 to $10), measures the cost per session before the full
run. Estimated full run, four arms:

| Size | Sessions | At $0.20 a session | At $0.40 |
|---|---|---|---|
| 24 questions, 5 sessions | 480 | $96 | $192 |
| 24 questions, 3 sessions | 288 | $58 | $115 |
| 16 questions, 3 sessions | 192 | $38 | $77 |

With four arms running side by side and about a minute a session, 480 sessions
take about two hours.

## Build order

1. Fix the cookbook problems above, with tests (on #49). Done.
2. `scale.py fetch` and `build`: both releases as one git repository with two
   commits; index, convert and load both into Omnigraph (1.146.0 on `main`,
   1.145.0 on `v1.145.0`); the compiler reference of each. Done.
3. `scale.py questions`: the selector and the source check. Done; the pilot's
   six keys were also checked by hand.
4. Pilot (`scale-pilot.sh`): one session of each family's first question in
   four arms, 24 sessions, on a dev box with a stable network.
5. Index with the other three tools; record times and failures.
6. Decide the size of the full run; run, score, write up in `bench/README.md`
   and the cookbook README.

## Limits

- One repository, one language, one model. VS Code favors a graph more than a
  repository with few interfaces would.
- Keys share the TypeScript compiler with scip-typescript, so they do not test
  Omnigraph's resolution, only what an agent does with it. Execution traces
  would, but VS Code's tests need its full build; they are left out.
- Questions are capped at 40 answers so they fit one read. Larger answer
  sets, where enumeration itself is the cost, are not measured.
