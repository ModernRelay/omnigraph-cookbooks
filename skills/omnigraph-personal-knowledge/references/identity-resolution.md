# Identity-resolution wizard

Run after a multi-source first import (Phase 2.5 in SKILL.md). The same person commonly shows up under different `Person` slugs across sources — Notion mention "Jane", Slack DM partner "Jane Park", LinkedIn connection "Jane Park" with email. The wizard finds likely matches, gathers evidence per pair, **auto-decides when shared context is strong**, and only asks the user when evidence is ambiguous.

## Detection — candidate finder

Run `omnigraph read --alias identity-candidates` to get every Person row. Then in code, apply three matchers in this order and union the candidate set:

1. **Email-prefix collision (high confidence)** — strip trailing digits and dots from the local part (so `priya.shah.97` and `priya` both normalize to `priya`); group on prefix; flag groups with >1 distinct email address.
2. **Exact-name match (high confidence)** — group by `name` after lowercasing and stripping punctuation; flag groups with >1 distinct slug.
3. **First-name alias (medium confidence)** — group by the lowercased first word of `name`; flag when at least one record's full name *is* that first word (e.g. "Jane") while another's first word *matches* it within a longer name ("Jane Park").

Skip pairs that already have a `SameAs` edge between them (query `person-same-as <slug>` first; pre-merged pairs should not re-surface).

## Per-pair evidence + auto-decision

For each candidate pair `(slug_a, slug_b)`, gather:

| Signal | Query |
|---|---|
| Email domains | `person-external-ids <slug>` filtered to `source=email` |
| Organizations | `person-orgs <slug>` (drop null rows) |
| Mention counts | `person-mentions <slug>` (len of results) |
| External ID sources | `person-external-ids <slug>` (set of `source` values) |

Apply this auto-decision policy:

- **Shared email domain** (e.g. both `@kettle.so`) → `merge`, high confidence, "same workplace context"
- **Shared organization** (both have `BelongsTo` to the same org) → `merge`, high confidence
- **Domain-org match** (one side's email domain core, e.g. `kettle` from `kettle.so`, equals the other side's org name lowercased) → `merge`, medium confidence
- **Otherwise** → `ask`. Surface the full evidence to the user via `AskUserQuestion` with three options: Yes / No / Skip.

The point of the policy: don't make the user adjudicate obvious cases, don't auto-merge ambiguous ones.

## Walk-through — one pair at a time

For each candidate pair (or group of N>2, walk transitively), AskUserQuestion:

```
"Looks like {NAME_A} and {NAME_B} might be the same person.
Evidence:
- {NAME_A}: {EVIDENCE_A}
- {NAME_B}: {EVIDENCE_B}

Same person?"
options:
  - "Yes, merge them"
  - "No, different people"
  - "Skip for now"
```

**Order**: highest-confidence pairs first (email match before name match). Cap at 20 candidates per session — beyond that, the user is fatigued; offer to schedule the rest for a later session.

## On "yes, merge"

Run `link-same-as` mutation between the two slugs:

```
omnigraph change --alias link-same-as \
  --from <slug-a> --to <slug-b> \
  --confidence 0.95 --method "user-confirmed"
```

Then run the same edge in reverse for symmetry:

```
omnigraph change --alias link-same-as \
  --from <slug-b> --to <slug-a> \
  --confidence 0.95 --method "user-confirmed"
```

Don't physically merge the nodes — `SameAs` is the edge that lets queries traverse them as one. The data layer keeps both Persons (because external IDs continue to come in tagged with their original ID), but downstream queries can union them.

If the user wants a "true" merge (one canonical Person, drop the other), that's a follow-up — write a query that rewrites edges from B onto A, then deletes B. Don't do this by default; it loses provenance.

## On "no" or "skip"

Move on. Don't ask the same pair again in this session. (No need to persist the "no" response for v1; the user can re-skip if a future sync re-surfaces it.)

## After the wizard

Tell the user: "Merged {N} pairs. Skipped {M}. Cross-source `SameAs` edges added — your follow-up queries will see these slugs as one person."

Then immediately demonstrate by running the **SameAs-aware mentions** pattern (below) on a recently-merged person and showing the delta vs the direct query.

## SameAs-aware traversal (skill-level pattern)

The shipped aliases — `person-mentions`, `notes-about-person`, `tasks-for-person`, etc. — match on an exact slug. They do **not** follow `SameAs` automatically. The skill compensates at orchestration time: when a user asks "show me everything about Priya," the skill resolves the SameAs closure first and queries each slug, then unions the results.

Pseudocode for any "_about a person_" question:

```
def about_person(start_slug, alias_to_run):
    # 1. Resolve SameAs closure (both directions, transitive)
    aliases = {start_slug}
    queue = [start_slug]
    while queue:
        cur = queue.pop()
        for row in omnigraph_read("person-same-as", cur):
            other = row["other.slug"]
            if other not in aliases:
                aliases.add(other)
                queue.append(other)

    # 2. Run the user-requested alias for every aliased slug, dedup by result key
    seen = {}
    for s in aliases:
        for row in omnigraph_read(alias_to_run, s):
            seen[row["a.slug"]] = row     # or whatever the key column is
    return list(seen.values())
```

Apply this wrapper to `person-mentions`, `notes-about-person`, `person-events`, `person-artifacts`, `tasks-for-person` — any read alias that takes a person slug. The skill should narrate when the SameAs traversal added rows ("3 extra mentions surfaced because Priya's work + personal slugs are linked").

For one-off natural-language questions where Claude composes a new query inline (not a shipped alias), Claude should fold the same union into the query — either by issuing multiple matches in one query (if Omnigraph supports it for that pattern) or by running the query once per alias slug.
