#!/usr/bin/env python3
"""Agent benchmark: what a coding agent spends, in tokens and time, to answer
code-structure questions about hono with each code graph, and how right it is.

    python3 code-graph/bench/agent.py setup [--arms A,B]
    python3 code-graph/bench/agent.py index [--arms A,B] [--reps N]   # time each tool's first index
    python3 code-graph/bench/agent.py run [--arms A,B] [--questions Q,R] [--reps N] [--model M] [--jobs J]
    python3 code-graph/bench/agent.py score [--model M]
    python3 code-graph/bench/agent.py --suite vscode setup|run|score ...   # the benchmark at scale

The vscode suite (scale.py, scale-design.md) uses VS Code 1.146.0 with 1.145.0
as its previous commit; every arm there also gets a `git` that only reads.

Each arm is a git worktree of hono at the base revision under work/agent/ARM,
with at most one code graph, set up by that tool's own Claude Code installer:
its MCP server, instructions, skills, subagents and hooks, whatever it writes.
An installer that writes to the user's home writes to a scratch home instead,
and setup moves what it wrote into the worktree's project settings, so a run
loads it without loading anything of the user's. `bare` has no graph.
`omnigraph` is this cookbook: the graph converted from scip-typescript and
loaded into a local Omnigraph graph, read through `cg`, with a CLAUDE.md
section written for this benchmark, since the cookbook has no installer.

A run is one headless Claude Code session (`claude -p`) in the arm's worktree
with the same model, built-in tools and question for every arm. It loads
project settings only (`--setting-sources project`) and only the arm's MCP
servers (`--strict-mcp-config`). Every arm may read and search with Read, Grep,
Glob, skills, subagents (Task) and a read-only set of shell commands; an arm whose tool has a command
line may also run it. Its stream is kept under work/agent-runs/.

Needs the tools the recall benchmark installed under work/tools (codegraph,
GitNexus, codebase-memory-mcp), uv for Graphify and code-review-graph, Node.js
22.23.4 or later (NODE_BIN, else `mise where node@24.20.0`), the locked
indexer, the omnigraph CLI (OMNIGRAPH_BIN; the README names the version each
result used) and a signed-in `claude`.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import functools
import json
import math
import os
import random
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
COOKBOOK = BENCH.parent
WORK = BENCH / "work"
AGENTS = WORK / "agent"
RUNS = WORK / "agent-runs"
TOOLS = WORK / "tools"
REPO = WORK / "repo"
QUESTIONS = BENCH / "agent-questions.json"
sys.path.insert(0, str(BENCH))
from common import load_reference  # noqa: E402

BASE = json.loads(QUESTIONS.read_text())["revision"]
SCALE = WORK / "scale"
# A suite is one repository and its question file. `vscode` is the benchmark at
# scale (scale.py builds its repository, graph, reference and questions).
SUITES = {
    "hono": {"questions": QUESTIONS, "repo": REPO, "agents": AGENTS, "runs": RUNS,
             "reference": WORK / "ref-base.json", "results": "agent.json"},
    "vscode": {"questions": BENCH / "scale-questions.json", "repo": SCALE / "repo.git", "agents": SCALE / "agent",
               "runs": SCALE / "agent-runs", "reference": SCALE / "ref-1.146.0.json", "results": "agent-scale.json"},
}
SUITE = "hono"
REFERENCE, RESULTS = SUITES["hono"]["reference"], SUITES["hono"]["results"]
# The vscode suite's git reads no global configuration (scale.py GIT_ENV).
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# Commands a vscode arm's `git` wrapper lets the agent run: it reads the
# previous release, never changes the checkout.
READ_ONLY_GIT = ("log", "diff", "show", "blame", "grep", "ls-files", "ls-tree", "rev-parse", "tag",
                 "cat-file", "describe", "shortlog", "status")
ARMS = ("bare", "omnigraph", "codegraph", "graphify", "gitnexus", "cbm", "crg")
TOOL_NAMES = {"bare": "no code graph", "omnigraph": "Omnigraph (this cookbook, through cg)",
              "codegraph": "codegraph 1.6.2", "graphify": "Graphify 0.9.102", "gitnexus": "GitNexus 1.6.12",
              "cbm": "codebase-memory-mcp 0.12.1", "crg": "code-review-graph 2.3.9"}
DEFAULT_MODEL = "claude-sonnet-5-5"
BUILTIN_TOOLS = "Read,Grep,Glob,Bash,Skill,Task"
# Commands that cannot change the checkout. --allowedTools splits on spaces, so
# no pattern may hold one.
READ_ONLY_SHELL = ["grep", "find", "ls", "cat", "head", "tail", "wc"]
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
RUN_TIMEOUT = 900
# Claude Code's usage-limit messages (the same pattern the box's claude-accounts
# uses). A session they end did not answer, so it is rerun, not scored.
USAGE_LIMIT = re.compile(r"(?i)(hit your [\w -]*limit|usage limit reached|out of extra usage)")
LIMITED_EXIT = 4


class UsageLimited(Exception):
    pass
SETUP_TIMEOUT = 1800
MAX_TURNS = 80
NO_TELEMETRY = {"DO_NOT_TRACK": "1", "CODEGRAPH_TELEMETRY": "0", "CODEGRAPH_NO_DOWNLOAD": "1",
                "SCARF_ANALYTICS": "false", "GRAPHIFY_QUERY_LOG_DISABLE": "1"}
OMNIGRAPH_CLAUDE_MD = """\
## Code graph

This repository's definitions and the references between them are in an
Omnigraph code graph built from the TypeScript compiler's index, so a
reference is resolved by type, not by name. Query it with `cg` before
searching text; `cg --help` lists every command.

