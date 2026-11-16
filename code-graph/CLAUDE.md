# CLAUDE.md — code-graph

Scoped guidance for the `code-graph/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general Omnigraph operations — schema authoring, queries,
loading, branches, cluster commands, the CLI — use the **omnigraph** skill;
this file covers only what is specific to code-graph.

## What this is

A graph of one repository's definitions (`Symbol`) and the references between
them, one graph state per git revision, generated from a SCIP index. `main` is
the indexed default branch; each pull request is a branch holding its
revision, reviewed with `branch diff` and merged by a person. The seed is real:
hono's router at the parent of PR #5267 (`seed.jsonl`) and at the PR
(`examples/pr-5267.jsonl`). `seed.md` lists what each read returns.

## Key files

- `schema.pg` — the executable schema. `Symbol` keys are SCIP descriptors
  without scheme, package or version.
- `queries/code.gq` — the stored reads. There are no stored mutations.
- `seed.jsonl`, `examples/pr-5267.jsonl` — generated; never edit them.
- `sources/` — `source.json` pins the repository, commits, slice and indexer;
  `fetch.py` checks out and indexes; `build_seed.py` converts; `scip_index.py`
  reads SCIP with the standard library; `indexer/` locks scip-typescript and
  its TypeScript.
- `cluster.yaml` (graph `code`), `policies/`, `omnigraph-config.example.yaml`.

## Writing

- **The graph is only written by loading generated revisions.** Do not
  `mutate` symbols or references by hand: the next load of that revision
  replaces them.
- **Every revision loads with `--mode overwrite`.** It replaces each type in
  the file, so deleted symbols and references leave the branch; `merge` would
  keep them. A type missing from the file keeps its old rows, which is why
  `build_seed.py` refuses to write the cookbook's files without every type.
  Against a server, `overwrite` needs `--yes`.
- **`act-agent` is the indexer.** It opens branches and writes on them only;
  `act-writer` merges into `main` and deletes branches.
- **To change the seed**, change `sources/source.json` or the converter, run
  `fetch.py` then `build_seed.py`, update `seed.md` from the reads' actual
  output, and confirm `build_seed.py --check`. CI does not run these scripts.

## Query notes

- Keys contain backticks and dots: ``src/router/`utils.ts`/createNullObject.``.
  Find a key with `symbols_named` or `file_symbols`, and pass it in single
  quotes in a shell.
- A line number is on `Location` (`$s definedAt $l`), never on `Symbol`.
- `References` means "names", not "calls": filter on the bound edge's `call`
  for call sites (`$c $r:references $t`, then `$r.call`).
- Multi-hop reads work because every definition is one `Symbol` type; keep it
  that way rather than adding a node type per kind.
- Lint after every edit: `omnigraph lint --schema schema.pg --query
  queries/code.gq`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
