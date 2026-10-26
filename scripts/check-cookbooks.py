#!/usr/bin/env python3
"""Qualify cookbook bundles with released binaries against disposable local roots.

Usage: check-cookbooks.py [COOKBOOK ...]   (default: every cookbook)
"""

import collections
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
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
    "company-brain": ("company", "current_decisions"),
    "hardware-program": ("program", "budget_rollup"),
}
# Cookbooks whose policy lets act-agent write only on unprotected branches.
BRANCH_ONLY_AGENTS = {"company-brain", "hardware-program"}
ACTORS = ("act-admin", "act-writer", "act-reader", "act-agent")
TOKENS = {actor: f"cookbook-test-{actor}" for actor in ACTORS}
GATEWAY = ROOT / "scripts" / "local-tls-gateway.py"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def target(actor):
    """The operator target that authenticates as one actor."""
    return f"ck-{actor}"


def token_variable(actor):
    return "OG_CK_" + actor.upper().replace("-", "_") + "_TOKEN"


def write_operator_config(home, endpoint, ca):
    """One server target per actor, as the root README's local setup has.
    The 0.14 CLI sends tokens only over HTTPS, so each target trusts the
    local gateway's CA and reads its token from one named variable."""
    lines = ["version: 1", "targets:"]
    for actor in ACTORS:
        lines += [f"  {target(actor)}:", "    kind: server", f"    endpoint: {endpoint}",
                  f"    auth: {{provider: token, source: {{env: {token_variable(actor)}}}}}",
                  f"    transport: {{tls: {{ca: {{mode: append, file: {json.dumps(str(ca))}}}}}}}"]
    (home / "config.yaml").write_text("\n".join(lines) + "\n")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(check, process, log, seconds=30):
    deadline = time.monotonic() + seconds
    while True:
        assert process.poll() is None, f"process exited; see {log}"
        try:
            if check():
                return
        except (OSError, AssertionError, ValueError):
            if time.monotonic() >= deadline:
                raise
        time.sleep(0.1)


def refused(result, code="forbidden"):
    """A refusal reports its typed code and that nothing changed."""
    output = result.stdout + result.stderr
    assert f'"code": "{code}"' in output and '"effects": "none"' in output, output[-3000:]