- `cg find NAME`: the definitions with that name, and their keys
- `cg callers SYMBOL`: the definitions whose code calls SYMBOL; for a class, the code that constructs it with `new`
- `cg callees SYMBOL`: what SYMBOL's code calls
- `cg referrers SYMBOL`: every definition whose code names SYMBOL: calls, type uses, imports and values
- `cg transitive-callers SYMBOL`: SYMBOL's callers at any depth, through up to sixteen calls; a call through an interface reaches the methods implementing it
- `cg impact SYMBOL`: every definition that reaches SYMBOL through up to sixteen references and implementations: what a change to it can break
- `cg implementers MEMBER`: the class members that implement or override an interface or base member
- `cg members SYMBOL`: what a module, class or interface declares

SYMBOL is a name or a key from `cg find`; a name that several definitions
share lists the candidates, so pass the key.
"""
OMNIGRAPH_CLAUDE_MD_SCALE = OMNIGRAPH_CLAUDE_MD + """
The graph holds release 1.146.0 on `main` and release 1.145.0 on branch
`v1.145.0`. Every read takes `--branch v1.145.0` to read the previous
release, and `cg diff main --into v1.145.0` lists everything 1.146.0 added and
removed, which is over 300,000 lines. A read that stops at its row limit says
so.
"""


def configure(suite: str):
    """Point the module's paths at one suite."""
    global SUITE, QUESTIONS, REPO, AGENTS, RUNS, REFERENCE, RESULTS, BASE, RUN_TIMEOUT, SETUP_TIMEOUT
    spec = SUITES[suite]
    SUITE = suite
    QUESTIONS, REPO, AGENTS, RUNS = spec["questions"], spec["repo"], spec["agents"], spec["runs"]
    REFERENCE, RESULTS = spec["reference"], spec["results"]
    if suite == "vscode":
        # Sessions on 2.3 million lines take longer, and each tool's first
        # index of the repository gets the design's 60-minute budget.
        RUN_TIMEOUT, SETUP_TIMEOUT = 1800, 3600
    if QUESTIONS.exists():
        BASE = json.loads(QUESTIONS.read_text())["revision"]


@functools.cache
def node_bin() -> Path:
    if os.environ.get("NODE_BIN"):
        return Path(os.environ["NODE_BIN"])
    out = subprocess.run(["mise", "where", "node@24.20.0"], capture_output=True, text=True, check=True).stdout
    return Path(out.strip()) / "bin"


def omnigraph_bin() -> str:
    binary = os.environ.get("OMNIGRAPH_BIN") or shutil.which("omnigraph")
    if not binary:
        raise SystemExit("set OMNIGRAPH_BIN to the omnigraph CLI")
    return binary


def sh(*args, cwd=None, env=None, timeout=None) -> str:
    p = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True,
                       timeout=timeout or SETUP_TIMEOUT)
    if p.returncode:
        raise SystemExit(f"{' '.join(map(str, args))} failed:\n{p.stdout[-1500:]}\n{p.stderr[-2500:]}")
    return p.stdout


class Arm:
    """One arm's paths and the environment its tool runs in."""

    def __init__(self, name: str):
        self.name = name
        self.root = AGENTS / name
        self.repo = self.root / "hono"
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.mcp = self.root / "mcp.json"
        self.meta = self.root / "setup.json"

    def tool_env(self) -> dict:
        """What every command of this arm's tool runs with: its scratch home."""
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:{node_bin()}:{SYSTEM_PATH}", **NO_TELEMETRY}
        if self.name == "cbm":
            env["CBM_CACHE_DIR"] = str(self.root / "cache")
        if self.name == "omnigraph":
            env["OMNIGRAPH_HOME"] = str(self.root / "og")
        return env

    def env_prefix(self) -> str:
        return "env " + " ".join(f"{k}={shlex.quote(v)}" for k, v in self.tool_env().items())

    def wrap(self, name: str, target: str | Path, *pre: str, env: dict | None = None):
        """A command on the arm's PATH that runs `target` in the tool's environment."""
        self.bin.mkdir(parents=True, exist_ok=True)
        exports = " ".join(f"{k}={shlex.quote(str(v))}" for k, v in {**self.tool_env(), **(env or {})}.items())
        argv = " ".join(shlex.quote(str(a)) for a in (*pre, target))
        path = self.bin / name
        path.write_text(f"#!/bin/sh\nexport {exports}\nexec {argv} \"$@\"\n")
        path.chmod(0o755)

    def shell(self) -> list[str]:
        """Shell commands this arm's agent may run besides the read-only set."""
        tool = {"omnigraph": ["cg"], "codegraph": ["codegraph"], "graphify": ["graphify"],
                "gitnexus": ["gitnexus"], "cbm": ["codebase-memory-mcp"], "crg": ["code-review-graph"]}.get(self.name, [])
        return (["git"] if SUITE == "vscode" else []) + tool


# --- setup -------------------------------------------------------------------

def worktree(arm: Arm):
    env = {**os.environ, **GIT_ENV} if SUITE == "vscode" else None
    if not arm.repo.exists():
        arm.root.mkdir(parents=True, exist_ok=True)
        sh("git", "-C", REPO, "worktree", "add", "--quiet", "--detach", arm.repo, BASE, env=env)
    head = sh("git", "-C", arm.repo, "rev-parse", "HEAD", env=env).strip()
    if head != BASE:
        raise SystemExit(f"{arm.repo} is at {head}, not {BASE}")
    (arm.home / ".claude").mkdir(parents=True, exist_ok=True)
    if not (arm.home / ".claude.json").exists():
        (arm.home / ".claude.json").write_text("{}\n")


def timed(fn) -> float:
    start = time.monotonic()
    fn()
    return round(time.monotonic() - start, 2)


