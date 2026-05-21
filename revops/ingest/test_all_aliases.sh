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

pass=0
fail=0
declare -a failures

# alias_name arg1 arg2 ... → run, count rows, record pass/fail
run() {
    local name="$1"; shift
    local out
    out=$(omnigraph read --alias "$name" "$@" 2>&1)
    if grep -q "^Error:" <<<"$out" || grep -q "not found" <<<"$out" ; then
        echo "FAIL $name $* :: $(head -2 <<<"$out" | tail -1 | tr -d '[:cntrl:]' | sed 's/\[[0-9;]*m//g' | cut -c1-100)"
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

# ─── decisions.gq ────────────────────────────────────────────────────────
echo "── decisions ──"
run decision                 dec-classify-cognition-2026-04
run decisions                "$SINCE_RECENT"
run decision-trace           dec-classify-cognition-2026-04
run decisions-by-intent      classify_workload
run account-decisions        acc-cognition
run opportunity-decisions    opp-github-2026
run agent-decisions          act-agent-classifier
run low-confidence           0.7

# ─── measurements.gq ─────────────────────────────────────────────────────
echo "── measurements ──"
run account-metrics          acc-cognition
run metric-stream            acc-anthropic estimated_annual_spend_usd
run latest-metric            acc-anthropic estimated_annual_spend_usd
run total-metric             estimated_annual_spend_usd prospect
run predicted-vs-actual      "$SINCE_RECENT"
run top-accounts-by-metric   funding_raised_usd
run measurements-from-decision  dec-classify-cognition-2026-04

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

# ─── opportunities.gq ────────────────────────────────────────────────────
echo "── opportunities ──"
run opportunity              opp-github-2026
run pipeline
run pipeline-by-stage        qualified
run pipeline-by-deal-type
run committee                opp-github-2026
run buyers                   opp-github-2026
run influencers              opp-github-2026
run blockers                 opp-github-2026
run loss-reasons

# ─── cohorts.gq ──────────────────────────────────────────────────────────
echo "── cohorts ──"
run cohort                   coh-q2-targets
run cohorts
run cohort-accounts          coh-q2-targets
run account-cohorts          acc-cognition
run cohort-stats             coh-q2-targets
run cohort-top-targets       coh-q2-targets

# ─── engagements.gq ──────────────────────────────────────────────────────
echo "── engagements ──"
run engagements              "$SINCE_RECENT"
run person-engagements       per-maya-chen
run actions                  "$SINCE_RECENT"
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
