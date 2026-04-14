# SPIKE Seed Dataset

Seed data for five-patterns, mapped to `schema.pg`. Updated: 2026-04-14.

---

## Patterns (5)

| slug | name | kind | brief |
|------|------|------|-------|
| `pat-sovereign-ai` | Sovereign AI | disruption | Own your stack end-to-end: infra, models, context, ontology. Regulatory enforcement removed optionality; agents flatten setup cost. |
| `pat-saaspocalypse` | SaaSpocalypse | disruption | Agents destroying the SaaS presentation layer + business model. $830B wiped in 6 days. Per-seat pricing evaporates when agents don't sit in seats. |
| `pat-context-graphs` | Context Graphs | dynamic | Decision traces + ontology + temporal reasoning as new infrastructure layer above databases. Event clock is the novel product. |
| `pat-new-cyber-threats` | New Cyber Threats | challenge | AI models exploiting vulnerabilities autonomously + agentic enterprise attack surfaces. Capability jumps are discontinuous. |
| `pat-accelerated-research` | Accelerated Research | dynamic | AI agents autonomously conducting research — from Karpathy loops to AlphaEvolve to Tao's AI-assisted proofs. |

---

## Signals (15)

| slug | name | brief | domain | stagingTimestamp |
|------|------|-------|--------|-----------------|
| `sig-93pct-repatriation` | 93% of enterprises repatriating AI workloads | Cloudian survey: 93% evaluating or actively moving AI off public cloud. $80B sovereign cloud IaaS in 2026. | infra | 2026-02-01 |
| `sig-kimi-k25-oss-frontier` | Kimi K2.5: open-source frontier at 76% lower cost | Moonshot AI. 1T/32B MoE. 96.1% AIME, 76.8% SWE-Bench. $0.27 vs $1.14. Modified MIT. Sovereign by default. | inference | 2026-01-26 |
| `sig-zylon-onprem-ai` | Zylon: on-prem AI platform in <1 week | PrivateGPT creators (57k stars). Air-gapped, fixed-cost. SOC 2, HIPAA, GDPR, EU AI Act. Customers: Orsa CU, ASOS. | infra | 2026-03-01 |
| `sig-830b-software-selloff` | $830B wiped from S&P software index in 6 days | Claude Cowork launches as catalyst. Varonis -25%, Thomson Reuters -19%, CrowdStrike -15%, IBM -13%. | harness | 2026-02-04 |
| `sig-sap-consumption-pricing` | SAP shifts to AI consumption pricing | First major incumbent pivot from per-seat to AI usage-based. Bloomberg sourced. | harness | 2026-03-18 |
| `sig-klarna-replaces-salesforce` | Klarna replaces Salesforce with homegrown AI | Named enterprise replacing named incumbent CRM. Canonical case study. | infra | 2026-02-01 |
| `sig-edra-30m-series-a` | Edra: $30M Series A, Sequoia-led, ex-Palantir founders | Operational data → living knowledge base. Customers: HubSpot, ASOS, Cushman & Wakefield. Workflow-first ontology. | harness | 2026-03-18 |
| `sig-forbes-context-graphs` | Forbes: "VCs say context graphs might be the next big thing" | Mainstream category formation. Forrester: "convergence not invention." Foundation Capital thesis going mainstream. | context | 2026-04-03 |
| `sig-gartner-50pct-context-graphs` | Gartner: 50%+ of AI agent systems will use context graphs by 2028 | Named analyst firm, concrete prediction. Legitimizes category for enterprise procurement. | context | 2026-04-01 |
| `sig-mythos-181-exploits` | Mythos Preview: 0% → 181 working exploits on Firefox benchmark | Opus 4.6 near-0%. Mythos: 181 working exploits. 4-vuln browser chain. FreeBSD RCE CVE-2026-4747. Emerged from general reasoning. | security | 2026-04-07 |
| `sig-meta-rogue-agent-breach` | Meta rogue agent breach | Internal AI agent exposed sensitive data to unauthorized engineers. First major enterprise agentic breach. | security | 2026-03-18 |
| `sig-openclaw-unvetted-access` | Users giving unvetted AI agents shell access + all their data | OpenClaw (85k stars in one week) gets shell access, email, files, calendar, persistent memory. Snyk demonstrated prompt injection exfiltrating API keys via spoofed email. Palo Alto: "persistent memory turns point-in-time exploits into stateful, delayed-execution attacks." China banned at state enterprises. | security | 2026-01-29 |
| `sig-karpathy-autoresearch-700` | Karpathy autoresearch: 700 experiments in 2 days | 70.5k stars. Single GPU, 5-min cycles. Human writes program.md; agent writes train.py. Fortune coverage. | training | 2026-03-07 |
| `sig-alphaevolve-matrix-multiply` | AlphaEvolve: first improvement to matrix multiplication in 56 years | Gemini-powered. 48 scalar ops for 4×4 complex (beat Strassen 1969). 23% kernel speedup. UK lab 2026. | inference | 2025-06-16 |
| `sig-tao-erdos-728` | Terence Tao: AI autonomously solves Erdos problem #728 | ChatGPT generated proof, Aristotle auto-repaired, Lean-verified. First AI Erdos solution not in literature. | inference | 2026-01-07 |

### Signal → Pattern edges (FormsPattern)

| signal | pattern |
|--------|---------|
| `sig-93pct-repatriation` | `pat-sovereign-ai` |
| `sig-kimi-k25-oss-frontier` | `pat-sovereign-ai` |
| `sig-zylon-onprem-ai` | `pat-sovereign-ai` |
| `sig-830b-software-selloff` | `pat-saaspocalypse` |
| `sig-sap-consumption-pricing` | `pat-saaspocalypse` |
| `sig-klarna-replaces-salesforce` | `pat-saaspocalypse` |
| `sig-edra-30m-series-a` | `pat-context-graphs` |
| `sig-forbes-context-graphs` | `pat-context-graphs` |
| `sig-gartner-50pct-context-graphs` | `pat-context-graphs` |
| `sig-mythos-181-exploits` | `pat-new-cyber-threats` |
| `sig-meta-rogue-agent-breach` | `pat-new-cyber-threats` |
| `sig-openclaw-unvetted-access` | `pat-new-cyber-threats` |
| `sig-karpathy-autoresearch-700` | `pat-accelerated-research` |
| `sig-alphaevolve-matrix-multiply` | `pat-accelerated-research` |
| `sig-tao-erdos-728` | `pat-accelerated-research` |

### Signal → Element edges (OnElement)

| signal | element |
|--------|---------|
| `sig-kimi-k25-oss-frontier` | `el-kimi-k25` |
| `sig-zylon-onprem-ai` | `el-zylon` |
| `sig-830b-software-selloff` | `el-claude-cowork` |
| `sig-sap-consumption-pricing` | `el-sap-ai` |
| `sig-klarna-replaces-salesforce` | `el-salesforce-crm` |
| `sig-edra-30m-series-a` | `el-edra` |
| `sig-mythos-181-exploits` | `el-claude-mythos-preview` |
| `sig-meta-rogue-agent-breach` | `el-meta-internal-agents` |
| `sig-openclaw-unvetted-access` | `el-openclaw` |
| `sig-karpathy-autoresearch-700` | `el-autoresearch` |
| `sig-alphaevolve-matrix-multiply` | `el-alphaevolve` |
| `sig-tao-erdos-728` | `el-erdos-ai-tools` |