def request(url, path, actor="act-admin", body=None, expected=200):
    headers = {"Omnigraph-Http-Api": "0.14", "Authorization": f"Bearer {TOKENS[actor]}"}
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
        assert response.headers.get_all("Omnigraph-Http-Api") == ["0.14"]
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
    plan = run(env, "cluster", "plan", "--target", str(bundle), "--config", str(bundle), "--json")
    assert plan["ok"]
    applied = run(env, "cluster", "apply", "--target", str(bundle), "--config", str(bundle),
                  "--as", "act-admin", "--json")
    assert applied["status"] == "complete" and applied["result"]["converged"]
    status = run(env, "cluster", "status", "--target", str(bundle), "--json")
    lock = status["lock_id"]
    assert lock
    # This harness created the exclusive local root. The direct child exited;
    # no external object store or other owner can have accepted work here.
    run(env, "cluster", "force-unlock", lock, "--target", str(bundle), "--json")

    port, gateway_port = free_port(), free_port()
    url = f"http://127.0.0.1:{port}"
    write_operator_config(Path(env["OMNIGRAPH_HOME"]), f"https://localhost:{gateway_port}", workspace / "tls/ca.pem")
    tls = ssl.create_default_context(cafile=str(workspace / "tls/ca.pem"))
    server_env = {**env, "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON": json.dumps(TOKENS)}
    with (bundle / "server.log").open("w") as log:
        process = subprocess.Popen([SERVER, "--cluster", str(bundle), "--bind", f"127.0.0.1:{port}"],
                                   env=server_env, stdout=log, stderr=log)
        gateway = subprocess.Popen([sys.executable, str(GATEWAY), "--listen", f"127.0.0.1:{gateway_port}",
                                    "--upstream", f"127.0.0.1:{port}", "--certs", str(workspace / "tls")],
                                   stdout=log, stderr=log)
        try:
            wait_ready(lambda: request(url, "/readyz")["loading_graph_count"] == 0, process, bundle / "server.log")
            wait_ready(lambda: urllib.request.urlopen(f"https://localhost:{gateway_port}/readyz",
                                                      context=tls, timeout=5).status == 200,
                       gateway, bundle / "server.log")

            def scope(actor="act-admin"):
                return ("--target", target(actor), "--graph", graph)
            def verify_receipt(commit):
                assert commit and commit["graph_commit_id"], "write must return its exact commit"
                # This fixture has one writer and no intervening operation.
                snapshot = request(url, f"/graphs/{graph}/snapshot", "act-reader")
                # The commit API represents main as null.
                assert (commit["graph_branch"] or "main") == snapshot["graph_branch"] == "main"
                assert commit["graph_manifest_version"] == snapshot["graph_manifest_version"]
                assert request(url, f"/graphs/{graph}/commits/{commit['graph_commit_id']}", "act-reader") == commit
            seed = run(env, "load", *scope(), "--data", str(bundle / "seed.jsonl"), "--mode", "append", "--json")
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
            read = run(env, "query", stored_query, *scope("act-reader"), "--json")
            assert read["rows"], f"{stored_query} must demonstrate populated seed data"
            # Writers can create and retire a review branch but cannot deploy.
            run(env, "branch", "create", "cookbook-review", *scope("act-writer"), "--json")
            run(env, "branch", "delete", "cookbook-review", *scope("act-writer"), "--yes", "--json")
            refused(run(env, "cluster", "plan", "--target", target("act-writer"), "--config", str(bundle),
                        "--json", ok=False))

            # Add a harmless type and query to exercise real schema + registry
            # activation on the same PID, not merely an unchanged apply.
            with (bundle / "schema.pg").open("a") as schema:
                schema.write("\nnode CookbookCheck {\n  slug: String @key\n}\n")
            (bundle / "queries/cookbook-check.gq").write_text(
                "query cookbook_check() { match { $n: CookbookCheck } return { count($n) as total } }\n")
            before = run(env, "snapshot", *scope(), "--json")
            run(env, "cluster", "plan", "--target", target("act-admin"), "--config", str(bundle), "--json")
            assert run(env, "snapshot", *scope(), "--json") == before, "plan changed graph state"
            deployed = run(env, "cluster", "apply", "--target", target("act-admin"), "--config", str(bundle), "--json")
            assert deployed["active"] and not deployed["in_progress"], deployed
            exact = run(env, "cluster", "status", "--target", target("act-admin"), "--deployment-id",
                        deployed["deployment"]["result"]["id"], "--wait", "--json")
            assert exact["active"] and not exact["in_progress"]
            assert exact["deployment"]["result"] == deployed["deployment"]["result"]
            check = run(env, "query", "cookbook_check", *scope(), "--json")
            assert check["rows"] == [{"total": 0}], check
            sample = bundle / "check.jsonl"
            sample.write_text('{"type":"CookbookCheck","data":{"slug":"smoke"}}\n')
            # Refuse a fresh valid row for policy, not a duplicate-key error.
            refused(run(env, "load", *scope("act-reader"), "--data", str(sample), "--mode", "append", "--json",
                        ok=False))
            assert run(env, "query", "cookbook_check", *scope(), "--json")["rows"] == [{"total": 0}]
            if name in BRANCH_ONLY_AGENTS:
                # An agent drafts on its own branch; only a person merges into main.
                agent = scope("act-agent")
                refused(run(env, "load", *agent, "--data", str(sample), "--mode", "append", "--json", ok=False))
                run(env, "branch", "create", "agent-draft", *agent, "--json")
                drafted = run(env, "load", *agent, "--branch", "agent-draft", "--data", str(sample),
                              "--mode", "append", "--json")
                assert drafted["commit"]["graph_commit_id"]
                refused(run(env, "branch", "merge", "agent-draft", "--into", "main", *agent, "--json", ok=False))
                # Agents cannot delete a branch, so one cannot discard another's draft.
                refused(run(env, "branch", "delete", "agent-draft", *agent, "--yes", "--json", ok=False))
                run(env, "branch", "delete", "agent-draft", *scope("act-writer"), "--yes", "--json")
                assert run(env, "query", "cookbook_check", *scope(), "--json")["rows"] == [{"total": 0}]
            written = run(env, "load", *scope("act-writer"), "--data", str(sample), "--mode", "append", "--json")
            verify_receipt(written["commit"])
            expected_counts[("node", "CookbookCheck")] = 1
            assert request(url, f"/graphs/{graph}/queries/cookbook_check", "act-reader",
                           {"params": {}})["rows"] == [{"total": 1}]
            count()
            if name == "beads":
                beads_client_journey(env)
            if name == "company-brain":
                company_brain_journey(env)
            assert process.poll() is None
            assert request(url, "/readyz")["loading_graph_count"] == 0
            print(f"PASS {name}: lint, seed counts, roles, branches, live schema/query activation"
                  + (", ob client" if name == "beads" else "")
                  + (", review journey" if name == "company-brain" else ""), flush=True)
        finally:
            gateway.terminate()
            process.terminate()
            for child in (gateway, process):
                try:
                    child.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def beads_client_journey(env):
    """Drive beads' `ob` client through each actor's server target: stored
    queries only, the token's actor in history, and the reader's refusal."""
    base = {k: v for k, v in env.items() if not k.startswith("OB_")}
    base.update(OB_OMNIGRAPH=CLI, OB_GRAPH="beads")

    def ob(actor, *args, ok=True):
        result = subprocess.run([str(ROOT / "beads/client/ob"), "--json", *args], capture_output=True, text=True,
                                timeout=120, env={**base, "OB_ACTOR": actor, "OB_TARGET": target(actor)})
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


