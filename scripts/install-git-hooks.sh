#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
git -C "$repo_root" config --local core.hooksPath .githooks
printf 'Git hooks enabled: %s/.githooks\n' "$repo_root"
