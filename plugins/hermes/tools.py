"""Tool handlers + lifecycle hooks.

Handlers take ``(args: dict, **kwargs)`` and ALWAYS return a JSON string — never
raise (a raised exception would break the tool loop). They funnel every CLI call
through :mod:`runner` and resolve config through :mod:`discovery`.
"""

from __future__ import annotations

import json
import os
import re
import tempfile

try:
    from . import discovery, runner, verify, capture, settings
except ImportError:        # standalone dev tests
    import discovery, runner, verify, capture, settings

ROW_CAP = 200              # max rows returned inline from a read query


# ---- helpers ---------------------------------------------------------------

def _resolve(args: dict):
    target = (args or {}).get("target") or settings.default_target()
    return discovery.resolve(target=target, explicit_config=(args or {}).get("config"))


def _no_config():
    return json.dumps({"error": "No Omnigraph config found. Run omnigraph_doctor "
                                "(or set OMNIGRAPH_CONFIG / plugins.entries.omnigraph.config_paths)."})


def _split_meta(records: list):
    if records and isinstance(records[0], dict) and "row_count" in records[0]:
        return records[0], records[1:]
    return None, records


def _run_kwargs(args: dict) -> dict:
    return dict(
        alias=args.get("alias"),
        args=args.get("args"),
        query_file=args.get("query_file"),
        query_name=args.get("query_name"),
        query_string=args.get("query_string"),
        params=args.get("params"),
        branch=args.get("branch"),
    )


# ---- read tools ------------------------------------------------------------

def doctor(args: dict, **kwargs) -> str:
    try:
        report: dict = {"binary": runner.OMNIGRAPH_BIN}
        v = runner.run("version")
        report["version"] = (v.stdout or v.stderr).strip().splitlines()[0] if (v.stdout or v.stderr) else None
        report["binary_ok"] = v.returncode == 0

        infos = discovery.scan()
        report["configs"] = []
        overall_issues: list[str] = []
        for info in infos:
            graphs = {}
            for g in info.graphs:
                uri = info.graph_uris.get(g, "")
                # token env name from the source config
                token_env = _token_env(info.path, g)
                token_set = bool(os.environ.get(token_env)) if token_env else None
                remote = uri.startswith("http://") or uri.startswith("https://")
                reach = None
                if remote:
                    c = runner.run("commit list", config=info.path, target=g,
                                   branch="main", env_file=info.env_file, timeout=15)
                    reach = "ok" if c.ok else (f"http {c.http}" if c.http else f"rc {c.returncode}")
                    if not c.ok:
                        overall_issues.append(f"{g}: unreachable ({reach})")
                if token_env and token_set is False:
                    overall_issues.append(f"{g}: token env {token_env} not set")
                graphs[g] = {"uri": uri, "remote": remote, "token_env": token_env,
                             "token_set": token_set, "reachable": reach}
            report["configs"].append({
                "path": info.path, "cli_graph": info.cli_graph,
                "aliases": sorted(info.aliases.keys()), "graphs": graphs,
            })
        report["ok"] = report["binary_ok"] and not overall_issues
        report["issues"] = overall_issues
        report["registry"] = str(discovery.registry_path())
        return json.dumps(report)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def _token_env(config_path: str, graph: str) -> str | None:
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return ((data.get("graphs") or {}).get(graph) or {}).get("bearer_token_env")
    except Exception:
        return None


def targets(args: dict, **kwargs) -> str:
    try:
        infos = discovery.scan()        # fresh (includes aliases); also refreshes the registry
        return json.dumps({"configs": [
            {"path": i.path, "kind": i.kind, "cli_graph": i.cli_graph,
             "graphs": i.graphs, "aliases": sorted(i.aliases.keys())}
            for i in infos
        ]})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def schema(args: dict, **kwargs) -> str:
    try:
        res = _resolve(args)
        if not res.config_path:
            return _no_config()
        s = runner.run("schema show", config=res.config_path, target=res.target,
                       env_file=(res.info.env_file if res.info else None))
        if not s.ok:
            return json.dumps({"error": "schema show failed", "stderr": s.error_text()[:600]})
        schema_file = s.stdout_file
        if not schema_file:
            fd, schema_file = tempfile.mkstemp(prefix="omni-schema-", suffix=".pg")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(s.stdout)
        summary = {
            "nodes": len(re.findall(r"(?m)^\s*node\s+\w+", s.stdout)),
            "edges": len(re.findall(r"(?m)^\s*edge\s+\w+", s.stdout)),
            "interfaces": len(re.findall(r"(?m)^\s*interface\s+\w+", s.stdout)),
        }
        return json.dumps({"target": res.target, "config": res.config_path,
                           "schema_file": schema_file, "bytes": len(s.stdout),
                           "summary": summary,
                           "note": "Read schema_file for exact node/edge/property/enum names."})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def query(args: dict, **kwargs) -> str:
    try:
        res = _resolve(args)
        if not res.config_path:
            return _no_config()
        q = runner.run("query", config=res.config_path, target=res.target,
                       env_file=(res.info.env_file if res.info else None), **_run_kwargs(args))
        if not q.ok:
            out = {"error": "query failed", "stderr": q.error_text()[:600]}
            if q.http:
                out["http"] = q.http
            return json.dumps(out)
        meta, data = _split_meta(q.records)
        truncated = len(data) > ROW_CAP
        return json.dumps({
            "target": res.target,
            "row_count": (meta or {}).get("row_count", len(data)),
            "returned": min(len(data), ROW_CAP),
            "truncated": truncated,
            "rows": data[:ROW_CAP],
            "stdout_file": q.stdout_file,
        })
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def search(args: dict, **kwargs) -> str:
    try:
        res = _resolve(args)
        if not res.config_path:
            return _no_config()
        alias = (args or {}).get("alias") or settings.search_alias(res.target)
        if not alias:
            return json.dumps({"error": "No search alias configured. Pass alias=, or set "
                                        "plugins.entries.omnigraph.search_aliases.<target>."})
        a = [(args or {}).get("query_text")]
        q = runner.run("query", alias=alias, args=a, config=res.config_path, target=res.target,
                       env_file=(res.info.env_file if res.info else None))
        if not q.ok:
            return json.dumps({"error": "search failed", "stderr": q.error_text()[:600],
                               "hint": "The search alias's query must end with `limit N`."})
        meta, data = _split_meta(q.records)
        return json.dumps({"target": res.target, "alias": alias,
                           "row_count": (meta or {}).get("row_count", len(data)),
                           "rows": data[:ROW_CAP]})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ---- write tools -----------------------------------------------------------

