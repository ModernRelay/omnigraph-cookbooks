# Design: the agent benchmark at scale

Status: run. The pilot and the full run are below, with what each changed in
the benchmark; [README.md](README.md#agent-cost-at-scale) has the results.
Measurements up to the pilot were taken on
2026-11-17 on one Mac (18 cores, 48 GiB) with the 0.14.0 `omnigraph` CLI; the
runs were on a dev box. `scale.py` builds the repository, graph, reference and questions;
`agent.py --suite vscode` sets up the arms and runs and scores the sessions.

## Why

On hono, an agent with no code graph answered all 24 sessions exactly.
Omnigraph cut cost by 16% and the other five tools saved nothing. hono
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

## Pilot

Run on 2026-11-17 on a dev box (64 GB, Node 24.22.3, Claude Code 2.1.316,
Sonnet 5.5) by `scale-run.sh pilot`, 64 minutes end to end, one session of
each of six questions in each of the four arms, 24 sessions for $5.00 at list
price. Its sessions are in `results/agent-scale-pilot.json`, its questions in
`scale-pilot-questions.json`. It measured the cost per session and checked
the protocol, and is not a result. What it changed:

- **The transitive key was wrong.** All four arms missed `transitive-1`, and
  the others named `ProtocolServerHandler` methods the key left out. Those
  are right: `_dispatchClientActionNow` calls `this._agentService.dispatchAction()`
  on an `IAgentService`, which runs `AgentService.dispatchAction`. The key
  followed direct calls only. The selector now continues a chain through a
  member to everything implementing it, which takes the key from 21 to 34
  definitions; `scale.py regrade-pilot` grades the pilot against it. It also
  now refuses a direct-call target that implements another member, whose
  callers have two readings, and ranks candidates by a hash so a rule change
  moves only the candidates it affects. `scale-questions.json` is the set for
  the full run.
- **A walk over two edge types meets two engine limits.** The engine admits
  it against every selected edge table's full row count on each probe:
  VS Code's 1.9 million edges exceed the default `traversal_work_limit` of 1
  million before any row is read, and a hub then needs more than the default
  150 MiB of `query_memory_bytes`. `cg` lifts the first and raises the second
  to 2 GiB for `impact` on a local graph. A server's stored query takes no
  session settings, so a served graph needs them raised on the server.
- **`impact` is every reference, not every call.** For the fourth transitive
  target, `logAuthenticationSessionResolution`, the key has 17 callers, but
  `impact` reaches 107,836 definitions, mostly through type uses, so the read
  stops at its 5,000-row limit and the alphabetical first 5,000 hold none of
  them. A walk over calls alone needs either a filter on each hop of a
  multi-hop traversal, which GQ does not have, or calls as an edge type of
  their own, beside `References`. Until then the agent has to follow `cg
  callers` itself.
- **Graph use is counted by tool.** The pilot's own summary counted `git` as
  a graph tool; `agent.py` no longer does.

Estimate for the full run from the pilot's mean session cost, $0.21: 480
sessions (24 questions, five sessions, four arms) at about $100 at list
price, about 2.5 hours of sessions plus an hour of setup.

## Full run

Run on 2026-11-18 on the dev box by `scale-run.sh full`: 24 questions, five
sessions each, four arms, 480 sessions from 03:51 to 07:12 UTC, with no
usage-limit stop and no session over its time limit. The API wrote a median
127 to 139 output tokens a second in every arm. Setup, each tool's first
index of 1.146.0 on the box: Omnigraph 6.5 min (scip-typescript 173 s,
convert 140 s, load 77 s), codegraph 10.1 min (606 s), Graphify 12.4 min
(744 s).

### What the run turned up before the scores

1. **The graph had no indexes.** The build loaded both releases with
   overwrite loads, which write every table without its indexes, and nothing
   ran `omnigraph optimize`, so every Omnigraph read scanned whole tables: on
   the box `cg members` took a median 48 s. `cg load` now runs `optimize`
   after a load onto `main` of a local graph. Omnigraph's arm was therefore
   run again on the optimized graph, in a second window beside its own
   no-graph arm, and that is the arm the scores report. The first window's
   results, `results/agent-scale.json`, hold no graph, codegraph and Graphify.
2. **Static members were missing from the graph.** scip-typescript gives a
   static method and a static property kinds of their own, which the
   converter's kind map did not include, so VS Code's graph lacked 1,751
   static methods and 3,651 static properties. An instance member sharing a
   static member's symbol went with it: `Color` has a static and an instance
   `equals`, and the graph had neither. The converter maps both kinds now. Two
   of the 24 questions touch a static member (`shared-name-2`'s target, and
   four entries of `construction-4`'s key); the scored graph ran without them.
3. **Keys needed correcting.** Every entry that most of a question's 20
   sessions disagreed with the key about was read in the source:
   - The compiler reference covered `src/vs/`, the questions `src/`.
     `src/server-main.ts` reaches `transitive-2`'s target through a
     dynamically imported `createServer`. The reference now covers `src/`.
   - VS Code reaches its services through dependency injection:
     `invokeFunction(fn)` calls `fn` and `createInstance(C)` constructs a `C`.
     The reference counted neither as a call. It counts both now, which adds
     one or two definitions to `transitive-1`, `-2`, `-3` and `construction-2`,
     each one most sessions had found.
   - With those calls counted, `transitive-4`'s chain reaches
     `BaseActionViewItem.render`, and through it every call that can dispatch
     to an override of it: 44,328 definitions. The question has no answer to
     list and is left out of the scores, which cover 23 questions.
   - `shared-name-2` asks for the callers of `Color`'s `equals`, which is two
     methods. The static one, which calls the instance one, and
     `Settings.equals`, which calls only the static one, count neither way.
     `TokenStyle.equals` calls the instance method on a value of type `any`
     narrowed by `instanceof`, which the reference does not resolve, and was
     added.
   - In `dispatch-1` and `dispatch-4`, anonymous classes declared inside a
     method override `render`. The reference does not model them, and the
     answer format does not say whether to name one by its file or by the
     method around it, so both spellings count neither way.
   - In `release-3` the file moved between the releases, and both methods the
     key named called `getSelection` at the old path. By path they gained the
     call and by code they did not, so they count neither way.

   `scale.py rekey` recomputes every key with the current rules for the
   questions the run asked, applies the hand-read corrections in
   `CORRECTIONS`, each with its note, and keeps the asked key as
   `asked_answer`. Under the new rules `questions` would pick a different set,
   so the asked set is the one in `scale-questions.json`.
4. **The scorer read only a session's last message.** One Omnigraph session
   answered, then replied to a late tool notification with "The answer above
   stands", and scored 0. The scorer now takes the last `ANSWER:` line in any
   of a session's messages; that changed only this session.
5. **The question selector depended on set order**: under different hash
   seeds it counted 849 or 850 transitive candidates. Each hop is now computed
   from whole sets, and two runs under different seeds write the same file as
   the one the run asked.

### The second window

Run on 2026-11-18 from 07:35 to 09:07 UTC on the same box. The build ran the
two loads again, each followed by `optimize` (72.5 s and 80.9 s), and no graph
and Omnigraph ran the same 24 questions five times each, 240 sessions, with no
usage-limit stop and no session over its time limit. The API wrote a median
138 output tokens a second for no graph and 126 for Omnigraph. Results are in
`results/agent-scale-window2.json`, scored against the corrected keys. `cg`
answered in a median 0.43 s for `callers`, 0.53 s for `find`, 0.47 s for
`impact` and 0.23 s for `members`; the slowest of its 453 calls took 4.0 s.

### Scores

Medians per session over the 23 scored questions, five sessions each, each
arm beside the no-graph arm of its own window:

| Arm | Window | Exact | Mean F1 | Cost | Wall time | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | first | 73 of 115 | 0.960 | $0.103 | 23.6 s | 2,744 | 8 | |
| codegraph | first | 73 of 115 | 0.960 | $0.112 | 42.2 s | 2,784 | 8 | 0.3% |
| Graphify | first | 68 of 115 | 0.949 | $0.121 | 25.4 s | 2,968 | 10 | 5% |
| No code graph | second | 69 of 115 | 0.951 | $0.091 | 22.9 s | 2,724 | 9 | |
| Omnigraph | second | 80 of 115 | 0.953 | $0.047 | 14.1 s | 1,455 | 5 | 36% |

Against the no-graph arm of the same window, question by question (geometric
mean of the ratio of medians, 95% bootstrap interval, questions where the arm
spent less):

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph | 0.52× [0.39, 0.69], 17 of 23 | 0.70× [0.57, 0.87], 16 | 0.64× [0.52, 0.80], 17 | 0.64× [0.48, 0.84], 15 |
| codegraph | 0.91× [0.83, 1.01], 16 of 23 | 1.88× [1.65, 2.13], 1 | 0.94× [0.86, 1.02], 12 | 1.04× [0.82, 1.49], 12 |
| Graphify | 1.12× [1.02, 1.22], 5 of 23 | 1.10× [1.02, 1.17], 3 | 1.05× [0.97, 1.13], 6 | 1.26× [1.05, 1.71], 6 |

Exact sessions by family:

| Family | No graph, first | codegraph | Graphify | No graph, second | Omnigraph | Omnigraph's cost | Omnigraph's wall time |
|---|---|---|---|---|---|---|---|
| Shared-name callers | 13 of 20 | 14 of 20 | 11 of 20 | 12 of 20 | 9 of 20 | 1.03× [0.98, 1.10] | 1.29× [1.14, 1.45] |
| Interface dispatch | 17 of 20 | 18 of 20 | 18 of 20 | 19 of 20 | 20 of 20 | 0.80× [0.66, 0.91] | 0.85× [0.72, 0.95] |
| Transitive callers | 1 of 15 | 1 of 15 | 0 of 15 | 0 of 15 | 0 of 15 | 0.17× [0.11, 0.25] | 0.31× [0.24, 0.45] |
| Constructions | 11 of 20 | 9 of 20 | 13 of 20 | 9 of 20 | 13 of 20 | 1.06× [0.89, 1.21] | 1.18× [0.97, 1.39] |
| Release changes | 12 of 20 | 11 of 20 | 7 of 20 | 11 of 20 | 18 of 20 | 0.30× [0.19, 0.41] | 0.45× [0.35, 0.54] |
| Controls | 19 of 20 | 20 of 20 | 19 of 20 | 18 of 20 | 20 of 20 | 0.36× [0.26, 0.44] | 0.56× [0.47, 0.65] |

The no-graph arm was exact in 73 sessions in one window and 69 in the other
with the same keys, which shows how far a count moves between runs.

The hypotheses:

1. **Correctness: refuted.** Without a graph, exactness fell on chains (0 and
   1 of 15) and on shared names (12 and 13 of 20), though not on dispatch (17
   and 19 of 20), as predicted. With Omnigraph it fell the same way, 0 of 15
   and 9 of 20. Only on release changes did Omnigraph's agents answer
   differently: 18 of 20, against 7 to 12, because `cg` reads both releases
   where the others diff text. On `release-4` the code calling `moveEditors`
   moved from `mergeGroup` into a new method, `doMergeGroup`; Omnigraph's five
   sessions named it, and none of the other arms' 20 did.
2. **Cost: refuted.** The rank correlation between a question's grep count
   and Omnigraph's cost ratio is +0.60, so the ratio rises with the lines a
   search returns, where the hypothesis said it would fall. Omnigraph saved
   most where one `cg` read answers: controls (0.36×), release changes
   (0.30×) and chains (0.17×, none exact). It saved least on dispatch (0.80×)
   and nothing on shared names and constructions (1.03× and 1.06×): `cg
   callers` of a class lists every reference to it, type annotations included,
   so on constructions the agents searched text for `new` anyway, 184
   searches to 37 `cg` calls.
3. **Name matching: not tested.** codegraph's agents called its tool for
   0.3% of their calls, Graphify's for 5%; both arms mostly searched text, as
   on hono.

Omnigraph's 35 inexact answers, by cause:

- **Chains (15).** `impact` follows every reference, not every call, so
  agents that trusted it took definitions that only reference the chain, and
  a class handed to `createInstance` is a reference to the class, not a call
  to its constructor, so `impact` does not reach a constructor called that
  way.
- **Shared names (11).** The graph lacked `Color.equals`, so all five
  `shared-name-2` sessions searched text for its callers; on `shared-name-1`
  and `shared-name-4` sessions left out or added one or two entries.
- **Constructions (7) and release changes (2).** One or two entries a
  session, such as a `createInstance` site left out of `construction-2`, static fields
  of `Color` and `PaneDraggable` that construct an `RGBA` in `construction-4`
  (the graph lacked `Color`'s), and `release-3`'s moved file.
- **`impact` from a hub ran out of memory.** All five Omnigraph sessions on
  `transitive-4`, the question left out of the scores, hit the 2 GiB
  `query_memory_bytes` limit, 18 times in all. OmniGraph 0.16 streams each
  traversal step's edge probe and fixes it.

## Build order

1. Fix the cookbook problems above, with tests (on #49). Done.
2. `scale.py fetch` and `build`: both releases as one git repository with two
   commits; index, convert and load both into Omnigraph (1.146.0 on `main`,
   1.145.0 on `v1.145.0`); the compiler reference of each. Done.
3. `scale.py questions`: the selector and the source check. Done; the pilot's
   six keys were also checked by hand.
4. Pilot (`scale-run.sh pilot`): one session of each family's first question in
   four arms, 24 sessions, on a dev box. Done; results above.
5. Index with the other three tools; record times and failures. Not done:
   their Linux installs are not scripted, so the full run had four arms.
6. Full run, 480 sessions, then a second window for no graph and Omnigraph
   on the optimized graph; scored, written up here, in `bench/README.md`
   (Results). Done.

## Limits

- One repository, one language, one model. VS Code favors a graph more than a
  repository with few interfaces would.
- Keys share the TypeScript compiler with scip-typescript, so they do not test
  Omnigraph's resolution, only what an agent does with it. Execution traces
  would, but VS Code's tests need its full build; they are left out.
- Questions are capped at 40 answers so they fit one read. Larger answer
  sets, where enumeration itself is the cost, are not measured.
- The keys were corrected after the runs, from reading the entries most
  sessions disagreed with. Two of the rules added then, calls through
  `invokeFunction` and constructions through `createInstance`, are VS Code's
  own idiom for dependency injection.
- Each window's arms ran side by side, but the two windows ran hours apart,
  so wall times compare within a window, not across.