---

## Elements (26)

*(includes 5 elements with minimal metadata: `el-claude-cowork`, `el-sap-ai`, `el-salesforce-crm`, `el-meta-internal-agents`, `el-openclaw`, `el-headless-saas`)*

| slug | name | kind | brief | category |
|------|------|------|-------|----------|
| `el-zylon` | Zylon | product | On-prem AI platform for regulated industries. PrivateGPT (57k stars). Air-gapped, fixed-cost. | [infrastructure] |
| `el-palantir-apollo` | Palantir Apollo | product | Deployment orchestration across air-gapped, classified, edge environments. FedRAMP High, IL5/IL6. | [infrastructure, agentic] |
| `el-nanograph` | nanograph | product | Schema-first embedded property graph, Rust, local-first. SPIKE ontology. "SQLite for graphs." | [database] |

| `el-hermes-agent` | Hermes Agent | framework | NousResearch OSS agent framework. 40+ tools. Runs on $300 mini PC with local models. | [agentic] |
| `el-kimi-k25` | Kimi K2.5 | product | Moonshot AI. 1T/32B MoE. OSS frontier. Agent Swarm: 100 parallel sub-agents. Modified MIT. | [ai_model] |
| `el-mcp` | MCP | technology | Model Context Protocol. Agent-tool communication standard. Agentic AI Foundation governed. | [agentic, infrastructure] |
| `el-anthropic-managed-agents` | Anthropic Managed Agents | product | Hosted service for long-running agents. Public beta Apr 2026. | [agentic, infrastructure] |
| `el-headless-saas` | Headless SaaS | concept | Traditional software rebuilt with agent-first APIs, no UI. New business model category. | [infrastructure] |
| `el-edra` | Edra | product | Auto-updating knowledge bases from operational data. Sequoia-backed. Ex-Palantir founders. | [agentic, rag] |
| `el-hornet` | Hornet | product | Retrieval engine for agents. Vespa veterans. Schema-first APIs. VPC/on-prem. OSS. | [rag, infrastructure] |
| `el-playerzero-sim1` | PlayerZero / Sim-1 | product | Long-trace reasoning engine. 92.6% prediction accuracy. PR-level blast radius in CI/CD. | [agentic, dev_tools] |
| `el-zep-graphiti` | Zep / Graphiti | framework | Temporal knowledge graph for agent memory. Bi-temporal tracking. 94.8-98.2% Deep Memory Retrieval. | [memory, database] |
| `el-genkm` | GenKM | concept | Unified framework for AI-native KGs. 4-stage architecture. 20+ operator algebra. Provenance tracking. | [rag] |
| `el-claude-mythos-preview` | Claude Mythos Preview | product | Emergent cybersecurity capabilities. Zero-day exploitation. Not generally available — Project Glasswing only. | [ai_model] |
| `el-project-glasswing` | Project Glasswing | product | Anthropic's defender-first release of Mythos for securing critical software. | [infrastructure] |
| `el-permissioned-inference` | Permissioned Inference | concept | Isolate reasoning, not just retrieval. Multi-tenant inference leakage. OWASP LLM08. | [agentic] |
| `el-precedent-poisoning` | Precedent Poisoning | concept | Agents reinforce bad decisions at scale. FDE productization loop's dark twin. | [agentic, memory] |
| `el-autoresearch` | autoresearch | framework | Karpathy. 70.5k stars. Single GPU, single file, 5-min cycles. MIT. | [agentic, ml] |
| `el-alphaevolve` | AlphaEvolve | product | Google DeepMind. Gemini-powered evolutionary coding agent. Beat Strassen. Production deployments. | [agentic, ml] |
| `el-karpathy-llm-wiki` | Karpathy LLM Wiki | concept | Raw sources → LLM-compiled .md wiki → schema file. Ingest, query, lint. ~400K words without RAG. | [rag, memory] |
| `el-erdos-ai-tools` | Erdos Problem Database + AI tools | product | Tao's framework. ChatGPT + AlphaProof + Aristotle solve open math. Lean-verified. | [ml] |
| `el-claude-cowork` | Claude Cowork | product | Anthropic's enterprise AI plugins for legal, finance, HR, cybersecurity. Catalyst for $830B SaaS selloff. | [agentic] |
| `el-sap-ai` | SAP AI Platform | product | SAP's AI consumption-based platform. First major incumbent to pivot from per-seat pricing. | [infrastructure, agentic] |
| `el-salesforce-crm` | Salesforce CRM | product | Incumbent CRM platform. Replaced by Klarna with homegrown AI system. | [infrastructure] |
| `el-meta-internal-agents` | Meta Internal AI Agents | product | Meta's internal autonomous agents. Source of first major enterprise agentic breach (Mar 2026). | [agentic] |
| `el-openclaw` | OpenClaw | product | Open-source AI agent with shell access, persistent memory, 85k GitHub stars in one week. Canonical example of the unvetted-access cyber threat. | [agentic] |

### Element → Pattern edges

| edge | element | pattern |
|------|---------|---------|
| ExemplifiesPattern | `el-zylon` | `pat-sovereign-ai` |
| ExemplifiesPattern | `el-kimi-k25` | `pat-sovereign-ai` |
| ExemplifiesPattern | `el-nanograph` | `pat-sovereign-ai` |
| ExemplifiesPattern | `el-headless-saas` | `pat-saaspocalypse` |
| ExemplifiesPattern | `el-claude-cowork` | `pat-saaspocalypse` |
| ExemplifiesPattern | `el-sap-ai` | `pat-saaspocalypse` |
| ExemplifiesPattern | `el-salesforce-crm` | `pat-saaspocalypse` |
| ExemplifiesPattern | `el-edra` | `pat-context-graphs` |
| ExemplifiesPattern | `el-claude-mythos-preview` | `pat-new-cyber-threats` |
| ExemplifiesPattern | `el-openclaw` | `pat-new-cyber-threats` |
| ExemplifiesPattern | `el-permissioned-inference` | `pat-new-cyber-threats` |
| ExemplifiesPattern | `el-precedent-poisoning` | `pat-new-cyber-threats` |
| ExemplifiesPattern | `el-meta-internal-agents` | `pat-new-cyber-threats` |
| ExemplifiesPattern | `el-autoresearch` | `pat-accelerated-research` |
| ExemplifiesPattern | `el-alphaevolve` | `pat-accelerated-research` |
| ExemplifiesPattern | `el-erdos-ai-tools` | `pat-accelerated-research` |
| EnablesPattern | `el-mcp` | `pat-context-graphs` |
| EnablesPattern | `el-mcp` | `pat-saaspocalypse` |
| EnablesPattern | `el-palantir-apollo` | `pat-sovereign-ai` |
| EnablesPattern | `el-hornet` | `pat-context-graphs` |
| EnablesPattern | `el-zep-graphiti` | `pat-context-graphs` |
| EnablesPattern | `el-project-glasswing` | `pat-new-cyber-threats` |
| EnablesPattern | `el-karpathy-llm-wiki` | `pat-accelerated-research` |

### Element → Element edges

