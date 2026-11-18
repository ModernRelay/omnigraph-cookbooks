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

## Pilot results

Run on 2026-11-17 on a dev box (64 GB, Node 24.22.3, Claude Code 2.1.316,
Sonnet 5.5) by `scale-pilot.sh`, 64 minutes end to end. Results are in
`results/agent-scale-pilot.json`, the six questions it asked in
`scale-pilot-questions.json`. One session per question and arm, so these are
directions, not measurements.

Setup, each tool's first index of the whole repository on the box: Omnigraph
11 min (scip-typescript 309 s, convert 224 s, load 123 s), codegraph 13 min
(785 s), Graphify 17 min (1,018 s). All four arms set up within budget, and
the API's speed stayed between 108 and 156 output tokens a second across the
24 sessions, so the wall times are comparable.

| Arm | Exact, regraded | Mean F1, regraded | Median cost | Median turns | Median output tokens | Median wall time |
|---|---|---|---|---|---|---|
| No code graph | 5 of 6 | 0.952 | $0.158 | 8 | 2,460 | 19.5 s |
| Omnigraph | 5 of 6 | 0.931 | $0.125 | 5.5 | 1,183 | 22.9 s |
| codegraph | 5 of 6 | 0.953 | $0.177 | 7 | 2,552 | 43.4 s |
| Graphify | 5 of 6 | 0.981 | $0.194 | 9.5 | 2,871 | 24.5 s |

Against no graph, question by question: Omnigraph 0.70× the cost (lower on 4
of 6), 0.53× the output tokens and 0.61× the turns; codegraph 0.99× the cost
and 1.99× the wall time, its hook adding about 25 s a session; Graphify 1.00×.
The costs are list prices; box sessions run on the Max plan. The 24 sessions
came to $5.00 at list price.

What the six questions showed:

- **Five questions every arm answered exactly.** On the release question
  Omnigraph's agent compared `cg callers` on both branches in 5 turns for
  $0.109; the others diffed with git in 13 to 20 turns for $0.27 to $0.30. On
  the shared-name and control questions it also cost least. On the dispatch
  and construction questions, which one text search answers, it cost about
  the same or more.
- **The transitive key was wrong.** All four arms missed `transitive-1`, and
  the others named `ProtocolServerHandler` methods the key left out. Those
  are right: `_dispatchClientActionNow` calls `this._agentService.dispatchAction()`
  on an `IAgentService`, which runs `AgentService.dispatchAction`. The key
  followed direct calls only. The selector now continues a chain through a
  member to everything implementing it, which takes the key from 21 to 34
  definitions; `scale.py regrade-pilot` grades the pilot against it. It also
  now refuses a direct-call target that implements another member, whose
  callers have two readings, and ranks candidates by a hash so a rule change
  moves only the candidates it affects. `scale-questions.json` is the new set
  for the full run.
- **Omnigraph is last on that question once regraded** (F1 0.58; Graphify
  0.89, codegraph 0.72, no graph 0.71), with precision 1.00 and recall 0.41.
  `impact` follows `References` only. A call through an injected interface
  references the interface member, and `Implements` points from the
  implementation to it; GQ 0.14 cannot walk one member of a multi-hop
  alternation backwards, so `impact` cannot reach the implementation. This is
  a gap in the cookbook's model, not in the engine. Two ways to close it: a
  derived edge from an interface member to each implementation, walked as
  `references | dispatches`, or `Implements` reversed.
- **Graph use.** Omnigraph's agents ran `cg` for 12 of their 45 tool calls
  (27%; on hono, about half). codegraph's and Graphify's agents ran their
  tools for 0 and 1 of 59 and 68. The share counted `git` as a graph tool in
  the pilot's own summary; `agent.py` no longer does.

Estimate for the full run from the pilot's mean session cost, $0.21: 480
sessions (24 questions, five sessions, four arms) at about $100 at list
price, about 2.5 hours of sessions plus an hour of setup.

## Build order

1. Fix the cookbook problems above, with tests (on #49). Done.
2. `scale.py fetch` and `build`: both releases as one git repository with two
   commits; index, convert and load both into Omnigraph (1.146.0 on `main`,
   1.145.0 on `v1.145.0`); the compiler reference of each. Done.
3. `scale.py questions`: the selector and the source check. Done; the pilot's
   six keys were also checked by hand.
4. Pilot (`scale-pilot.sh`): one session of each family's first question in
   four arms, 24 sessions, on a dev box. Done; results above.
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
