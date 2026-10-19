#!/usr/bin/env python3
"""Qualify cookbook bundles with released binaries against disposable local roots."""

import collections
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CLI = shutil.which(os.environ.get("OMNIGRAPH_BIN", "omnigraph"))
SERVER = shutil.which(os.environ.get("OMNIGRAPH_SERVER_BIN", "omnigraph-server"))
COOKBOOKS = {
    "industry-intel": ("spike", "recent_signals"),
    "pharma-intel": ("pharma", "recent_signals"),
    "second-brain": ("brain", "people_all"),
    "vc-os": ("vcos", "deals_open"),
    "dev-graph": ("dev", "open_epics"),
    "beads": ("beads", "ready"),
    "company-brain": ("knowledge", "current_decisions"),
}
# Cookbooks whose policy lets act-agent write only on unprotected branches.
BRANCH_ONLY_AGENTS = {"company-brain"}
TOKENS = {actor: f"cookbook-test-{actor}"
          for actor in ("act-admin", "act-writer", "act-reader", "act-agent")}
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(url, path, actor="act-admin", body=None, expected=200):
    headers = {"Omnigraph-Http-Api": "0.13", "Authorization": f"Bearer {TOKENS[actor]}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url + path, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        response = HTTP.open(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read()
        assert response.status == expected, (path, response.status, payload[:1000])
        assert response.headers.get_all("Omnigraph-Http-Api") == ["0.13"]
        return json.loads(payload)


def run(env, *args, ok=True):
    result = subprocess.run([CLI, *args], env=env, capture_output=True, text=True, timeout=120)
    if (result.returncode == 0) != ok:
        raise AssertionError(f"{args}: exit {result.returncode}\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    return json.loads(result.stdout) if ok and "--json" in args else result


def qualify(name, graph, stored_query, workspace, env):
    source = ROOT / name
    bundle = workspace / name
    bundle.mkdir()
    # Copy only declared inputs, never local graph state or operator credentials.
    for file in ("cluster.yaml", "schema.pg", "seed.jsonl"):
        shutil.copyfile(source / file, bundle / file)
    for directory in ("queries", "policies"):
        shutil.copytree(source / directory, bundle / directory)

    valid = run(env, "cluster", "validate", "--config", str(bundle), "--json")
    assert valid["ok"]
    for query in sorted((bundle / "queries").glob("*.gq")):
        run(env, "lint", "--schema", str(bundle / "schema.pg"), "--query", str(query), "--json")
    plan = run(env, "cluster", "plan", "--config", str(bundle), "--json")
    assert plan["ok"]
    applied = run(env, "cluster", "apply", "--config", str(bundle), "--as", "act-admin", "--json")
    assert applied["status"] == "complete" and applied["result"]["converged"]
    status = run(env, "cluster", "status", "--config", str(bundle), "--json")
    lock = status["state_observations"]["lock_id"]
    assert status["state_observations"]["locked"] and lock
    # This harness created the exclusive local root. The direct child exited;
    # no external object store or other owner can have accepted work here.
    run(env, "cluster", "force-unlock", lock, "--config", str(bundle), "--json")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    server_env = {**env, "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON": json.dumps(TOKENS)}
    with (bundle / "server.log").open("w") as log:
        process = subprocess.Popen([SERVER, "--cluster", str(bundle), "--bind", f"127.0.0.1:{port}"],
                                   env=server_env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while True:
                assert process.poll() is None, f"server exited; see {bundle / 'server.log'}"
                try:
                    ready = request(url, "/readyz")
                    assert ready["loading_graph_count"] == 0
                    break
                except (OSError, AssertionError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            scope = ("--server", url, "--graph", graph)
            def verify_receipt(commit):
                assert commit and commit["graph_commit_id"], "write must return its exact commit"
                # This fixture has one writer and no intervening operation.
                snapshot = request(url, f"/graphs/{graph}/snapshot", "act-reader")
                # The commit API represents main as null.
                assert (commit["graph_branch"] or "main") == snapshot["graph_branch"] == "main"
                assert commit["graph_manifest_version"] == snapshot["graph_manifest_version"]
                assert request(url, f"/graphs/{graph}/commits/{commit['graph_commit_id']}", "act-reader") == commit
            seed = run(env, "load", *scope, "--data", str(bundle / "seed.jsonl"), "--mode", "append", "--json")
            verify_receipt(seed["commit"])
            rows = [json.loads(line) for line in (bundle / "seed.jsonl").read_text().splitlines() if line.strip()]
            counts = collections.Counter(row["type"] for row in rows if "type" in row)
            expected_counts = collections.Counter(
                ("node", row["type"]) if "type" in row else ("edge", row["edge"])
                for row in rows
            )
            node = next(iter(counts))
            query = f"query cookbook_count() {{ match {{ $n: {node} }} return {{ count($n) as total }} }}"
            def count():
                snapshot = request(url, f"/graphs/{graph}/snapshot", "act-reader")
                actual = {(item["entity_kind"], item["type_name"]): item["entity_count"]
                          for item in snapshot["datasets"] if item["entity_count"]}
                assert actual == dict(expected_counts), (actual, expected_counts)
                result = request(url, f"/graphs/{graph}/query", "act-reader", {"query": query})
                assert result["rows"] == [{"total": counts[node]}], result
            count()
            read = run({**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-reader"]}, "query", stored_query, *scope, "--json")
            assert read["rows"], f"{stored_query} must demonstrate populated seed data"
            # Writers can create and retire a review branch but cannot deploy.
            writer = {**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-writer"]}
            run(writer, "branch", "create", "cookbook-review", *scope, "--json")
            run(writer, "branch", "delete", "cookbook-review", *scope, "--yes", "--json")
            refused = run(writer, "cluster", "plan", "--config", str(bundle), "--server", url, "--json", ok=False)
            assert "403" in refused.stdout + refused.stderr or "denied" in (refused.stdout + refused.stderr).lower(), (refused.stdout, refused.stderr)

            # Add a harmless type and query to exercise real schema + registry
            # activation on the same PID, not merely an unchanged apply.
            with (bundle / "schema.pg").open("a") as schema:
                schema.write("\nnode CookbookCheck {\n  slug: String @key\n}\n")
            (bundle / "queries/cookbook-check.gq").write_text(
                "query cookbook_check() { match { $n: CookbookCheck } return { count($n) as total } }\n")
            before = run(env, "snapshot", *scope, "--json")
            run(env, "cluster", "plan", "--config", str(bundle), "--server", url, "--json")
            assert run(env, "snapshot", *scope, "--json") == before, "plan changed graph state"
            deployed = run(env, "cluster", "apply", "--config", str(bundle), "--server", url, "--json")
            assert deployed["active"] and not deployed["in_progress"], deployed
            exact = run(env, "cluster", "status", "--server", url, "--deployment-id",
                        deployed["deployment"]["result"]["id"], "--wait", "--json")
            assert exact["active"] and not exact["in_progress"]
            assert exact["deployment"]["result"] == deployed["deployment"]["result"]
            check = run(env, "query", "cookbook_check", *scope, "--json")
            assert check["rows"] == [{"total": 0}], check
            sample = bundle / "check.jsonl"
            sample.write_text('{"type":"CookbookCheck","data":{"slug":"smoke"}}\n')
            # Refuse a fresh valid row for policy, not a duplicate-key error.
            refused = run({**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-reader"]}, "load", *scope,
                          "--data", str(sample), "--mode", "append", "--json", ok=False)
            assert "403" in refused.stdout + refused.stderr or "denied" in (refused.stdout + refused.stderr).lower(), (refused.stdout, refused.stderr)
            assert run(env, "query", "cookbook_check", *scope, "--json")["rows"] == [{"total": 0}]
            if name in BRANCH_ONLY_AGENTS:
                # An agent drafts on its own branch; only a person merges into main.
                agent = {**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-agent"]}
                refused = run(agent, "load", *scope, "--data", str(sample), "--mode", "append", "--json", ok=False)
                assert "403" in refused.stdout + refused.stderr, (refused.stdout, refused.stderr)
                run(agent, "branch", "create", "agent-draft", *scope, "--json")
                drafted = run(agent, "load", *scope, "--branch", "agent-draft", "--data", str(sample),
                              "--mode", "append", "--json")
                assert drafted["commit"]["graph_commit_id"]
                refused = run(agent, "branch", "merge", "agent-draft", "--into", "main", *scope, "--json", ok=False)
                assert "403" in refused.stdout + refused.stderr, (refused.stdout, refused.stderr)
                # Agents cannot delete a branch, so one cannot discard another's draft.
                refused = run(agent, "branch", "delete", "agent-draft", *scope, "--yes", "--json", ok=False)
                assert "403" in refused.stdout + refused.stderr, (refused.stdout, refused.stderr)
                run(writer, "branch", "delete", "agent-draft", *scope, "--yes", "--json")
                assert run(env, "query", "cookbook_check", *scope, "--json")["rows"] == [{"total": 0}]
            written = run(writer, "load", *scope, "--data", str(sample), "--mode", "append", "--json")
            verify_receipt(written["commit"])
            expected_counts[("node", "CookbookCheck")] = 1
            assert request(url, f"/graphs/{graph}/queries/cookbook_check", "act-reader",
                           {"params": {}})["rows"] == [{"total": 1}]
            count()
            if name == "beads":
                beads_client_journey(url, env)
            if name == "company-brain":
                company_brain_journey(url, env)
            assert process.poll() is None
            assert request(url, "/readyz")["loading_graph_count"] == 0
            print(f"PASS {name}: lint, seed counts, roles, branches, live schema/query activation"
                  + (", ob client" if name == "beads" else "")
                  + (", review journey" if name == "company-brain" else ""), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def beads_client_journey(url, env):
    """Drive beads' `ob` client over HTTP against the served graph: stored
    queries only, the token's actor in history, and the reader's refusal."""
    base = {k: v for k, v in env.items() if not k.startswith("OB_")}
    base.update(OB_OMNIGRAPH=CLI, OB_SERVER=url, OB_GRAPH="beads")

    def ob(actor, *args, ok=True):
        result = subprocess.run([str(ROOT / "beads/client/ob"), "--json", *args], capture_output=True, text=True,
                                timeout=120, env={**base, "OB_ACTOR": actor, "OB_TOKEN": TOKENS[actor]})
        if (result.returncode == 0) != ok:
            raise AssertionError(f"ob {args} as {actor}: exit {result.returncode}\n{result.stdout}{result.stderr}")
        return json.loads(result.stdout) if ok else result

    def ready(actor):
        return [row["slug"] for row in ob(actor, "ready", "-n", "500")]

    blocker = ob("act-admin", "create", "served blocker")["id"]
    work = ob("act-admin", "create", "served work", "--deps", blocker)["id"]
    assert blocker in ready("act-writer") and work not in ready("act-writer")
    ob("act-writer", "claim", blocker)
    ob("act-writer", "close", blocker)
    assert work in ready("act-reader")
    ob("act-reader", "claim", work, ok=False)
    events = [(e["actor"], e["type"]) for e in ob("act-reader", "history", blocker)]
    assert events == [("act-admin", "Issue"), ("act-admin", "BlockedBy"), ("act-writer", "Issue"),
                      ("act-writer", "Issue")], events


def company_brain_journey(url, env):
    """An agent records on a branch, a person merges and settles on main.
    Creates refuse an existing slug, and a rejected successor can be
    withdrawn so the decision it named can be replaced again."""
    scope = ("--server", url, "--graph", "knowledge")
    agent = {**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-agent"]}
    writer = {**env, "OMNIGRAPH_BEARER_TOKEN": TOKENS["act-writer"]}

    def mutate(who, query, params, *branch, ok=True):
        return run(who, "mutate", query, *scope, *branch, "--params", json.dumps(params), "--json", ok=ok)

    def rows(query, params=None):
        return run(env, "query", query, *scope, "--params", json.dumps(params or {}), "--json")["rows"]

    def refused_by_card(result):
        assert "@card violation" in result.stdout + result.stderr, (result.stdout, result.stderr)

    claim = {"slug": "checker-claim", "kind": "proposal", "statement": "Resume the billing migration.",
             "quote": "Let's resume billing.", "locator": None, "recorded_at": "2026-10-15T00:00:00.000Z",
             "source": "doc:billing-plan", "speaker": "dana"}
    run(agent, "branch", "create", "agent-claims", *scope, "--json")
    mutate(agent, "record_claim", claim, "--branch", "agent-claims")
    refused_by_card(mutate(agent, "record_claim", claim, "--branch", "agent-claims", ok=False))
    refused = mutate(agent, "verify_claim", {"slug": "checker-claim"}, ok=False)
    assert "403" in refused.stdout + refused.stderr, (refused.stdout, refused.stderr)
    run(writer, "branch", "merge", "agent-claims", "--into", "main", *scope, "--json")
    run(writer, "branch", "delete", "agent-claims", *scope, "--yes", "--json")
    mutate(writer, "verify_claim", {"slug": "checker-claim"})

    # Re-recording a verified seed claim must not reset it to unverified.
    refused_by_card(mutate(writer, "record_claim", {**claim, "slug": "launch-nov-13"}, ok=False))
    assert not rows("accepted_on_unverified")

    successor = {"previous": "billing-freeze", "claim": "checker-claim", "reason": "Resume", "slug": "billing-go",
                 "title": "Resume billing", "statement": "Resume.", "rationale": None, "decided_at": None,
                 "recorded_at": "2026-10-15T00:00:00.000Z", "project": "billing-migration"}
    refused_by_card(mutate(writer, "propose_successor", {**successor, "slug": "billing-freeze"}, ok=False))
    mutate(writer, "propose_successor", successor)
    mutate(writer, "reject_decision", {"slug": "billing-go"})
    statuses = {row["decision"]: row["status"] for row in rows("project_decisions", {"project": "billing-migration"})}
    assert statuses == {"Freeze the billing migration until Q1": "accepted", "Resume billing": "rejected"}, statuses
    assert not rows("decision_successor", {"decision": "billing-freeze"})
    refused_by_card(mutate(writer, "propose_successor", {**successor, "slug": "billing-go-2"}, ok=False))
    mutate(writer, "withdraw_successor", {"previous": "billing-freeze", "successor": "billing-go"})
    mutate(writer, "propose_successor", {**successor, "slug": "billing-go-2"})

    # The reason survives a successor whose claim contradicts nothing.
    assert rows("why_superseded", {"decision": "billing-freeze"}) == [
        {"replaced_by": "billing-go-2", "status": "proposed", "reason": "Resume"}]
    assert not rows("superseding_contradictions", {"decision": "billing-freeze"})

    # A deprecated successor keeps the decision it replaced out of the log.
    mutate(writer, "deprecate_decision", {"slug": "search-in-house"})
    current = {row["decision"] for row in rows("current_decisions")}
    assert "search-vendor-buy" not in current and "search-in-house" not in current, current

    # A current decision on a rejected claim is flagged; a cancelled item
    # does not count as implementing its decision.
    mutate(writer, "reject_claim", {"slug": "provider-certifies-nov-6"})
    assert rows("current_on_rejected") == [{"decision": "checkout-launch-nov-13", "claim": "provider-certifies-nov-6"}]
    mutate(writer, "cancel_action", {"slug": "launch-checklist"})
    assert "checkout-launch-nov-13" in {row["decision"] for row in rows("unimplemented_decisions")}

    # Departures stay departed: an ended stint recorded again stays closed,
    # a profile update keeps active, and a retired actor cannot be re-added.
    mutate(writer, "add_member", {"person": "chen", "team": "discovery", "role": "engineer", "since": "2025-05-12"})
    assert "Chen Wei" not in {row["person"] for row in rows("team_members", {"team": "discovery"})}
    mutate(writer, "deactivate_person", {"slug": "chen"})
    mutate(writer, "update_person", {"slug": "chen", "name": "Chen Wei", "title": "Senior engineer",
                                     "email": "chen@lanternworks.example", "slack": "u07chen", "github": "chenwei"})
    assert rows("person_handles", {"person": "chen"})[0]["active"] is False
    mutate(writer, "deactivate_actor", {"slug": "act-slack-bot"})
    refused_by_card(mutate(writer, "add_actor", {"slug": "act-slack-bot", "kind": "agent", "name": "Slack agent",
                                                 "purpose": None, "person": "eli"}, ok=False))


def main():
    if not CLI or not SERVER:
        raise SystemExit("Put 0.13.0 omnigraph and omnigraph-server on PATH or set OMNIGRAPH_BIN / OMNIGRAPH_SERVER_BIN")
    workspace = Path(tempfile.mkdtemp(prefix="omnigraph-cookbooks-test-"))
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("OMNIGRAPH_", "AWS_", "AZURE_"))}
    env.update(OMNIGRAPH_HOME=str(workspace / "operator"), OMNIGRAPH_BEARER_TOKEN=TOKENS["act-admin"])
    try:
        version = run(env, "version").stdout
        assert version.splitlines()[0] == "omnigraph 0.13.0", version
        for name, (graph, query) in COOKBOOKS.items():
            qualify(name, graph, query, workspace, env)
    except BaseException:
        print(f"Failed fixture retained: {workspace}", flush=True)
        raise
    else:
        shutil.rmtree(workspace)
        print(f"All {len(COOKBOOKS)} cookbooks passed against OmniGraph 0.13.0.")


if __name__ == "__main__":
    main()
