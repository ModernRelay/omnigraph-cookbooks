# CLAUDE.md — beads

Scoped guidance for the `beads/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general OmniGraph operations use the **omnigraph** skill;
this file covers only what is specific to beads.

## What This Is

A beads-style work queue for coding agents: issues, typed links between them,
comments and memories, with readiness derived on every read using beads'
rules. Unlike the other cookbooks it ships a client, `client/ob` (Python,
standard library only), with the `bd` command set and the retry discipline
that concurrent agents need. The seed is a fictional note-taking app,
"Larkspur"; all names are made up.

## Key Files

- `schema.pg` — 3 node types (`Issue`, `Comment`, `Memory`), 8 edge types.
- `queries/issues.gq` — reads, including `ready`, `blocked`,
  `blocked_by_ancestor` and the guard queries `ob` runs before writes.
- `queries/mutations.gq` — stored writes; each re-checks its own condition.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  lists the ready and blocked sets the seed must produce.
- `client/` — `ob`, `ob_cli.py` and `tests/`.

## Rules

- Graph id `beads`. Stored queries and parameters:
  `omnigraph queries list --target local --graph beads`.
- Readiness lives only in the queries. Do not add a stored `blocked` status or
  flag. If you change the `ready` rule, change `ready`, `ready_labeled`,
  `ready_filtered`, `ready_count` and `unblocked_open_count` together, and the
  positive forms `blocked_by_ancestor` and `ancestor_blockers`.
- A claim must stay one conditional `update` on the `Issue` row; an edge insert
  cannot re-check state.
- A write refused with `read_set_conflict` had no effect (`disposition.effects`
  is `none`); rerun it. Do not rerun after a timeout or `effects` `unknown` or
  `partial` without reading the issue first. `ob` never resends such a write:
  it exits 3 with `"outcome": "unknown"`. Only `claim`, `update` and `create`
  read the row and finish on their own.
- `ob` reaches a server only through a server target (`OB_TARGET`, `OB_GRAPH`)
  and never handles tokens.
- A claim ends when its issue leaves `in_progress`: keep `release`,
  `reclaim_expired`, `reopen` and `defer` clearing the assignee and lease.
- Do not link an issue to wait on its own ancestor or descendant; `ob` refuses
  both, as `bd` does. It also refuses parent loops and hierarchies deeper than
  the eight levels readiness follows, so `lineage` and `subtree` see whole
  trees.
- After a query or client change, run `python3 -m unittest discover -s tests`
  from `client/` (local graphs, and a served one behind the local HTTPS
  gateway; it needs the 0.15.0 `omnigraph` and `omnigraph-server`, and
  `openssl`) and `../scripts/check-cookbooks.py`, which also drives `ob` against
  the served cookbook. `SeedTests` pins the ready and blocked sets in `seed.md`.

## Running it


Use the shared [local setup](../README.md#local-setup) with folder `beads` and
graph `beads`, then load `seed.jsonl` (a fictional project, described in
[seed.md](seed.md)). With the server and the HTTPS gateway up, in the terminal
where you configured the CLI:

```bash
omnigraph query ready --target local-reader --graph beads
omnigraph query blocked --target local-reader --graph beads
omnigraph mutate claim --target local-writer --graph beads \
  --params '{"id":"lk-acl","who":"act-writer","lease":null}'
