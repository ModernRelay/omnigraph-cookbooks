#!/bin/sh
# The agent benchmark at scale end to end (scale-design.md): both VS Code
# releases, the graph and reference, the 24 questions, four arms, and their
# sessions. Run from anywhere; outputs go under work/scale/ and
# results/agent-scale.json.
#
#   OMNIGRAPH_BIN=/path/to/0.14.0/omnigraph NODE_BIN=/path/to/node/bin sh code-graph/bench/scale-run.sh pilot
#   ... sh code-graph/bench/scale-run.sh full
#
# pilot: one session of each family's first question in each arm (24).
# full: five sessions of every question in each arm (480).
# Every step skips what it has already done, so running the same command again
# resumes. A run that stops on a Claude usage limit exits 4: run it again once
# an account has usage.
set -eu
MODE=${1:-pilot}
cd "$(dirname "$0")"
ARMS=${ARMS:-bare,omnigraph,codegraph,graphify}
case "$MODE" in
    pilot) SELECT="--questions shared-name-1,dispatch-1,transitive-1,construction-1,release-1,control-1 --reps 1" ;;
    full) SELECT="--reps 5" ;;
    *) echo "usage: scale-run.sh pilot|full" >&2; exit 2 ;;
esac
# The tools the hono benchmarks installed by hand, at the versions they ran.
if [ ! -x work/tools/codegraph/node_modules/.bin/codegraph ]; then
    mkdir -p work/tools/codegraph
    npm install --prefix work/tools/codegraph --no-audit --no-fund @colbymchenry/codegraph@1.6.2
fi
python3 scale.py fetch
python3 scale.py build
python3 scale.py questions
python3 agent.py --suite vscode setup --arms "$ARMS"
# shellcheck disable=SC2086  # SELECT is several arguments
python3 agent.py --suite vscode run --arms "$ARMS" $SELECT --jobs 4
python3 agent.py --suite vscode score