| edge | source | target |
|------|--------|--------|
| EnablesElement | `el-mcp` | `el-anthropic-managed-agents` |
| EnablesElement | `el-mcp` | `el-hornet` |
| EnablesElement | `el-mcp` | `el-edra` |
| EnablesElement | `el-claude-mythos-preview` | `el-project-glasswing` |
| UsesElement | `el-zylon` | `el-mcp` |
| UsesElement | `el-autoresearch` | `el-karpathy-llm-wiki` |
| UsesElement | `el-edra` | `el-genkm` |
| UsesElement | `el-edra` | `el-mcp` |

---

## Insights (3)

| slug | name | brief | importance |
|------|------|-------|------------|
| `ins-agents-informed-walkers` | Agents are informed walkers | Agent traverses context graph → adds decision trace → graph compounds → agent becomes smarter. Graph sits as semantic layer on existing data. | Reframes context graphs from product to protocol — works on SQL, NoSQL, markdown. |
| `ins-functionality-portable` | Functionality is now portable | Claude Code enables cloning cloud apps locally. Not data portability — functionality portability. Apps without network effects are easy to clone. | Explains why SaaS moat was never the feature set — it was the rebuild cost. That cost is now near-zero. |
| `ins-agents-thrive-messy-systems` | Agents thrive in messy legacy systems | Agents don't need clean APIs. They navigate complex, poorly designed systems natively, choosing tools by semantic value and durability. | Inverts the conventional build-for-agents narrative. Legacy isn't a blocker, it's an opportunity. |

### Insight → Pattern edges (HighlightsPattern)

| insight | pattern |
|---------|---------|
| `ins-agents-informed-walkers` | `pat-context-graphs` |
| `ins-functionality-portable` | `pat-saaspocalypse` |
| `ins-agents-thrive-messy-systems` | `pat-new-cyber-threats` |

---

## KnowHows (2)

| slug | name | brief | guidelines |
|------|------|-------|------------|
| `how-to-deploy-onprem-ai` | Deploy on-prem AI in <1 week (Zylon pattern) | Three tiers: Cloud VPC, Managed On-Prem (partner runs infra), Fully In-House / Air-Gapped. Or: "Zylon in a Box" pre-configured server. | ["Choose tier by constraint: VPC for elasticity + residency, Managed for no MLOps team, In-House for air-gap", "Partner scopes requirements → provisions GPU → installs → monitors → updates", "All tiers: audit logs, RBAC, encryption at rest + transit", "Stack: local LLMs + vector DB + API gateway + n8n + workspace"] |
| `how-to-autonomous-research-loop` | Set up autonomous research loop (Karpathy + Google) | Two loops: autoresearch (single file, scalar metric, time-boxed) and AI co-scientist (multi-agent hypothesis generation). | ["Loop 1: One editable file, one scalar metric, fixed 5-min budget, program.md for instructions", "Loop 2: State research goal in NL → Generation + Reflection + Ranking + Evolution agents → hypotheses + protocols", "~12 experiments/hour, ~100 overnight", "Scientist provides feedback → system iterates"] |

### KnowHow → Element edges (ReferencesElement)

| knowhow | element |
|---------|---------|
| `how-to-deploy-onprem-ai` | `el-zylon` |
| `how-to-deploy-onprem-ai` | `el-mcp` |
| `how-to-autonomous-research-loop` | `el-autoresearch` |
| `how-to-autonomous-research-loop` | `el-alphaevolve` |
| `how-to-autonomous-research-loop` | `el-karpathy-llm-wiki` |

---

## Companies (14 + 3 for experts = 17 total)

| slug | name | type | brief |
|------|------|------|-------|
| `co-anthropic` | Anthropic | developer | Claude, Mythos Preview, Project Glasswing, Managed Agents |
| `co-google-deepmind` | Google DeepMind | research | AlphaEvolve, AI co-scientist, ScholarPeer, agent attack taxonomy |
| `co-moonshot-ai` | Moonshot AI | developer | Kimi K2.5. Beijing. Alibaba-backed. |
| `co-zylon` | Zylon | developer | On-prem AI platform. Built PrivateGPT. |
| `co-palantir` | Palantir | developer | AIP, Apollo, Ontology, FDE model |
| `co-meta` | Meta | bigtech | KernelEvolve. Rogue agent breach Mar 2026. |
| `co-edra` | Edra | developer | Auto-updating knowledge bases. Ex-Palantir. |
| `co-hornet` | Hornet | developer | Agentic retrieval engine. Vespa veterans. |
| `co-playerzero` | PlayerZero | developer | Sim-1 long-trace reasoning. Context graph vertical. |
| `co-sequoia` | Sequoia | investor | "Services is the new software" thesis. Led Edra Series A. |
| `co-sap` | SAP | bigtech | First major SaaS to pivot to AI consumption pricing. |
| `co-nousresearch` | NousResearch | developer | Hermes Agent. Open-source agent framework. |
| `co-klarna` | Klarna | developer | Replaced Salesforce with homegrown AI. |
| `co-salesforce` | Salesforce | bigtech | CRM incumbent being replaced. |

### Element → Company edges (DevelopedByCompany)

| element | company |
|---------|---------|
| `el-zylon` | `co-zylon` |
| `el-palantir-apollo` | `co-palantir` |
| `el-kimi-k25` | `co-moonshot-ai` |

| `el-hermes-agent` | `co-nousresearch` |
| `el-mcp` | `co-anthropic` |
| `el-anthropic-managed-agents` | `co-anthropic` |
| `el-edra` | `co-edra` |
| `el-hornet` | `co-hornet` |
| `el-playerzero-sim1` | `co-playerzero` |
| `el-claude-mythos-preview` | `co-anthropic` |
| `el-project-glasswing` | `co-anthropic` |
| `el-claude-cowork` | `co-anthropic` |
| `el-alphaevolve` | `co-google-deepmind` |
| `el-sap-ai` | `co-sap` |
| `el-salesforce-crm` | `co-salesforce` |
| `el-meta-internal-agents` | `co-meta` |

### Signal → Company edges (RelevantCompany)

| signal | company |
|--------|---------|
| `sig-830b-software-selloff` | `co-anthropic` |
| `sig-sap-consumption-pricing` | `co-sap` |
| `sig-klarna-replaces-salesforce` | `co-klarna` |
| `sig-klarna-replaces-salesforce` | `co-salesforce` |
| `sig-edra-30m-series-a` | `co-edra` |
| `sig-edra-30m-series-a` | `co-sequoia` |
| `sig-mythos-181-exploits` | `co-anthropic` |
| `sig-meta-rogue-agent-breach` | `co-meta` |
| `sig-alphaevolve-matrix-multiply` | `co-google-deepmind` |

---

## Experts (7)

| slug | name | affiliatedWith |
|------|------|---------------|
| `exp-karpathy` | Andrej Karpathy | — (independent; formerly OpenAI, Tesla) |
| `exp-terence-tao` | Terence Tao | `co-ucla` |
| `exp-balaji` | Balaji Srinivasan | — (independent) |
| `exp-aaron-levie` | Aaron Levie | `co-box` |
| `exp-andrew-altshuler` | Andrew Altshuler | `co-modern-relay` |
| `exp-eugen-alpeza` | Eugen Alpeza | `co-edra` |
| `exp-animesh-koratana` | Animesh Koratana | `co-playerzero` |

### Expert → Company edges (AffiliatedWithCompany)

| expert | company |
|--------|---------|
| `exp-terence-tao` | `co-ucla` |
| `exp-aaron-levie` | `co-box` |
| `exp-andrew-altshuler` | `co-modern-relay` |
| `exp-eugen-alpeza` | `co-edra` |
| `exp-animesh-koratana` | `co-playerzero` |