```

Or with the client, as an agent would. `OB_TARGET` names a server target from
that operator configuration and `OB_GRAPH` the graph (default `beads`); the
target supplies the endpoint and the token, so `ob` never handles one:

```bash
export PATH=$PWD/client:$PATH
export OB_TARGET=local-writer OB_GRAPH=beads OB_ACTOR=act-writer
ob ready
ob claim lk-acl --lease 2h     # or: ob ready --claim, which takes the top issue
ob show lk-acl
ob close lk-acl --reason "ACLs enforced server-side"
ob ready                       # the sharing tasks are ready now
```

The answers the README promises, as commands. `seed.md` lists what each returns
on the fresh seed:

```bash
omnigraph query ready --target local-reader --graph beads
omnigraph query blocked --target local-reader --graph beads
omnigraph query ancestor_blockers --target local-reader --graph beads --params '{"id":"lk-share-api"}'
omnigraph query downstream --target local-reader --graph beads --params '{"id":"lk-queue"}'
```

## Your own project

`ob` also runs without a server on a local graph of its own. Start from a
shell without the Quick Start's `OB_*` variables: `OB_TARGET` sends every
command to the server.

```bash
export PATH=$PWD/client:$PATH  # from the beads folder
cd ~/your-project
ob init                        # creates .ob/ with a local graph
ob create "Fix login timeout" -t bug -p 1 --id ob-login
ob create "Write auth docs" --deps ob-login
ob ready                       # only the bug: the docs wait on it
ob onboard >> AGENTS.md        # tell agents how to use it
```

Add `--json` to any `ob` command, before or after the subcommand, for
machine-readable output. `ob` needs only Python 3.10+ and the `omnigraph` CLI
on `PATH` (or `OB_OMNIGRAPH`). In served mode the CLI finds its operator
configuration as usual (`OMNIGRAPH_HOME`, else `~/.omnigraph`);
`OB_OPERATOR_CONFIG=FILE` passes `--operator-config FILE` instead.

## Workflows

Agents run these as `local-writer` (or through `ob`); every read also works as
`local-reader`. `ob` retries lost races and never replays a write whose outcome
is unknown (see "Writes for many agents"). In each workflow, step 1 is the
trigger, 2 the reads, 3 the writes or outside action, 4 the decision.

### Discovered work

1. Trigger: an agent working on `lk-queue` finds a crash.
2. Reads: `search` for the same title, so it does not file a duplicate.
3. Writes: `ob create "Crash on empty note" -t bug -p 1 --discovered-from lk-queue`
   files the issue and the link in one commit. For an issue that exists, use
   the stored links:
   `omnigraph mutate link_discovered_from --target local-writer --graph beads --params '{"src":"lk-crash-empty","dst":"lk-queue"}'`
   (also `link_blocks`, `link_parent`).
4. Decision: a person or the planner sets its priority.

### Notes and memories

1. Trigger: an agent finishes a step, or learns a fact later sessions need.
2. Reads: `memories_about` and `recall` for what is already stored.
3. Writes: `omnigraph mutate comment --target local-writer --graph beads --params '{"slug":"c-1","id":"lk-queue","body":"Retry is capped at 5.","author":"agent-builder"}'`;
   `remember_about` stores a memory under a key and links it, `remember` stores
   it without a link.
4. Decision: none; memories are curated by the workflow below.

### Claim and finish

1. Trigger: an agent is free.
2. Reads: `ready`, or `ob ready --claim`, which takes the top issue.
3. Writes: `claim` (one conditional update; it affects 0 rows when someone else
   holds the issue), `renew` while working, `release` to give it back, `close`
   when done. A closed blocker makes its dependents ready.
4. Decision: a person reviews the work as the team does today; the queue does
   not hold a close for review.

### Lease reclaim

1. Trigger: a schedule.
2. Reads: `expired_leases`.
3. Writes: `omnigraph mutate reclaim_expired --target local-writer --graph beads --params '{"none":null,"never":null}'`
   (or `ob reclaim`) reopens them unassigned.
4. Decision: none. Run the Stalled claim alert first if a person should know.

### Close guard, link hygiene and duplicate triage

`ob close` reads `open_children_of` and `open_blockers_of` first and refuses
unless they close together or `--force` is given. `ob dep add` reads `reaches`,
`lineage` and `subtree` and refuses a link to an ancestor or descendant, a
parent loop, or a hierarchy deeper than eight levels. Duplicate triage runs
`search` (and `similar`, when embeddings are loaded), then
`link_duplicates` or `link_supersedes`, then `close`. These guards read before
they write and are not atomic with the write (see Limits).

### Memory curation

1. Trigger: a schedule, or a closed issue that has memories (`memories_about`).
2. Reads: `memories`, `recall`.
3. Writes: `remember` with the same key replaces a memory; `forget` deletes one.
4. Decision: on a branch, a person merges the change; on `main` the agent's
   writer role can already do it, so keep this workflow to a branch.

### Stalled claim alert, unblock request, queue digest

1. Trigger: a schedule, or a lapsed lease.
2. Reads: `expired_leases` and `assigned`; `blocked` and `blocked_by_ancestor`;
   `stats`, `ready_count` and `ready`.
3. Acts outside the queue with the agent's own tools: a message, a ticket or a
   post. The queue does not hold it back and has no integration for it.
4. Record it: write a comment on the issue with `comment` ("alert sent to
   agent-builder"), and read `comments` before sending again. The schema has no
   other place for it.

## Plans on branches

`ob branch create plan`, then `ob --branch plan create ...` files work that
`main` does not see; read `ob --branch plan ready` to see what it would
release. An admin merges with `ob branch merge plan`. `omnigraph branch diff`
and `omnigraph branch merge --dry-run` show the change and the merge first.

## Readiness, with beads' rules

[`queries/issues.gq`](queries/issues.gq) computes readiness on every read. An
issue is ready when it is open, its `defer_until` has passed, no open issue
blocks it, and no ancestor passes a block down. An ancestor passes one down when
it is not closed, no closed issue sits between it and the issue, and at least
one of its open blockers lies outside its own subtree:

```gq
match {
    $i: Issue { status: "open" }
    $i.defer_until is null or $i.defer_until <= now()
    not { $i blockedBy $b  $b.status != "closed" }
    not { $i childOf{1,8} $a  $a.status != "closed"  $a blockedBy $c  $c.status != "closed"
          not { $c childOf{1,8} $a }
          not { $i childOf{1,8} $x  $x.status = "closed"  $x childOf{1,8} $a } }
}
```

The shipped query splits the last block into the parent and the deeper
ancestors, so only the deeper ones pay for the closed-in-between check.

The writes follow beads too. A parent waits for its children through the link
alone: `ob close` refuses an issue with an open child or an open blocker unless
they close together or `--force` is given. So `ob` refuses a link that makes an
issue wait on its own ancestor (it would wait forever) or a parent wait on its
own descendant (the link already says so), and `ob import` skips both, as `bd`
does. Moving an issue under a new parent is checked for its whole subtree, and
`ob` refuses parent loops and hierarchies deeper than eight levels.

## Writes for many agents

- **One commit per command.** `ob create` writes the issue and all its links in
  one strict JSONL append, which refuses an existing id instead of upserting.
  `ob close a b c` is one update.
- **Atomic claims.** The claim is one conditional update on one row:
  `update Issue set { status: "in_progress", assignee: $who, … } where slug = $id
  and status = "open" and (assignee is null or assignee = $who)`. Of several
  agents racing for one issue, exactly one matches.
- **Retry lost races.** Every write to a branch is checked against its head; a
  writer that loses is refused before any effect (`read_set_conflict`), even
  when it touched a different issue. Rerun it: every mutation here re-checks its
  own condition, so a rerun cannot apply twice. `ob` does this with jittered
  backoff, and spreads agents over the ready list after a lost claim.
- **Never replay a lost response.** Every failed `omnigraph` command reports a
  `disposition` whose `effects` (`none`, `partial` or `unknown`) say whether it
  changed anything. A timeout, a dropped connection or a 502/503/504 leaves a
  write's effects unknown. `ob` resends reads, and writes refused before they
  started (`effects: none`: busy, or the server not reached), but never a write
  whose effects are unknown: it exits 3 with `"outcome": "unknown"`, and the
  issue has to be read before the command runs again. `ob claim`, `ob update`
  and `ob create` do that read themselves, since the row shows whether their
  write landed.
- **Concurrent commands on one operator configuration.** Each `omnigraph`
  command on a server target briefly locks its operator configuration's
  credential state, and a concurrent command that finds the lock held is
  refused before it sends anything. `ob` runs such a command again.
- **Per-issue compare-and-swap edits.** Every write stamps `updated_at`.
  `ob update` writes back with `where slug = $id and updated_at = $expected`
  and re-reads if someone edited the issue in between, so concurrent label
  edits both survive.
- **Leases, not heartbeats.** A claim can carry a lease (`--lease 2h`);
  `ob renew` (or claiming again with `--lease`) extends it and `ob reclaim`
  reopens every expired one in one update. A heartbeat every few seconds would
  be a commit every few seconds. A claim ends when its issue leaves
  `in_progress`: release, reclaim, reopen, defer and `ob update --status` clear
  the lease and the assignee (close keeps the assignee as a record), so a
  reopened issue is free for anyone to claim.
- **History from commits.** `ob history <id>` reads the change feed; each
  commit records its actor, which in served mode comes from the target's token.

## Roles

The bundle's [policies](policies/) follow the repository's three roles:
`act-admin` manages configuration and merges planning branches into `main`;
`act-writer` (agents) reads, writes, and creates or deletes branches;
`act-reader` (dashboards, auditors) reads and invokes stored reads, and is
refused on stored mutations. `OB_ACTOR` should name the same actor as the
target's token: the history records the token's actor regardless, but
`assignee` is a value the client sends.

Plans go on branches: `ob branch create plan`, then
`ob --branch plan create …` files work that `main` does not see until an admin
runs `ob branch merge plan`.

## Semantic search (optional)

With an embedding provider configured (see [cluster.yaml](cluster.yaml)),
`ob init --embed` fills issue-title and memory vectors through the offline
`omnigraph embed` pipeline before each write, and `ob similar` and
`ob recall --semantic` rank by meaning. The pipeline embeds each title or
memory body exactly as written, as a query embeds its text. Vectors stored with
OmniGraph 0.13 embedded a templated line instead; regenerate them with
`omnigraph embed --reembed-all` and reload them, as the engine's
[embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/search/embeddings.md#offline-file-pipeline)
describes. Set `OMNIGRAPH_EMBEDDINGS_MOCK=1` for deterministic test vectors.

## Compared with beads

`client/tests/compare_bd.py` runs `bd` 1.3.1 and `ob` on the same generated
project (`bd`'s usage metrics off). On 2,000 issues and 3,171 links, and on this
seed, both return **the same ready and blocked sets**; reaching that fixed
`ob`'s handling of closed parents and adopted beads' two link rules above.
Neither tool ever handed one issue to two agents.

Measured with OmniGraph 0.13.0 on one laptop with other work running, so
treat the timings as rough. After `bd gc`, which shrank the imported Dolt
journal from 314 MB to 3 MB, `ready`, `show` and `search` take 200–470 ms in
`bd` and about 200 ms in `ob`; `bd blocked` takes 1.3 s. `ob`'s writes were 2.5–7 times faster, but a local
OmniGraph store does not fsync and Dolt syncs every commit, so that gap is not
like for like. `bd import` took about 10 minutes for 2,000 issues, against under
a second for `ob`'s batched load. About 90 ms of each `ob` command is Python
starting up.

## Files

| Path | What |
|---|---|
| `schema.pg` | The ontology |
| `queries/issues.gq` | Reads: readiness, blocked, links, search, memories, guards |
| `queries/mutations.gq` | Writes: claim, release, renew, close, defer, links, comments, memories, the CAS edit |
| `policies/` | Admin, writer and reader roles |
| `cluster.yaml` | The deployment, with optional embeddings |
| `seed.jsonl`, `seed.md` | A fictional project and its description |
| `omnigraph-config.example.yaml` | Read aliases and mutation examples |
| `client/ob`, `client/ob_cli.py` | The client |
| `client/tests/test_ob.py` | End-to-end tests on local graphs, and on a served graph behind the local HTTPS gateway |
| `client/tests/bench_ob.py` | Latency and concurrent-agent benchmark |
| `client/tests/compare_bd.py` | Side-by-side run against `bd` |

```bash
cd client
python3 -m unittest discover -s tests -v                  # needs omnigraph, omnigraph-server, openssl
python3 tests/bench_ob.py --issues 2000 --agents 8        # a scratch local graph
python3 tests/bench_ob.py --target local-writer           # a running server, on a scratch branch
python3 tests/compare_bd.py --issues 2000 --agents 8      # needs bd
```

## Limits

- `ready` lists at most 500 issues and `blocked` at most 10,000; `ob stats` and
  `ob prime` count with aggregates. `ob ready` filters on the server, so the
  limit applies to matching issues; only a second `-l` label is checked in the
  client.
- Readiness follows parent links up to eight levels; GQ needs a finite bound.
  `ob` keeps hierarchies within that depth, but data loaded directly can go
  deeper.
- `upstream`, `downstream` and `ob dep tree` reach 32 links, and `ob dep tree`
  says when a chain goes on. The cycle check before `ob dep add` follows chains
  of any length.
- The close guard and the link rules read before they write; unlike the claim
  they are not atomic with the write.
- A claim does not re-check blockers atomically; a blocker added between
  `ready` and `claim` does not stop it. The same is true of beads.
- Every write to a branch takes its turn at the head, so heavy write
  contention is bounded by commit latency.
- `ob history` replays the change feed from the beginning, so its cost grows
  with history.
- beads' molecules, gates, wisps, agent mail and the `conditional-blocks` and
  `waits-for` link types are orchestration features and are not modelled.
  `ob import` maps unknown issue types to `task` with a `bd-type:` label.
