# Seed: Petrel

`seed.jsonl` describes **Petrel**, a fictional 150 kg-class Earth-observation
smallsat program partway through its engineering-model iteration. Every person,
number and test result is made up. The seed is shaped so that each stored read
has something to find; the expected results below are what the stored queries
return on a freshly loaded graph.

153 nodes and 296 edges. Load it once into an empty graph with
`--mode append`.

## The program

| Kind | Count | Notes |
|---|---|---|
| Engineers | 8 | Seven people and one agent, `agent-checker` |
| Blocks | 28 | The spacecraft, 8 subsystems, 17 components, plus the launch vehicle and the ground stations as external blocks |
| Requirements | 23 | 4 mission goals, 9 system requirements, 10 design criteria |
| Interfaces | 6 | Each joins exactly two blocks |
| Parameters | 34 | Mass and power on every component, plus single values such as the first mode and the bus voltage |
| Test cases / runs | 13 / 13 | 10 passing, 1 failing, 2 not run; one aborted run |
| Iterations | 3 | V0 breadboard (done), V1 engineering model (active), V2 flight model (planned) |
| Reviews | 3 | PDR passed (closed V0), CDR planned (closes V1), test readiness review planned (closes V2) |
| Risks, decisions, findings | 6, 3, 5 | |
| Standards | 2 | Referenced by public identifier; clauses are described, not numbered |
| Variants | 2 | Demonstrator (no propulsion) and production |

Requirements flow down from the mission goals: imaging at 1.5 m, a five-year
life, delivery within three hours, and a twelve-month demonstrator life.
Launch-provider and regulatory requirements arrive from outside and have no
parent. Design criteria carry checkable limits (quantity, comparator, limit,
unit) except where the limit is two-sided or a protocol.

## Expected results

### Budgets

`budget_rollup` adds up every parameter of the requirement's quantity on the
blocks beneath the one it is allocated to:

| Requirement | Limit | Allocated | Contributors | |
|---|---|---|---|---|
| `dc-eps-generation` | min 180 W | 186 W | 1 | closes |
| `dc-pl-mass` | max 28 kg | **30.8 kg** | 2 | **over by 2.8 kg** |
| `dc-str-mass` | max 40 kg | 38.2 kg | 2 | closes |
| `req-lv-mass` | max 150 kg | 142.6 kg | 17 | closes with 7.4 kg margin |
| `req-sys-power` | max 160 W | 157 W | 8 | closes with 3 W margin |

The launch mass closes although the payload sub-budget does not: the margin
sits at system level. `budget_contributors` for `dc-pl-mass` returns the
optics (24.5 kg, estimated, resting on the low-confidence `asm-optics-mass`)
and the imager electronics (6.3 kg).

`limit_check` returns seven single-value limits beside the design value each
bounds. One fails: `req-obc-temp`, a maximum of 70 degC, against a measured
73.4 degC.

### Verification

| Query | Rows |
|---|---|
| `failing_requirements` | `req-obc-temp`: thermal vacuum measured 73.4 degC against 70 degC |
| `stale_verification` | `tc-mass-props` passed on 2026-08-20; `req-lv-mass` changed on 2026-09-29, when the launch allowance dropped from 155 to 150 kg |
| `measurement_mismatch` | `tc-pointing-sim` verifies `req-pointing` (pointing error) but measures `p-jitter` |
| `unverified_requirements` | 7: `dc-adapter`, `dc-adcs-jitter`, `dc-eps-generation`, `dc-pl-mass`, `req-passivation`, `req-prop-deltav`, `req-protoflight` |
| `test_status_summary` | fail 1, not_run 2, pass 10 |
| `test_history` (`tc-xband`) | the passing run on 2026-09-05, then the aborted run on 2026-09-03 |

### Review readiness

For the planned critical design review, `ms-cdr`:

| Query | Rows |
|---|---|
| `gate_unverified` | `dc-pl-mass` |
| `gate_not_passing` | `dc-batt-temp` (battery thermal balance not run), `dc-bus-voltage` (EMC not run), `req-obc-temp` (thermal vacuum failed) |
| `gate_unfrozen_interfaces` | `if-battery-thermal` and `if-obc-payload` (tentative), `if-xband-ground` (stable) |
| `gate_stale_verification` | `req-lv-mass` / `tc-mass-props` |

The same four queries return nothing for `ms-pdr`: the review that has already
passed had a clean scope.

### Change impact

| Query | Rows |
|---|---|
| `impacted_requirements` (`req-lv-mass`) | `dc-pl-mass` (Lena Vogel), `dc-str-mass` (Jonas Berg) |
| `impacted_tests` (`req-lv-mass`) | `tc-str-weigh`, through `dc-str-mass` |
| `impacted_requirements` (`mg-imaging`) | 6, through `req-sys-power` and `req-pointing` |
| `impacted_interfaces` (`req-sys-power`) | `if-eps-obc`, through `dc-bus-voltage` |
| `trace_up` (`dc-adcs-jitter`) | `req-pointing`, `mg-imaging` |
| `why_exists` (`blk-battery`) | `dc-batt-dod` and `dc-batt-temp`, both serving `mg-life` |

### Hygiene, risks and review

| Query | Rows |
|---|---|
| `unowned_requirements` | `req-passivation` |
| `untraced_requirements` | `req-protoflight` (internal, no parent) |
| `unexplained_components` | `blk-sband-ttc`: no requirement asks for the command radio |
| `untested_interfaces` | `if-battery-thermal`, `if-lv-adapter` |
| `awaiting_review` | `dc-adcs-jitter`, drafted by an agent with vague wording |
| `open_findings` | 4, oldest first: thermal vacuum failure, vague jitter wording, stale mass properties, thin power margin |
| `open_risks` | battery thermal runaway (5×2), processor board overheating (4×4), optics mass growth (3×4) |
| `unmitigated_risks` | `risk-xband-license`, accepted with no mitigating requirement |
| `assumptions_under_frozen_work` | `asm-launch-env` (medium confidence) under the frozen `req-lv-frequency` |
| `assumptions_due` with `today` 2026-10-12 | `asm-launch-env`, due 2026-09-30 |
| `compliance_matrix` (`std-iso-24113`) | three clause stances: two comply, one not applicable with its justification |
| `variant_requirements` (`var-prod`) | `mg-life`, `req-debris`, `req-prop-deltav` |
| `decisions_affecting` (`req-obc-temp`) | `dec-obc-heatsink`, proposed |
| `search_requirements` (`mass`) | `req-lv-mass`, `dc-pl-mass`, `dc-str-mass` |

`similar_requirements` needs embeddings; the seed carries none.
