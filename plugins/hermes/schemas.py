"""Tool JSON schemas — what the LLM reads to decide when/how to call each tool.

Descriptions are deliberately specific: they steer the model toward the graph as
the source of truth, schema-first querying, branch-not-main writes, and capture.
"""

_TARGET = {
    "type": "string",
    "description": "Graph name, e.g. 'personal' or 'modernrelay'. Omit to use the config default. "
                   "Call omnigraph_targets if unsure which graphs exist.",
}

DOCTOR = {
    "name": "omnigraph_doctor",
    "description": "Preflight/health check for Omnigraph. Reports the binary + version, which config(s) "
                   "were discovered and where, the graphs each defines, whether bearer tokens are set, "
                   "and reachability of each remote graph. Run this first when anything Omnigraph-related "
                   "is failing or to confirm setup.",
    "parameters": {"type": "object", "properties": {"target": _TARGET}, "required": []},
}

TARGETS = {
    "name": "omnigraph_targets",
    "description": "List the Omnigraph graphs available on this machine and the query aliases each config "
                   "defines. Use to discover what you can query before writing a query.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SCHEMA = {
    "name": "omnigraph_schema",
    "description": "Fetch the current schema (.pg) for a graph and write it to a file (avoids truncation). "
                   "Returns the file path plus a node/edge/interface summary. ALWAYS fetch the schema before "
                   "writing an ad-hoc query so you use real type/edge/enum names — never guess fields.",
    "parameters": {"type": "object", "properties": {"target": _TARGET}, "required": []},
}

QUERY = {
    "name": "omnigraph_query",
    "description": "Run a READ query against a graph and return rows (JSONL). Strongly prefer a configured "
                   "`alias` (see omnigraph_targets). Only pass an ad-hoc `query_string`/`query_file` when no "
                   "alias fits — and fetch the schema first. Pass `params` as typed values (never inline them "
                   "into the query). The graph is the canonical source of truth — consult it before answering "
                   "factual questions about people/tasks/projects/commitments.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": _TARGET,
            "alias": {"type": "string", "description": "A configured query alias (preferred)."},
            "args": {"type": "array", "items": {}, "description": "Positional args for the alias, in order."},
            "query_string": {"type": "string", "description": "Inline GQ source (when no alias fits)."},
            "query_file": {"type": "string", "description": "Path to a .gq file (alternative to query_string)."},
            "query_name": {"type": "string", "description": "Query symbol inside query_file."},
            "params": {"type": "object", "description": "Typed named params (written to a file, never inlined)."},
            "branch": {"type": "string", "description": "Branch to read (default main)."},
        },
        "required": [],
    },
}

SEARCH = {
    "name": "omnigraph_search",
    "description": "Semantic (meaning-based) search over a graph via a configured search alias. Pass natural-"
                   "language `query_text`. Scope-then-rank with a bounded limit is applied. Use when you need "
                   "to find content by meaning rather than by exact key.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": _TARGET,
            "query_text": {"type": "string", "description": "Natural-language search query."},
            "alias": {"type": "string", "description": "Search alias to use (defaults to the configured one)."},
            "limit": {"type": "integer", "description": "Max results (the alias/query must end with `limit`)."},
        },
        "required": ["query_text"],
    },
}

MUTATE = {
    "name": "omnigraph_mutate",
    "description": "Run a MUTATION (insert/update/delete, or a mutate-alias). Writes go to a feature BRANCH, "
                   "never main. For REMOTE graphs this automatically runs the verification ritual (compares the "
                   "commit head before/after) and reports landed/did_not_land — it NEVER blind-retries. Use this "
                   "instead of running `omnigraph mutate` via the terminal.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": _TARGET,
            "alias": {"type": "string", "description": "A configured mutate alias (preferred)."},
            "args": {"type": "array", "items": {}, "description": "Positional args for the alias, in order."},
            "query_string": {"type": "string", "description": "Inline GQ mutation source (when no alias fits)."},
            "query_file": {"type": "string", "description": "Path to a .gq file."},
            "query_name": {"type": "string", "description": "Mutation symbol inside query_file."},
            "params": {"type": "object", "description": "Typed named params (written to a file, never inlined)."},
            "branch": {"type": "string", "description": "Target branch. Defaults to a generated feature branch; "
                                                        "pass 'main' only when explicitly intended (discouraged)."},
        },
        "required": [],
    },
}

CAPTURE = {
    "name": "omnigraph_capture",
    "description": "Import durable information the user shared (a task, person, place, project, commitment, note, "
                   "or media) into the graph. The graph is the system of record. This fetches the schema, resolves "
                   "any person via ExternalID first (never creating a duplicate), builds a parameterized mutation, "
                   "and — per policy — either PROPOSES it for your confirmation (default 'suggest') or writes it to "
                   "a branch ('auto-branch'). Use whenever the user shares something worth remembering.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": _TARGET,
            "info_text": {"type": "string", "description": "The durable info to import, in the user's words."},
            "categories": {"type": "array", "items": {"type": "string"},
                           "description": "Optional: detected categories (task, person, place, project, ...)."},
            "mode": {"type": "string", "enum": ["suggest", "auto-branch"],
                     "description": "Override the configured capture policy for this call."},
        },
        "required": ["info_text"],
    },
}

LINT = {
    "name": "omnigraph_lint",
    "description": "Validate a .gq query file against a .pg schema (offline; no server needed). Run after editing "
                   "a query or schema. Local-dev/cookbook authoring.",
    "parameters": {
        "type": "object",
        "properties": {
            "schema_path": {"type": "string", "description": "Path to the .pg schema."},
            "query_path": {"type": "string", "description": "Path to the .gq query file."},
        },
        "required": ["schema_path", "query_path"],
    },
}

PLAN = {
    "name": "omnigraph_schema_plan",
    "description": "Plan a schema migration (dry-run) for a graph against a candidate .pg file. ALWAYS run this "
                   "before any schema apply; reports whether the migration is supported and its steps. Local-dev.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": _TARGET,
            "schema_path": {"type": "string", "description": "Path to the candidate .pg schema."},
        },
        "required": ["schema_path"],
    },
}
