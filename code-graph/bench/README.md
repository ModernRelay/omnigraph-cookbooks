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
The PR-diff results come from the 0.15.0 CLI the cookbooks pin, the agent-cost
results from 0.14.0. Every `omnigraph` call runs with its own `OMNIGRAPH_HOME`
under `work/`.
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
  model. A changed symbol is one whose code digest moved.

Results, `results/pr_diff.json`:

| | Exact pull requests | Added | Removed | Changed | References added | References removed |
|---|---|---|---|---|---|---|
| Mechanics | 40 of 40 | 19 of 19 | 9 of 9 | 48 of 48 | 91 of 91 | 40 of 40 |
| Accuracy, precision | 37 of 40 | 1.000 | 0.667 | 0.938 | 1.000 | 0.875 |
| Accuracy, recall | | 1.000 | 1.000 | 1.000 | 1.000 | 0.972 |

The three inexact pull requests, checked against their source diffs:

- **`8a103aa5`**: three updates the reference does not count are real
  changes. A constant's value changed, such as `ONLY_WILDCARD_REG_EXP_STR`
  from `".*"` to `"[^]*"`, and a field's type changed; the cookbook reports
  them through `signature`. The reference tracks code changes of callables only.
- **`e9c01079`**: `HonoOptions` became a union of two object types, and
  scip-typescript stopped indexing their properties, so the diff reports
  `getPath`, `router` and `strict` removed with five references.
- **`6cadf753`**: one removed reference the cookbook still has; unexplained.

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

Omnigraph's row is what the cookbook's reads answer: `callers`, `callees` and
`impact` follow every `References` edge and report `call` as a column, not a
filter. Adding a second read, `implementers`, which follows a call through an
interface member to the implementations the graph records, raises it to
0.932. Keeping only the edges whose `call` is true, as a call graph does,
gives 0.778: 0.865 of functions and methods, 0.875 of constructors and none
of the getters and setters.

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

Results, `results/agent.json`, 168 sessions: the no-graph arm and the five
tools on 2026-11-16, Omnigraph on 2026-11-17. Medians per session; input
tokens include every cached read:

| Arm | Exact answers | Cost | Wall time | Input tokens | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|
| No code graph | 24 of 24 | $0.100 | 16.1 s | 198k | 1,926 | 6 | |
| Omnigraph | 24 of 24 | $0.069 | * | 153k | 1,198 | 5 | 48% |
| codegraph | 24 of 24 | $0.094 | 17.6 s | 221k | 1,766 | 6 | 0% |
| Graphify | 21 of 24 | $0.100 | 16.0 s | 165k | 1,866 | 6 | 9% |
| GitNexus | 22 of 24 | $0.102 | 14.3 s | 207k | 1,368 | 5 | 17% |
| codebase-memory-mcp | 24 of 24 | $0.114 | 18.1 s | 207k | 2,016 | 6 | 1% |
| code-review-graph | 24 of 24 | $0.107 | 20.1 s | 225k | 1,931 | 6 | 7% |

\* Not comparable. On the day Omnigraph's sessions ran, the API wrote a
median 74 output tokens a second, against 113 to 139 for the other arms, so
its sessions spent longer waiting on the API for the same work. Cost moves
with prompt caching: a session that writes 25k tokens to the cache costs
about $0.13, one that writes 4k about $0.05, for the same answer, and with
three sessions per question the median can land on either.