---

## SourceEntity (16)

| slug | name | type | platform | url |
|------|------|------|----------|-----|
| `source-reuters-nl` | Reuters | newsletter | web | https://reuters.com |
| `source-bloomberg-nl` | Bloomberg | newsletter | web | https://bloomberg.com |
| `source-techcrunch-bl` | TechCrunch | blog | web | https://techcrunch.com |
| `source-fortune-nl` | Fortune | newsletter | web | https://fortune.com |
| `source-forbes-nl` | Forbes | newsletter | web | https://forbes.com |
| `source-sequoia-bl` | Sequoia Capital Blog | blog | web | https://sequoiacap.com |
| `source-anthropic-bl` | Anthropic Blog | blog | web | https://anthropic.com |
| `source-red-anthropic-bl` | Anthropic Red Team | blog | web | https://red.anthropic.com |
| `source-deepmind-bl` | Google DeepMind Blog | blog | web | https://deepmind.google |
| `source-google-research-bl` | Google Research Blog | blog | web | https://research.google |
| `source-tao-mastodon-bl` | Terence Tao (Mastodon) | blog | mastodon | https://mathstodon.xyz/@tao |
| `source-snyk-bl` | Snyk | blog | web | https://snyk.io |
| `source-paloalto-bl` | Palo Alto Networks | blog | web | https://www.paloaltonetworks.com/blog |
| `source-cloudian-bl` | Cloudian / EnterpriseNews | blog | web | https://enterprisenews.com |
| `source-moonshot-bl` | Moonshot AI | blog | web | https://kimi.com |
| `source-zylon-bl` | Zylon | blog | web | https://zylon.ai |

---

## InformationArtifact (20)

| slug | name | artifactType | link | stagingTimestamp |
|------|------|-------------|------|-----------------|
| `ia-cloudian-93pct-survey` | Enterprise Survey: 93% Repatriating AI | article | https://www.enterprisenews.com/press-release/story/83547 | 2026-02-01 |
| `ia-kimi-k25-release` | Kimi K2.5 Release | article | https://www.kimi.com/blog/kimi-k2-5.html | 2026-01-26 |
| `ia-zylon-deployment-options` | Zylon Deployment Options | article | https://www.zylon.ai/deployment-options | 2026-03-01 |
| `ia-reuters-830b-selloff` | Selloff wipes $830B from software stocks | article | https://www.reuters.com/business/media-telecom/global-software-stocks-hit-2026-02-04 | 2026-02-04 |
| `ia-bloomberg-sap-pricing` | SAP Shifts to AI-Based Pricing | article | https://www.bloomberg.com/news/articles/2026-03-18/sap-ceo-pushes-ai | 2026-03-18 |
| `ia-techcrunch-klarna-salesforce` | Klarna Replaces Salesforce | article | https://techcrunch.com/2026/03/01/saas-in-saas-out | 2026-03-01 |
| `ia-techcrunch-edra-stealth` | Two Palantir veterans out of stealth with $30M | article | https://techcrunch.com/2026/03/18/two-palantir-veterans | 2026-03-18 |
| `ia-forbes-context-graphs` | VCs say context graphs might be the next big thing | article | https://www.forbes.com/sites/josipamajic/2026/04/03 | 2026-04-03 |
| `ia-mythos-preview-assessment` | Assessing Claude Mythos Preview cybersecurity capabilities | article | https://red.anthropic.com/2026/mythos-preview | 2026-04-07 |
| `ia-techcrunch-meta-rogue-agent` | Meta is having trouble with rogue AI agents | article | https://techcrunch.com/2026/03/18/meta-is-having-trouble | 2026-03-18 |
| `ia-bloomberg-openclaw-china-ban` | China Moves to Curb OpenClaw AI Use at Banks | article | https://www.bloomberg.com/news/articles/2026-03-11 | 2026-03-11 |
| `ia-fortune-karpathy-loop` | The Karpathy Loop: 700 experiments, 2 days | article | https://fortune.com/2026/03/17/andrej-karpathy-loop | 2026-03-17 |
| `ia-deepmind-alphaevolve` | AlphaEvolve: Gemini-powered coding agent | article | https://deepmind.google/blog/alphaevolve | 2025-06-16 |
| `ia-tao-erdos-728` | Terence Tao on AI solving Erdos problem #728 | article | https://mathstodon.xyz/@tao/115855840223258103 | 2026-01-07 |
| `ia-sequoia-services-new-software` | Services: The New Software | article | https://sequoiacap.com/article/services-the-new-software | 2026-03-25 |
| `ia-snyk-openclaw-security` | Your OpenClaw AI Assistant Has Shell Access | article | https://snyk.io/articles/clawdbot-ai-assistant/ | 2026-01-27 |
| `ia-paloalto-openclaw-crisis` | OpenClaw May Signal the Next AI Security Crisis | article | https://www.paloaltonetworks.com/blog/network-security/why-moltbot-may-signal-ai-crisis/ | 2026-01-29 |
| `ia-levie-agents-legacy` | Aaron Levie on AI agents and legacy systems (a16z podcast) | youtube | https://www.youtube.com/watch?v=dvt_74kV-RM | 2026-04-01 |
| `ia-altshuler-informed-walkers` | Andrew Altshuler on agents as informed walkers | article | https://x.com/1eo/status/2028566640145670413 | 2026-03-01 |
| `ia-balaji-functionality-portable` | Balaji on functionality portability via Claude Code | article | https://x.com/balajis/status/2008847069386273211 | 2026-01-08 |

### InformationArtifact → SourceEntity edges (PublishedBySource)

| artifact | source |
|----------|--------|
| `ia-reuters-830b-selloff` | `source-reuters-nl` |
| `ia-bloomberg-sap-pricing` | `source-bloomberg-nl` |
| `ia-bloomberg-openclaw-china-ban` | `source-bloomberg-nl` |
| `ia-snyk-openclaw-security` | `source-snyk-bl` |
| `ia-paloalto-openclaw-crisis` | `source-paloalto-bl` |
| `ia-techcrunch-edra-stealth` | `source-techcrunch-bl` |
| `ia-techcrunch-klarna-salesforce` | `source-techcrunch-bl` |
| `ia-techcrunch-meta-rogue-agent` | `source-techcrunch-bl` |
| `ia-fortune-karpathy-loop` | `source-fortune-nl` |
| `ia-forbes-context-graphs` | `source-forbes-nl` |
| `ia-sequoia-services-new-software` | `source-sequoia-bl` |
| `ia-mythos-preview-assessment` | `source-red-anthropic-bl` |
| `ia-deepmind-alphaevolve` | `source-deepmind-bl` |
| `ia-tao-erdos-728` | `source-tao-mastodon-bl` |
| `ia-cloudian-93pct-survey` | `source-cloudian-bl` |
| `ia-kimi-k25-release` | `source-moonshot-bl` |
| `ia-zylon-deployment-options` | `source-zylon-bl` |

### InformationArtifact → Expert edges (ContributedByExpert)

| artifact | expert |
|----------|--------|
| `ia-fortune-karpathy-loop` | `exp-karpathy` |
| `ia-tao-erdos-728` | `exp-terence-tao` |
| `ia-levie-agents-legacy` | `exp-aaron-levie` |
| `ia-altshuler-informed-walkers` | `exp-andrew-altshuler` |
| `ia-balaji-functionality-portable` | `exp-balaji` |

