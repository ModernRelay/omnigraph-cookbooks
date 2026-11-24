# code-graph benchmarks

Four benchmarks for the claims this cookbook makes: three on
[hono](https://github.com/honojs/hono), TypeScript, MIT, and the agent-cost
benchmark again on [VS Code](https://github.com/microsoft/vscode), MIT. They
are run by hand, not in CI, and write everything they fetch or build under
`work/`, which git ignores. The headline results are in the cookbook README,
under [Benchmarks](../README.md#benchmarks).

| Benchmark | Claim | Ground truth |
|---|---|---|
| [PR diff](#pr-diff) | A pull request's branch diff is exactly what it changed | Two reference graphs built with the TypeScript compiler API, at the base and the merge commit |
| [Execution recall](#execution-recall) | The graph contains the calls the code really makes | Calls recorded while hono's own test suite runs |
| [Agent cost](#agent-cost) | An agent with the graph answers code-structure questions for fewer tokens and less time | Eight questions with keys from the compiler reference, checked against the source |
| [Agent cost at scale](#agent-cost-at-scale) | The same on a repository where text search answers badly | 24 questions picked by rule from a compiler reference of VS Code, with keys corrected after the run |

The cookbook resolves references through scip-typescript, which runs the
TypeScript compiler. A compiler-built reference therefore cannot test the
cookbook's resolution, only its conversion and diffs: the PR-diff benchmark
uses one for that. The execution-recall benchmark's truth comes from running
code, not from the compiler, so it can compare Omnigraph, loaded with this
cookbook's graph, with other tools.

## Requirements

git, Python 3, Node.js 22.23.4 or later, bun (hono's tests), the locked
indexer (`npm ci` in `code-graph/sources/indexer`) and the `omnigraph` CLI.
The PR-diff results come from the 0.15.0 CLI the cookbooks pin. Omnigraph's
agent-cost sessions ran on 0.16.0, whose multi-hop reads stream each hop's
edge probe; on 0.15, `impact` from a hub on VS Code exceeds any memory limit.
Every `omnigraph` call runs with its own `OMNIGRAPH_HOME` under `work/`.
The agent-cost benchmark also needs a signed-in `claude` (Claude Code), uv, and
the other tools installed as the execution-recall benchmark installed them.

## PR diff

```bash
OMNIGRAPH_BIN=/path/to/omnigraph python3 code-graph/bench/pr_diff.py
```

The sample, pinned in `pr-sample.json`, is the 40 most recent first-parent
commits on hono's `main` before 2026-11-01 that change a non-test `.ts` file
under `src/`. hono squash-merges, so each is one pull request. For each, both
commits are indexed and converted, loaded with `cg load` (the base onto
`main`, the merge commit onto a branch with `--mode overwrite`) and reviewed
with `cg diff`. The review is scored twice:

- **Mechanics**, against the set difference of the two converted files. This
  tests overwrite loads and `branch diff`.
- **Accuracy**, against the difference of two reference graphs from
  `reference.mjs`, over the definitions both the reference and the cookbook
  model. A changed symbol is one whose code digest moved. A call is one the
  compiler's syntax tree marks: a callee, a `new` or a tagged template.

Results, `results/pr_diff.json`:

| | Exact pull requests | Added | Removed | Changed | References added | References removed | Calls added | Calls removed |
|---|---|---|---|---|---|---|---|---|
| Mechanics | 40 of 40 | 19 of 19 | 9 of 9 | 48 of 48 | 91 of 91 | 40 of 40 | 12 of 12 | 6 of 6 |
| Accuracy, precision | 36 of 40 | 1.000 | 0.667 | 0.938 | 1.000 | 0.875 | 1.000 | 1.000 |
| Accuracy, recall | | 1.000 | 1.000 | 1.000 | 1.000 | 0.972 | 1.000 | 0.857 |

The four inexact pull requests, checked against their source diffs:

- **`8a103aa5`**: three updates the reference does not count are real
  changes. A constant's value changed, such as `ONLY_WILDCARD_REG_EXP_STR`
  from `".*"` to `"[^]*"`, and a field's type changed; the cookbook reports
  them through `signature`. The reference tracks code changes of callables only.
- **`e9c01079`**: `HonoOptions` became a union of two object types, and
  scip-typescript stopped indexing their properties, so the diff reports
  `getPath`, `router` and `strict` removed with five references.
- **`6cadf753`**: one removed reference the cookbook still has; unexplained.
- **`34f90432`**: the removed `this.getPath(request)` in `Hono.mount` is a
  removed call to the compiler. `getPath` is a property whose type is the
  alias `GetPath<E>`, which the converter does not count as callable, so the
  diff reports a removed reference and no removed call.

The call rule over hono's whole `src/` at the seed's base, against the
compiler's calls: precision 0.991 and recall 0.985 (8 calls too many, 13 too
few). The 13 are all calls to properties the converter does not count as
callable, a type alias hiding their function type. Six of the 8 are a method
written in an object literal, `{ close(code) { … } }`, which scip-typescript
records as a reference to the member it implements, followed by `(`; the
other two are `match` followed by `<` without a call.

Cached conversions and references are keyed by a digest of the code that made
them, so a change to the converter or the reference builder rebuilds them.

## Execution recall

```bash
node code-graph/bench/instrument.mjs CHECKOUT work/traced     # then install hono's dependencies with bun
CG_TRACE_DIR=work/trace work/traced/node_modules/.bin/vitest --run --project main --coverage.enabled=false --pool forks
python3 code-graph/bench/recall.py work/trace COOKBOOK.jsonl REFERENCE.json [TOOL.json ...]
```

`instrument.mjs` copies the base revision of the cookbook's seed, `a10592f3`,
and wraps every function under `src/` so that a call into a definition records
`caller -> callee`. The caller is the definition that owns the code making the
call, by the same rules as the static graphs: a callback written in F is F's
code wherever it runs, and so are F's default parameters and, in a
constructor, its `super(...)`; a field's initializer is the field's code.
Test code runs as `<outside>` and is never a caller. The owner travels
through awaits in an `AsyncLocalStorage`. The instrumented suite runs 3,956
tests like the untouched copy; one test differs. The tests executed 917
distinct calls between hono's definitions.

Recall is the share of executed calls a graph contains. An edge the tests
never ran is not wrong, so this measures recall only. Every graph is mapped
into one identity space, `path:Container.member`; a tool's local helper
functions map to the definition that holds them, as the traces do. The tools
ran at their defaults, each on its own copy of the checkout with a scratch
home, telemetry off and no model keys: codegraph 1.6.2 (calls and instantiations),
codebase-memory-mcp 0.12.1, GitNexus 1.6.12, Graphify 0.9.102 (calls,
AST only) and code-review-graph 2.3.9.

Results, `results/recall.json`:

| Graph | All 917 | Functions and methods (768) | Constructors (56) | Getters and setters (93) |
|---|---|---|---|---|
| Compiler reference | 0.891 | 0.882 | 0.875 | 0.978 |
| Omnigraph | 0.893 | 0.882 | 0.875 | 1.000 |
| codegraph | 0.686 | 0.758 | 0.839 | 0 |
| Graphify | 0.677 | 0.749 | 0.821 | 0 |
| GitNexus | 0.632 | 0.694 | 0.839 | 0 |
| codebase-memory-mcp | 0.627 | 0.690 | 0.804 | 0 |
| code-review-graph | 0.604 | 0.721 | 0 | 0 |

Omnigraph's row is every `References` edge, what `referrers` returns and
`impact` follows. Adding a second read, `implementers`, which follows a call
through an interface member to the implementations the graph records, raises
it to 0.932. The `Calls` edges alone, what `callers` returns and a call graph
holds, give 0.778: 0.865 of functions and methods, 0.875 of constructors and
none of the getters and setters.

The tools record calls, so the like-for-like column is functions and
methods, where Omnigraph's call edges find 0.865 and its references 0.882.
Getter calls are property reads: only a graph of references contains them. A
graph of every reference also holds more edges than a call graph, and this
benchmark does not count the edges the tests never ran.

### Where the difference comes from

Two things separate Omnigraph from the tools, and they are of different
kinds. The first is what is recorded. Omnigraph's references contain 819
executed calls and its call edges 713; the 106 between them are 93 getter
calls, which run when a property is read, and 13 calls to functions the code
passes as values. That is half of the gap between 0.893 and the tools' best,
0.686, and it is a choice of what to record more than better extraction.

The second is resolution. The tools find definitions by name; the graph
loaded into Omnigraph comes from the type checker, through scip-typescript.
Recall on calls to functions and methods, from `functions_by_call_shape` in
`results/recall.json`:

| Callee | Executed | Omnigraph calls | codegraph | Graphify | GitNexus | codebase-memory-mcp | code-review-graph |
|---|---|---|---|---|---|---|---|
| Top-level function | 569 | 0.896 | 0.852 | 0.880 | 0.824 | 0.854 | 0.838 |
| Class member | 199 | 0.774 | 0.487 | 0.372 | 0.322 | 0.221 | 0.387 |
| Name defined once | 513 | 0.955 | 0.877 | 0.918 | 0.838 | 0.867 | 0.858 |
| Name defined 4 or more times | 125 | 0.640 | 0.424 | 0.288 | 0.272 | 0.192 | 0.264 |

Where a name identifies its definition, the tools come close: Graphify is
within two to four points of Omnigraph. The gap opens where it does not: a method
call such as `c.req.header()` resolves to `HonoRequest.header` only if the
type of `c.req` is known, and hono defines `header` in several places. Of
the calls to a shared class-member name each tool missed, it recorded 14 to
26 as the caller calling another definition of that name.

The tools find 23 executed calls Omnigraph lacks, 13 of them codegraph's.
Most are calls dispatched to an override, which matching by name catches by
linking every method of that name.

The compiler reference misses 100 executed calls, about one in nine. 47 are
function values called indirectly: a function passed as an argument, stored
in a property or returned, then called by code that never names it. 44 are
calls dispatched to an override, such as `this.getHeaders()` in an abstract
class running a subclass's method; Omnigraph's `ImplementedBy` edges recover
most of these. The other nine reach constructors and getters, among them
four `super(...)` calls, which no graph here records.

## Agent cost

```bash
python3 code-graph/bench/agent.py setup    # one hono worktree per arm, set up by each tool's own installer
python3 code-graph/bench/agent.py index    # each tool's first index of a fresh checkout, three times
python3 code-graph/bench/agent.py run      # 8 questions, 7 arms, 3 sessions each
python3 code-graph/bench/agent.py score    # results/agent.json
```

The other two benchmarks measure the graph. This one measures what a coding
agent spends with it: the tokens, time and turns Claude Code 2.1.267 takes to
answer a question about hono's code structure, and whether the answer is
right. Seven arms get the same model (Sonnet 5.5), the same questions and the
same read and search tools: no code graph, Omnigraph with this cookbook's
graph, and the five tools of the execution-recall benchmark.

Each tool is set up by its own Claude Code installer: its MCP server, the
instructions it writes into CLAUDE.md, its skills, subagents and hooks. An
installer that writes to the home directory writes to a scratch one, and
setup moves what it wrote into the project, so a session loads the tool and
nothing of the user's. Omnigraph has no installer for a repository: its arm
reads a local graph through `cg`, with a CLAUDE.md section written for this
benchmark (`OMNIGRAPH_CLAUDE_MD` in `agent.py`). Every arm may use Read, Grep,
Glob, skills, subagents and, in the shell, grep, find, ls, cat, head, tail and
wc; an arm whose tool has a command line may also run it. A session loads
project settings only and its arm's MCP servers only, with auto-memory off.

The eight questions in `agent-questions.json` each ask for a set of
definitions: the callers of a method whose name six definitions share, of a
function constant and of a uniquely named function; the classes implementing
an interface; the overrides a call dispatches to; the users of a property; the
constructions of a class; and the callers through any chain of calls. Keys
come from the compiler reference and were checked against the source. Two
were corrected after the runs, and their `note` says why: one call is reached
through a table of functions, which the reference records as no call, and one
definition only assigns the property, which "use" may or may not include. An
answer is the JSON list on a session's last `ANSWER:` line, mapped to the
definitions the answer format names (a getter or field to its class, a
constant that holds no function to its file) and graded by F1.

Results come from two windows, and each arm is compared with the no-graph arm
that ran in its own window: the first, `results/agent.json`, on 2026-11-16,
holds no graph and the five tools; the second, `results/agent-window2.json`,
on 2026-11-23, holds no graph and Omnigraph, on the current converter and
OmniGraph 0.16.0. Claude Code's own starting context grew between them, from
36.2k to 45.3k tokens, so the windows' no-graph arms differ. Medians per
session; input tokens include every cached read:

| Arm | Window | Exact answers | Cost | Wall time | Input tokens | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | first | 24 of 24 | $0.100 | 16.1 s | 198k | 1,926 | 6 | |
| codegraph | first | 24 of 24 | $0.094 | 17.6 s | 221k | 1,766 | 6 | 0% |
| Graphify | first | 21 of 24 | $0.100 | 16.0 s | 165k | 1,866 | 6 | 9% |
| GitNexus | first | 22 of 24 | $0.102 | 14.3 s | 207k | 1,368 | 5 | 17% |
| codebase-memory-mcp | first | 24 of 24 | $0.114 | 18.1 s | 207k | 2,016 | 6 | 1% |
| code-review-graph | first | 24 of 24 | $0.107 | 20.1 s | 225k | 1,931 | 6 | 7% |
| No code graph | second | 21 of 24 | $0.137 | 18.3 s | 287k | 1,725 | 6 | |
| Omnigraph | second | 21 of 24 | $0.061 | 13.6 s | 185k | 925 | 4 | 52% |

The API wrote a median 113 to 139 output tokens a second in every arm of
both windows. Cost moves with prompt caching: two of Omnigraph's three
sessions on the callers of `getCookie` wrote about 40k tokens to the cache
and cost $0.17 and $0.18, the third wrote 1k and cost $0.03, for the same
answer, so with three sessions per question the median can land on either.
Turns and output tokens move less.

Each arm paired with the no-graph arm of its window, question by question:
the geometric mean over the eight questions of the ratio of the two arms'
medians, and on how many questions the arm spent less:

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph | 0.62×, 5 of 8 | 0.81×, 5 of 8 | 0.58×, 7 of 8 | 0.66×, 6 of 8 |
| codegraph | 1.01×, 5 of 8 | 1.02×, 4 of 8 | 0.91×, 6 of 8 | 0.98×, 2 of 8 |
| Graphify | 1.01×, 4 of 8 | 1.03×, 3 of 8 | 0.99×, 5 of 8 | 0.94×, 4 of 8 |
| GitNexus | 0.97×, 4 of 8 | 1.01×, 3 of 8 | 0.81×, 6 of 8 | 0.87×, 4 of 8 |
| codebase-memory-mcp | 1.14×, 0 of 8 | 1.11×, 1 of 8 | 1.04×, 1 of 8 | 1.06×, 2 of 8 |
| code-review-graph | 1.33×, 2 of 8 | 1.15×, 1 of 8 | 0.95×, 5 of 8 | 1.08×, 2 of 8 |

Input tokens are mostly the same context read again on every turn, cheap from
the cache; cost follows what each turn adds and what the model writes. A `cg`
read returns the definitions as one table, where a text search returns lines
the agent then reads files around. The saving was largest where a search
takes several rounds: for the callers of `HonoRequest.header`, a name several
definitions share, an Omnigraph session cost $0.028 against $0.172 without a
graph (3 turns against 13); for the callers through a chain of calls to the
cookie `parse`, $0.079 against $0.224 (3 turns against 10); for the users of
`HonoRequest.path`, $0.044 against $0.082. On questions one text search
answers, such as the classes implementing `Router`, it cost about the same
($0.029 against $0.025).

A tool also costs context before the question: in the first window a session
without a graph started at 36.2k tokens, and the tools added 0.6k (Graphify),
5.7k (codegraph), 9.4k (codebase-memory-mcp), 15.9k (code-review-graph) and
20.0k (GitNexus) of tool schemas, instructions and skills; in the second,
Omnigraph's `cg` section added 0.5k to 45.3k.

The agents with the other tools mostly searched text, calling their tool for
0 to 17% of their tool calls. codegraph delivers its graph through a hook that
adds context to every prompt, which needs no call; the context it gave for
`header` counted 2 callers of `HonoRequest.header` and 14 of `Context.header`,
which matching names produces, and its agents searched to check.

On the chain-of-calls question, `detectLanguage` calls `detectFromCookie`
through the `detectors` table, `detectors[name](c)`. In the second window
every session, with and without the graph, left out `detectLanguage` and its
caller `languageDetector`, which reach `parse` only through that table; in
the first, the no-graph sessions named both. `cg transitive-callers` follows
calls, and a call through a table is a reference to the table, so it stops
before them; `cg impact` reaches them. In the first window Graphify and
GitNexus missed the two in two of three sessions, and one Graphify session
missed `serveStatic`'s chained `header` call.

Each tool's first index of a fresh checkout, median of three, from
`index_seconds_fresh` in `work/agent/ARM/setup.json`:

| Arm | Index time | Three runs |
|---|---|---|
| Omnigraph: scip-typescript, convert and load | 2.2 s | 2.6, 2.2, 2.2 |
| codebase-memory-mcp | 2.0 s | 2.0, 1.7, 2.0 |
| codegraph | 3.9 s | 4.2, 3.9, 3.9 |
| Graphify, without its LLM extraction | 4.3 s | 4.3, 4.0, 4.5 |
| code-review-graph | 5.8 s | 5.8, 5.8, 4.9 |
| GitNexus | 21.3 s | 23.0, 21.3, 20.3 |

## Agent cost at scale

```bash
OMNIGRAPH_BIN=/path/to/omnigraph sh code-graph/bench/scale-run.sh full   # build, questions, setup, 480 sessions
python3 code-graph/bench/scale.py rekey                                  # the asked questions, current keys
python3 code-graph/bench/agent.py --suite vscode score                   # results/agent-scale.json
python3 code-graph/bench/scale.py analyze                                # by family, against no graph
python3 code-graph/bench/graph_answers.py                                # the graph's own answers
```

A later window keeps its sessions apart: `agent.py --suite vscode run --arms
bare,omnigraph --reps 5 --runs DIR`, then `score --runs DIR --results
NAME.json` and `scale.py analyze --results results/NAME.json`.

On hono one text search returns a short list, so the agent-cost benchmark
could not show what a graph is for. This one asks about VS Code 1.146.0, 89
times hono's size, whose services are injected through interfaces and where
376 names have 50 or more definitions. 24 questions in six families are
picked from the compiler reference by rule with a fixed seed, and asked five
times each in four arms: no code graph, Omnigraph, codegraph and Graphify.
1.145.0 is the previous release for the release questions.
[`scale-design.md`](scale-design.md) has the design, the hypotheses stated
before the runs, the pilot, and every correction.

The run turned up errors in its own keys. The compiler reference covered
`src/vs/` rather than `src/`, and did not count a call or construction through
dependency injection (`invokeFunction`, `createInstance`). Counting them leaves
one question with 44,328 answers, so 23 are scored.

codegraph and Graphify ran in the first window, on 2026-11-18 on a dev box,
`results/agent-scale.json`. Omnigraph ran in the third, on 2026-11-24 on a
Mac with OmniGraph 0.16.0, on the graph with static members and `Calls`
edges, `results/agent-scale-window3.json`. Each arm is compared with the
no-graph arm of its own window. The windows differ in more than the day: in
the third, Claude Code started each session with 45k tokens of context
against 25k, and only half the sessions of either arm found it in the prompt
cache, against three in four in the first; a miss adds about $0.15 to a
session. Medians per session:

| Arm | Window | Exact answers | Mean F1 | Cost | Wall time | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | first | 73 of 115 | 0.960 | $0.103 | 23.6 s | 2,744 | 8 | |
| codegraph | first | 73 of 115 | 0.960 | $0.112 | 42.2 s | 2,784 | 8 | 0.3% |
| Graphify | first | 68 of 115 | 0.949 | $0.121 | 25.4 s | 2,968 | 10 | 5% |
| No code graph | third | 67 of 115 | 0.944 | $0.224 | 30.8 s | 3,305 | 10 | |
| Omnigraph | third | 85 of 115 | 0.981 | $0.166 | 16.0 s | 1,361 | 4 | 50% |

Against no graph, question by question (geometric mean of the ratio of
medians, 95% bootstrap interval, questions where the arm spent less):

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph | 0.61× [0.43, 0.85], 20 of 23 | 0.54× [0.43, 0.67], 20 | 0.41× [0.33, 0.51], 22 | 0.39× [0.30, 0.51], 21 |
| codegraph | 0.91× [0.83, 1.01], 16 of 23 | 1.88× [1.65, 2.13], 1 | 0.94× [0.86, 1.02], 12 | 1.04× [0.82, 1.49], 12 |
| Graphify | 1.12× [1.02, 1.22], 5 of 23 | 1.10× [1.02, 1.17], 3 | 1.05× [0.97, 1.13], 6 | 1.26× [1.05, 1.71], 6 |

Omnigraph's cost ratio is nearer 1 than its ratios of turns and output
tokens because a cache miss costs both arms the same. By family, Omnigraph
against no graph (`results/agent-scale-window3-analysis.json`), with the
questions the graph answers exactly by itself:

| Family | Exact, no graph | Exact, Omnigraph | The graph by itself | Cost | Wall time | Median turns |
|---|---|---|---|---|---|---|
| Constructions | 10 of 20 | 14 of 20 | 3 of 4 | 0.21× | 0.35× | 16.5 → 3 |
| Transitive callers | 0 of 15 | 0 of 15 | 0 of 3 | 0.59× | 0.36× | 19 → 4 |
| Shared-name callers | 13 of 20 | 15 of 20 | 3 of 4 | 0.35× | 0.48× | 10.5 → 3 |
| Release changes | 7 of 20 | 18 of 20 | 4 of 4 | 0.73× | 0.49× | 13 → 6 |
| Controls (a uniquely named callable) | 19 of 20 | 20 of 20 | 4 of 4 | 1.32× | 0.82× | 5 → 3 |
| Interface dispatch | 18 of 20 | 18 of 20 | 4 of 4 | 1.20× | 0.93× | 8.5 → 7.5 |

Omnigraph was exact in 18 more sessions than no graph, 11 of them on release
changes; the no-graph arm itself was exact in 73 sessions in one window and 67
in the other, so a few sessions either way is within run-to-run noise. On
release changes `cg` reads both releases, where the others diff text: when
1.146.0 moved the call to `moveEditors` into a new method, `doMergeGroup`,
only Omnigraph's sessions named it.

The graph saves most where one `cg` read is the answer and a text search
returns lines the agent has to sort into definitions: the constructions of a
class, the callers of a shared method name and of a chain of calls. There an
Omnigraph session took three or four turns where a no-graph session took 10
to 19. It saved least on interface dispatch, where both arms took about eight
turns. On the controls and dispatch both arms answer in a few turns, so the
cost of a median session follows which sessions missed the cache, and the
cost ratio is above 1 while the ratio of turns is below.

`graph_answers.py` asks the graph each question with the one read the
Omnigraph arm's instructions name for its family, and grades the rows like a
session's answer: 18 of 23 exact, mean F1 0.989
(`results/graph-answers.json`). The sessions mostly took that answer, so 24
of Omnigraph's 30 inexact sessions are the graph's five inexact answers: a
construction through dependency injection, where `createInstance(C)` passes
`C` as an argument and the graph records a reference, not a call (three
questions); a function constant declared in a block of module code, whose
calls the converter assigns to the module; and a call on a value of type
`any` that the compiler does not resolve. Every chain question has one of
these, so no session in either arm answered one exactly. The design
predicted that the saving would grow with the lines a text search returns;
the rank correlation between a question's grep lines and its cost ratio is
−0.34, in that direction but, over 23 questions, indistinguishable from none.
No session ran out of memory, including the five whose walk starts at a hub.
codegraph's and Graphify's agents barely used their tools, so the run says
little about those tools.

## Limits

- One repository in one language for three benchmarks, and two for the
  agent-cost benchmark. The ranking may differ elsewhere.
- The scale benchmark's keys were corrected after its run, from reading the
  entries most sessions disagreed with; `scale-design.md` lists each
  correction and why, and every question keeps the key it was asked with.
- The agent-cost benchmark ran one model, in one harness, three sessions per
  question and arm, with list prices. Omnigraph's instructions were written
  for it, the other tools' by their authors, and the keys come from the same
  compiler as Omnigraph's graph; every key was checked against the source.
- The reference shares the TypeScript compiler with scip-typescript, so the
  PR-diff accuracy measures conversion and modeling, not resolution.
- Execution recall covers only what hono's tests run, and the tracer skips
  two generators. It would credit a getter that a parameter's destructuring
  reads to the caller; no parameter in hono reads one.
- Tools are mapped by file, name and line into the reference's identities; a
  tool's own node that the reference does not model counts as not found.
