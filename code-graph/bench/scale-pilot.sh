#!/bin/sh
# The scale pilot end to end (scale-design.md): both VS Code releases, the
# graph and reference, the 24 questions, four arms, and one session of each
# family's first question in each arm. Run from anywhere; outputs go under
# work/scale/ and results/agent-scale.json.
#
#   OMNIGRAPH_BIN=/path/to/0.14.0/omnigraph NODE_BIN=/path/to/node/bin sh code-graph/bench/scale-pilot.sh
set -eu
cd "$(dirname "$0")"
ARMS=${ARMS:-bare,omnigraph,codegraph,graphify}
PILOT=shared-name-1,dispatch-1,transitive-1,construction-1,release-1,control-1
# The tools the hono benchmarks installed by hand, at the versions they ran.
if [ ! -x work/tools/codegraph/node_modules/.bin/codegraph ]; then
    mkdir -p work/tools/codegraph
    npm install --prefix work/tools/codegraph --no-audit --no-fund @colbymchenry/codegraph@1.6.2
fi
python3 scale.py fetch
python3 scale.py build
python3 scale.py questions
python3 agent.py --suite vscode setup --arms "$ARMS"
python3 agent.py --suite vscode run --arms "$ARMS" --questions "$PILOT" --reps 1 --jobs 4
python3 agent.py --suite vscode score