def venv_tool(arm: Arm, package: str, command: str) -> Path:
    venv = arm.root / "venv"
    if not (venv / "bin" / command).exists():
        env = {**os.environ, "UV_CACHE_DIR": str(Path.home() / ".cache" / "uv")}
        sh("uv", "venv", "-q", "--python", "3.12", venv, env=env)
        sh("uv", "pip", "install", "-q", "--python", venv / "bin" / "python", package, env=env)
    return venv / "bin" / command


def read_only_git(arm: Arm):
    """A `git` on the arm's PATH that runs only commands that read."""
    arm.bin.mkdir(parents=True, exist_ok=True)
    real = shutil.which("git", path=SYSTEM_PATH) or shutil.which("git")
    (arm.bin / "git").write_text(f"""#!/usr/bin/env python3
import os, sys
args, i = sys.argv[1:], 0
while i < len(args) and args[i].startswith("-"):
    if args[i] == "-C":
        i += 2
    elif args[i] in ("--no-pager", "-P", "--no-optional-locks"):
        i += 1
    else:
        sys.exit(f"git {{args[i]}} is not allowed here: the repository is read-only")
if i >= len(args) or args[i] not in {READ_ONLY_GIT!r}:
    sys.exit("only these git commands are allowed here: " + ", ".join({READ_ONLY_GIT!r}))
os.execve({real!r}, [{real!r}, *args], {{**os.environ, **{GIT_ENV!r}}})
""")
    (arm.bin / "git").chmod(0o755)


def setup_omnigraph(arm: Arm) -> dict:
    if SUITE == "vscode":
        # The graph scale.py built, both releases; its index times are in build.json.
        graph = SCALE / "graph.omni"
        if not (SCALE / "graph.omni.done").exists():
            raise SystemExit("no vscode graph: run `scale.py build` first")
        arm.wrap("cg", COOKBOOK / "client" / "cg", sys.executable, env={"CG_TARGET": graph, "CG_OMNIGRAPH": omnigraph_bin()})
        (arm.repo / "CLAUDE.md").write_text(OMNIGRAPH_CLAUDE_MD_SCALE)
        (arm.repo / ".claude").mkdir(exist_ok=True)
        if not (arm.repo / ".claude" / "settings.json").exists():
            (arm.repo / ".claude" / "settings.json").write_text("{}\n")
        build = json.loads((SCALE / "build.json").read_text())
        # Index, convert and load; the reference builds answer keys, not the graph.
        return {"index_seconds": {k: v for k, v in build.items() if "1.146.0" in k and not k.startswith("reference")}}
    og, graph = omnigraph_bin(), arm.root / "graph.omni"
    index, rows = arm.root / "index.scip", arm.root / "graph.jsonl"
    indexer = COOKBOOK / "sources" / "indexer" / "node_modules" / ".bin" / "scip-typescript"
    env = {**os.environ, "PATH": f"{node_bin()}:{os.environ['PATH']}"}
    times = {}
    if not graph.exists():
        times["index"] = timed(lambda: sh(indexer, "index", "tsconfig.build.json", "--no-progress-bar",
                                          "--output", index, cwd=arm.repo, env=env))
        times["convert"] = timed(lambda: sh(sys.executable, "-I", COOKBOOK / "sources" / "build_seed.py",
                                            "--index", index, "--checkout", arm.repo, "--revision", BASE,
                                            "--repository", "https://github.com/honojs/hono.git", "--out", rows))
        og_env = {**os.environ, **arm.tool_env(), "PATH": os.environ["PATH"]}
        (arm.root / "og").mkdir(exist_ok=True)
        sh(og, "init", "--schema", COOKBOOK / "schema.pg", graph, env=og_env)
        times["load"] = timed(lambda: sh(og, "load", "--target", graph, "--data", rows, "--mode", "overwrite",
                                         "--yes", "--json", env=og_env))
    arm.wrap("cg", COOKBOOK / "client" / "cg", sys.executable, env={"CG_TARGET": graph, "CG_OMNIGRAPH": og})
    claude_md = arm.repo / "CLAUDE.md"
    claude_md.write_text(OMNIGRAPH_CLAUDE_MD)
    (arm.repo / ".claude").mkdir(exist_ok=True)
    settings = arm.repo / ".claude" / "settings.json"
    if not settings.exists():
        settings.write_text("{}\n")
    return {"index_seconds": times}


def setup_codegraph(arm: Arm) -> dict:
    binary = TOOLS / "codegraph" / "node_modules" / ".bin" / "codegraph"
    arm.wrap("codegraph", binary)
    times = {}
    if not (arm.repo / ".codegraph").exists():
        times["install_and_index"] = timed(lambda: sh(arm.bin / "codegraph", "install", "--target", "claude",
                                                      "--location", "local", "--yes", "--init",
                                                      cwd=arm.repo, env=arm.tool_env()))
    return {"index_seconds": times}


def setup_gitnexus(arm: Arm) -> dict:
    binary = TOOLS / "gitnexus" / "node_modules" / ".bin" / "gitnexus"
    arm.wrap("gitnexus", binary)
    times = {}
    if not (arm.repo / "CLAUDE.md").exists():
        times["analyze"] = timed(lambda: sh(arm.bin / "gitnexus", "analyze", ".", cwd=arm.repo, env=arm.tool_env()))
    if not (arm.home / ".claude" / "skills").exists():
        sh(arm.bin / "gitnexus", "setup", "-c", "claude", cwd=arm.repo, env=arm.tool_env())
    return {"index_seconds": times}


