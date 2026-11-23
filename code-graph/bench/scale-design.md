# Design: the agent benchmark at scale

Status: run. The pilot and the full run are below, with what each changed in
the cookbook and the benchmark. Measurements up to the pilot were taken on
2026-11-17 on one Mac (18 cores, 48 GiB) with the 0.14.0 `omnigraph` CLI; the
runs were on a dev box. `scale.py` builds the repository, graph, reference and questions;
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
Sonnet 5.5) by `scale-run.sh pilot`, 64 minutes end to end. Results are in
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
- **Omnigraph was last on that question once regraded** (F1 0.58; Graphify
  0.89, codegraph 0.72, no graph 0.71), with precision 1.00 and recall 0.41.
  `impact` follows `References` only. A call through an injected interface
  references the interface member, and `Implements` points from the
  implementation to it; GQ 0.14 cannot walk one member of a multi-hop
  alternation backwards, so `impact` cannot reach the implementation. This is
  a gap in the cookbook's model, not in the engine. Two ways to close it: a
  derived edge from an interface member to each implementation, walked as
  `references | dispatches`, or `Implements` reversed.
- **Fixed since:** `Implements` is now `ImplementedBy`, from the interface
  or base member to each implementation, the way a call goes, and `impact`
  walks `(references | implementedBy){1,16}`. On the rebuilt graph, `impact`
  on the pilot's transitive target returns all 34 of the corrected key, in
  66 rows and 3.7 s, and on the full run's four transitive targets 10 of 10,
  18 of 18, 32 of 32 and 0 of 17. The agents have not been rerun on it.
  Two engine limits came with the walk over two edge types. The engine
  admits it against every selected edge table's full row count on each
  probe: VS Code's 1.9 million edges exceed the default
  `traversal_work_limit` of 1 million before any row is read, and a hub then
  needs more than the default 150 MiB of `query_memory_bytes`. `cg` lifts the
  first and raises the second to 2 GiB for `impact` on a local graph; a hub
  then takes about 34 s. A server's stored query takes no session settings,
  so a served graph needs them raised on the server.
- **Still open: `impact` is every reference, not every call.** For the fourth
  transitive target, `logAuthenticationSessionResolution`, the key has 17
  callers, but `impact` reaches 107,836 definitions, mostly through type
  uses, so the read stops at its 5,000-row limit and the alphabetical first
  5,000 hold none of them. Leaving out the references to files changes that
  only to 103,802. A walk over calls alone needs either a filter on each hop
  of a multi-hop traversal, which GQ 0.14 does not have (it cannot bind a
  multi-hop edge), or calls as an edge type of their own, beside
  `References`. Until then the agent has to follow `cg callers` itself.
- **Graph use.** Omnigraph's agents ran `cg` for 12 of their 45 tool calls
  (27%; on hono, about half). codegraph's and Graphify's agents ran their
  tools for 0 and 1 of 59 and 68. The share counted `git` as a graph tool in
  the pilot's own summary; `agent.py` no longer does.

Estimate for the full run from the pilot's mean session cost, $0.21: 480
sessions (24 questions, five sessions, four arms) at about $100 at list
price, about 2.5 hours of sessions plus an hour of setup.

## Full run

Run on 2026-11-18 on the dev box by `scale-run.sh full`: 24 questions, five
sessions each, four arms, 480 sessions from 03:51 to 07:12 UTC, with no
usage-limit stop and no session over its time limit. The API wrote a median
127 to 139 output tokens a second in every arm, so the arms' wall times are
comparable with each other. The 480 sessions came to $72 at list price. Setup,
each tool's first index of 1.146.0 on the box: Omnigraph 6.5 min
(scip-typescript 173 s, convert 140 s, load 77 s), codegraph 10.1 min (606 s),
Graphify 12.4 min (744 s). Results are in `results/agent-scale.json`, scored
against the corrected keys below.

### What the run turned up before the scores

1. **The graph had no indexes.** The build loaded both releases with
   overwrite loads, which write every table without its indexes, and nothing
   ran `omnigraph optimize`, so every Omnigraph read scanned whole tables. On
   the box `cg members` took a median 48 s, `cg callers` 1.8 s with a tail to
   56 s, and `cg impact` 7.6 s; an Omnigraph session spent a median 5.6 s and
   a mean 37 s waiting on `cg`. After `optimize`, which took 7 s on the Mac,
   `members` takes 0.06 s, `callers` 0.3 s and `impact` 0.1 s there. `cg load`
   now runs `optimize` after a load onto `main` of a local graph. The run's
   answers, tokens and costs stand; Omnigraph's wall times do not, so a second
   window ran no graph and Omnigraph again on the optimized graph.
