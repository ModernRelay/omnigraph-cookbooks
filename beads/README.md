# Beads: an agent work queue

A dependency-aware issue tracker for coding agents, in the style of
[beads](https://github.com/gastownhall/beads) (`bd`): file work, link what
waits on what, ask for ready work, claim it, close it. Readiness is derived on
every read with beads' rules, claims are atomic, and the commit history is the
audit trail. Graph ID `beads`.

The bundle (schema, stored queries, policies, seed) works with plain
`omnigraph` commands. [`client/ob`](client/) is a small Python client with the
`bd` command set; it adds the retry and reconciliation that many agents
writing at once need.

For a full engineering knowledge graph (specs, components, PRs, releases,
incidents) see [dev-graph](../dev-graph/); this cookbook is the minimal queue.

## Quick start

Use the shared [local setup](../README.md#local-setup) with folder `beads` and
graph `beads`, then load `seed.jsonl` (a fictional project, described in
[seed.md](seed.md)). With the server up:

```bash
omnigraph query ready --server http://127.0.0.1:8080 --graph beads
omnigraph query blocked --server http://127.0.0.1:8080 --graph beads
omnigraph mutate claim --server http://127.0.0.1:8080 --graph beads \
  --params '{"id":"lk-acl","who":"act-writer","lease":null}'
```

Or with the client, as an agent would:

```bash
export PATH=$PWD/client:$PATH
export OB_SERVER=http://127.0.0.1:8080 OB_GRAPH=beads OB_TOKEN=local-writer-token OB_ACTOR=act-writer
ob ready
ob claim lk-acl --lease 2h     # or: ob ready --claim, which takes the top issue
ob show lk-acl
ob close lk-acl --reason "ACLs enforced server-side"
ob ready                       # the sharing tasks are ready now
```

`ob` also runs without a server on a local graph of its own:

```bash
cd your-project
ob init                        # creates .ob/ with a local graph
ob create "Fix login timeout" -t bug -p 1
ob create "Write auth docs" --deps <bug-id>
ob ready
ob onboard >> AGENTS.md        # tell agents how to use it
```

Add `--json` to any `ob` command for machine-readable output. `ob` needs only
Python 3.10+ and the `omnigraph` CLI on `PATH` (or `OB_OMNIGRAPH`).

## Model

[`schema.pg`](schema.pg) has three node types and eight edge types.

| Type | Holds |
|---|---|
| `Issue` | A unit of work: title, kind, status (`open`, `in_progress`, `deferred`, `closed`), priority 0–4, labels, the claim (`assignee`, `lease_expires_at`), deferral and free-form JSON `metadata` |
| `Comment` | A comment, linked to one issue by `CommentOn` |
| `Memory` | A durable project fact that `ob prime` gives every new session, optionally linked to issues by `MemoryAbout` |
| `BlockedBy` | The source cannot start until the target closes |
| `ChildOf` | The source is part of the target; at most one parent (`@card(0..1)`) |
| `RelatesTo`, `DiscoveredFrom`, `Duplicates`, `Supersedes` | Annotations; none affects readiness |

There is no `blocked` status: blocking is derived from the links, so it cannot
disagree with them. Every edge is keyed by its endpoints, so adding a link twice
is a no-op.

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
does.

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
- **Per-issue compare-and-swap edits.** Every write stamps `updated_at`.
  `ob update` writes back with `where slug = $id and updated_at = $expected`
  and re-reads if someone edited the issue in between, so concurrent label
  edits both survive.
- **Leases, not heartbeats.** A claim can carry a lease (`--lease 2h`);
  `ob renew` extends it and `ob reclaim` reopens every expired one in one
  update. A heartbeat every few seconds would be a commit every few seconds.
- **History from commits.** `ob history <id>` reads the change feed; each
  commit records its actor, which in served mode comes from the bearer token.

## Roles

The bundle's [policies](policies/) follow the repository's three roles:
`act-admin` manages configuration and merges planning branches into `main`;
`act-writer` (agents) reads, writes, and creates or deletes branches;
`act-reader` (dashboards, auditors) reads and invokes stored reads, and is
refused on stored mutations. `OB_ACTOR` should name the same actor as the
token: the history records the token's actor regardless, but `assignee` is a
value the client sends.

Plans go on branches: `ob branch create plan`, then
`ob --branch plan create …` files work that `main` does not see until an admin
runs `ob branch merge plan`.

## Semantic search (optional)

With an embedding provider configured (see [cluster.yaml](cluster.yaml)),
`ob init --embed` fills issue-title and memory vectors through the offline
`omnigraph embed` pipeline before each write, and `ob similar` and
`ob recall --semantic` rank by meaning. OmniGraph 0.13.0's pipeline embeds
`type: Issue\ntitle: <value>` while a query embeds its text as given, so `ob`
sends queries in the pipeline's shape. Set `OMNIGRAPH_EMBEDDINGS_MOCK=1` for
deterministic test vectors.

## Compared with beads

`client/tests/compare_bd.py` runs `bd` 1.3.1 and `ob` on the same generated
project (`bd`'s usage metrics off). On 2,000 issues and 3,171 links, and on this
seed, both return **the same ready and blocked sets**; reaching that fixed
`ob`'s handling of closed parents and adopted beads' two link rules above.
Neither tool ever handed one issue to two agents.

Measured on one laptop with other work running, so treat the timings as
rough. After `bd gc`, which shrank the imported Dolt journal from 314 MB to
3 MB, `ready`, `show` and `search` take 200–470 ms in `bd` and about 200 ms in
`ob`; `bd blocked` takes 1.3 s. `ob`'s writes were 2.5–7 times faster, but a local
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
| `client/tests/test_ob.py` | End-to-end tests, local and served |
| `client/tests/bench_ob.py` | Latency and concurrent-agent benchmark |
| `client/tests/compare_bd.py` | Side-by-side run against `bd` |

```bash
cd client
python3 -m unittest discover -s tests -v                  # needs omnigraph (and omnigraph-server for served mode)
python3 tests/bench_ob.py --issues 2000 --agents 8 [--served]
python3 tests/compare_bd.py --issues 2000 --agents 8      # needs bd
```

## Limits

- `ready` lists at most 500 issues and `blocked` at most 10,000; `ob stats` and
  `ob prime` count with aggregates.
- Readiness follows parent links up to eight levels; GQ needs a finite bound.
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