def setup_cbm(arm: Arm) -> dict:
    opt = arm.root / "opt"
    source = TOOLS / "cbm" / "codebase-memory-mcp"
    env = arm.tool_env()
    times = {}
    if not (opt / "codebase-memory-mcp").exists():
        for key in ("watcher_enabled", "auto_watch"):
            sh(source, "config", "set", key, "false", env=env)
        sh(source, "install", "-y", "--clients=claude", f"--dir={opt}", cwd=arm.repo, env=env)
    arm.wrap("codebase-memory-mcp", opt / "codebase-memory-mcp")
    if not [p for p in (arm.root / "cache").glob("*.db") if not p.name.startswith("_")]:  # _config.db is settings
        times["index"] = timed(lambda: sh(arm.bin / "codebase-memory-mcp", "cli", "--quiet", "index_repository",
                                          json.dumps({"repo_path": str(arm.repo)}), env=env))
    return {"index_seconds": times}


def setup_graphify(arm: Arm) -> dict:
    arm.wrap("graphify", venv_tool(arm, "graphifyy==0.9.102", "graphify"))
    times = {}
    if not (arm.repo / "graphify-out" / "graph.json").exists():
        times["update"] = timed(lambda: sh(arm.bin / "graphify", "update", ".", cwd=arm.repo, env=arm.tool_env()))
    if not (arm.home / ".claude" / "skills").exists():
        sh(arm.bin / "graphify", "install", "--platform", "claude", cwd=arm.repo, env=arm.tool_env())
        sh(arm.bin / "graphify", "claude", "install", cwd=arm.repo, env=arm.tool_env())
    return {"index_seconds": times}


def setup_crg(arm: Arm) -> dict:
    arm.wrap("code-review-graph", venv_tool(arm, "code-review-graph==2.3.9", "code-review-graph"))
    times = {}
    if not (arm.repo / ".code-review-graph").exists():
        times["build"] = timed(lambda: sh(arm.bin / "code-review-graph", "build", "--repo", ".",
                                          cwd=arm.repo, env=arm.tool_env()))
        sh(arm.bin / "code-review-graph", "install", "--platform", "claude", "--yes", "--repo", ".",
           cwd=arm.repo, env=arm.tool_env())
    return {"index_seconds": times}


def adopt(arm: Arm):
    """Move what an installer wrote to the scratch home into the project, and
    point every hook and MCP server at the tool's environment."""
    home, project = arm.home / ".claude", arm.repo / ".claude"
    project.mkdir(exist_ok=True)
    for sub in ("skills", "agents", "commands"):
        if (home / sub).is_dir():
            shutil.copytree(home / sub, project / sub, dirs_exist_ok=True)
    if (home / "CLAUDE.md").exists():
        claude_md, extra = arm.repo / "CLAUDE.md", (home / "CLAUDE.md").read_text()
        if extra not in (claude_md.read_text() if claude_md.exists() else ""):
            with claude_md.open("a") as f:
                f.write("\n" + extra)
    # Start from the settings the installer wrote, kept on the first run, so
    # that running setup again gives the same settings.
    settings_path, installed = project / "settings.json", arm.root / "installer-settings.json"
    if not installed.exists():
        installed.write_text(settings_path.read_text() if settings_path.exists() else "{}\n")
    settings = json.loads(installed.read_text())
    global_settings = json.loads((home / "settings.json").read_text()) if (home / "settings.json").exists() else {}
    hooks = settings.setdefault("hooks", {})
    for event, entries in global_settings.get("hooks", {}).items():
        for entry in entries:
            if entry not in hooks.setdefault(event, []):
                hooks[event].append(entry)
    prefix = arm.env_prefix()
    for entries in hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") != "command":
                    continue
                command = hook["command"]
                if hook.get("args"):
                    command = shlex.join([command, *hook.pop("args")])
                if not command.startswith("env HOME="):
                    command = f"{prefix} {command}"
                hook["command"] = command
    if not hooks:
        settings.pop("hooks")
    else:
        for event, entries in hooks.items():
            hooks[event] = [e for i, e in enumerate(entries) if e not in entries[:i]]
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    servers = {}
    for source in (arm.home / ".claude.json", arm.repo / ".mcp.json"):
        if source.exists():
            servers.update(json.loads(source.read_text()).get("mcpServers", {}))
    # A repository can commit its own MCP servers (VS Code commits one for its
    # own development); they are the repository's, not the tool's, so no arm
    # gets them. A tool's installer adds its servers to the same file.
    committed = subprocess.run(["git", "-C", arm.repo, "show", "HEAD:.mcp.json"], capture_output=True, text=True,
                               env={**os.environ, **GIT_ENV})
    if committed.returncode == 0:
        for name in json.loads(committed.stdout).get("mcpServers", {}):
            servers.pop(name, None)
    for server in servers.values():
        server["env"] = {**server.get("env", {}), **arm.tool_env()}
    arm.mcp.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n")


def inventory(arm: Arm) -> dict:
    """What the agent of this arm is given beyond the stock session."""
    project = arm.repo / ".claude"
    settings = json.loads((project / "settings.json").read_text()) if (project / "settings.json").exists() else {}
    claude_md = [p for p in (arm.repo / "CLAUDE.md", project / "CLAUDE.md", arm.repo / "AGENTS.md") if p.exists()]
    return {
        "mcp_servers": sorted(json.loads(arm.mcp.read_text())["mcpServers"]),
        "instructions_bytes": {str(p.relative_to(arm.repo)): p.stat().st_size for p in claude_md},
        "skills": sorted(p.name for p in (project / "skills").glob("*")) if (project / "skills").is_dir() else [],
        "subagents": sorted(p.stem for p in (project / "agents").glob("*.md")) if (project / "agents").is_dir() else [],
        "hooks": {event: len(entries) for event, entries in settings.get("hooks", {}).items()},
        "shell": arm.shell(),
    }


SETUP = {"bare": lambda arm: {}, "omnigraph": setup_omnigraph, "codegraph": setup_codegraph,
         "graphify": setup_graphify, "gitnexus": setup_gitnexus, "cbm": setup_cbm, "crg": setup_crg}


