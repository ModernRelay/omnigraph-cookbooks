#!/bin/bash
# Vendor the engine's `omnigraph` skill at the release the cookbooks pin (deploy/railway/Dockerfile
# OMNIGRAPH_REF), so Claude Code (.claude/skills/) and Codex (.agents/skills/, a symlink to the same
# directory) load it with no install step, and so the skill never runs ahead of the engine it
# describes. Re-run after bumping the pin; `.source` records what was vendored.
#   scripts/sync-skill.sh            # the pinned ref
#   scripts/sync-skill.sh v0.11.0    # an explicit ref
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
REF=${1:-$(sed -n 's/^ARG OMNIGRAPH_REF=\(.*\)$/\1/p' "$ROOT/deploy/railway/Dockerfile" | head -1)}
[ -n "$REF" ] || { echo "no OMNIGRAPH_REF in deploy/railway/Dockerfile" >&2; exit 1; }
DEST="$ROOT/.claude/skills/omnigraph"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://api.github.com/repos/ModernRelay/omnigraph/tarball/$REF" -o "$TMP/src.tgz"
mkdir -p "$TMP/x" && tar -xzf "$TMP/src.tgz" -C "$TMP/x"
SRC=$(find "$TMP/x" -type d -path '*/skills/omnigraph' | head -1)
[ -n "$SRC" ] || { echo "skills/omnigraph is not in ModernRelay/omnigraph at $REF" >&2; exit 1; }
rm -rf "$DEST" && mkdir -p "$DEST" && cp -R "$SRC/." "$DEST/"
# manifest hash: sha256 over "<sha256 of file>  <path>" lines, paths sorted bytewise — the harness
# `skill:pin` check recomputes it the same way
if command -v sha256sum >/dev/null; then H=sha256sum; else H="shasum -a 256"; fi
TREE=$(cd "$DEST" && find . -type f ! -name .source | LC_ALL=C sort | while read -r f; do $H "$f"; done | $H | cut -d' ' -f1)
printf 'ref=%s\ntree=%s\n' "$REF" "$TREE" > "$DEST/.source"
echo "vendored skills/omnigraph@$REF into ${DEST#$ROOT/}: $(find "$DEST" -type f ! -name .source | wc -l | tr -d ' ') files, tree $TREE"