2. **Static members were missing from the graph.** scip-typescript gives a
   static method and a static property kinds of their own, which the
   converter's kind map did not include, so VS Code's graph lacked 1,751
   static methods and 3,651 static properties. An instance member sharing a
   static member's symbol went with it: `Color` has a static and an instance
   `equals`, and the graph had neither. The converter maps both kinds now. Two
   of the 24 questions touch a static member (`shared-name-2`'s target, and
   four entries of `construction-4`'s key); both windows ran without them.
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

### Scores

Medians per session over the 23 scored questions, five sessions each:

| Arm | Exact | Mean F1 | Cost | Wall time | Time on the API | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | 73 of 115 | 0.960 | $0.103 | 23.6 s | 20.1 s | 2,744 | 8 | |
| Omnigraph | 79 of 115 | 0.964 | $0.076 | 41.7 s* | 11.3 s | 1,417 | 5 | 36% |
| codegraph | 73 of 115 | 0.960 | $0.112 | 42.2 s | 20.5 s | 2,784 | 8 | 0.3% |
| Graphify | 68 of 115 | 0.949 | $0.121 | 25.4 s | 21.9 s | 2,968 | 10 | 5% |

\* On a graph without indexes; see the second window.

Against no graph, question by question: the geometric mean of the ratio of
the two arms' medians, its 95% bootstrap interval over the questions, and on
how many of the 23 the arm spent less.

| Arm | Cost | Output tokens | Turns | Wall time |
|---|---|---|---|---|
| Omnigraph | 0.58× [0.44, 0.77], 17 | 0.61× [0.48, 0.75], 16 | 0.71× [0.48, 1.13], 15 | 1.28× [0.88, 1.87], 13* |
| codegraph | 0.91× [0.83, 1.01], 16 | 0.94× [0.86, 1.02], 12 | 1.04× [0.82, 1.49], 12 | 1.88× [1.65, 2.13], 1 |
| Graphify | 1.12× [1.02, 1.22], 5 | 1.05× [0.97, 1.13], 6 | 1.26× [1.05, 1.71], 6 | 1.10× [1.02, 1.17], 3 |

By family, exact answers and Omnigraph's cost against no graph:

| Family | No graph | Omnigraph | codegraph | Graphify | Omnigraph's cost |
|---|---|---|---|---|---|
| Shared-name callers | 13 of 20 | 12 of 20 | 14 of 20 | 11 of 20 | 0.74× [0.39, 1.16] |
| Interface dispatch | 17 of 20 | 17 of 20 | 18 of 20 | 18 of 20 | 1.14× [0.84, 1.75] |
| Transitive callers | 1 of 15 | 0 of 15 | 1 of 15 | 0 of 15 | 0.28× [0.18, 0.57] |
| Constructions | 11 of 20 | 11 of 20 | 9 of 20 | 13 of 20 | 0.98× [0.76, 1.26] |
| Release changes | 12 of 20 | 19 of 20 | 11 of 20 | 7 of 20 | 0.34× [0.27, 0.44] |
| Controls | 19 of 20 | 20 of 20 | 20 of 20 | 19 of 20 | 0.40× [0.26, 0.62] |

The hypotheses:

1. **Correctness: refuted.** Without a graph, exactness fell on chains (1 of
   15) and on shared names (13 of 20), though not on dispatch (17 of 20), as
   predicted. With Omnigraph it fell the same way, 0 of 15 and 12 of 20. Only
   on release changes did Omnigraph's agents answer differently: 19 of 20,
   against 7 to 12, because `cg` reads both releases where the others diff
   text. On `release-4` the code calling `moveEditors` moved from `mergeGroup`
   into a new method, `doMergeGroup`; Omnigraph's five sessions named it, and
   none of the other fifteen did.
2. **Cost: refuted.** The rank correlation between a question's grep count
   and Omnigraph's cost ratio is +0.62, so the ratio rises with the lines a
   search returns, where the hypothesis said it would fall. Omnigraph saved
   most where one `cg` read answers: controls (0.40×), release changes
   (0.34×) and chains (0.28×, none exact), and least on dispatch, which a
   search for the method's name answers.
3. **Name matching: not tested.** codegraph's agents called its tool 6 times
   in 115 sessions, Graphify's for 5% of their calls; both arms mostly searched
   text, as on hono.

Omnigraph's 36 inexact answers, by cause:

- **Chains (15).** `impact` follows every reference, not every call, and
  agents that trusted it took definitions that only reference the chain: four
  of five `transitive-3` sessions named `SimpleFindReplaceWidget.find`,
  `hide`, `replaceOne` and `show`. And a class handed to `createInstance` is a
  reference to the class, not a call to its constructor, so `impact` does not
  reach `NotebookFindContrib`'s constructor, which none of the 20 sessions in
  any arm named.
- **Shared names (8).** The graph lacked `Color.equals`, so the agents
  searched text for `shared-name-2` and, like every arm in all 20 sessions,
  took `MinimapOptions.equals`, which compares `RGBA8` values. On
  `shared-name-1` three sessions left out the class's own constructor and
  `dispose`, which `cg callers` listed.
- **The rest (13), one or two entries a session.** An override missed or
  added among `dispatch-1`'s 14, a `createInstance` site left out of
  `construction-2`, static fields of `Color` and `PaneDraggable` that
  construct an `RGBA` in `construction-4` (the graph lacked `Color`'s), one
  extra class in `construction-3`, and `release-1`'s two entries once.

### Second window: no graph and Omnigraph on the optimized graph

Run on 2026-11-18 from 07:35 to 09:07 UTC on the same box. The build ran the
two loads again, each now followed by `optimize`: 72.5 s and 80.9 s, against
69.5 s and 76.9 s without it. Then the two arms ran the same 24 questions five
times each, 240 sessions, with no usage-limit stop and no session over its
time limit. The graph still lacked static members, because the converter fix
came after the build. The API wrote a median 138 output tokens a second for
no graph and 126 for Omnigraph, against 139 and 127 in the first window.
Results are in `results/agent-scale-window2.json`, scored against the
corrected keys.

With indexes, `cg` answered in a median 0.43 s for `callers`, 0.53 s for
`find`, 0.47 s for `impact` and 0.23 s for `members`; the slowest of its 453
calls took 4.0 s. An Omnigraph session waited a median 1.3 s on its tools, as
long as a session without a graph.

Medians per session over the 23 scored questions, five sessions each:

| Arm | Exact | Mean F1 | Cost | Wall time | Time on the API | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | 69 of 115 | 0.951 | $0.091 | 22.9 s | 20.3 s | 2,724 | 9 | |
| Omnigraph | 80 of 115 | 0.953 | $0.047 | 14.1 s | 11.7 s | 1,455 | 5 | 36% |

Against no graph, question by question, as above:

| Arm | Cost | Output tokens | Turns | Wall time |
|---|---|---|---|---|
| Omnigraph | 0.52× [0.39, 0.69], 17 | 0.64× [0.52, 0.80], 17 | 0.64× [0.48, 0.84], 15 | 0.70× [0.57, 0.87], 16 |

By family:

| Family | No graph | Omnigraph | Omnigraph's cost | Omnigraph's wall time |
|---|---|---|---|---|
| Shared-name callers | 12 of 20 | 9 of 20 | 1.03× [0.98, 1.10] | 1.29× [1.14, 1.45] |
| Interface dispatch | 19 of 20 | 20 of 20 | 0.80× [0.66, 0.91] | 0.85× [0.72, 0.95] |
| Transitive callers | 0 of 15 | 0 of 15 | 0.17× [0.11, 0.25] | 0.31× [0.24, 0.45] |
| Constructions | 9 of 20 | 13 of 20 | 1.06× [0.89, 1.21] | 1.18× [0.97, 1.39] |
| Release changes | 11 of 20 | 18 of 20 | 0.30× [0.19, 0.41] | 0.45× [0.35, 0.54] |
| Controls | 18 of 20 | 20 of 20 | 0.36× [0.26, 0.44] | 0.56× [0.47, 0.65] |

What the second window shows:

1. **Wall time follows the indexes.** Omnigraph's sessions took 0.70× the
   time of no graph's, against 1.28× on the graph without indexes. Time on
   the API hardly moved (11.3 s and 11.7 s), so the difference was the wait
   on `cg`.
2. **The first window's answers and costs hold.** Omnigraph cost 0.52× of no
   graph, against 0.58×, and was exact in 80 sessions, against 79. No
   graph's exact answers went from 73 to 69 with the same arm and keys,
   which shows how far a count moves between runs. The rank correlation of
   grep count with Omnigraph's cost ratio was +0.60, against +0.62.
3. **The accuracy gain is on release changes only.** Over both windows
   Omnigraph was exact in 17 more of 230 sessions than no graph, with a 95%
   bootstrap interval over questions of −4 to 43. Without the release
   questions it was 3 more, −10 to 16. `release-4` alone gave 10: all ten of
   Omnigraph's sessions named `doMergeGroup`, and none of no graph's.
4. **Omnigraph saved nothing on shared names and constructions** (1.03× and
   1.06×). `cg callers` of a class lists every reference to it, type
   annotations included, so on constructions the agents searched text for
   `new` anyway: 184 searches to 37 `cg` calls.
5. **`impact` from a hub ran out of memory.** All five Omnigraph sessions on
   `transitive-4`, the question left out of the scores, hit the 2 GiB
   `query_memory_bytes` limit, 18 times in all. On the graph without indexes
   no session did. The cookbook's CLAUDE.md lists this under What it does not do.

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