The same sessions paired with no code graph, question by question: the
geometric mean over the eight questions of the ratio of the two arms' medians,
and on how many questions the arm spent less:

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph | 0.84×, 5 of 8 | not comparable | 0.75×, 5 of 8 | 0.95×, 4 of 8 |
| codegraph | 1.01×, 5 of 8 | 1.02×, 4 of 8 | 0.91×, 6 of 8 | 0.98×, 2 of 8 |
| Graphify | 1.01×, 4 of 8 | 1.03×, 3 of 8 | 0.99×, 5 of 8 | 0.94×, 4 of 8 |
| GitNexus | 0.97×, 4 of 8 | 1.01×, 3 of 8 | 0.81×, 6 of 8 | 0.87×, 4 of 8 |
| codebase-memory-mcp | 1.14×, 0 of 8 | 1.11×, 1 of 8 | 1.04×, 1 of 8 | 1.06×, 2 of 8 |
| code-review-graph | 1.33×, 2 of 8 | 1.15×, 1 of 8 | 0.95×, 5 of 8 | 1.08×, 2 of 8 |

Input tokens are mostly the same context read again on every turn, cheap from
the cache; cost follows what each turn adds and what the model writes. A `cg`
read returns the definitions as one table, where a text search returns lines
the agent then reads files around. The saving was largest where a search
takes several rounds: for the users of `HonoRequest.path` an Omnigraph
session cost $0.040 against $0.094 without a graph (5 turns against 11), for
the callers through a chain of calls to the cookie `parse` $0.071 against
$0.129, and for the callers of `HonoRequest.header`, a name several
definitions share, $0.135 against $0.161 (5 turns against 11). On questions
one text search answers, such as the classes implementing `Router`, it cost a
little more ($0.028 against $0.019).

A tool also costs context before the question: a session without a graph
starts at 36.2k tokens, and the tools add 0.4k (Omnigraph), 0.6k (Graphify),
5.7k (codegraph), 9.4k (codebase-memory-mcp), 15.9k (code-review-graph) and
20.0k (GitNexus) of tool schemas, instructions and skills.

The agents with the other tools mostly searched text, calling their tool for
0 to 17% of their tool calls. codegraph delivers its graph through a hook that
adds context to every prompt, which needs no call; the context it gave for
`header` counted 2 callers of `HonoRequest.header` and 14 of `Context.header`,
which matching names produces, and its agents searched to check.

On the chain-of-calls question, `detectLanguage` calls `detectFromCookie`
through the `detectors` table. Omnigraph's sessions ran `impact`, then read
`language.ts` once to rule out `validateOptions`, which reads the table's
keys, and the `Detectors` type, and all three answered exactly. Graphify and
GitNexus missed the two in two of three sessions, and one Graphify session
missed `serveStatic`'s chained `header` call.

Each tool's first index of a fresh checkout, median of three, from
`index_seconds_fresh` in `work/agent/ARM/setup.json`:

| Arm | Index time | Three runs |
|---|---|---|
| Omnigraph: scip-typescript, convert and load | 2.3 s | 2.2, 2.3, 2.3 |
| codebase-memory-mcp | 2.0 s | 2.0, 1.7, 2.0 |
| codegraph | 3.9 s | 4.2, 3.9, 3.9 |
| Graphify, without its LLM extraction | 4.3 s | 4.3, 4.0, 4.5 |
| code-review-graph | 5.8 s | 5.8, 5.8, 4.9 |
| GitNexus | 21.3 s | 23.0, 21.3, 20.3 |

## Agent cost at scale

```bash
OMNIGRAPH_BIN=/path/to/0.14.0/omnigraph sh code-graph/bench/scale-run.sh full   # build, questions, setup, 480 sessions
python3 code-graph/bench/scale.py rekey                                          # the asked questions, current keys
python3 code-graph/bench/agent.py --suite vscode score                           # results/agent-scale.json
python3 code-graph/bench/scale.py analyze                                        # by family, against no graph
```

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

The arms ran in two windows, each beside its own no-graph arm, on 2026-11-18:
codegraph and Graphify in the first, `results/agent-scale.json`, and
Omnigraph, on the graph with its indexes, in the second,
`results/agent-scale-window2.json`. Each arm is compared with the no-graph arm
of its own window, since API speed and caching differ between windows. Medians
per session:

| Arm | Window | Exact answers | Mean F1 | Cost | Wall time | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|---|
| No code graph | first | 73 of 115 | 0.960 | $0.103 | 23.6 s | 2,744 | 8 | |
| codegraph | first | 73 of 115 | 0.960 | $0.112 | 42.2 s | 2,784 | 8 | 0.3% |
| Graphify | first | 68 of 115 | 0.949 | $0.121 | 25.4 s | 2,968 | 10 | 5% |
| No code graph | second | 69 of 115 | 0.951 | $0.091 | 22.9 s | 2,724 | 9 | |
| Omnigraph | second | 80 of 115 | 0.953 | $0.047 | 14.1 s | 1,455 | 5 | 36% |

Against no graph, question by question (geometric mean of the ratio of
medians, 95% bootstrap interval, questions where the arm spent less):

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph | 0.52× [0.39, 0.69], 17 of 23 | 0.70× [0.57, 0.87], 16 | 0.64× [0.52, 0.80], 17 | 0.64× [0.48, 0.84], 15 |
| codegraph | 0.91× [0.83, 1.01], 16 of 23 | 1.88× [1.65, 2.13], 1 | 0.94× [0.86, 1.02], 12 | 1.04× [0.82, 1.49], 12 |
| Graphify | 1.12× [1.02, 1.22], 5 of 23 | 1.10× [1.02, 1.17], 3 | 1.05× [0.97, 1.13], 6 | 1.26× [1.05, 1.71], 6 |

By family, Omnigraph against no graph (`results/agent-scale-window2-analysis.json`):

| Family | Exact, no graph | Exact, Omnigraph | Cost | Wall time | Median turns |
|---|---|---|---|---|---|
| Release changes | 11 of 20 | 18 of 20 | 0.30× | 0.45× | 9 → 5 |
| Transitive callers | 0 of 15 | 0 of 15 | 0.17× | 0.31× | 15 → 3 |
| Controls (a uniquely named callable) | 18 of 20 | 20 of 20 | 0.36× | 0.56× | 5 → 2 |
| Interface dispatch | 19 of 20 | 20 of 20 | 0.80× | 0.85× | 5.5 → 6 |
| Constructions | 9 of 20 | 13 of 20 | 1.06× | 1.18× | 18 → 16.5 |
| Shared-name callers | 12 of 20 | 9 of 20 | 1.03× | 1.29× | 8.5 → 11 |

Omnigraph was exact in 11 more sessions than no graph, 7 of them on release
changes; the no-graph arm itself was exact in 73 sessions in one window and 69
in the other, so a few sessions either way is within run-to-run noise. On
release changes `cg` reads both releases, where the others diff text: when
1.146.0 moved the call to `moveEditors` into a new method, `doMergeGroup`,
only Omnigraph's sessions named it.

Omnigraph saved most where one `cg` read is the answer: release changes,
chains of calls and the controls. Even for a uniquely named callable a text
search returns lines, and the agent reads files to tell which definition each
line belongs to; the graph returns the definitions. Its saving did not grow
with the lines a search returns, as the design predicted (Spearman +0.60
between a question's grep lines and its cost ratio). It saved nothing where
the graph lacks the relation the question asks for and its agents read the
code as no-graph agents do: a construction through dependency injection,
where `createInstance(C)` names `C` without calling it, and the callers of a
shared method name, where the agents searched the code to check the graph's
answer, and where the graph had no static members, such as `Color`'s static
`equals`. On
chains of calls its answers were close (mean F1 0.90) but never exact,
because `impact` follows every reference, not only calls; and `impact` from
a hub ran out of memory in all five sessions of the question left out of the
scores, which OmniGraph 0.16 fixes. codegraph's and Graphify's agents barely
used their tools, so the run says little about those tools.

## Limits

- One repository in one language for three benchmarks, and two for the
  agent-cost benchmark. The ranking may differ elsewhere.
- The scale benchmark's graph had no static members, 5,402 of VS Code's
  definitions, which the converter now includes. The callers of `Color`'s
  `equals` are one question they touch.
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
