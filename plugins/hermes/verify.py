"""Remote-write verification ritual.

On a remote graph the CLI exit code can lie — a proxy may drop the response after
the server committed (or a 504 may mean the write is still in flight). So for remote
mutations we compare the target branch's commit head before and after the write and
report a definite verdict, NEVER blind-retrying — duplicates on append-only node
types are the failure this prevents.

Local repos keep the authoritative exit code (no proxy in the path).
"""

from __future__ import annotations

try:                       # loaded as a hermes plugin package
    from . import runner
except ImportError:        # loaded standalone (dev unit tests from the dir)
    import runner

# Append-only node kinds: a blind retry DUPLICATES them (no @key upsert dedup).
APPEND_ONLY = {"Signal", "Claim", "Decision", "Event", "Interaction",
               "MarketingElement", "Policy", "Outcome"}


def head_commit_id(config: str, target: str | None, branch: str,
                   env_file: str | None) -> str | None:
    """The graph_commit_id of the latest commit on *branch* (max manifest_version)."""
    res = runner.run("commit list", config=config, target=target, branch=branch,
                     env_file=env_file)
    commits = (res.parsed or {}).get("commits", []) if isinstance(res.parsed, dict) else []
    if not commits:
        return None
    head = max(commits, key=lambda c: c.get("manifest_version", -1))
    return head.get("graph_commit_id")


def mutate_verified(*, config: str, target: str | None, is_remote: bool,
                    branch: str, env_file: str | None, **run_kwargs) -> dict:
    """Run a mutation; for remote graphs, verify via the commit head before/after.

    Returns a dict with a ``status``:
      applied        — local write, exit code authoritative
      landed         — remote write confirmed (branch head advanced)
      did_not_land   — remote write not confirmed; SAFE to retry (verify again first)
      safe_retry     — 409/429: write never committed; retry (honor Retry-After on 429)
      unknown        — head unchanged with a clean exit (likely a no-op); inspect manually
      error          — local write failed
    """
    if not is_remote:
        res = runner.run("mutate", config=config, target=target, branch=branch,
                         env_file=env_file, **run_kwargs)
        return {
            "status": "applied" if res.ok else "error",
            "ok": res.ok, "returncode": res.returncode,
            "stderr": res.error_text()[:600], "result": res.parsed,
            "argv": _redacted(res.argv),
        }

    before = head_commit_id(config, target, branch, env_file)
    res = runner.run("mutate", config=config, target=target, branch=branch,
                     env_file=env_file, **run_kwargs)

    if res.http in (409, 429):
        return {
            "status": "safe_retry", "http": res.http,
            "guidance": ("Write never committed (409 stale-snapshot / 429 throttle). Safe to retry; "
                         "honor Retry-After on a 429."),
            "stderr": res.error_text()[:600], "argv": _redacted(res.argv),
        }

    after = head_commit_id(config, target, branch, env_file)
    if after and after != before:
        return {"status": "landed", "branch": branch,
                "head_before": before, "head_after": after,
                "result": res.parsed, "argv": _redacted(res.argv)}

    if res.http == 504 or not res.ok:
        return {
            "status": "did_not_land", "http": res.http, "branch": branch,
            "head_before": before, "head_after": after,
            "guidance": ("Response lost but the branch head did not advance — the write likely did not "
                         "land. SAFE to retry, but re-check the head first. NEVER blind-retry append-only "
                         f"types ({', '.join(sorted(APPEND_ONLY))}) — they duplicate."),
            "stderr": res.error_text()[:600], "argv": _redacted(res.argv),
        }

    return {"status": "unknown", "branch": branch, "head_before": before, "head_after": after,
            "note": "Clean exit but head unchanged — likely a no-op or read-only mutation. Inspect manually.",
            "result": res.parsed, "argv": _redacted(res.argv)}


def _redacted(argv: list[str]) -> list[str]:
    """argv never carries tokens (creds go via env), but redact just in case."""
    out = []
    for a in argv:
        out.append(a if not any(s in a.lower() for s in ("token", "secret", "key=")) else "***")
    return out
