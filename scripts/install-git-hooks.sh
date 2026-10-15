#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
for hook in pre-commit pre-push; do
    if [ ! -x "$repo_root/.githooks/$hook" ]; then
        printf 'Missing or non-executable hook: %s/.githooks/%s\n' "$repo_root" "$hook" >&2
        exit 1
    fi
done
git -C "$repo_root" config --local core.hooksPath .githooks
printf 'Git hooks enabled: %s/.githooks\n' "$repo_root"