def setup(arms: list[str]):
    for name in arms:
        arm = Arm(name)
        worktree(arm)
        if SUITE == "vscode":
            read_only_git(arm)
        try:
            meta = SETUP[name](arm)
        except (subprocess.TimeoutExpired, SystemExit) as e:
            # A tool that cannot index the repository within the budget is a
            # result, not a reason to stop the other arms.
            arm.meta.write_text(json.dumps({"failed": str(e)[-2000:]}, indent=2) + "\n")
            print(f"{name}: setup failed: {str(e)[-300:]}", flush=True)
            continue
        adopt(arm)
        meta["given"] = inventory(arm)
        previous = json.loads(arm.meta.read_text()) if arm.meta.exists() else {}
        if not meta.get("index_seconds"):
            meta["index_seconds"] = previous.get("index_seconds", {})
        arm.meta.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"{name}: {json.dumps(meta)}")


# --- index -------------------------------------------------------------------

def index_command(name: str, scratch: Arm) -> list[list]:
    """The commands that build this tool's index of a fresh checkout."""
    repo = scratch.repo
    if name == "omnigraph":
        indexer = COOKBOOK / "sources" / "indexer" / "node_modules" / ".bin" / "scip-typescript"
        index, rows, graph = scratch.root / "index.scip", scratch.root / "graph.jsonl", scratch.root / "graph.omni"
        og = omnigraph_bin()
        return [[indexer, "index", "tsconfig.build.json", "--no-progress-bar", "--output", index],
                [sys.executable, "-I", COOKBOOK / "sources" / "build_seed.py", "--index", index, "--checkout", repo,
                 "--revision", BASE, "--out", rows],
                [og, "init", "--schema", COOKBOOK / "schema.pg", graph],
                [og, "load", "--target", graph, "--data", rows, "--mode", "overwrite", "--yes", "--json"]]
    tool = Arm(name).bin  # the arm's wrappers name the installed tools
    real = {line.split("exec ", 1)[1] for line in (tool / {"codegraph": "codegraph", "graphify": "graphify",
            "gitnexus": "gitnexus", "cbm": "codebase-memory-mcp", "crg": "code-review-graph"}[name]).read_text()
            .splitlines() if line.startswith("exec ")}.pop().removesuffix(' "$@"')
    binary = shlex.split(real)
    return {
        "codegraph": [[*binary, "init", "-y", "."]],
        "graphify": [[*binary, "update", "."]],
        "gitnexus": [[*binary, "analyze", "--skip-agents-md", "--skip-skills", "."]],
        "cbm": [[*binary, "cli", "--quiet", "index_repository", json.dumps({"repo_path": str(repo)})]],
        "crg": [[*binary, "build", "--repo", "."]],
    }[name]


def index_times(arms: list[str], reps: int):
    """Time each tool's first index of a fresh checkout, with an empty home."""
    for name in [a for a in arms if a != "bare"]:
        seconds = []
        for rep in range(reps):
            scratch = Arm(f"index-{name}")
            scratch.root = WORK / "index-timing" / name
            scratch.repo, scratch.home, scratch.bin = scratch.root / "hono", scratch.root / "home", Arm(name).bin
            if scratch.root.exists():
                if scratch.repo.exists():
                    sh("git", "-C", REPO, "worktree", "remove", "--force", scratch.repo)
                shutil.rmtree(scratch.root)
            scratch.root.mkdir(parents=True)
            sh("git", "-C", REPO, "worktree", "add", "--quiet", "--detach", scratch.repo, BASE)
            (scratch.home / ".claude").mkdir(parents=True)
            env = {**scratch.tool_env(), "CBM_CACHE_DIR": str(scratch.root / "cache"),
                   "OMNIGRAPH_HOME": str(scratch.root / "og")}
            start = time.monotonic()
            for command in index_command(name, scratch):
                sh(*command, cwd=scratch.repo, env=env)
            seconds.append(round(time.monotonic() - start, 2))
            sh("git", "-C", REPO, "worktree", "remove", "--force", scratch.repo)
            shutil.rmtree(scratch.root)
        meta = json.loads(Arm(name).meta.read_text())
        meta["index_seconds_fresh"] = {"runs": seconds, "median": statistics.median(seconds)}
        Arm(name).meta.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"{name}: {seconds}")


# --- run ---------------------------------------------------------------------

