#!/usr/bin/env bash

# Focused Stage-0 artifact-contract test. It consumes two independently
# produced archives and therefore performs no compiler build or upstream
# acquisition itself.

set -euo pipefail
export LC_ALL=C

usage() {
    echo "usage: $0 --archive FILE --checksum FILE --reproduction-archive FILE --reproduction-checksum FILE" >&2
    exit 2
}

archive=""
checksum=""
reproduction_archive=""
reproduction_checksum=""
while (($#)); do
    case "$1" in
        --archive) archive="${2:-}"; shift 2 ;;
        --checksum) checksum="${2:-}"; shift 2 ;;
        --reproduction-archive) reproduction_archive="${2:-}"; shift 2 ;;
        --reproduction-checksum) reproduction_checksum="${2:-}"; shift 2 ;;
        *) usage ;;
    esac
done
[[ -n "$archive" && -n "$checksum" \
    && -n "$reproduction_archive" && -n "$reproduction_checksum" ]] || usage

root="$(cd "$(dirname "$0")/../.." && pwd)"
inputs="$root/.ai/config/development/ryeos/stage0-platform-x86_64-linux.yaml"
producer="$root/scripts/release/produce-development-toolchain-stage0.sh"
verifier="$root/scripts/release/verify-development-toolchain-stage0.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Discovery is not acquisition authority. Neither endpoint may accept a live
# catalog field, even alongside an otherwise complete pinned input contract.
sed '$a zig_index_url: "https://ziglang.org/download/index.json"' \
    "$inputs" > "$tmp/mutable-input.yaml"
if "$producer" --inputs "$tmp/mutable-input.yaml" \
    --cache "$tmp/cache" --output "$tmp/output.tar.gz" \
    > "$tmp/producer-refusal" 2>&1; then
    echo "Stage-0 producer accepted a mutable catalog dependency" >&2
    exit 1
fi
grep -Fq 'unknown field: zig_index_url' "$tmp/producer-refusal"
if "$verifier" --inputs "$tmp/mutable-input.yaml" \
    --producer "$producer" --archive "$archive" \
    > "$tmp/verifier-refusal" 2>&1; then
    echo "Stage-0 verifier accepted a mutable catalog dependency" >&2
    exit 1
fi
grep -Fq 'unknown field: zig_index_url' "$tmp/verifier-refusal"

cmp "$archive" "$reproduction_archive" || {
    echo "independent Stage-0 productions emitted different archive bytes" >&2
    exit 1
}
cmp "$checksum" "$reproduction_checksum" || {
    echo "independent Stage-0 productions emitted different checksum bytes" >&2
    exit 1
}

"$verifier" \
    --inputs "$inputs" \
    --producer "$producer" \
    --archive "$archive" \
    --checksum "$checksum" \
    --materialize "$tmp/toolchain"
[[ -x "$tmp/toolchain/rust/bin/cargo" && -x "$tmp/toolchain/zig/zig" ]]

"$verifier" \
    --inputs "$inputs" \
    --producer "$producer" \
    --archive "$reproduction_archive" \
    --checksum "$reproduction_checksum"

if "$verifier" \
    --inputs "$inputs" \
    --producer "$producer" \
    --archive "$archive" \
    --checksum "$checksum" \
    --materialize "$tmp/toolchain" >/dev/null 2>&1; then
    echo "Stage-0 verifier replaced an existing materialization" >&2
    exit 1
fi

mkdir "$tmp/bad"
checksum_name="$(basename "$checksum")"
cp "$checksum" "$tmp/bad/$checksum_name"
sed -i -E 's/^[0-9a-f]{64}/0000000000000000000000000000000000000000000000000000000000000000/' "$tmp/bad/$checksum_name"
if "$verifier" \
    --inputs "$inputs" \
    --producer "$producer" \
    --archive "$archive" \
    --checksum "$tmp/bad/$checksum_name" >/dev/null 2>&1; then
    echo "Stage-0 verifier accepted a contradictory checksum" >&2
    exit 1
fi

echo "Stage-0 development toolchain contract test passed"
