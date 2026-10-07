#!/bin/bash
# Refresh the vendored skill from its immutable documentation revision.
# Edit omnigraph-skill.ref when adopting reviewed upstream documentation;
# the runtime release remains pinned separately in deploy/railway/Dockerfile.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
REF=$(cat "$ROOT/scripts/omnigraph-skill.ref")
[[ "$REF" =~ ^[0-9a-f]{40}$ ]] || { echo "omnigraph-skill.ref must contain a full commit SHA" >&2; exit 1; }
DEST="$ROOT/.claude/skills/omnigraph"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://api.github.com/repos/ModernRelay/omnigraph/tarball/$REF" -o "$TMP/src.tgz"
mkdir -p "$TMP/x" && tar -xzf "$TMP/src.tgz" -C "$TMP/x"
SRC=$(find "$TMP/x" -type d -path '*/skills/omnigraph' | head -1)
[ -n "$SRC" ] || { echo "skills/omnigraph is not in ModernRelay/omnigraph at $REF" >&2; exit 1; }
rm -rf "$DEST" && mkdir -p "$DEST" && cp -R "$SRC/." "$DEST/"
# Manifest hash: SHA-256 over sorted "<file SHA-256>  <relative path>" lines.
if command -v sha256sum >/dev/null; then H=sha256sum; else H="shasum -a 256"; fi
TREE=$(cd "$DEST" && find . -type f ! -name .source | LC_ALL=C sort | while read -r f; do $H "$f"; done | $H | cut -d' ' -f1)
printf 'ref=%s\ntree=%s\n' "$REF" "$TREE" > "$DEST/.source"
echo "vendored skills/omnigraph@$REF into ${DEST#"$ROOT"/}: $(find "$DEST" -type f ! -name .source | wc -l | tr -d ' ') files, tree $TREE"
