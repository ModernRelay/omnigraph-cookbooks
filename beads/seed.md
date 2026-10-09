# Reference seed: "Larkspur" (fictional note-taking app)

Human-readable twin of `seed.jsonl`. Every name is made up. Change both files
together.

**The project:** *Larkspur*, a note-taking app whose offline sync, shared
notebooks and 0.9 release are being built by three agents: `agent-planner`
files work, `agent-builder` implements it, `agent-reviewer` tests it.

**Totals (loaded):** 26 nodes and 22 edges. The seed ships no embeddings; the
`Vector(1536)` columns are null until `ob init --embed` or the offline
`omnigraph embed` pipeline fills them.

| Node type | # | Edge type | # |
|---|---|---|---|
| Issue | 22 | ChildOf | 9 |
| Comment | 2 | BlockedBy | 5 |
| Memory | 2 | RelatesTo | 2 |
| | | CommentOn | 2 |
| | | DiscoveredFrom | 1 |
| | | Duplicates | 1 |
| | | Supersedes | 1 |
| | | MemoryAbout | 1 |

## Issues

| Slug | Kind | Status | P | Parent | Waits on |
|---|---|---|---|---|---|
| `lk-sync` | epic | open | 0 | | |
| `lk-schema` | task | closed | 1 | `lk-sync` | |
| `lk-queue` | feature | in_progress (`agent-builder`, leased) | 1 | `lk-sync` | `lk-schema` (closed) |
| `lk-conflict` | feature | open | 1 | `lk-sync` | `lk-queue` |
| `lk-sync-docs` | task | open | 3 | `lk-sync` | `lk-conflict` |
| `lk-crash-empty` | bug | open | 0 | | |
| `lk-crash-dup` | bug | closed | 1 | | |
| `lk-crdt-spike` | spike | closed | 2 | | |
| `lk-decide-crdt` | decision | closed | 1 | | |
| `lk-share` | epic | open | 1 | | `lk-acl` |
| `lk-acl` | task | open | 1 | | |
| `lk-share-api` | feature | open | 2 | `lk-share` | |
| `lk-share-ui` | feature | open | 2 | `lk-share` | |
| `lk-legacy` | epic | closed | 3 | | `lk-acl` |
| `lk-import-md` | feature | open | 2 | `lk-legacy` | |
| `lk-release` | milestone | open | 1 | | |
| `lk-changelog` | chore | open | 2 | `lk-release` | |
| `lk-version` | chore | open | 3 | `lk-release` | |
| `lk-queue-v1` | task | closed | 2 | | |
| `lk-mobile-perf` | task | deferred | 3 | | |
| `lk-telemetry` | feature | open, hidden until 2027-01-15 | 3 | | |
| `lk-search` | feature | open | 2 | | |

Annotations: `lk-crash-empty` was discovered from `lk-queue`; `lk-crash-dup`
duplicates it; `lk-queue` supersedes `lk-queue-v1`; `lk-conflict` and
`lk-decide-crdt` relate to `lk-crdt-spike`.

## What the seed demonstrates

`ready` returns eight issues, highest priority first: `lk-sync`,
`lk-crash-empty`, `lk-acl`, `lk-release`, `lk-import-md`, `lk-changelog`,
`lk-search`, `lk-version`. `blocked` returns five:

| Issue | Why |
|---|---|
| `lk-conflict` | waits on `lk-queue`, which is in progress |
| `lk-sync-docs` | waits on `lk-conflict` |
| `lk-share` | waits on `lk-acl` |
| `lk-share-api`, `lk-share-ui` | their parent `lk-share` passes its block down |

Each rule appears once:

- **A closed blocker releases its dependent:** `lk-queue` waits on the closed
  `lk-schema`, so only its own claim keeps it out of `ready`.
- **An open parent with an outside blocker blocks its children:** the two
  sharing tasks.
- **A closed parent passes nothing down:** `lk-legacy` was closed while
  `lk-acl` was still open, and its child `lk-import-md` is ready.
- **A parent waits for its children through the link alone:** `lk-release` is
  ready to claim, but `ob close lk-release` refuses while `lk-changelog` and
  `lk-version` are open.
- **Deferral:** `lk-mobile-perf` is deferred and `lk-telemetry` is hidden until
  2027, so neither is ready.

Loaded into beads (`bd` 1.3.1) through `ob export`, the same issues give the
same ready and blocked sets.

## Comments and memories

| Slug | On | Text |
|---|---|---|
| `c-conflict-1` | `lk-conflict` | Last-writer-wins lost a paragraph in testing; going with the CRDT from the spike. |
| `c-crash-1` | `lk-crash-empty` | Reproduces on a fresh install with airplane mode on. |

| Memory | About | Text |
|---|---|---|
| `test-before-push` | | Run `make test-sync` before pushing; the sync suite is not in the default target. |
| `crdt-choice` | `lk-conflict` | Sync merges at paragraph level with a CRDT; do not reintroduce last-writer-wins. |