def mutate(args: dict, **kwargs) -> str:
    try:
        res = _resolve(args)
        if not res.config_path:
            return _no_config()
        tgt, info = res.target, res.info
        env_file = info.env_file if info else None
        is_remote = info.is_remote(tgt) if info else False

        branch = (args or {}).get("branch") or f"hermes-{tgt or 'wip'}"
        warnings = []
        if branch == "main":
            warnings.append("Writing to main is discouraged — prefer a feature branch.")
        else:
            # ensure the feature branch exists (idempotent; ignore 'already exists')
            runner.run("branch create", args=[branch], extra_args=["--from", "main"],
                       config=res.config_path, target=tgt, env_file=env_file)

        rk = _run_kwargs(args)
        rk.pop("branch", None)
        result = verify.mutate_verified(config=res.config_path, target=tgt, is_remote=is_remote,
                                        branch=branch, env_file=env_file, **rk)
        if warnings:
            result["warnings"] = warnings
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# capture handler lives in capture.py
capture_tool = capture.capture


# ---- local-dev tools -------------------------------------------------------

def lint(args: dict, **kwargs) -> str:
    try:
        r = runner.run("lint", schema_path=(args or {}).get("schema_path"),
                       query_file=(args or {}).get("query_path"), json_flag=True)
        return json.dumps({"ok": r.ok, "result": r.parsed, "stderr": r.error_text()[:600]})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def schema_plan(args: dict, **kwargs) -> str:
    try:
        res = _resolve(args)
        r = runner.run("schema plan", config=res.config_path, target=res.target,
                       schema_path=(args or {}).get("schema_path"), json_flag=True,
                       env_file=(res.info.env_file if res.info else None))
        return json.dumps({"ok": r.ok, "result": r.parsed, "stderr": r.error_text()[:600]})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ---- hooks -----------------------------------------------------------------

def on_session_start(session_id=None, **kwargs):
    """Discover Omnigraph configs once per session (populates the registry)."""
    try:
        discovery.scan()
    except Exception:
        pass
    return None


_BANNER = (
    "Omnigraph is available (targets: {targets}). It is the canonical source of truth for "
    "people / tasks / projects / commitments / places. Consult it (omnigraph_query) before answering "
    "factual questions about those; fetch the schema (omnigraph_schema) before ad-hoc queries; writes go "
    "to a branch, never main. Load skill_view(\"omnigraph:best-practices\") for the full ruleset."
)


def banner(session_id=None, user_message="", is_first_turn=False, **kwargs):
    """pre_llm_call: inject a compact, relevance-gated context banner."""
    try:
        parts = []
        if is_first_turn:
            infos = discovery.read_registry()
            tgts = sorted({g for i in infos for g in i.graphs})
            if tgts:
                parts.append(_BANNER.format(targets=", ".join(tgts)))
        cats = capture.classify(user_message)
        if cats:
            parts.append(
                f"This message appears to contain durable info ({', '.join(cats)}). The graph is the "
                f"system of record — after addressing the request, propose importing it via omnigraph_capture."
            )
        return {"context": "\n\n".join(parts)} if parts else None
    except Exception:
        return None


def harden_output(tool_name=None, result=None, arguments=None, **kwargs):
    """transform_tool_result: redact any leaked bearer-token values from results."""
    if not isinstance(result, str):
        return None
    secrets = [os.environ.get(v) for v in ("OMNIGRAPH_BEARER_TOKEN", "OMNIGRAPH_MR_BEARER_TOKEN")]
    secrets = [s for s in secrets if s and len(s) >= 8]
    if any(s in result for s in secrets):
        for s in secrets:
            result = result.replace(s, "***")
        return result
    return None


# ---- slash command ---------------------------------------------------------

def slash(ctx, raw: str):
    parts = (raw or "").split()
    cmd = parts[0].lower() if parts else "help"
    if cmd == "doctor":
        return doctor({})
    if cmd == "targets":
        return targets({})
    if cmd == "schema":
        return schema({"target": parts[1] if len(parts) > 1 else None})
    if cmd in ("q", "query"):
        if len(parts) < 2:
            return "Usage: /omni q <alias> [args...]"
        return query({"alias": parts[1], "args": parts[2:]})
    return "Usage: /omni doctor | targets | schema [target] | q <alias> [args...]"
