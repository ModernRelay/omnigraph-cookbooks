#!/usr/bin/env bash
# Smoke-test every read alias in omnigraph.yaml against the loaded graph.
# Skips mutation aliases (would modify state).
#
# Each row prints:
#   PASS|FAIL <alias> <rows>
#
# Exit non-zero if any alias errors out.

set -u

cd "$(dirname "$0")/.."

python ingest/check_alias_coverage.py || exit 1

pass=0
fail=0
declare -a failures
read_opts=()
if [ -n "${OMNIGRAPH_TEST_URI:-}" ]; then
    read_opts+=(--uri "$OMNIGRAPH_TEST_URI")
fi

# alias_name arg1 arg2 ... → run, count rows, record pass/fail.
# Fails if `omnigraph read` exits non-zero OR emits a recognised error string.
run() {
    local name="$1"; shift
    local out rc
    out=$(omnigraph read "${read_opts[@]}" --alias "$name" "$@" 2>&1)
    rc=$?
    if [ $rc -ne 0 ] || grep -q "^Error:" <<<"$out" || grep -q "not found" <<<"$out" ; then
        local detail
        detail=$(head -2 <<<"$out" | tail -1 | tr -d '[:cntrl:]' | sed 's/\[[0-9;]*m//g' | cut -c1-100)
        echo "FAIL $name $* :: rc=$rc :: $detail"
        fail=$((fail+1))
        failures+=("$name $*")
    else
        local rows
        rows=$(head -1 <<<"$out" | grep -oE '^[0-9]+ rows' | grep -oE '^[0-9]+' || echo "?")
        echo "PASS $name $* :: $rows rows"
        pass=$((pass+1))
    fi
}

SINCE_RECENT="2026-01-01T00:00:00Z"
SINCE_OLD="2025-01-01T00:00:00Z"

# ─── accounts.gq ─────────────────────────────────────────────────────────
echo "── accounts ──"
run account                  acc-cognition
run accounts                 prospect
run accounts-by-segment      mid_market
run account-search           Cursor
run account-people           acc-anthropic
run account-role-history     acc-anthropic
run account-parents          acc-github
run account-subsidiaries     acc-microsoft
run account-tech             acc-cursor
run accounts-using-tech      tech-modal
run account-signals          acc-cognition
run account-opportunities    acc-anthropic
run account-policy-matches   acc-cognition

# ─── people.gq ───────────────────────────────────────────────────────────
echo "── people ──"
run person                   per-maya-chen
run person-search            Maya
run person-history           per-maya-chen
run person-current-role      per-maya-chen
run champion-tracking
run people-by-segment-function  enterprise engineering
run recent-job-changes       "$SINCE_RECENT"
run lead-resolution          lead-cognition-form
run person-leads             per-maya-chen

# ─── signals.gq ──────────────────────────────────────────────────────────
echo "── signals ──"
run signal                   sig-cognition-series-d
run signals                  "$SINCE_RECENT"
run signals-by-kind          funding
run strong-signals           "$SINCE_RECENT"
run funding-feed             "$SINCE_OLD"
run account-heat             "$SINCE_RECENT"
run signal-evidence          sig-cognition-series-d
run signal-account           sig-cognition-series-d
run signal-person            sig-maya-job-change
run search-signals           funding

# ─── prioritization.gq ───────────────────────────────────────────────────
echo "── prioritization ──"
run daily-priority-accounts  "$SINCE_RECENT" pol-icp-v2
run account-priority-detail  acc-cognition "$SINCE_RECENT"
run champion-job-change-queue "$SINCE_RECENT" pol-icp-v2
run champion-context         per-maya-chen
run customer-champion-departures "$SINCE_RECENT"