### Signal → InformationArtifact edges (SpottedInArtifact)

| signal | artifact |
|--------|----------|
| `sig-93pct-repatriation` | `ia-cloudian-93pct-survey` |
| `sig-kimi-k25-oss-frontier` | `ia-kimi-k25-release` |
| `sig-zylon-onprem-ai` | `ia-zylon-deployment-options` |
| `sig-830b-software-selloff` | `ia-reuters-830b-selloff` |
| `sig-sap-consumption-pricing` | `ia-bloomberg-sap-pricing` |
| `sig-klarna-replaces-salesforce` | `ia-techcrunch-klarna-salesforce` |
| `sig-edra-30m-series-a` | `ia-techcrunch-edra-stealth` |
| `sig-forbes-context-graphs` | `ia-forbes-context-graphs` |
| `sig-mythos-181-exploits` | `ia-mythos-preview-assessment` |
| `sig-meta-rogue-agent-breach` | `ia-techcrunch-meta-rogue-agent` |
| `sig-openclaw-unvetted-access` | `ia-snyk-openclaw-security` |
| `sig-openclaw-unvetted-access` | `ia-paloalto-openclaw-crisis` |
| `sig-openclaw-unvetted-access` | `ia-bloomberg-openclaw-china-ban` |
| `sig-karpathy-autoresearch-700` | `ia-fortune-karpathy-loop` |
| `sig-alphaevolve-matrix-multiply` | `ia-deepmind-alphaevolve` |
| `sig-tao-erdos-728` | `ia-tao-erdos-728` |

### Signal → SourceEntity edges (SourcedFromSource)

| signal | source |
|--------|--------|
| `sig-830b-software-selloff` | `source-reuters-nl` |
| `sig-sap-consumption-pricing` | `source-bloomberg-nl` |
| `sig-openclaw-unvetted-access` | `source-snyk-bl` |
| `sig-edra-30m-series-a` | `source-techcrunch-bl` |
| `sig-meta-rogue-agent-breach` | `source-techcrunch-bl` |
| `sig-klarna-replaces-salesforce` | `source-techcrunch-bl` |
| `sig-karpathy-autoresearch-700` | `source-fortune-nl` |
| `sig-forbes-context-graphs` | `source-forbes-nl` |
| `sig-mythos-181-exploits` | `source-red-anthropic-bl` |
| `sig-alphaevolve-matrix-multiply` | `source-deepmind-bl` |
| `sig-tao-erdos-728` | `source-tao-mastodon-bl` |

---

## Element Metadata (websites, repos, licenses)

| slug | website | repository | license | release_year |
|------|---------|-----------|---------|-------------|
| `el-zylon` | https://zylon.ai | https://github.com/zylon-ai/private-gpt | proprietary | 2025 |
| `el-palantir-apollo` | https://palantir.com | — | proprietary | 2020 |
| `el-nanograph` | — | — | — | 2026 |

| `el-hermes-agent` | https://nousresearch.com | https://github.com/NousResearch/hermes-agent | Apache 2.0 | 2026 |
| `el-kimi-k25` | https://kimi.com | https://huggingface.co/moonshotai/Kimi-K2.5 | Modified MIT | 2026 |
| `el-mcp` | https://modelcontextprotocol.io | https://github.com/modelcontextprotocol | MIT | 2024 |
| `el-anthropic-managed-agents` | https://anthropic.com | — | proprietary | 2026 |
| `el-edra` | https://edra.ai | — | proprietary | 2026 |
| `el-hornet` | https://hornet.dev | — | open source (TBA) | 2026 |
| `el-playerzero-sim1` | https://playerzero.app | — | proprietary | 2024 |
| `el-zep-graphiti` | https://getzep.com | https://github.com/getzep/graphiti | Apache 2.0 | 2024 |
| `el-genkm` | — | — | — | 2026 |
| `el-claude-mythos-preview` | — | — | restricted (Glasswing only) | 2026 |
| `el-project-glasswing` | https://anthropic.com/glasswing | — | — | 2026 |
| `el-permissioned-inference` | — | — | — | — |
| `el-precedent-poisoning` | — | — | — | — |
| `el-autoresearch` | — | https://github.com/karpathy/autoresearch | MIT | 2026 |
| `el-alphaevolve` | https://deepmind.google | — | proprietary | 2025 |
| `el-karpathy-llm-wiki` | — | gist (github.com/karpathy) | — | 2026 |
| `el-erdos-ai-tools` | https://erdosproblems.com | https://github.com/teorth/erdosproblems | — | 2026 |
| `el-openclaw` | https://github.com/openclaw/openclaw | https://github.com/openclaw/openclaw | open source | 2025 |
| `el-claude-cowork` | https://anthropic.com | — | proprietary | 2026 |
| `el-sap-ai` | https://sap.com | — | proprietary | 2026 |
| `el-salesforce-crm` | https://salesforce.com | — | proprietary | 1999 |
| `el-meta-internal-agents` | — | — | internal | 2026 |
| `el-headless-saas` | — | — | — | 2026 |

---

## Additional Companies (for expert affiliations)

| slug | name | type | site |
|------|------|------|------|
| `co-box` | Box | bigtech | https://box.com |
| `co-modern-relay` | Modern Relay | developer | — |
| `co-ucla` | UCLA | research | https://ucla.edu |

---

## KnowHow → InformationArtifact edges (SourcedFromArtifact)

| knowhow | artifact |
|---------|----------|
| `how-to-deploy-onprem-ai` | `ia-zylon-deployment-options` |
| `how-to-autonomous-research-loop` | `ia-fortune-karpathy-loop` |
| `how-to-autonomous-research-loop` | `ia-deepmind-alphaevolve` |

---

## Descriptions

### Patterns

**`pat-sovereign-ai`** — Enterprises are moving AI workloads out of public cloud and onto infrastructure they own and control. The shift is driven by a regulatory trifecta — DORA (Jan 2025), EU Data Act (Sep 2025), and EU AI Act (Aug 2026) — that imposes legal penalties up to 7% of global turnover for non-compliance. Simultaneously, on-prem GPU breakeven has dropped below 4 months for sustained workloads, and AI agents can now configure firmware, networking, Kubernetes, and Terraform in hours, collapsing the setup cost that made self-hosting impractical. Open-source frontier models like Kimi K2.5 (matching proprietary benchmarks at 76% lower cost under Modified MIT) and turnkey platforms like Zylon (air-gapped, production-ready in under a week) have made sovereign AI deployable by teams without dedicated MLOps staff.

**`pat-saaspocalypse`** — The S&P 500 software and services index lost approximately $830 billion in market value over six trading days in February 2026, directly catalyzed by Anthropic's Claude Cowork plugin launches covering legal, finance, HR, cybersecurity, and legacy modernization. The event exposed a structural weakness: SaaS per-seat pricing assumes growing headcount, but AI agents that replace the work of multiple employees break that assumption entirely. SAP became the first major incumbent to formally pivot to AI consumption-based pricing (March 2026). Klarna replaced Salesforce's CRM with a homegrown AI system. Sequoia's "Services is the new software" thesis argues the next trillion-dollar companies will sell completed work against $6T in outsourced services budgets, not compete for $1T in software tool budgets. Harvey ($190M ARR, $11B valuation) and Sierra ($100M ARR in under two years on outcome-based pricing) are early proof points.

