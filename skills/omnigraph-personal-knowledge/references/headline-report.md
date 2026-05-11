# Headline report — "Your graph in 5 numbers"

Run this AFTER every successful first-time load and AFTER the dedup wizard finishes. Skip on incremental syncs (use the slim delta-report instead — see `sync.md`).

The point: turn a "loaded N nodes" CLI exit into a five-line report that makes the graph feel alive, plus 3-5 ready-to-run follow-up queries. The user goes from "I just imported stuff" to "oh — I see patterns about myself" in under 5 seconds of reading.

## Queries to run

Five aliases, in order. Run them via `omnigraph read --alias <name> --format jsonl`. The first JSONL line is a `{"kind":"metadata", "row_count": N, ...}` envelope; skip it before parsing data rows (filter by `kind != "metadata"` or just drop the first line):

1. `headline-notes-by-source` — count of Notes per `Artifact.source`.
2. `headline-top-persons` — top mentioned Persons by `Mentions` count.
3. `headline-recent-artifacts` — most recent 200 Artifacts (you'll bucket by source + summarize).
4. `headline-cross-source-persons` — Persons appearing via multiple `ExternalID.source` values (the dedup-candidate seed).
5. `headline-recent-conversations` — recent Conversations and their participant counts.

For each, post-process in code (Claude does this in-context):

- Aggregate `headline-notes-by-source` rows into a per-source count.
- Group `headline-top-persons` by person, sort by mention count desc, take top 5.
- Pivot `headline-recent-artifacts` rows into per-source counts + a date range.
- Group `headline-cross-source-persons` by person, count distinct sources per person, take any with `>=2`.
- Group `headline-recent-conversations` by conversation slug, count distinct participants, take top 5 with longest spans.

## Format the output

Match this layout exactly. Use the user's actual numbers:

```
Your personal-knowledge graph
─────────────────────────────
{TOTAL_NOTES} Notes from {N_SOURCES} sources ({source_breakdown})
   {N_PERSONS} Persons    → top: {TOP_PERSON} (mentioned {TOP_COUNT}×)
   {N_TOPICS} Topics      → top: {TOP_TAG_LIST}
   {N_CROSS_SOURCE} cross-source mentions
   {N_LONG_CONVS} long-running conversations (>30 days)
```

## Pick ONE observation

After the five numbers, print one observation line. Pick from the menu below based on what's actually true about the loaded graph — the first applicable trigger wins. Don't write platitudes; if no trigger fires, surface the most-mentioned source/person directly.

| Trigger | Observation template |
|---|---|
| `headline-recent-artifacts` shows granola has ≥3 artifacts AND ≥2 derived Notes per transcript on average | "Meeting transcripts are your highest-leverage source — {N} transcripts anchored {M} derived notes plus the Events and attendees in a single load." |
| Any single Person has ExternalIDs from ≥2 distinct sources | "{name} is your most cross-referenced contact — they appear across {sources}. High-value relationship to keep current." |
| `headline-cross-source-persons` flags ≥1 dedup candidate AND wizard hasn't run yet | "{N} duplicate-person candidate(s) flagged. Running the dedup wizard now tightens the graph before you trust any 'who do I talk to about X' query." |
| One Note kind ≥50% of all notes | "Your graph is {kind}-heavy ({pct}% of notes). The other kinds are where compounding shows up — `kind=insight` notes especially." |
| One source ≥70% of all artifacts | "{source} carries {pct}% of your artifacts. The other sources are wired but quiet — your second-brain is currently single-channel." |
| Zero Conversations imported | "No conversations yet. Slack/email is where the densest context lives for most users — worth wiring next." |
| ≥70% of artifacts in the last 7 days | "{N} of your {total} artifacts are from the last week. The graph is freshly seeded; re-ask follow-ups next Sunday and you'll see compound effects." |
| Zero cross-source mentions | "All contacts come from a single source. The graph gets exponentially more interesting once you have a second source in (e.g., Slack on top of Obsidian)." |

## Pick 4-5 follow-ups

Offer queries that demonstrate **graph value** — the questions you can't easily answer in a single source. Generic "list my notes" suggestions waste the moment. Use this menu, fill placeholders from the user's actual data:

```
Try next:
- "What customer pain points have I heard across meetings, Slack, and notes in the last 60 days?"
- "Who keeps coming up in my notes but I haven't talked to in 30+ days?"
- "Show me everything connected to {TOP_PROJECT} — notes, tasks, meetings, people, conversations."
- "Where has '{TOP_TAG}' come up across all my sources, in chronological order?"
- "Who's attending {NEXT_EVENT} and what's the most recent thing I know about each of them?"
```

Placeholder injection rules:
- `{TOP_PROJECT}` = the active Project with the most attached records (count `NoteAboutProject` + `TaskForProject` + `EventForProject` + `InvolvedIn`). If no Projects exist, drop that line.
- `{TOP_TAG}` = the most common Note tag, **excluding values that collide with `Note.kind` enum** (`idea`, `reflection`, `insight`, `quote`, `dream`, `journal`, `principle` — those are meta-classifications, not topics). If, after that filter, tags are sparse or generic, substitute the top-mentioned Person's name and switch the framing to "Where has {name} come up across all my sources, in chronological order?"
- `{NEXT_EVENT}` = the upcoming Event with the soonest `date` field; if no future events, the most recent past event with ≥2 attendees.

Always include line 1 (cross-source pain points) — it's the most universally compelling and the seed always satisfies it.

Always include the "Connect my real apps" or "Walk me through the identity-resolution candidates" CTA as the 5th line if the user is on the demo path (so they have a forward step beyond reading).

## Do NOT

- Dump raw JSON.
- Print all 200 recent artifacts. Bucket and sample.
- Use placeholders that didn't get filled. If the data doesn't support a line, drop it instead of showing `{TOP_PROJECT}` literally.
- Promise anything about the graph that isn't supported by the data on hand.
- Suggest follow-up queries the user could answer in one Slack search or one Notion search. Pick cross-source / cross-time / cross-entity questions every time.
