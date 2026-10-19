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
  `omnigraph queries list --cluster . --graph beads`.
- Readiness lives only in the queries. Do not add a stored `blocked` status or
  flag. If you change the `ready` rule, change `ready`, `ready_labeled`,
  `ready_filtered`, `ready_count` and `unblocked_open_count` together, and the
  positive forms `blocked_by_ancestor` and `ancestor_blockers`.
- A claim must stay one conditional `update` on the `Issue` row; an edge insert
  cannot re-check state.
- A write refused with `read_set_conflict` had no effect; rerun it. Do not rerun
  after a timeout or an unknown outcome without reading the issue first. `ob`
  never resends such a write: it exits 3 with `"outcome": "unknown"`. Only
  `claim`, `update` and `create` read the row and finish on their own.
- A claim ends when its issue leaves `in_progress`: keep `release`,
  `reclaim_expired`, `reopen` and `defer` clearing the assignee and lease.
- Do not link an issue to wait on its own ancestor or descendant; `ob` refuses
  both, as `bd` does. It also refuses parent loops and hierarchies deeper than
  the eight levels readiness follows, so `lineage` and `subtree` see whole
  trees.
- After a query or client change, run `python3 -m unittest discover -s tests`
  from `client/` (local graphs; it needs the 0.13.0 `omnigraph`) and
  `../scripts/check-cookbooks.py`, which also drives `ob` against the served
  cookbook. `SeedTests` pins the ready and blocked sets in `seed.md`.