# ─── decisions.gq ────────────────────────────────────────────────────────
echo "── decisions ──"
run decision                 dec-classify-cognition-2026-04
run decisions                "$SINCE_RECENT"
run decision-trace           dec-classify-cognition-2026-04
run decision-lineage         dec-classify-cognition-2026-04
run decision-replaced-by     dec-classify-cognition-2026-02
run decisions-by-intent      classify_workload
run account-decisions        acc-cognition
run opportunity-decisions    opp-github-2026
run agent-decisions          act-agent-classifier
run decision-actions         dec-classify-cognition-2026-04
run low-confidence           0.7
run superseded-decisions
run decision-precedents      dec-classify-cognition-2026-04

# ─── measurements.gq ─────────────────────────────────────────────────────
echo "── measurements ──"
run measurement              meas-cognition-intent-score-2026-04
run account-metrics          acc-cognition
run metric-stream            acc-anthropic estimated_annual_spend_usd
run latest-metric            acc-anthropic estimated_annual_spend_usd
run total-metric             estimated_annual_spend_usd prospect
run predicted-vs-actual      "$SINCE_RECENT"
run top-accounts-by-metric   funding_raised_usd
run measurements-from-decision  dec-classify-cognition-2026-04
run measurements-from-source src-parallel-task

# ─── governance.gq ───────────────────────────────────────────────────────
echo "── governance ──"
run policy                   pol-icp-v2
run active-policies          icp
run policy-history           icp.ai_native_mid_market
run policy-supersedes        pol-icp-v2
run policy-decisions         pol-icp-v2
run policy-accounts          pol-icp-v2
run decisions-by-domain
run decisions-by-actor-type
run policy-decision-count    pol-icp-v2
run prompt-governance        pol-signal-score-v1
run enrichment-audit         "$SINCE_RECENT"

# ─── opportunities.gq ────────────────────────────────────────────────────
echo "── opportunities ──"
run opportunity              opp-github-2026
run opportunity-account      opp-github-2026
run pipeline
run pipeline-by-stage        qualified
run pipeline-by-deal-type
run committee                opp-github-2026
run buyers                   opp-github-2026
run influencers              opp-github-2026
run blockers                 opp-github-2026
run loss-reasons
run opportunity-origin-lead  opp-cognition-2026

# ─── cohorts.gq ──────────────────────────────────────────────────────────
echo "── cohorts ──"
run cohort                   coh-q2-targets
run cohorts
run cohorts-by-kind          target
run cohort-accounts          coh-q2-targets
run account-cohorts          acc-cognition
run cohort-stats             coh-q2-targets
run cohort-top-targets       coh-q2-targets

# ─── engagements.gq ──────────────────────────────────────────────────────
echo "── engagements ──"
run engagements              "$SINCE_RECENT"
run person-engagements       per-maya-chen
run engagements-with-artifact ia-linkedin-maya-chen
run actions                  "$SINCE_RECENT"
run actions-to-person        per-maya-chen
run account-actions          acc-cognition
run failed-actions           "$SINCE_OLD"

# ─── exports.gq ──────────────────────────────────────────────────────────
echo "── exports ──"
run export-accounts
run export-people
run export-funding-trigger   "$SINCE_OLD"
run export-pipeline
run export-cohort            coh-q2-targets
run export-decisions         "$SINCE_RECENT"
run export-priority-accounts "$SINCE_RECENT" pol-icp-v2
run export-champion-job-changes "$SINCE_RECENT" pol-icp-v2

# ─── search.gq ───────────────────────────────────────────────────────────
echo "── search ──"
run search-chunks            funding                       # 0 rows OK — chunks not loaded by default
run artifact-chunks          ia-bloomberg-cognition        # 0 rows OK — same reason
run account-mentions         acc-anthropic
run person-mentions          per-maya-chen
# nearest-chunks omitted — requires a Vector(3072) literal as $q

echo
echo "── summary ──"
echo "PASS: $pass"
echo "FAIL: $fail"
if [ "$fail" -gt 0 ]; then
    echo
    echo "Failures:"
    for f in "${failures[@]}"; do echo "  - $f"; done
fi

exit $fail
