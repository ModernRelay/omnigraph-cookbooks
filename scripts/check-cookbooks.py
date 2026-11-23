#!/usr/bin/env python3
"""Qualify cookbook bundles with released binaries against disposable local roots.

Usage: check-cookbooks.py [--site] [COOKBOOK ...]   (default: every cookbook)

Every run first checks each cookbook's site.json, the copy omnigraph.dev shows
for it (see "The website" in AGENTS.md), and the sections of its README (see
"Writing a cookbook README" there). --site runs only
that check: it is offline and needs no binaries.
"""

import re

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
    "health-record": ("health", "latest_results"),
    "code-graph": ("code", "most_referenced"),
}
# Cookbooks whose policy lets act-agent write only on unprotected branches.
BRANCH_ONLY_AGENTS = {"company-brain", "hardware-program", "health-record", "code-graph"}
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
    """One server target per actor, as docs/local-setup.md has.
    The CLI sends tokens only over HTTPS, so each target trusts the
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
            # An answer the README promises is a read that finds something in the seed.
            answers = promised_answers(name)
            for question, answer, params in answers:
                shown = run(env, "query", answer, *scope("act-reader"), "--params", json.dumps(params), "--json")
                assert shown["rows"], f"{name}/site.json: {question!r} runs {answer}, which returns no rows on the seed"
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
            if name == "hardware-program":
                hardware_program_journey(env)
            if name == "health-record":
                health_record_journey(env)
            if name == "code-graph":
                code_graph_journey(env)
            assert process.poll() is None
            assert request(url, "/readyz")["loading_graph_count"] == 0
            print(f"PASS {name}: lint, seed counts, roles, branches, live schema/query activation"
                  + (f", {len(answers)} README answers" if answers else "")
                  + (", ob client" if name == "beads" else "")
                  + (", review journey" if name == "company-brain" else "")
                  + (", review gate" if name == "hardware-program" else "")
                  + (", intake review" if name == "health-record" else "")
                  + (", pull request diff, cg client" if name == "code-graph" else ""), flush=True)
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


def hardware_program_journey(env):
    """Budgets and limits flag their own violations. A change merges as an
    unpublished commit, the review gate reads that exact result while main
    stays put, an agent cannot publish it, and a writer can."""
    def scope(actor):
        return ("--target", target(actor), "--graph", "program")

    def rows(query, *extra, params=None):
        return run(env, "query", query, *scope("act-reader"), "--params", json.dumps(params or {}),
                   *extra, "--json")["rows"]

    violated = {row["r.slug"] for row in rows("budget_rollup") if row["violated"]}
    assert violated == {"dc-pl-mass"}, violated
    assert [row["r.slug"] for row in rows("limit_violations")] == ["req-obc-temp"]

    writer = scope("act-writer")
    run(env, "branch", "create", "cr-heatsink", *writer, "--json")
    run(env, "mutate", "set_parameter", *writer, "--branch", "cr-heatsink",
        "--params", json.dumps({"slug": "p-obc-temp", "value": 66.2, "basis": "measured"}), "--json")
    merged = run(env, "branch", "merge", "cr-heatsink", "--into", "main", "--as-commit", *writer, "--json")
    commit = merged["commit"]["graph_commit_id"]
    assert merged["commit"]["published"] is False, merged
    assert [row["r.slug"] for row in rows("limit_violations")] == ["req-obc-temp"], "main moved before publish"
    assert rows("limit_violations", "--snapshot", commit) == []
    # A denied publish answers as an unknown commit, so the id discloses nothing.
    refused(run(env, "commit", "publish", commit, *scope("act-agent"), "--json", ok=False), code="not_found")
    run(env, "commit", "publish", commit, *writer, "--json")
    assert rows("limit_violations") == []
    run(env, "branch", "delete", "cr-heatsink", *writer, "--yes", "--json")


def health_record_journey(env):
    """Off target and an unfinished vaccine series are derived from the results and doses.
    An agent cannot record a dose on main; on its own branch the dose completes the series
    there while main stays put, and the series is complete on main once a person merges.
    Recording the same dose again is refused."""
    def scope(actor):
        return ("--target", target(actor), "--graph", "health")

    def rows(query, *extra, params=None):
        return run(env, "query", query, *scope("act-reader"), "--params", json.dumps(params or {}),
                   *extra, "--json")["rows"]

    assert {row["marker"] for row in rows("off_target")} == {"mk-ldl", "mk-vitd"}
    assert [row["disease"] for row in rows("incomplete_series")] == ["cond-hepatitis-b"]
    assert all(row["m.slug"] != "m-2026-01-weight-typo" for row in rows("marker_history", params={"marker": "mk-weight"}))

    agent, writer = scope("act-agent"), scope("act-writer")
    dose = json.dumps({"slug": "imm-hepb-3", "vaccine": "Hepatitis B", "administered_on": "2026-11-20",
                       "date_precision": "day", "origin": "provider_record", "person": "per-noa",
                       "disease": "cond-hepatitis-b", "dose_number": 3, "series_doses": 3})
    refused(run(env, "mutate", "record_dose", *agent, "--params", dose, "--json", ok=False))
    run(env, "branch", "create", "intake-vaccines", *agent, "--json")
    run(env, "mutate", "record_dose", *agent, "--branch", "intake-vaccines", "--params", dose, "--json")
    assert rows("incomplete_series", "--branch", "intake-vaccines") == []
    assert [row["disease"] for row in rows("incomplete_series")] == ["cond-hepatitis-b"], "main moved before the merge"
    run(env, "branch", "merge", "intake-vaccines", "--into", "main", *writer, "--json")
    assert rows("incomplete_series") == []
    run(env, "branch", "delete", "intake-vaccines", *writer, "--yes", "--json")
    # A record is written once: the same slug again, with other values, is refused and changes nothing.
    replay = json.dumps({**json.loads(dose), "vaccine": "Hepatitis B, replayed"})
    again = run(env, "mutate", "record_dose", *writer, "--params", replay, "--json", ok=False)
    assert "@card violation" in again.stdout + again.stderr, (again.stdout, again.stderr)
    doses = rows("disease_doses", params={"disease": "cond-hepatitis-b"})
    assert [row["i.vaccine"] for row in doses] == ["Hepatitis B"] * 3, doses


def code_graph_journey(env):
    """The indexer loads a pull request's revision onto its own branch, the
    branch diff is exactly what the PR changed, the reads see the new code
    only on the branch, a person merges, and the previous main stays readable."""
    def scope(actor):
        return ("--target", target(actor), "--graph", "code")

    def rows(query, params=None, *extra):
        return run(env, "query", query, *scope("act-reader"), "--params", json.dumps(params or {}),
                   *extra, "--json")["rows"]

    base, head = "a10592f3e1864cbe277619633db953450a6b1e4b", "4b44abe1b5c7755aac8555d7943611555183450b"
    helper = {"symbol": "src/router/`utils.ts`/createNullObject."}
    assert [row["r.sha"] for row in rows("revision")] == [base]
    routers = {"linear-router/`router.ts`/LinearRouter", "pattern-router/`router.ts`/PatternRouter",
               "reg-exp-router/`prepared-router.ts`/PreparedRegExpRouter", "reg-exp-router/`router.ts`/RegExpRouter",
               "smart-router/`router.ts`/SmartRouter", "trie-router/`router.ts`/TrieRouter"}
    implementers = {row["i.symbol"] for row in rows("implementers", {"symbol": "src/`router.ts`/Router#add()."})}
    assert implementers == {f"src/router/{r}#add()." for r in routers}, implementers
    previous = run(env, "commit", "list", *scope("act-reader"), "--json")["commits"][0]["graph_commit_id"]

    # The cg client, through each actor's server target like any operator.
    base_env = {k: v for k, v in env.items() if not k.startswith("CG_")}
    base_env.update(CG_OMNIGRAPH=CLI, CG_GRAPH="code")

    def cg(actor, *args, ok=True):
        result = subprocess.run([sys.executable, str(ROOT / "code-graph/client/cg"), *args, "--json"],
                                capture_output=True, text=True, timeout=120,
                                env={**base_env, "CG_TARGET": target(actor)})
        if (result.returncode == 0) != ok:
            raise AssertionError(f"cg {args} as {actor}: exit {result.returncode}\n{result.stdout}{result.stderr}")
        return json.loads(result.stdout) if ok else result

    pr_file = str(ROOT / "code-graph/examples/pr-5267.jsonl")
    denied = cg("act-reader", "load", pr_file, "--branch", "pr-5267", ok=False)
    # Refused before any effect, so cg reports a plain failure, not an unknown outcome.
    assert denied.returncode == 1 and "policy denied" in denied.stderr, (denied.returncode, denied.stderr)
    loaded = cg("act-agent", "load", pr_file, "--branch", "pr-5267")
    assert loaded["branch"] == "pr-5267" and loaded["commit"] and loaded["rows"] == 854, loaded
    changes = run(env, "branch", "diff", "pr-5267", *scope("act-reader"), "--json")["changes"]
    summary = collections.Counter((c["type"]["name"], c["op"]) for c in changes)
    assert summary == {("Symbol", "insert"): 2, ("Symbol", "update"): 5, ("References", "insert"): 18,
                       ("MemberOf", "insert"): 1, ("DefinedAt", "insert"): 2, ("Location", "insert"): 2,
                       ("Location", "update"): 58, ("Revision", "insert"): 1, ("Revision", "delete"): 1}, summary
    changed = {c["id"] for c in changes if c["type"]["name"] == "Symbol" and c["op"] == "update"}
    assert changed == {f"src/router/reg-exp-router/`router.ts`/RegExpRouter#{m}" for m in
                       ("`<constructor>`().", "add().", "buildAllMatchers().", "`#buildMatcher`().")} | {
                       "src/router/trie-router/`node.ts`/Node#`#pushHandlerSets`()."}, changed
    review = cg("act-reader", "diff", "pr-5267")
    assert (review["from_revision"], review["to_revision"]) == (base, head), review
    assert [r["symbol"] for r in review["added"]] == ["src/router/`utils.ts`/", helper["symbol"]], review["added"]
    assert {r["symbol"] for r in review["changed"]} == changed and review["moved"] == 53, review
    assert (len(review["references"]["added"]), len(review["references"]["removed"])) == (18, 0)

    assert rows("callers", helper) == []
    assert len(rows("callers", helper, "--branch", "pr-5267")) == 14
    # cg resolves a unique name to its key, and lists the candidates of an ambiguous one.
    assert len(cg("act-reader", "callers", "createNullObject", "--branch", "pr-5267")["rows"]) == 14
    assert cg("act-reader", "implementers", "add", ok=False).returncode == 2
    # impact walks references and implementations: a call to Router#match can run SmartRouter#match.
    reach = {r["reaches it"] for r in cg("act-reader", "impact", "src/`router.ts`/Router#add().")["rows"]}
    assert "src/router/smart-router/`router.ts`/SmartRouter#match()." in reach and len(reach) == 8, reach
    refused(run(env, "branch", "merge", "pr-5267", "--into", "main", *scope("act-agent"), "--json", ok=False))
    merged = run(env, "branch", "merge", "pr-5267", "--into", "main", *scope("act-writer"), "--json")
    assert merged["outcome"] == "fast_forward", merged
    run(env, "branch", "delete", "pr-5267", *scope("act-writer"), "--yes", "--json")
    assert [row["r.sha"] for row in rows("revision")] == [head]
    assert len(rows("callers", helper)) == 14
    assert [row["r.sha"] for row in rows("revision", None, "--snapshot", previous)] == [base]
    assert rows("callers", helper, "--snapshot", previous) == []

    # Loading the base back over the merged PR removes what the PR added.
    cg("act-agent", "load", str(ROOT / "code-graph/seed.jsonl"), "--branch", "revert-5267")
    revert = cg("act-reader", "diff", "revert-5267")
    assert [r["symbol"] for r in revert["removed"]] == ["src/router/`utils.ts`/", helper["symbol"]], revert
    assert (len(revert["references"]["added"]), len(revert["references"]["removed"])) == (0, 18), revert
    run(env, "branch", "delete", "revert-5267", *scope("act-writer"), "--yes", "--json")


# What omnigraph.dev accepts in a site.json; its importer
# (ModernRelay/brand apps/omnigraph/scripts/sync-cookbooks.mjs) checks the same.
SITE_CATEGORIES = {"Company", "Engineering", "Hardware", "Research", "Investing", "Personal"}
SITE_TITLE_MAX = 60  # a search result shows about this much; the site appends " | Omnigraph"
SITE_HEADING_MAX = 70  # the second line of the page's H1
SITE_ABOUT_MAX = 600  # two to four sentences: what the graph is, who it is for, what it takes the place of
QUERY_START = re.compile(r"^query\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
WRITES = re.compile(r"\b(insert|update|delete)\b")


def stored_queries(folder):
    """Each stored query in the cookbook's queries/*.gq, by name: whether it writes."""
    found = {}
    for path in sorted((ROOT / folder / "queries").glob("*.gq")):
        source = path.read_text()
        starts = list(QUERY_START.finditer(source))
        for i, match in enumerate(starts):
            body = source[match.end():starts[i + 1].start() if i + 1 < len(starts) else len(source)]
            body = re.sub(r'"(?:[^"\\]|\\.)*"', "", body)
            body = re.sub(r"//.*", "", body)
            found[match.group(1)] = bool(WRITES.search(body))
    return found


