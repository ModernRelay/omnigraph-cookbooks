# Custom Domain — Elicitation

Collect only decisions not already supplied. Group related questions so setup
does not become a long interview. When the user delegates a choice, use a
reasonable default and record it.

## Scope

- **Domain:** biotech, fintech, crypto, geopolitics, macroeconomics, SaaS,
  climate tech, or the user's own domain.
- **Breadth:** for example, all biotech versus oncology therapeutics, or all
  crypto versus DeFi on Ethereum L2s.
- **Geography:** global or selected regions.
- **Project slug:** a filesystem-safe name such as `bio-intel`, `crypto-intel`,
  or `geo-intel`. It names the cookbook folder and the graph declaration;
  apply derives `graphs/<slug>.omni`.

## Use

| Question | Why it matters |
|----------|----------------|
| Which actors matter: companies, labs, regulators, experts, protocols, investors? | Choose useful Company classifications and Element kinds. |
| How much history: recent months or foundational events too? | Bound research and timestamp coverage. |
| How often will the graph be updated? | Describe the ongoing research and review routine. |
| Who consumes it: analysts, dashboards, agents, or a mix? | Select useful queries and aliases. |

Keep the SPIKE core narrow. An actor category does not automatically require a
new node type; start with the existing Company, Expert, and Element types.

## Sources

Start with the user's own reading list, then fill the relevant gaps. Capture
source name, URL, format, and why it matters. For experts, also record their
affiliation and publishing venue.

| Category | Prompts and examples |
|----------|---------------------|
| Regular reading | Newsletters, blogs, publications, and podcasts the user already follows. |
| Experts | Analysts, researchers, or practitioners whose work should be attributable to an Expert node. |
| Regulatory or authoritative | FDA/EMA/clinicaltrials.gov for biotech; SEC/CFPB/FCA/BIS for finance; government and UN publications for geopolitics. |
| Primary research | Papers, trial registries, statistical releases, protocol proposals, and first-party technical reports. |
| Community | Forums, social accounts, podcasts, and governance discussions; verify factual claims against primary evidence. |

The [domain examples](domain-examples.md) provide starter lists. Offer a small
relevant subset if the user has no preferences; verify actual URLs and recent
material during research. Do not treat a source list as current evidence.

Deduplicate sources. An author and their outlet can be separate Expert and
SourceEntity nodes, connected through the artifacts they produce.

## Record the result

Write `<slug>/setup-notes.md` with:

- Domain, scope, geography, and project slug.
- Actors, historical horizon, cadence, and consumers.
- Sources grouped by category, with URLs and attribution.
- Any assumptions that influenced schema or research choices.

Resolve consequential ambiguities before researching a full seed. Use the
notes as the schema and research brief; keep later corrections there rather
than appending a second setup narrative elsewhere.