**`pat-context-graphs`** — A thesis originating from Foundation Capital (Dec 2025) that decision traces, ontology, and temporal reasoning create a new infrastructure layer above databases. State clocks (what's true now) are commoditized — every database does this. Event clocks (what happened, why, who approved, what exception was granted) are novel and largely unsolved. Edra ($30M Series A from Sequoia, founded by Palantir AIP and first FDE veterans) validates the "workflow-first ontology" approach — learning the graph bottom-up from operational data rather than prescribing it. Forbes brought the thesis mainstream in April 2026; Gartner predicts 50%+ of AI agent systems will rely on context graphs by 2028. The market is contested: the KG community calls it rebranding of temporal KGs plus process mining, @rahulgs calls it "ngmi," and Forrester frames it as "convergence not invention." Products are shipping: TrustGraph v2.2, Semantica v0.4.0, Azure MCP Server 2.0, Neo4j agent-memory library.

**`pat-new-cyber-threats`** — AI models capable of autonomously finding and exploiting software vulnerabilities have arrived. Anthropic's Claude Mythos Preview (April 7, 2026) went from near-0% exploit development success (Opus 4.6) to 181 working exploits on the same Firefox JS engine benchmark — an overnight capability jump that was not explicitly trained but emerged from general improvements in code, reasoning, and autonomy. The same model found and exploited a 17-year-old FreeBSD remote code execution vulnerability (CVE-2026-4747) granting full root to unauthenticated users, and wrote browser exploit chains combining JIT heap sprays with sandbox escapes. Simultaneously, enterprise agentic deployments are creating new attack surfaces: Meta experienced its first rogue agent breach in March 2026 (agent exposed data to unauthorized engineers); Cisco discovered a third-party OpenClaw skill silently exfiltrating data, prompting China to ban OpenClaw at banks and state enterprises. OWASP published the Agentic Top 10; NIST launched an AI Agent Standards Initiative; the FTC clarified Section 5 applies to autonomous agents.

**`pat-accelerated-research`** — AI agents are transforming research from a human-paced activity into an autonomous, iterative loop. Andrej Karpathy's autoresearch project (70.5k GitHub stars, March 2026) ran 700 LLM training experiments in two days on a single GPU — the agent modifies architecture, hyperparameters, and optimizer, trains for 5 minutes, evaluates, keeps or discards, and repeats at ~12 experiments per hour. Google DeepMind's AlphaEvolve used Gemini-powered evolutionary coding to find the first improvement to Strassen's 1969 matrix multiplication algorithm in 56 years, while also achieving a 23% speedup on Gemini's own training kernel. Terence Tao reported that AI "more or less autonomously" solved Erdos problem #728 in January 2026 — ChatGPT generated the proof, Aristotle auto-repaired gaps, and the result was Lean-verified. Tao's emerging best practice: "have statements reviewed by humans, proofs can be delegated to automated tools." Google Research shipped PaperVizAgent (publication-ready academic figures scoring above human baseline) and ScholarPeer (AI reviewer agent with adversarial baseline scouting).

### Signals

**`sig-93pct-repatriation`** — A Cloudian-commissioned enterprise survey found that 93% of organizations are either actively repatriating AI workloads from public cloud or evaluating a move. Sovereign cloud IaaS is projected at $80 billion in 2026 (35.6% YoY growth). The regulatory drivers are concrete: DORA (enforceable since January 2025) imposes operational suspension risk; the EU Data Act (September 2025) explicitly prohibits vendor lock-in; the EU AI Act (full enforcement August 2026) carries penalties up to 7% of global annual turnover.

**`sig-kimi-k25-oss-frontier`** — Moonshot AI released Kimi K2.5 in January 2026, a 1-trillion-parameter Mixture-of-Experts model activating only 32 billion parameters per token. It scores 96.1% on AIME 2025, 76.8% on SWE-Bench Verified, and 50.2% on HLE-Full with tools (beating Claude Opus 4.5 at 43.2% and GPT-5.2 at 45.5%). Benchmark evaluation cost $0.27 versus Claude's $1.14 — 76% cheaper. Its Agent Swarm mode coordinates up to 100 parallel sub-agents. Released under Modified MIT license, it proves frontier-class AI is deployable without API dependency.

**`sig-zylon-onprem-ai`** — Zylon is an on-premise AI platform for regulated industries built by the creators of PrivateGPT (57,000+ GitHub stars). It deploys as a complete stack — local LLMs, vector database, API gateway, workspace, and n8n automation — entirely within customer infrastructure, including fully air-gapped environments. Deployment options range from cloud VPC to managed on-prem (via certified partners NeuralRack, Panchaea, Occentus) to fully in-house, with a "Zylon in a Box" pre-configured server option. Compliant with SOC 2, HIPAA, GDPR, ISO 27001, and EU AI Act. Fixed-cost pricing, no per-token charges. Customers include Orsa Credit Union and ASOS.

**`sig-830b-software-selloff`** — The S&P 500 software and services index shed approximately $830 billion in market value across six trading days in early February 2026. The selloff was directly catalyzed by sequential Anthropic Claude Cowork updates: legal plugins (Varonis -25%, Thomson Reuters -19%, RELX -15%), Claude Code Security (CrowdStrike -15%, Okta -12%, Zscaler -11%), and Claude COBOL modernization (IBM -13%, Asana -9%, Snowflake -8%). Markets are no longer treating AI as a universal tailwind for software — they are punishing companies whose value proposition relies on workflow convenience rather than proprietary data.

**`sig-sap-consumption-pricing`** — SAP announced in March 2026 that it is shifting from traditional per-seat software subscriptions to AI consumption-based pricing, becoming the first major enterprise software incumbent to formally make this transition. The move signals that the pricing model shift from per-seat to usage-based is no longer theoretical — the largest enterprise software company by European market cap has committed to it.

**`sig-klarna-replaces-salesforce`** — Klarna, the Swedish fintech company, replaced Salesforce's flagship CRM with an internally built AI system, saving millions in annual licensing costs. The case study became the canonical example that enterprise-grade SaaS is dispensable for workflow-oriented applications, demonstrating that a sufficiently capable AI team can rebuild core business software at a fraction of incumbent pricing.

**`sig-edra-30m-series-a`** — Edra emerged from stealth in March 2026 with a $30 million Series A led by Sequoia Capital (with 8VC and A* participating), building on a $6.5M seed round. Co-founded by Eugen Alpeza (who led the launch of Palantir's AIP platform) and Yannis Karamanlakis (Palantir's first forward-deployed AI engineer), Edra turns operational data — emails, logs, support tickets, chat histories — into a continuously updated knowledge base that trains AI agents. Deployed at HubSpot, ASOS, and Cushman & Wakefield, integrating with ServiceNow and Jira.

**`sig-forbes-context-graphs`** — Forbes published "VCs say context graphs might be the next big thing in AI" on April 3, 2026, marking mainstream category formation. The article synthesized Foundation Capital's "trillion-dollar opportunity" thesis with Forrester's response framing context graphs as "a convergence, not an invention" — arguing that Enterprise Architecture has been building the entity foundation for decades, and that decision traces are the genuinely new contribution.

**`sig-gartner-50pct-context-graphs`** — Gartner predicted that over 50% of AI agent systems will rely on context graphs by 2028, as part of its Data Management, Semantic Layers, and GraphRAG top trends for 2026. This moves context graphs from a VC thesis to an analyst forecast — the kind of prediction enterprise procurement teams use to justify budget allocation.

**`sig-mythos-181-exploits`** — On April 7, 2026, Anthropic published a technical assessment of Claude Mythos Preview's cybersecurity capabilities. Where Opus 4.6 had a near-0% success rate at autonomous exploit development, Mythos Preview produced 181 working exploits out of several hundred attempts on Firefox 147 JavaScript engine vulnerabilities (all patched in Firefox 148). The model also autonomously discovered and exploited a 17-year-old remote code execution vulnerability in FreeBSD's NFS server (CVE-2026-4747), granting full root access to unauthenticated users. It wrote a web browser exploit chaining four vulnerabilities with a JIT heap spray escaping both renderer and OS sandboxes. These capabilities were not explicitly trained — they emerged as a downstream consequence of general improvements in code, reasoning, and autonomy.

**`sig-meta-rogue-agent-breach`** — In March 2026, Meta experienced an incident where an internal AI agent inadvertently exposed sensitive company and user data to engineers who lacked the appropriate permissions. Reported by TechCrunch, this was the first high-profile enterprise breach caused by an autonomous AI agent rather than a human error or external attacker, proving that the agentic attack surface is production reality, not theoretical risk.

**`sig-openclaw-unvetted-access`** — Cisco's security team tested a third-party OpenClaw skill and discovered it was performing data exfiltration without user awareness. Following this and broader security concerns, Chinese authorities restricted state-run enterprises and government agencies from running OpenClaw AI applications on office computers in March 2026, as reported by Bloomberg and Reuters. OpenClaw is an open-source AI agent tool for developer workflow automation that had gained rapid adoption but whose skill repository lacked rigorous vetting for malicious submissions.

**`sig-karpathy-autoresearch-700`** — On March 7, 2026, Andrej Karpathy pushed autoresearch — a 630-line Python script that let an AI agent run 50 LLM training experiments overnight on a single GPU without human input. Within two days, the autonomous agents ran 700 experiments total. The design uses three strict primitives: a single editable file (train.py), a scalar metric (validation bits per byte), and a fixed 5-minute time budget per experiment. The human programs a `program.md` Markdown file providing context and instructions; the agent handles everything else. The project reached 70.5k GitHub stars and was covered by Fortune as "The Karpathy Loop."

**`sig-alphaevolve-matrix-multiply`** — Google DeepMind announced AlphaEvolve in mid-2025 (arxiv June 16, 2025) — a Gemini-powered evolutionary coding agent that pairs LLM creativity with automated evaluators in an evolutionary framework. AlphaEvolve discovered an algorithm to multiply two 4×4 complex-valued matrices using 48 scalar multiplications, offering the first improvement in 56 years over Strassen's 1969 algorithm. In production at Google, it achieved a 23% speedup on a Gemini training kernel (translating to 1% total training time reduction), improved data center scheduling, and simplified chip design. Google announced its first automated materials science lab in the UK for 2026, integrating AlphaEvolve with robotics.

**`sig-tao-erdos-728`** — On January 7, 2026, Terence Tao posted on Mastodon that AI tools had "more or less autonomously" solved Erdos problem #728 — a 1975 question about prime factorization of binomial coefficients. ChatGPT generated the proof after some feedback from an initial attempt; the AI tool Aristotle then automatically repaired minor errors and produced a Lean-verified proof. Tao noted the result was "not replicated in existing literature," making it the first AI solution to an Erdos problem that was genuinely new. He later found the methods were similar to a 2014 paper by Pomerance, but the AI-generated solution was the first to explicitly address this specific problem formulation.

### Elements

**`el-zylon`** — Full-stack on-prem AI platform from the PrivateGPT creators (57k stars). Air-gapped, fixed-cost, production-ready in days. Three tiers: cloud VPC, managed on-prem (via certified partners), or "Zylon in a Box" pre-configured server.

**`el-palantir-apollo`** — Palantir's deployment orchestration for air-gapped, classified (JWICS, SIPRNet), and edge environments. Manages thousands of microservices across hundreds of environments that can't reach the public internet. FedRAMP High, IL5/IL6.

**`el-nanograph`** — Schema-first embedded graph in Rust. Single binary, no cloud dependency. SPIKE ontology as core schema. "SQLite for graphs."


**`el-hermes-agent`** — NousResearch OSS agent framework. 40+ tools. Runs 26B MoE at 20 tok/s on a $300 mini PC via llama.cpp + Vulkan. No API keys. Apache 2.0.

**`el-kimi-k25`** — 1T-param open-source MoE (32B active). Beats Claude + GPT-5.2 on agentic benchmarks (50.2% HLE-Full, 78.4% BrowseComp). Agent Swarm: 100 parallel sub-agents. 76% cheaper than Claude. Modified MIT.

**`el-mcp`** — Model Context Protocol. The consolidating standard for agent-tool communication. Azure MCP Server 2.0: 276 tools across 57 Azure services, self-hosted. 2026 roadmap: audit trails, SSO, gateway patterns.

**`el-anthropic-managed-agents`** — Hosted service for long-running agents (hours/days, not single-turn). Public beta Apr 2026.

**`el-headless-saas`** — Emerging category: traditional software rebuilt as agent-first APIs with no UI. Same product, different interface, new business model. Coined by @ivanburazin.

**`el-edra`** — Turns operational data (emails, logs, tickets) into auto-updating knowledge bases. $30M Series A (Sequoia). Ex-Palantir founders. Customers: HubSpot, ASOS, Cushman & Wakefield. The "workflow-first ontology" thesis productized.

**`el-hornet`** — Retrieval engine for agents, not humans. Built by Vespa veterans. Agents issue long structured queries in reasoning loops — Hornet trades latency for throughput and recall. Schema-first APIs. On-prem, OSS.

**`el-playerzero-sim1`** — Long-trace reasoning engine. 92.6% accuracy predicting production failures (vs 73.8% Codex/Claude). 64% of failures predictable pre-merge; 83% invisible to CI/CD. $20M funded (Foundation Capital).

**`el-zep-graphiti`** — Temporal knowledge graph engine (Apache 2.0). Bi-temporal tracking: when it happened + when recorded. 94.8-98.2% on Deep Memory Retrieval. 90% faster than MemGPT. MCP server included.

**`el-genkm`** — Methodology unifying 40+ Graph RAG systems under one formalism. 4-stage architecture (Document → Entity-Relation → Cluster → Ontology). 20+ operator algebra with provenance tracking. By Fanghua Yu.

**`el-claude-mythos-preview`** — 100% on Cybench. Autonomously writes zero-day exploits for Firefox, FreeBSD, VMs, phone lock screens. Capabilities emerged from general reasoning improvements, not cybersecurity training. Not generally available — Glasswing only.

**`el-project-glasswing`** — Anthropic's defender-first release of Mythos Preview. Partnered with Linux Foundation to secure critical OSS before similar capabilities become broadly available.

**`el-permissioned-inference`** — Must isolate *reasoning*, not just data retrieval. Client A's precedent can't shape reasoning for Client B. Connects to OWASP LLM08. No production solutions exist.

**`el-precedent-poisoning`** — Agents learn from bad decisions and reinforce them at scale. One flawed template propagates to 100+ clients via FDE productization loop. The moat mechanism is also the risk vector.

**`el-autoresearch`** — Karpathy's autonomous research loop. 70.5k stars. One editable file, one scalar metric, 5-min time budget. Human writes `program.md`; agent runs ~100 experiments overnight. MIT.

**`el-alphaevolve`** — DeepMind's Gemini-powered evolutionary coding agent. Beat Strassen's 1969 matrix multiplication (first improvement in 56 years). In production: 23% Gemini kernel speedup, data center scheduling, chip design. UK automated lab opening 2026.

**`el-karpathy-llm-wiki`** — Raw sources → LLM-compiled .md wiki → schema file. Ingest, query, lint. ~400K words without RAG or graph DBs. Obsidian as frontend. 2.4M views. "There is room here for an incredible new product."

**`el-erdos-ai-tools`** — Tao's framework where ChatGPT + Aristotle autonomously solve open Erdos problems with Lean-verified proofs. Emerging practice: humans review statements, proofs delegated to AI.

**`el-claude-cowork`** — Anthropic's enterprise AI plugins covering legal, finance, HR, cybersecurity, and COBOL modernization. Sequential launches in Feb 2026 directly catalyzed the $830B SaaS selloff.

**`el-sap-ai`** — SAP's AI consumption-based platform. First major enterprise incumbent to formally abandon per-seat pricing for AI usage-based model (Mar 2026, Bloomberg).

**`el-salesforce-crm`** — Incumbent CRM. Replaced by Klarna with a homegrown AI system — the canonical "SaaS is dispensable" case study.

**`el-meta-internal-agents`** — Meta's internal autonomous AI agents. Source of first major enterprise agentic breach — agent exposed sensitive data to unauthorized engineers (Mar 2026).

**`el-openclaw`** — 85k stars in one week. Shell access, email, calendar, browser, messaging, persistent memory. Snyk: prompt injection exfiltrates API keys via spoofed email. Palo Alto: persistent memory turns exploits into delayed-execution attacks. China banned at state enterprises.

### Insights

**`ins-agents-informed-walkers`** — When an AI agent investigates an issue, it doesn't search a flat index — it traverses a context graph, following typed relationships between entities. Graphs give the agent reasoning structures that vector databases cannot: who approved what, which policy version applied, what exception was granted. Adding decision traces (the explicit HOWs and WHYs — workflows, exceptions, reasoning chains) creates a compounding loop: agent solves a problem, walks the graph, writes a new trace, and the graph grows richer. New reasoning paths emerge that didn't exist before — the agent becomes smarter with each traversal. Critically, this graph doesn't require a standalone graph database. It can sit as a semantic layer on top of existing data infrastructure: SQL databases, NoSQL document stores, or even a well-structured collection of markdown files.

**`ins-functionality-portable`** — The "file over app" philosophy (Kepano/Obsidian) argued that files are portable but apps are not. The new information as of 2026: apps are suddenly portable too. Claude Code enables rapid cloning of moderately complex cloud applications into local equivalents. This isn't data portability — it's functionality portability. Any SaaS application of moderate complexity without strong global network effects is now vulnerable to being cloned locally. The moat was never the feature set — it was the assumption that rebuilding was prohibitively expensive. That assumption has collapsed.

**`ins-agents-thrive-messy-systems`** — The conventional Silicon Valley narrative argues that developers must build clean APIs, IDLs, or MCP interfaces so AI agents can use their software. Aaron Levie (CEO, Box) argues this is fundamentally wrong: agents are exceptionally good at navigating complex, poorly designed systems natively. They choose tools based on semantic value (does this tool actually solve my problem?), backend cost (how expensive is this call?), and durability (will this interface still work tomorrow?) — rather than requiring elegant developer experience. The implication inverts the "build for agents" narrative: legacy systems aren't a blocker to agentic adoption, they're an opportunity. The enterprises with the messiest, most complex systems may benefit most.

### KnowHows

**`how-to-deploy-onprem-ai`** — A three-tier deployment pattern derived from Zylon's production architecture for regulated industries. Tier 1 (Cloud VPC): deploy into a logically isolated network within your AWS/GCP/Azure account — connect enterprise identity and internal data sources, keep endpoints private. Best for teams needing cloud elasticity with data residency and network isolation. Tier 2 (Managed On-Prem): a certified partner scopes requirements (users, workloads, latency, data classification), provisions compliant infrastructure including GPU, and installs, validates, monitors, and updates the platform under agreed controls. Partners include NeuralRack (US), Panchaea (UK), and Occentus (Spain). Best for organizations without an internal MLOps team. Tier 3 (Fully In-House / Air-Gapped): install on your own servers using online, semi-airgap, or full-airgap patterns; configure hardware/AI presets; integrate with internal identity, logging, and data systems; operate with your own patching and monitoring. Or use "Zylon in a Box" — a pre-configured server that arrives ready to run. All tiers include audit logs, RBAC, encryption at rest and in transit, and air-gap capable architecture.

**`how-to-autonomous-research-loop`** — Two complementary loops for accelerating research with AI agents. Loop 1 (autoresearch / Karpathy pattern): constrain the agent to one editable file, one scalar evaluation metric, and a fixed time budget per experiment (5 minutes). The human writes a `program.md` file containing research organization instructions; the agent iterates autonomously, modifying architecture, hyperparameters, and optimizer — keeping improvements and discarding regressions. Yields approximately 12 experiments per hour or 100 overnight on a single GPU. Loop 2 (AI co-scientist / Google pattern): state a research goal in natural language. The system deploys a coalition of specialized agents — Generation (proposes hypotheses), Reflection (self-critique), Ranking (tournament comparison), Evolution (quality improvement), Proximity (literature grounding), and Meta-review (synthesis) — that use self-play scientific debate and automated feedback to iteratively generate, evaluate, and refine hypotheses. Output: novel hypotheses, detailed research overview, and experimental protocols. Scientist provides feedback in natural language; the system iterates with increasing quality as it spends more compute.

---

## Remaining gaps

| What | Status | Action |
|------|--------|--------|
| `createdAt` / `updatedAt` timestamps | Not set | Set to `stagingTimestamp` on first load |
| `Chunk` nodes + embeddings | Not created | Populate on ingest pipeline |
| `Gartner` signal missing `InformationArtifact` | No direct Gartner URL | Cited via Forbes + Atlan secondary sources |
| `CompanyType` enum | Missing `startup` | Edra, Hornet, PlayerZero, Zylon should be `startup` not `developer` |

### Final counts

| Node type | Count | Complete? |
|-----------|-------|-----------|
| Pattern | 5 | Yes (brief + description) |
| Signal | 15 | Yes (brief + description + domain) |
| Element | 26 | Yes (brief + description + metadata) |
| Insight | 3 | Yes (brief + description) |
| KnowHow | 2 | Yes (brief + description + guidelines) |
| Company | 17 | Brief only |
| Expert | 7 | Affiliations complete |
| SourceEntity | 16 | Yes |
| InformationArtifact | 20 | Yes |
| **Total nodes** | **111** | |
| Edges | ~150 | FormsPattern, OnElement, ExemplifiesPattern, EnablesPattern, EnablesElement/UsesElement, HighlightsPattern, ReferencesElement, SpottedInArtifact, SourcedFromSource, PublishedBySource, ContributedByExpert, DevelopedByCompany, AffiliatedWithCompany, RelevantCompany, SourcedFromArtifact |