def check_site(folder):
    """The website's copy for one cookbook: present, complete, and naming only read queries it has."""
    path = ROOT / folder / "site.json"
    assert path.is_file(), f"{folder}: no site.json; every cookbook carries the copy omnigraph.dev shows"
    site = json.loads(path.read_text())
    where = f"{folder}/site.json"
    for key, kind in (("order", int), ("name", str), ("category", str), ("blurb", str),
                      ("sample", str), ("questions", list), ("search", dict)):
        assert isinstance(site.get(key), kind) and site[key] != "", f"{where}: {key} must be a non-empty {kind.__name__}"
    assert site["category"] in SITE_CATEGORIES, \
        f"{where}: category {site['category']!r} is not one of {', '.join(sorted(SITE_CATEGORIES))}"
    queries = stored_queries(folder)
    assert site["questions"], f"{where}: name at least one question"
    for question in site["questions"]:
        assert isinstance(question.get("q"), str) and question["q"], f"{where}: every question needs its text in q"
        name = question.get("query")
        assert name in queries, f"{where}: question {question['q']!r} names {name!r}, which queries/*.gq does not define"
        assert not queries[name], f"{where}: question {question['q']!r} names {name!r}, which writes; name a read"
    search = site["search"]
    title, keywords = search.get("title"), search.get("keywords")
    assert isinstance(title, str) and 0 < len(title) <= SITE_TITLE_MAX, \
        f"{where}: search.title must be 1 to {SITE_TITLE_MAX} characters"
    assert isinstance(keywords, list) and keywords and all(isinstance(k, str) and k == k.lower() and k for k in keywords), \
        f"{where}: search.keywords must be a non-empty list of lowercase phrases"
    # optional: the page's second H1 line, and its "What it is" paragraph
    heading, about = search.get("heading"), site.get("about")
    assert heading is None or (isinstance(heading, str) and 0 < len(heading) <= SITE_HEADING_MAX), \
        f"{where}: search.heading, when given, must be 1 to {SITE_HEADING_MAX} characters"
    assert about is None or (isinstance(about, str) and 0 < len(about) <= SITE_ABOUT_MAX), \
        f"{where}: about, when given, must be 1 to {SITE_ABOUT_MAX} characters"
    check_readme(folder, site, queries)
    return site