def run_one(arm: Arm, question: dict, rep: int, model: str, answer_format: str) -> Path:
    out_dir = RUNS / model / arm.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{question['id']}-{rep}.jsonl"
    if out.exists() and (out.with_suffix(".meta.json")).exists():
        return out
    allowed = ["Read", "Grep", "Glob", "Skill", "Task"]
    allowed += [f"Bash({c}:*)" for c in READ_ONLY_SHELL + arm.shell()]
    allowed += [f"mcp__{s}" for s in json.loads(arm.mcp.read_text())["mcpServers"]]
    argv = ["claude", "-p", "--model", model, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config",
            # Auto-memory is keyed by the shared hono repository, so one arm's
            # memories would reach the others.
            "--settings", json.dumps({"autoMemoryEnabled": False}),
            "--mcp-config", str(arm.mcp), "--tools", BUILTIN_TOOLS, "--allowedTools", ",".join(allowed),
            "--max-turns", str(MAX_TURNS)]
    env = {k: os.environ[k] for k in ("HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "TERM") if k in os.environ}
    # Where a box keeps Claude Code's login, when it is not under HOME.
    env.update({k: v for k, v in os.environ.items()
                if k in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")})
    env["PATH"] = f"{arm.bin}:{node_bin()}:{SYSTEM_PATH}:{Path(shutil.which('claude')).parent}"
    prompt = f"{question['question']}\n\n{answer_format}"
    start = time.monotonic()
    with open(out.with_suffix(".partial"), "w") as stream:
        proc = subprocess.Popen(argv, cwd=arm.repo, env=env, stdin=subprocess.PIPE, stdout=stream,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            _, err = proc.communicate(prompt, timeout=RUN_TIMEOUT)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            _, err = proc.communicate()
            timed_out = True
    wall = time.monotonic() - start
    text = out.with_suffix(".partial").read_text()
    result = next((json.loads(line) for line in reversed(text.splitlines())
                   if line.startswith("{") and '"type":"result"' in line.replace(" ", "")), None)
    said = (result or {}).get("result") or ""
    if (proc.returncode != 0 or (result or {}).get("is_error")) and USAGE_LIMIT.search(f"{said}\n{err}"):
        out.with_suffix(".partial").unlink()
        raise UsageLimited((said or err).strip()[-300:])
    out.with_suffix(".partial").rename(out)
    out.with_suffix(".meta.json").write_text(json.dumps({
        "arm": arm.name, "question": question["id"], "rep": rep, "model": model, "wall_seconds": round(wall, 2),
        "exit": proc.returncode, "timed_out": timed_out, "stderr": err[-2000:]}, indent=2) + "\n")
    return out


def run(arms: list[str], qids: list[str] | None, reps: int, model: str, jobs: int):
    spec = json.loads(QUESTIONS.read_text())
    questions = [q for q in spec["questions"] if not qids or q["id"] in qids]
    if qids and len(questions) != len(qids):
        raise SystemExit(f"unknown questions: {sorted(set(qids) - {q['id'] for q in questions})}")
    ready = []
    for name in arms:
        arm = Arm(name)
        if arm.meta.exists() and "failed" in json.loads(arm.meta.read_text()):
            print(f"{name}: skipped, its setup failed (see {arm.meta})", flush=True)
            continue
        if not arm.mcp.exists():
            raise SystemExit(f"arm {name} is not set up: run `agent.py setup --arms {name}`")
        ready.append(name)
    arms = ready
    work = [(name, q, rep) for rep in range(1, reps + 1) for q in questions for name in arms]
    random.Random(7).shuffle(work)
    locks = {name: threading.Lock() for name in arms}
    done = collections.Counter()
    limited = []

    def task(item):
        name, q, rep = item
        with locks[name]:  # one session per arm at a time: tools share one index
            if limited:
                return
            try:
                path = run_one(Arm(name), q, rep, model, spec["answer_format"])
            except UsageLimited as e:
                limited.append(str(e))
                return
        done[name] += 1
        print(f"{sum(done.values())}/{len(work)} {name} {q['id']} #{rep} -> {path.name}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for f in concurrent.futures.as_completed([pool.submit(task, w) for w in work]):
            f.result()
    if limited:
        # Finished sessions are kept, and a run skips them, so the same command
        # resumes once an account has usage again.
        print(f"stopped on a usage limit after {sum(done.values())} sessions: {limited[0]}", flush=True)
        raise SystemExit(LIMITED_EXIT)


# --- score -------------------------------------------------------------------

def owner_lift(nodes: dict):
    """Map an answer to the granularity the answer format asks for: functions,
    methods, classes, interfaces and function constants. A getter, field or
    variable lifts to its class, and a constant that holds no function to its
    file, so naming `upgradeWebSocket` and naming its file grade alike, though
    the graph and the reference give such a constant its own code. A method
    with no class is a member of an object literal written at the top of a
    file, which has no name of its own, so it lifts to its file."""
    non_owner = {"getter", "setter", "property", "variable", "enum_member"}

    def lift(ident: str) -> str:
        n = nodes[ident]
        while (n["kind"] in non_owner or (n["kind"] == "constant" and not n["callable"])
               or (n["kind"] == "method" and ":" in ident and "." not in ident.split(":", 1)[1])):
            tail = ident.split(":", 1)[-1]
            parent = ident.rsplit(".", 1)[0] if ":" in ident and "." in tail else n["path"]
            if parent not in nodes or parent == ident:
                return n["path"]
            ident, n = parent, nodes[parent]
        return ident
    return lift


def normalize(item: str) -> str:
    s = str(item).strip().strip("`'\"").strip()
    s = re.sub(r"\(\)$", "", s)
    s = re.sub(r"^(?:\./|/)", "", s)
    s = re.sub(r"^.*?(?=src/)", "", s) if "src/" in s else s
    if ":" not in s and " " in s:
        s = re.sub(r"\s+", ":", s, count=1)
    s = re.sub(r"(?<=[\w$])#(?=[\w$])", ".", s)
    s = re.sub(r"\.prototype\.", ".", s)
    return s


def grade(answer: list, key: set, nodes: dict, lift, optional: set = frozenset()) -> dict:
    """F1 of an answer against the key; an optional definition counts neither way."""
    got = set()
    for item in answer:
        ident = normalize(item)
        if ident not in nodes and ":" in ident and "." in ident.split(":", 1)[1]:
            private = re.sub(r"\.([\w$]+)$", r".#\1", ident)  # Hono.dispatch for Hono.#dispatch
            ident = private if private in nodes else ident
        if ident in nodes:
            ident = lift(ident)
        got.add(ident)
    got -= optional
    tp = len(got & key)
    p = tp / len(got) if got else 0.0
    r = tp / len(key)
    return {"tp": tp, "fp": len(got - key), "fn": len(key - got), "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0, "exact": got == key,
            "wrong": sorted(got - key), "missed": sorted(key - got)}


ANSWER_LINE = re.compile(r"ANSWER:\s*(\[.*?\])\s*$", re.S | re.M)


def parse_stream(path: Path) -> dict:
    tools, text, result, init, first_context, texts = collections.Counter(), "", None, None, None, []
    for line in path.read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = ev
        elif ev.get("type") == "assistant":
            usage = ev.get("message", {}).get("usage")
            if usage and first_context is None:  # what the session starts with, before any tool runs
                first_context = sum(usage.get(k, 0) for k in
                                    ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    name = block["name"]
                    tools["mcp" if name.startswith("mcp__") else name] += 1
                    if name == "Bash":
                        first = block.get("input", {}).get("command", "").split()[:1]
                        tools[f"Bash:{first[0] if first else ''}"] += 1
                elif block.get("type") == "text":
                    text = block["text"]
                    texts.append(text)
        elif ev.get("type") == "result":
            result = ev
    texts.append((result or {}).get("result") or "")
    # The session's answer is its last ANSWER: line in any message: an agent
    # that answers, then replies to a late tool notification with "the answer
    # above stands", has still answered.
    answer = next((t for t in reversed(texts) if ANSWER_LINE.search(t)), "")
    return {"tools": tools, "answer_text": answer,
            "result": result, "init": init, "first_context": first_context}


def score(model: str):
    spec = json.loads(QUESTIONS.read_text())
    nodes, _ = load_reference(REFERENCE)
    lift = owner_lift(nodes)
    # A dropped question has no answer to grade against (its `note` says why).
    scored = [q for q in spec["questions"] if not q.get("dropped")]
    keys = {q["id"]: set(q["answer"]) for q in scored}
    family = {q["id"]: q.get("family", q["id"]) for q in scored}
    families = list(dict.fromkeys(family.values()))
    optional = {q["id"]: set(q.get("optional", [])) for q in scored}
    for qid, key in keys.items():
        missing = [k for k in key | optional[qid] if k not in nodes and k.split(":")[0] not in nodes]
        if missing:
            raise SystemExit(f"{qid}: key entries the reference does not know: {missing}")
    rows = []
    for meta_path in sorted((RUNS / model).glob("*/*.meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta["question"] not in keys:
            continue
        parsed = parse_stream(meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")))
        res = parsed["result"] or {}
        usage = res.get("modelUsage") or {}
        tokens_in = sum(u.get("inputTokens", 0) + u.get("cacheReadInputTokens", 0)
                        + u.get("cacheCreationInputTokens", 0) for u in usage.values())
        tokens_out = sum(u.get("outputTokens", 0) for u in usage.values())
        cache_writes = sum(u.get("cacheCreationInputTokens", 0) for u in usage.values())
        match = ANSWER_LINE.findall(parsed["answer_text"])
        try:
            answer = json.loads(match[-1]) if match else []
        except json.JSONDecodeError:
            answer = []
        g = grade(answer, keys[meta["question"]], nodes, lift, optional[meta["question"]])
        mcp_status = {s["name"]: s["status"] for s in (parsed["init"] or {}).get("mcp_servers", [])}
        rows.append({**{k: meta[k] for k in ("arm", "question", "rep", "wall_seconds", "timed_out")},
                     "completed": bool(res) and not res.get("is_error") and not meta["timed_out"],
                     "answered": bool(match), "api_seconds": round(res.get("duration_api_ms", 0) / 1000, 2),
                     # The API's speed during this session, so a slow window shows.
                     "output_tokens_per_api_second": round(tokens_out / (res["duration_api_ms"] / 1000), 1)
                     if res.get("duration_api_ms") else None,
                     "turns": res.get("num_turns"), "input_tokens": tokens_in, "output_tokens": tokens_out,
                     "cache_write_tokens": cache_writes, "first_context_tokens": parsed["first_context"],
                     "cost_usd": res.get("total_cost_usd"), "tool_calls": dict(parsed["tools"]),
                     "mcp_status": mcp_status, **{k: g[k] for k in ("precision", "recall", "f1", "exact",
                                                                       "wrong", "missed")}})
    if not rows:
        raise SystemExit(f"no runs under {RUNS / model}")
    med = lambda xs: statistics.median(xs) if xs else None  # noqa: E731
    rnd = lambda x, n: round(x, n) if x is not None else None  # noqa: E731

    # A session that ended without a result, such as one that timed out, has
    # no cost, turn count or first context. Its value is unknown, not zero, so
    # it is left out of those medians and pairs.
    def known(rs, k):
        return [r[k] for r in rs if r[k] is not None]
    summary = {}
    for arm in [a for a in ARMS if any(r["arm"] == a for r in rows)]:
        rs = [r for r in rows if r["arm"] == arm]
        calls = [sum(v for k, v in r["tool_calls"].items() if ":" not in k) for r in rs]
        summary[arm] = {
            "tool": TOOL_NAMES[arm], "runs": len(rs), "completed": sum(r["completed"] for r in rs),
            "mean_f1": round(statistics.mean(r["f1"] for r in rs), 3),
            "exact": sum(r["exact"] for r in rs),
            "median_input_tokens": med([r["input_tokens"] for r in rs]),
            "median_output_tokens": med([r["output_tokens"] for r in rs]),
            "median_cache_write_tokens": med([r["cache_write_tokens"] for r in rs]),
            "median_first_context_tokens": med(known(rs, "first_context_tokens")),
            "median_cost_usd": rnd(med(known(rs, "cost_usd")), 4),
            "total_cost_usd": round(sum(known(rs, "cost_usd")), 2),
            "median_wall_seconds": med([r["wall_seconds"] for r in rs]),
            "median_api_seconds": med([r["api_seconds"] for r in rs]),
            "median_turns": med(known(rs, "turns")),
            "median_output_tokens_per_api_second": med([r["output_tokens_per_api_second"] for r in rs
                                                        if r["output_tokens_per_api_second"]]),
            "per_family": {fam: {"runs": len(fr), "exact": sum(r["exact"] for r in fr),
                                 "mean_f1": round(statistics.mean(r["f1"] for r in fr), 3),
                                 "median_cost_usd": rnd(med(known(fr, "cost_usd")), 4),
                                 "median_turns": med(known(fr, "turns"))}
                           for fam in families if (fr := [r for r in rs if family[r["question"]] == fam])},
            "median_tool_calls": med(calls),
            "graph_tool_share": round(sum(r["tool_calls"].get("mcp", 0) + sum(
                v for k, v in r["tool_calls"].items() if k.startswith("Bash:") and k[5:] in Arm(arm).shell() and k[5:] != "git")
                for r in rs) / max(1, sum(calls)), 3),
            "per_question": {q: {"mean_f1": round(statistics.mean(r["f1"] for r in rs if r["question"] == q), 3),
                                 "median_input_tokens": med([r["input_tokens"] for r in rs if r["question"] == q]),
                                 "median_wall_seconds": med([r["wall_seconds"] for r in rs if r["question"] == q])}
                             for q in keys if any(r["question"] == q for r in rs)},
            "setup": json.loads(Arm(arm).meta.read_text()) if Arm(arm).meta.exists() else {},
        }
    # Paired with the arm without a graph: per question, the ratio of the two
    # arms' medians over the repetitions, then the geometric mean over the
    # questions, and on how many questions the arm spent less. A question
    # counts for a measure once both arms have a positive median of it.
    def qmed(arm, q, k):
        return med(known([r for r in rows if r["arm"] == arm and r["question"] == q], k))
    if "bare" in summary:
        for arm, s in summary.items():
            s["vs_bare"] = {}
            for k in ("cost_usd", "wall_seconds", "input_tokens", "output_tokens", "turns"):
                ratios = [a / b for q in keys if (a := qmed(arm, q, k)) and (b := qmed("bare", q, k))]
                s["vs_bare"][k] = {"geomean_ratio": round(math.exp(statistics.mean(math.log(x) for x in ratios)), 3)
                                   if ratios else None,
                                   "questions_lower": sum(x < 1 for x in ratios), "questions": len(ratios)}
    out = BENCH / "results"
    out.mkdir(exist_ok=True)
    (out / RESULTS).write_text(json.dumps({"suite": SUITE, "model": model, "summary": summary, "runs": rows},
                                          indent=2) + "\n")
    print(f"{'arm':<11} {'runs':>4} {'F1':>6} {'exact':>5} {'in tok':>9} {'out tok':>8} {'cost $':>7} "
          f"{'wall s':>7} {'api s':>6} {'turns':>5} {'calls':>5} {'graph%':>6}")
    def num(x, spec):
        # A measure no session reported prints as "-" in the same width.
        return format(x, spec) if x is not None else format("-", spec.split(".")[0])
    for arm, s in summary.items():
        print(f"{arm:<11} {s['runs']:>4} {s['mean_f1']:>6.3f} {s['exact']:>5} {num(s['median_input_tokens'], '>9.0f')} "
              f"{num(s['median_output_tokens'], '>8.0f')} {num(s['median_cost_usd'], '>7.3f')} "
              f"{num(s['median_wall_seconds'], '>7.1f')} {num(s['median_api_seconds'], '>6.1f')} "
              f"{num(s['median_turns'], '>5.0f')} {num(s['median_tool_calls'], '>5.0f')} "
              f"{s['graph_tool_share'] * 100:>5.0f}%")
    if "bare" in summary:
        print(f"\n{'vs bare':<11} " + " ".join(f"{k:>16}" for k in ("cost", "wall", "input tokens", "output tokens", "turns")))
        for arm, s in summary.items():
            v = s["vs_bare"]
            print(f"{arm:<11} " + " ".join(f"{num(v[k]['geomean_ratio'], '>9.2f')}x ({v[k]['questions_lower']}/{v[k]['questions']})"
                                           for k in ("cost_usd", "wall_seconds", "input_tokens", "output_tokens", "turns")))


def main():
    global RUNS, RESULTS
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--suite", choices=sorted(SUITES), default="hono",
                    help="the repository and questions: hono, or vscode (built by scale.py)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "index", "run", "score"):
        p = sub.add_parser(name)
        if name != "score":
            p.add_argument("--arms", default=",".join(ARMS))
        if name in ("run", "score"):
            p.add_argument("--model", default=DEFAULT_MODEL)
        if name in ("run", "score"):
            # A later window of sessions keeps its transcripts and results apart.
            p.add_argument("--runs", help="the transcripts' directory, instead of the suite's")
        if name == "score":
            p.add_argument("--results", help="the results file's name under results/, instead of the suite's")
        if name == "index":
            p.add_argument("--reps", type=int, default=3)
        if name == "run":
            p.add_argument("--questions")
            p.add_argument("--reps", type=int, default=3)
            p.add_argument("--jobs", type=int, default=3)
    args = ap.parse_args()
    configure(args.suite)
    arms = [a for a in getattr(args, "arms", "").split(",") if a]
    unknown = set(arms) - set(ARMS)
    if unknown:
        raise SystemExit(f"unknown arms: {sorted(unknown)}; choose from {ARMS}")
    if args.cmd == "setup":
        setup(arms)
    elif args.cmd == "index":
        if SUITE != "hono":
            raise SystemExit("index times the hono suite; the vscode suite records them in setup and build.json")
        index_times(arms, args.reps)
    elif args.cmd == "run":
        RUNS = Path(args.runs).resolve() if args.runs else RUNS
        run(arms, args.questions.split(",") if args.questions else None, args.reps, args.model, args.jobs)
    else:
        RUNS = Path(args.runs).resolve() if args.runs else RUNS
        RESULTS = args.results or RESULTS
        score(args.model)


if __name__ == "__main__":
    main()
