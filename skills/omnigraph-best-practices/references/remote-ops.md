# Remote Graph Operations

When the graph URI is a remote endpoint (`omnigraph-server` behind ALB / CloudFront, bearer-authenticated) instead of a local S3 path, several CLI behaviors change in ways the local-RustFS workflow never exposes. This reference covers the failures and operational rituals specific to remote graphs.

## What's different about remote

A remote graph runs server-side. Every write goes through the server's transactional run engine and is gated by a connection-level idle timeout — CloudFront defaults to ~30s. The local CLI is a thin client; it never sees run state directly, only the HTTP response. That asymmetry is the root of every gotcha below.

| Local repo | Remote repo |
|---|---|
| CLI writes S3 directly | Server orchestrates writes via runs |
| No connection timeout | ~30s idle timeout (CloudFront) |
| `load` works | `load` is rejected — use `ingest` |
| CLI exit code is authoritative | CLI exit code can lie — verify via `commit list` |

## Verify after every write

The CLI's exit code is **not authoritative on remote graphs**. The proxy can drop a response after the server has already committed. Always verify by comparing `main`'s head:

```bash
HEAD_BEFORE=$(omnigraph commit list --config X --branch main --json | jq -r '.commits[0].graph_commit_id')

# … run your change / ingest …

HEAD_AFTER=$(omnigraph commit list --config X --branch main --json | jq -r '.commits[0].graph_commit_id')

if [[ "$HEAD_BEFORE" != "$HEAD_AFTER" ]]; then
  echo "landed"
else
  echo "did NOT land — safe to retry"
fi
```

For `ingest`, also compare the `ingest/<name>` branch head's `graph_commit_id` against `main`'s. **Identical means the load didn't land — empty branch left behind.**

For pointed verification of a single record:

```bash
omnigraph export --config X --type <NodeType> | grep <slug>
omnigraph export --config X --type <EdgeType> | grep <slug>
```

## 504 Gateway Timeout: response lost, write status unknown

A 504 from the proxy means the server didn't respond within the idle timeout. Two server-side outcomes are possible — **the 504 alone cannot distinguish them**:

1. **Write completed and published** — landed, `main`'s head advanced. Common for small mutations finishing just past the 30s edge.
2. **Write still in progress** — will publish or fail soon. Re-check after a minute.

Always verify via `commit list` before retrying. Blind retry on append-only types creates duplicates.

## `ingest` 504 fingerprint

`ingest` creates the branch **before** loading data. A timed-out ingest where the load didn't land leaves an empty `ingest/<name>` branch at `main`'s head. Stale numbered branches (`feature-v2`, `-v3`, `-v4` …) all sitting at the same `graph_commit_id` as `main` are the fingerprint of prior 504-blocked attempts.

Find them by comparing each branch's head against `main`'s in `omnigraph branch list --config X --json`, then delete the empty ones.

## `load` rejects remote URIs

```
error: load is only supported against local repo URIs in this milestone
```

`load` writes S3-backed storage directly — that path doesn't go through the running server. For remote graphs use `ingest` instead. Same JSONL format; the server orchestrates the run, leaves a reviewable branch.

## Version drift / `sync_branch()`

```
version drift on node:<Type>: snapshot pinned vN but dataset is at vM — call sync_branch() and retry
```

- `sync_branch()` is **not a CLI command** — it's a server-internal directive that leaked into the error text. Don't go looking for it.
- Cause: another actor committed to `main` between your CLI's snapshot pin and your `change` attempt.
- Usually self-resolves on retry — the next call re-pins.
- Calling `omnigraph snapshot` does **not** reliably re-pin for subsequent `change`s in the same session.
- If persistent, fall back to `ingest` — feature branches don't suffer from concurrent-commit drift.

## Duplicate risk on blind retry

After a 504, never retry without verifying first. Different node kinds have different retry semantics:

| Kind | Retry safety |
|---|---|
| Pointer nodes (`Org`, `Person`, `Opportunity`, `Channel`, `Actor`, `ActionItem`, `Artifact`, `Meeting`, `Technology`, `Campaign`, `UseCase`) | ✓ Idempotent — `@key` upserts dedupe |
| Append-only nodes (`Signal`, `Claim`, `Decision`, `Event`, `Interaction`, `MarketingElement`, `Policy`, `Outcome`) | ✗ Duplicates on retry — verify before retrying |
| Edges | ⚠ No `@key`. Verify via `export --type <EdgeName>` + grep. Some simple edges dedupe server-side; don't rely on it. |

## Reading large schemas safely

Remote schemas can be large (tens of KB). Tools that cap stdout (~50KB is common) will truncate or duplicate the output silently — leading to memory-based answers from agents that look correct but reference nonexistent fields.

Always redirect to a file before reading:

```bash
omnigraph schema show --config X > /tmp/schema.pg
wc -l /tmp/schema.pg
```

Then read the file with offset/limit, not via piped stdout.

## Prevention checklist

- Keep mutations small. Single-node inserts finish well under the timeout.
- Prefer `change` over `ingest` for ≤ a handful of records.
- Always run `commit list` after a 504 before deciding to retry.
- For destructive or large-batch work, use `ingest` onto a feature branch and verify the branch head before merging.
- Read large schemas via file redirect, not piped stdout.
