# Initial Research Workflow

Phase 6: turn the elicited domain + source list into real seed content.

**Rule #1: do not fabricate signals, dates, URLs, or quotes.** Every signal must have a real dated source. If you can't find one, leave the signal out. A smaller seed with real sources beats a larger seed with plausible-sounding fiction.

## Target output

For a new cookbook, aim for:

| Node | Target count | Notes |
|------|--------------|-------|
| Pattern | 3–5 | Themes that recur across signals |
| Signal | 10–20 | Each dated, URL-backed, specific |
| Element | 15–30 | Products, concepts, companies-as-things |
| Insight | 2–4 | Non-obvious observations |
| KnowHow | 1–3 | Actionable practices (optional) |
| Company | 10–20 | Real entities with briefs |
| Expert | 3–8 | From Phase 3 |
| SourceEntity | 8–15 | From Phase 3 |
| InformationArtifact | 15–25 | One per signal roughly |

Totals: ~80–120 nodes, ~100–150 edges. Matches `industry-intel` scale.

## Step-by-step

### Step 1 — Gather source material

For each source from Phase 3's source list, pull recent items:

```
WebFetch https://endpts.com (for example) → extract dated articles from last N months
```

Use `WebFetch` for specific known URLs, `WebSearch` for discovering related items.

Save raw excerpts to a scratch file (`<slug>/research-notes.md` — gitignore this if large). Include URL, date, title, 1-3 sentence excerpt.

### Step 2 — Extract candidate signals

A signal is a **dated, specific, factual movement**. Examples:

- ✅ "Kimi K2.5 released Jan 26 2026 — 1T/32B MoE, 76% lower cost than Claude"
- ✅ "FDA approved drug X for indication Y on April 3 2026"
- ✅ "Bitcoin ETF flows turned negative for first time since launch, Mar 2026"
- ❌ "AI is getting better" (not dated, not specific)
- ❌ "Biotech funding is down" (generic)

Write a candidate list. Aim for 2× the target signal count — you'll cut weak ones later.

### Step 3 — Cluster into patterns

Look for recurring themes across your candidate signals. A pattern is a **repeatable theme that multiple signals evidence**.

Ask:
- What's happening multiple times, to multiple actors, from multiple sources?
- What's the structural force driving those signals?

Rules of thumb:
- A pattern needs **≥ 3 supporting signals**. If only 1–2 signals fit, either drop the pattern or find more signals.
- Aim for **3–5 patterns total**. More than 5 and your analysis gets diffuse.
- Name patterns with a **compelling phrase** that encapsulates the idea (e.g., "SaaSpocalypse", "Sovereign AI", "Context Graphs"). These become the narrative spine of the graph.

Pattern.kind mapping:
- `challenge` — a technical/business problem driving change
- `disruption` — a paradigm shift
- `dynamic` — an ongoing interaction or feedback loop

### Step 4 — Extract Elements

For each signal, identify the "things" it's about:
- Products (drugs, protocols, platforms, apps)
- Concepts (a technique, pattern, or idea)
- Frameworks (reusable toolkits)

These become Element nodes. Connect to signals via `OnElement`, to patterns via `ExemplifiesPattern` or `EnablesPattern`.

**Deduplication:**
- Same product mentioned in 3 signals = 1 Element with 3 incoming OnElement edges
- Similar products from different companies = separate Elements
- A generic concept = 1 Element referenced from many signals

Normalize slugs:
- Lowercase, hyphenated
- Strip company prefixes for well-known products: `el-kimi-k25` not `el-moonshot-kimi-k25`
- Abbreviate when common: `el-rag` not `el-retrieval-augmented-generation`

### Step 5 — Extract Companies, Experts, Sources

For each signal:
- **Company**: who is behind the Element, who's quoted, whose stock moved
- **Expert**: who wrote the piece, who's quoted as analyst
- **SourceEntity**: which publication/blog/podcast published
- **InformationArtifact**: the specific article/video/paper (must have a real URL)

Slug prefixes:
- `co-` for companies
- `exp-` for experts
- `source-` for source entities (often with suffix: `-nl` newsletter, `-bl` blog, `-pod` podcast)
- `ia-` for artifacts

### Step 6 — Draft Insights and KnowHows

Optional but valuable:

- **Insight** — a synthesized observation that explains why a pattern matters. Examples from `industry-intel`:
  - "Agents are informed walkers" (explains context-graphs pattern)
  - "Functionality is now portable" (explains SaaSpocalypse)

