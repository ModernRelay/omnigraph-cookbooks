"""The single chokepoint that runs the ``omnigraph`` CLI.

Every Omnigraph invocation in the plugin goes through :func:`run`. It bakes in the
correct defaults so the model can't get them wrong:

  * canonical verbs only (``query`` / ``mutate`` — never deprecated ``read`` / ``change``)
  * global flags placed **after** the subcommand
  * credentials injected via the subprocess ``env=`` dict (from ``auth.env_file``) —
    never a shell ``source``, never creds on argv
  * ``query`` -> ``--format jsonl``; ``mutate`` and admin reads -> ``--json``
  * params passed via a temp ``--params-file`` (never string-interpolated)
  * ``--config`` + ``--target`` always passed explicitly (deterministic, cwd-independent)
  * HTTP 504 / 409 / 429 classified for the verification ritual
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

OMNIGRAPH_BIN = shutil.which("omnigraph") or "/opt/homebrew/bin/omnigraph"
STDOUT_SPILL_THRESHOLD = 50_000           # bytes; larger results spill to a temp file
DEFAULT_TIMEOUT = 90                      # seconds (remote graphs can be slow)

# subcommands (first word) that emit structured output via --json (not --format)
_JSON_CMDS = {"mutate", "commit", "schema", "snapshot", "branch", "lint", "policy", "graphs"}


@dataclass
class RunResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    ok: bool
    http: int | None = None               # 504 / 409 / 429 if detected, else None
    parsed: Any = None                    # json.loads(stdout) when it's a JSON object/array
    records: list[Any] = field(default_factory=list)   # parsed JSONL rows (query)
    stdout_file: str | None = None        # path when stdout was large enough to spill

    def error_text(self) -> str:
        return (self.stderr or self.stdout or "").strip()


def _load_env_file(path: str | None) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path:
        return env
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        return env
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


# Precise patterns — a bare "409"/"429"/"504" appears in commit ids, timestamps and
# version numbers, so a numeric code only counts when it carries an HTTP reason/context
# (reason phrase, or http/status/code prefix). We also only ever scan stderr (data lives
# on stdout). Order: throttle -> conflict -> timeout.
_HTTP_PATTERNS = [
    (429, re.compile(r"too[ _]many[ _]requests|retry-after|(?:http|https|status|code)[\s:/]*429\b", re.I)),
    (409, re.compile(r"manifest_conflict|(?:http|https|status|code)[\s:/]*409\b|\b409\s+conflict", re.I)),
    (504, re.compile(r"gateway\s*time-?out|(?:http|https|status|code)[\s:/]*504\b|\b504\s+gateway", re.I)),
]


def _classify_http(text: str) -> int | None:
    t = text or ""
    for code, pat in _HTTP_PATTERNS:
        if pat.search(t):
            return code
    return None


def _parse_output(subcommand_base: str, stdout: str) -> tuple[Any, list[Any]]:
    """Return (parsed_json_or_None, jsonl_records)."""
    s = stdout.strip()
    if not s:
        return None, []
    # query default output is JSONL: first line is a metadata object, rest are rows
    if subcommand_base == "query":
        records = []
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
        return (records[0] if records else None), records
    # everything else uses --json (single object / array)
    try:
        return json.loads(s), []
    except Exception:
        return None, []


def build_argv(
    subcommand: str,
    *,
    config: str | None = None,
    target: str | None = None,
    branch: str | None = None,
    snapshot: str | None = None,
    actor: str | None = None,
    alias: str | None = None,
    query_string: str | None = None,
    query_file: str | None = None,
    query_name: str | None = None,
    params_file: str | None = None,
    schema_path: str | None = None,
    allow_data_loss: bool = False,
    fmt: str | None = None,
    json_flag: bool | None = None,
    args: Sequence[Any] | None = None,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build the omnigraph argv — pure, no side effects (unit-testable)."""
    parts = subcommand.split()
    base = parts[0]
    sub_full = " ".join(parts)
    argv: list[str] = [OMNIGRAPH_BIN, *parts]

    # global selectors — ALWAYS after the subcommand
    if config:
        argv += ["--config", str(config)]
    if target:
        argv += ["--target", str(target)]
    if branch:
        argv += ["--branch", str(branch)]
    if snapshot:
        argv += ["--snapshot", str(snapshot)]
    if actor:
        argv += ["--as", str(actor)]

    # query/mutation source
    if alias:
        argv += ["--alias", alias]
    elif query_string:
        argv += ["-e", query_string]
    elif query_file:
        argv += ["--query", str(query_file)]
        if query_name:
            argv += ["--name", query_name]

    if params_file:
        argv += ["--params-file", str(params_file)]
    if schema_path:
        argv += ["--schema", str(schema_path)]
    if allow_data_loss:
        argv += ["--allow-data-loss"]

    # structured output
    if base == "query":
        argv += ["--format", fmt or "jsonl"]
    elif json_flag is True:
        argv += ["--json"]
    elif json_flag is None and sub_full != "schema show" and base in _JSON_CMDS:
        # `schema show` must stay raw .pg text; `schema plan/apply` take --json
        argv += ["--json"]

    # positional alias args go last
    if args:
        argv += [str(a) for a in args]
    argv += list(extra_args)
    return argv


def run(
    subcommand: str,
    *,
    config: str | None = None,
    target: str | None = None,
    fmt: str | None = None,
    json_flag: bool | None = None,
    alias: str | None = None,
    args: Sequence[Any] | None = None,
    query_file: str | None = None,
    query_name: str | None = None,
    query_string: str | None = None,
    params: dict | None = None,
    branch: str | None = None,
    snapshot: str | None = None,
    schema_path: str | None = None,
    allow_data_loss: bool = False,
    extra_args: Sequence[str] = (),
    env_file: str | None = None,
    actor: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> RunResult:
    """Invoke ``omnigraph`` with correct flag ordering, format, and env injection."""
    base = subcommand.split()[0]

    # params via a temp file — never string-interpolated into argv/.gq
    params_tmp: str | None = None
    if params:
        fd, params_tmp = tempfile.mkstemp(prefix="omni-params-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(params, fh)

    argv = build_argv(
        subcommand, config=config, target=target, branch=branch, snapshot=snapshot, actor=actor,
        alias=alias, query_string=query_string, query_file=query_file, query_name=query_name,
        params_file=params_tmp, schema_path=schema_path, allow_data_loss=allow_data_loss,
        fmt=fmt, json_flag=json_flag, args=args, extra_args=extra_args,
    )

    # environment: inherit + overlay the config's env_file (AWS creds for local S3, etc.)
    env = dict(os.environ)
    env.update(_load_env_file(env_file))

    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, env=env, timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc, out, err = 124, (exc.stdout or ""), (exc.stderr or "") + "\n[timeout]"
    except FileNotFoundError:
        rc, out, err = 127, "", f"omnigraph binary not found at {OMNIGRAPH_BIN}"
    finally:
        if params_tmp:
            try:
                os.unlink(params_tmp)
            except OSError:
                pass

    http = _classify_http(err)        # errors live on stderr; stdout is data
    parsed, records = _parse_output(base, out)

    stdout_file = None
    if len(out.encode("utf-8", "ignore")) > STDOUT_SPILL_THRESHOLD:
        fd, stdout_file = tempfile.mkstemp(prefix=f"omni-{base}-", suffix=".out")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(out)

    return RunResult(
        argv=argv, returncode=rc, stdout=out, stderr=err,
        ok=(rc == 0 and http is None),
        http=http, parsed=parsed, records=records, stdout_file=stdout_file,
    )
