# OmniGraph Cookbooks

Each cookbook sets OmniGraph up for one kind of work: a living record that the
people and agents doing that work share, and the agent workflows around it.
You get the data model for the field, the questions the record answers, the
workflows agents run and sample data to try them on.

| Cookbook | What it keeps | A question it answers |
|---|---|---|
| [Company brain](company-brain/) | A company's people, projects, claims, decisions and commitments, each tied to the exact words it rests on, shared by its people and agents. | Which decisions are current, project by project? |
| [Development graph](dev-graph/) | Issues, epics, specs, decisions, pull requests, releases and incidents as one graph, with the Git host still the record for code. | What is ready to pick up? |
| [Agent work queue](beads/) | A dependency-aware issue queue for coding agents, in the style of beads: file work, link what waits on what, claim what is ready, close it. | What can an agent claim now? |
| [Hardware program](hardware-program/) | Requirements, budgets, interfaces and verification for a hardware program, with "verified" and "over budget" worked out from the evidence on every read. | Does each budget still close? |
| [Industry intelligence](industry-intel/) | Signals, patterns and insights about an industry, linked to the products and technologies they concern, with hybrid search over the sources. | Which patterns does new evidence contradict? |
| [Pharma intelligence](pharma-intel/) | Competitive intelligence for a biotech program: the compounds, trials and deals around it, the program's own assumptions, and which signals contradict them. | Which signals contradict an assumption the program relies on? |
| [Venture firm](vc-os/) | A venture firm's deals, portfolio, people and investment theses, with every signal tied to the beliefs it supports or contradicts. | Which active theses has new evidence contradicted? |
| [Second brain](second-brain/) | One person's people, projects, notes, tasks, habits and reading, with where each piece came from. | What do I still owe this person? |
| [Personal health record](health-record/) | One person's lab results, readings, targets, hypotheses, medication and vaccine doses, with "off target", "overdue" and "incomplete" worked out from the results on every read. | Which results are outside my own targets? |
| [Protein binder design campaign](binder-campaign/) | A de novo protein design campaign as a graph: every tested design, how it was made, the scores that selected it, the assays that tested it, and the gaps under each claim. | Which binder claims survive a stricter rule? |

Each cookbook's README is the page for its use case: the data model, how
changes are reviewed, the workflows, the tools it takes data from and the
questions you can ask.

> If you are an agent: [AGENTS.md](AGENTS.md) has the rules for working in
> this repository, and each cookbook's `AGENTS.md` has its commands.

## What is in a cookbook

- **A data model.** The types and links of the field in one file, `schema.pg`.
  It is a starting point: drop what you do not track and add what you do.
- **Stored queries.** The questions the record answers and the changes people
  and agents make to it, each with a name.
- **Agent workflows.** What agents bring into the record, what they keep
  consistent in it, and whom they tell when something needs a person.
- **Review on branches.** An agent makes its changes on a branch, and a person
  reads the difference and merges it. company-brain, hardware-program and
  health-record enforce this: an agent there cannot write the main record or
  merge. In the others it is how the workflows are written, and nothing
  enforces it.
- **Sample data.** A made-up case, described in `seed.md`, that every featured
  question returns an answer on.

## Try one

Paste this prompt into a coding agent such as Claude Code or Codex, with the
cookbook you picked:

```text
Read https://www.omnigraph.dev/onboarding.md and set up Omnigraph for me with the <name> cookbook: https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/<folder>
```

The agent installs OmniGraph, loads the cookbook into a graph on your machine
and runs its questions. Then it asks what you want your own record to hold and
trims the cookbook to that.
[omnigraph.dev/onboarding.md](https://www.omnigraph.dev/onboarding.md) is the
guide it follows, and the place to read what each step does.

To serve a cookbook the way a team or several agents would share it, follow
[local setup](docs/local-setup.md).

## Version

The cookbooks are checked against OmniGraph **0.15.0** on every pull request.
For a graph made with an earlier release, see
[upgrading](docs/local-setup.md#upgrading).

## Contributing

[AGENTS.md](AGENTS.md) says how to change a cookbook, how to write its README
and what `python3 scripts/check-cookbooks.py` checks.
[omnigraph.dev/use-cases](https://www.omnigraph.dev/use-cases) is built from
this repository, so a merged change shows up there.