- **KnowHow** — an actionable practice grounded in the graph. Examples:
  - "Deploy on-prem AI in <1 week (Zylon pattern)"
  - "Set up autonomous research loop (Karpathy + Google)"

Don't force these if the domain doesn't have obvious candidates.

### Step 7 — Write seed.md (tabular, for human review)

Structure matches `industry-intel/seed.md` (use it as template):

```markdown
# <Domain> Intel — Seed Dataset

## Patterns (N)

| slug | name | kind | brief |
|------|------|------|-------|
| pat-xxx | ... | disruption | ... |

## Signals (N)

| slug | name | brief | domain | stagingTimestamp |
|------|------|-------|--------|------------------|
| sig-xxx | ... | ... | <domain> | 2026-mm-dd |

### Signal → Pattern edges (FormsPattern)

| signal | pattern |
|--------|---------|
| ... | ... |

## Elements (N)

| slug | name | kind | brief |
|------|------|------|-------|

### Element → Pattern edges

| edge | element | pattern |
|------|---------|---------|

### Element → Element edges

...

## Insights (N)
## KnowHows (N)
## Companies (N)
## Experts (N)
## SourceEntity (N)
## InformationArtifact (N)

### All the provenance edges...

## Descriptions

### Patterns

**`pat-xxx`** — Full 2-4 sentence description with real dated evidence.

### Signals

**`sig-xxx`** — Full description with URL, date, and specific quantitative detail.
```

### Step 8 — **Present seed.md to the user for review**

Before generating JSONL, show the user the seed.md and ask:

> Here's the seed I compiled from your sources. Review the patterns, signals, and key elements. Any that should be removed, merged, or reframed? Any gaps?

Common corrections:
- Misframed patterns (user sees something you missed)
- Wrong attribution (company/author incorrect)
- Missing signals (user knows about one you didn't find)
- Pattern name too generic (user has a better phrase)

Cheap to fix here. Expensive to fix after load.

### Step 9 — Generate seed.jsonl from seed.md

Each row:

**Node:**
```json
{"type":"NodeType","data":{"id":"slug","slug":"slug","name":"...","kind":"...",...,"createdAt":"2026-04-14T00:00:00Z","updatedAt":"2026-04-14T00:00:00Z"}}
```

**Edge:**
```json
{"edge":"EdgeName","from":"src-slug","to":"dst-slug","data":{}}
```

Rules:
- `id` equals `slug`
- DateTime format: `YYYY-MM-DDT00:00:00Z`
- `createdAt` / `updatedAt` default to today (or `stagingTimestamp` if set)
- Include every required (non-nullable) property from the schema
- Omit optional properties when not set — don't emit `null`
- Edge names in `"edge":` field must match schema exactly (PascalCase)
- Emit nodes first, then edges (makes load deterministic)

### Step 10 — Validate

```bash
cd <slug>
omnigraph query lint --schema ./schema.pg --query ./queries/mutations.gq
```

Lint doesn't validate the seed directly, but it confirms the schema accepts every field.

Then load:

```bash
set -a && source ./.env.omni && set +a
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/<slug>
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/<slug>
```

If load fails (missing required field, invalid enum value, unknown type), fix seed.jsonl and retry.

### Step 11 — Smoke test

```bash
omnigraph read --config ./omnigraph.yaml --alias patterns disruption
omnigraph read --config ./omnigraph.yaml --alias signals
```

Should return the patterns and signals you seeded.

Try a traversal:

```bash
omnigraph read --config ./omnigraph.yaml --alias pattern-signals pat-<your-pattern>
```

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Signal has no `stagingTimestamp` | Derive from article publication date; emit ISO 8601 |
| Required `[String]` property is empty | Emit `[]`, not `null`, not omitted |
| Two similar elements with different slugs | Dedupe in seed.md step, before JSONL |
| Invented URL | Search again or drop the signal |
| Pattern with only 1 supporting signal | Drop the pattern or find more signals |
| Vague pattern name ("AI stuff") | Rewrite as a specific, compelling phrase |
| Enum value mismatch (typo in kind) | Check schema; enum values are case-sensitive |

## Delegate to a Subagent

For large research tasks, consider delegating to a subagent:

```
Agent: Research the <domain> space from these sources [list]. Return a seed.md in the format of
<path-to-industry-intel/seed.md>. Focus on real signals from the last <N> months. Include real
URLs and dates. Cluster into 3-5 patterns. Don't fabricate.
```

The subagent can do the WebFetch/WebSearch in parallel and return a compact seed.md for the main agent to review with the user.