# The sections of a cookbook README. It reads as the landing page of OmniGraph for one
# use case: a living source of truth and the agent workflows around it. It makes sense
# without the sample data, which has its own section, and omnigraph.dev draws its
# use-case page from the same sections (see "Writing a cookbook README" in AGENTS.md).
# Commands belong in the cookbook's AGENTS.md.
README_SECTIONS = ("The data model", "Branching and merging", "Agents and workflows",
                   "Data sources", "Questions you can ask", "Sample data", "Run it")
QUESTIONS = range(3, 6)   # how many questions a cookbook features
QUERY_NAME = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`")
CODE = re.compile(r"`([^`]+)`")
INVOCATION = re.compile(r"omnigraph\s+(query|mutate)\s+([A-Za-z_][A-Za-z0-9_]*)")
TYPE_NAME = re.compile(r"`([A-Z][A-Za-z0-9]*)`")
SCHEMA_TYPE = re.compile(r"^(?:node|edge)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
# What a site.json claims from the market vocabulary: the list, its slug prefix, the key holding the slug.
CLAIMS = (("needs", "need:", "need"), ("capabilities", "cap:", "capability"))


def readme_sections(folder):
    """A README as its lead and its `##` sections, each with its text and its `###` parts.
    A `#` line inside a code fence is a shell comment, not a heading."""
    lead, sections, section, part, fenced = [], {}, None, None, False
    for line in (ROOT / folder / "README.md").read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        heading = None if fenced else re.match(r"(#{1,3}) (.+)", line)
        if heading and heading[1] == "##":
            assert heading[2] not in sections, f"{folder}/README.md: ## {heading[2]} appears twice"
            section, part = sections.setdefault(heading[2], {"text": [], "parts": {}}), None
        elif heading and heading[1] == "###" and section:
            part = section["parts"].setdefault(heading[2], [])
        elif heading and heading[1] == "#":
            continue
        elif section is None:
            lead.append(line)
        else:
            section["text"].append(line)
            if part is not None:
                part.append(line)
    return lead, sections


def tables(lines):
    """The Markdown tables in some lines: each a list of rows, a row its cells by column header.
    A table is a header line, a delimiter line with as many cells, then its rows; lines of
    cells without that delimiter do not render as a table and are not read as one."""
    found, block = [], []
    for line in [*lines, ""]:
        if line.lstrip().startswith("|"):
            block.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            continue
        if len(block) > 1 and len(block[1]) == len(block[0]) and all(re.fullmatch(r":?-+:?", cell) for cell in block[1]):
            found.append([dict(zip(block[0], cells)) for cells in block[2:]])
        block = []
    return found


def fences(lines):
    """The fenced blocks in some lines, each as (label, body lines). One left open runs to the end."""
    found, body = [], None
    for line in lines:
        if line.startswith("```"):
            if body is None:
                body = []
                found.append((line[3:].strip(), body))
            else:
                body = None
        elif body is not None:
            body.append(line)
    return found


def prompt(name, folder):
    """What a reader pastes into a coding agent to have a cookbook set up."""
    return ("Read https://www.omnigraph.dev/onboarding.md and set up Omnigraph for me with the "
            f"{name} cookbook: https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/{folder}")


def check_readme(folder, site, queries):
    """The README in the shared sections, each claim backed by something the cookbook holds."""
    where, there = f"{folder}/README.md", f"{folder}/site.json"
    lead, sections = readme_sections(folder)
    assert tuple(sections) == README_SECTIONS, \
        f"{where}: its ## sections must be exactly {', '.join(README_SECTIONS)}, in that order; " \
        f"found {', '.join(sections) or 'none'}"
    for title, section in sections.items():
        assert "".join(section["text"]).strip(), f"{where}: ## {title} is empty"
    # The intro: the living thing the use case builds and the agent workflows around it, in the
    # words site.json's about carries, and where an agent finds the commands.
    intro = "\n".join(lead).strip()
    first = " ".join(intro.split("\n\n")[0].split())
    assert first and first == site.get("about"), \
        f"{where}: its first paragraph and about in site.json must be the same text"
    opening = first.split(". ")[0]
    assert opening.startswith("Build a living ") and "agent workflows around it" in opening, \
        f"{where}: the intro opens 'Build a living <what the use case keeps> ..., and the agent workflows around it.'"
    assert "(AGENTS.md)" in intro, f"{where}: the intro must point agents at AGENTS.md"
    # The questions table is site.json's questions: the same ones, word for word, in the same
    # order, each with its stored read.
    assert len(site["questions"]) in QUESTIONS, \
        f"{there}: feature {QUESTIONS.start} to {QUESTIONS.stop - 1} questions, found {len(site['questions'])}"
    for question in site["questions"]:
        assert isinstance(question.get("params", {}), dict), f"{there}: params of {question['q']!r} must be an object"
    listed = [(row.get("Question"), row.get("Stored query"))
              for table in tables(sections["Questions you can ask"]["text"]) for row in table]
    featured = [(question["q"], f"`{question['query']}`") for question in site["questions"]]
    assert listed == featured, \
        f"{where}: the Question and Stored query columns of ## Questions you can ask must be the questions of " \
        f"site.json, in order; the README has {listed}, site.json has {featured}"
    # A workflow or question names the stored queries behind it, and only ones the cookbook has:
    # everything in code in a stored-query column, and any snake_case name in code beside it.
    for title in ("Agents and workflows", "Questions you can ask"):
        text = sections[title]["text"]
        named = QUERY_NAME.findall("\n".join(text))
        named += [name for table in tables(text) for row in table for column, cell in row.items()
                  if column.startswith("Stored quer") for name in CODE.findall(cell)]
        assert named, f"{where}: ## {title} must name the stored queries behind it"
        for name in named:
            assert name in queries, f"{where}: ## {title} names `{name}`, which queries/*.gq does not define"
    assert "(seed.md)" in "\n".join(sections["Sample data"]["text"]), \
        f"{where}: ## Sample data must link seed.md"
    # A type the data model or the data sources name is one the schema declares.
    types = set(SCHEMA_TYPE.findall((ROOT / folder / "schema.pg").read_text()))
    for title in ("The data model", "Data sources"):
        for name in TYPE_NAME.findall("\n".join(sections[title]["text"])):
            assert name in types, f"{where}: ## {title} names `{name}`, which schema.pg does not declare"
    run_it = "\n".join(sections["Run it"]["text"])
    graph = COOKBOOKS[folder][0]
    for needed in ("../docs/local-setup.md", "(AGENTS.md)", f"`{graph}`"):
        assert needed in run_it, f"{where}: ## Run it must link local setup and AGENTS.md and give the Graph ID; {needed} is missing"
    head, tail = prompt("|", folder).split("|")
    assert any(label == "text" and len(body) == 1 and body[0].startswith(head) and body[0].endswith(tail)
               and len(body[0]) > len(head) + len(tail) for label, body in fences(sections["Run it"]["text"])), \
        f"{where}: ## Run it must give the onboarding prompt in a text block: {prompt('<name>', folder)}"
    # The commands live in the agent guide: each stored query it or the README runs exists, with the verb that fits.
    # AGENTS.md is a link to CLAUDE.md, which a checkout without symlinks does not follow.
    guide = (ROOT / folder / "CLAUDE.md").read_text()
    for source, text in ((where, (ROOT / folder / "README.md").read_text()), (f"{folder}/CLAUDE.md", guide)):
        for verb, name in INVOCATION.findall(text):
            assert name in queries, f"{source}: `omnigraph {verb} {name}` names no stored query in queries/*.gq"
            assert queries[name] == (verb == "mutate"), \
                f"{source}: {name} {'writes' if queries[name] else 'reads'}, so `omnigraph {verb} {name}` cannot run it"
    assert any(verb == "mutate" for verb, _ in INVOCATION.findall(guide)), \
        f"{folder}/CLAUDE.md: must run at least one stored mutation; a cookbook is written to, not only read"
    # Where mr-ops has a use case for the cookbook: a need met or a capability used
    # points at the heading that shows it. Where it has none, all three are left out.
    use_case = site.get("use_case")
    assert use_case is None or (isinstance(use_case, str) and use_case.startswith("usecase:")), \
        f"{there}: use_case, when given, must be a use case slug, usecase:<name>"
    headings = set(sections) | {heading for section in sections.values() for heading in section["parts"]}
    for key, prefix, field in CLAIMS:
        claims = site.get(key, [])
        assert isinstance(claims, list), f"{there}: {key} must be a list"
        assert use_case or not claims, \
            f"{there}: {key} needs a use_case; leave all three out where mr-ops has no use case for the cookbook"
        for claim in claims:
            slug, shown_in = claim.get(field), claim.get("shown_in")
            assert isinstance(slug, str) and slug.startswith(prefix), \
                f"{there}: every entry of {key} needs its slug in {field}, {prefix}<name>"
            assert shown_in in headings, \
                f"{there}: {slug} is shown in {shown_in!r}, which is not a heading in the README"


def promised_answers(folder):
    """The questions a cookbook's README answers, as (question, stored read, params)."""
    site = json.loads((ROOT / folder / "site.json").read_text())
    return [(q["q"], q["query"], q.get("params", {})) for q in site["questions"]]


def check_root_readme(sites):
    """The root README is the landing page for the collection: its table is each cookbook's
    name, blurb and first question from site.json, in order, and it carries no commands."""
    lines = (ROOT / "README.md").read_text().splitlines()
    listed = [tuple(row.values()) for table in tables(lines) for row in table]
    wanted = [(f"[{site['name']}]({folder}/)", site["blurb"], site["questions"][0]["q"])
              for folder, site in sorted(sites.items(), key=lambda item: item[1]["order"])]
    for have, want in zip(listed, wanted):
        assert have == want, f"README.md: a row of the cookbook table is {have}; site.json makes it {want}"
    assert len(listed) == len(wanted), \
        f"README.md: the cookbook table has {len(listed)} rows for {len(wanted)} cookbooks"
    assert fences(lines) == [("text", [prompt("<name>", "<folder>")])], \
        "README.md: its only fenced block is the onboarding prompt, in a text block; commands belong in " \
        "docs/local-setup.md and each cookbook's AGENTS.md"


def check_sites(selected):
    sites = {folder: check_site(folder) for folder in selected}
    if len(selected) == len(COOKBOOKS):
        orders = [site["order"] for site in sites.values()]
        assert len(set(orders)) == len(orders), f"site.json order values repeat: {sorted(orders)}"
        check_root_readme(sites)
    print(f"site.json passed for {len(selected)} cookbooks.")


def main():
    args = sys.argv[1:]
    site_only = "--site" in args
    selected = [a for a in args if a != "--site"] or list(COOKBOOKS)
    unknown = sorted(set(selected) - set(COOKBOOKS))
    if unknown:
        raise SystemExit(f"unknown cookbook: {', '.join(unknown)}; choose from {', '.join(COOKBOOKS)}")
    check_sites(selected)
    if site_only:
        return
    if not CLI or not SERVER:
        raise SystemExit("Put 0.15.0 omnigraph and omnigraph-server on PATH or set OMNIGRAPH_BIN / OMNIGRAPH_SERVER_BIN")
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
        assert version.splitlines()[0] == "omnigraph 0.15.0", version
        for name in selected:
            graph, query = COOKBOOKS[name]
            qualify(name, graph, query, workspace, env)
    except BaseException:
        print(f"Failed fixture retained: {workspace}", flush=True)
        raise
    else:
        shutil.rmtree(workspace)
        print(f"All {len(selected)} selected cookbooks passed against OmniGraph 0.15.0.")


if __name__ == "__main__":
    main()
