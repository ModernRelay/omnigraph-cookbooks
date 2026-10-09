#!/bin/sh
# Prepare a reviewable deployment bundle. Never changes cluster storage.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: OMNIGRAPH_CLUSTER_URI=s3://bucket/prefix $0 COOKBOOK NEW_DIRECTORY" >&2
  exit 1
fi
: "${OMNIGRAPH_CLUSTER_URI:?set the S3 cluster root}"
case "$OMNIGRAPH_CLUSTER_URI" in
  *[[:cntrl:]]*) echo "cluster root must be a single URI" >&2; exit 1 ;;
  s3://?*/*) ;;
  *) echo "cluster root must be s3://bucket/prefix" >&2; exit 1 ;;
esac
case "$1" in
  industry-intel|pharma-intel|second-brain|vc-os|dev-graph|beads) ;;
  *) echo "unknown cookbook: $1" >&2; exit 1 ;;
esac

repo=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)
source_dir="$repo/$1"
output=$2
if [ -e "$output" ] || [ -L "$output" ]; then
  echo "output already exists; choose a new directory: $output" >&2
  exit 1
fi
# Bundled cookbooks omit storage. Refuse a conflicting source declaration
# rather than quietly replacing a customized deployment's root.
if grep -q '^storage:' "$source_dir/cluster.yaml"; then
  echo "cookbook already declares storage; edit and validate its bundle directly" >&2
  exit 1
fi

umask 077
mkdir -- "$output"
# Copy deployment inputs only: no seed, credentials, graphs or ledger.
cp "$source_dir/cluster.yaml" "$source_dir/schema.pg" "$output/"
cp -R "$source_dir/queries" "$source_dir/policies" "$output/"
storage=$(printf '%s' "$OMNIGRAPH_CLUSTER_URI" | sed "s/'/''/g")
printf "\nstorage: '%s'\n" "$storage" >> "$output/cluster.yaml"
omnigraph cluster validate --config "$output"
printf 'Prepared %s. Review with cluster plan before applying.\n' "$output"
