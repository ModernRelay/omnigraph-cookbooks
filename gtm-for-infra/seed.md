# gtm-for-infra seed

Illustrative roster of 15 AI companies. **Account `status` values are illustrative** — customer / prospect labels are chosen to make the lookalike query return a compelling result set, not to reflect any actual customer relationships.

## Roster

| Slug | Name | Status | Product kind | Workload | Est. $/yr |
|---|---|---|---|---|---|
| `acct-cursor` | Cursor | customer | coding-agent | sandbox | $8.0M |
| `acct-sourcegraph` | Sourcegraph (Amp) | customer | coding-agent | sandbox | $2.5M |
| `acct-suno` | Suno | customer | music-gen | inference | $18.0M |
| `acct-cognition` | Cognition (Devin) | prospect | coding-agent | sandbox | $12.0M |
| `acct-factory` | Factory | prospect | coding-agent | sandbox | $3.0M |
| `acct-pika` | Pika Labs | prospect | video-gen | inference | $6.5M |
| `acct-krea` | Krea | prospect | image-gen | inference | $2.1M |
| `acct-mistral` | Mistral AI | prospect | foundation-model | training | $42.0M |
| `acct-harvey` | Harvey | prospect | vertical-saas | inference | $1.2M |
| `acct-character-ai` | Character.AI | prospect | consumer-agent | inference | $8.0M |
| `acct-liquid-ai` | Liquid AI | prospect | foundation-model | training | $5.0M |
| `acct-runway` | Runway | prospect | video-gen | inference | $11.0M |
| `acct-decagon` | Decagon | prospect | consumer-agent | inference | $0.9M |
| `acct-perplexity` | Perplexity | prospect | consumer-agent | inference | $4.5M |
| `acct-poolside` | Poolside | cold | foundation-model | training | $9.0M |

## Designed lookalike matches

The seed is tuned so `omnigraph read --alias lookalikes` returns four strong matches, sorted by prospect spend:

| Prospect | Matches customer | Shared investor | Shared workload | Prospect spend |
|---|---|---|---|---|
| Cognition | Cursor | Founders Fund | sandbox | $12.0M |
| Pika | Suno | Lightspeed | inference | $6.5M |
| Factory | Sourcegraph | Sequoia | sandbox | $3.0M |
| Krea | Suno | Matrix | inference | $2.1M |

Several prospects share investors with customers but have a different workload (Mistral, Harvey, Character.AI, Runway) — they're intentionally *not* matches, so the signal-to-noise ratio of the query is visible.

## Claim lineage seed

Two `ResearchRun` nodes are seeded to demo supersession:

- `run-enrich-2026-02` — promptVersion `v3`, ran Feb 15
- `run-enrich-2026-04` — promptVersion `v4`, ran Apr 15 (triggered by the Cognition Series C signal)

`claim-cognition-headcount-v4` supersedes `claim-cognition-headcount-v3` — the v3 prompt asserted 35 employees; the v4 prompt, post-Series-C, asserts 72. Running `claim-drift acct-cognition headcount` shows the diff.