def company_brain_journey(env):
    """An agent records on a branch, a person merges and settles on main.
    Creates refuse an existing slug, and a rejected successor can be
    withdrawn so the decision it named can be replaced again."""
    agent, writer = "act-agent", "act-writer"

    def scope(actor):
        return ("--target", target(actor), "--graph", "company")

    def mutate(who, query, params, *branch, ok=True):
        return run(env, "mutate", query, *scope(who), *branch, "--params", json.dumps(params), "--json", ok=ok)

    def rows(query, params=None):
        return run(env, "query", query, *scope("act-admin"), "--params", json.dumps(params or {}), "--json")["rows"]

    def refused_by_card(result):
        assert "@card violation" in result.stdout + result.stderr, (result.stdout, result.stderr)

    claim = {"slug": "checker-claim", "kind": "proposal", "statement": "Resume the billing migration.",
             "quote": "Let's resume billing.", "locator": None, "recorded_at": "2026-10-15T00:00:00.000Z",
             "source": "doc:billing-plan", "speaker": "dana"}
    run(env, "branch", "create", "agent-claims", *scope(agent), "--json")
    mutate(agent, "record_claim", claim, "--branch", "agent-claims")
    refused_by_card(mutate(agent, "record_claim", claim, "--branch", "agent-claims", ok=False))
    refused(mutate(agent, "verify_claim", {"slug": "checker-claim"}, ok=False))
    run(env, "branch", "merge", "agent-claims", "--into", "main", *scope(writer), "--json")
    run(env, "branch", "delete", "agent-claims", *scope(writer), "--yes", "--json")
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
    selected = sys.argv[1:] or list(COOKBOOKS)
    unknown = sorted(set(selected) - set(COOKBOOKS))
    if unknown:
        raise SystemExit(f"unknown cookbook: {', '.join(unknown)}; choose from {', '.join(COOKBOOKS)}")
    if not CLI or not SERVER:
        raise SystemExit("Put 0.14.0 omnigraph and omnigraph-server on PATH or set OMNIGRAPH_BIN / OMNIGRAPH_SERVER_BIN")
    workspace = Path(tempfile.mkdtemp(prefix="omnigraph-cookbooks-test-"))
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("OMNIGRAPH_", "OG_", "AWS_", "AZURE_"))}
    (workspace / "operator").mkdir()
    env.update(OMNIGRAPH_HOME=str(workspace / "operator"),
               **{token_variable(actor): token for actor, token in TOKENS.items()})
    # Every journey's gateway serves the same local CA and certificate.
    spec = importlib.util.spec_from_file_location("local_tls_gateway", GATEWAY)
    gateway = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gateway)
    gateway.ensure_certificates(workspace / "tls")
    try:
        version = run(env, "version").stdout
        assert version.splitlines()[0] == "omnigraph 0.14.0", version
        for name in selected:
            graph, query = COOKBOOKS[name]
            qualify(name, graph, query, workspace, env)
    except BaseException:
        print(f"Failed fixture retained: {workspace}", flush=True)
        raise
    else:
        shutil.rmtree(workspace)
        print(f"All {len(selected)} selected cookbooks passed against OmniGraph 0.14.0.")


if __name__ == "__main__":
    main()
