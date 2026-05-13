#!/usr/bin/env bash
# Run a frontend tool from inside frontend/ with repo-root-relative file paths
# rewritten as frontend-relative. Used by pre-commit hooks so eslint/prettier
# resolve their plugins via the project's own node_modules.
#
# Usage: scripts/pre-commit/run-in-frontend.sh <tool> [tool-args...] -- <files...>
# (pre-commit appends matched files after the entry args, so we treat the
#  trailing arguments that begin with `frontend/` as the file list.)

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: $0 <tool> [tool-args...] -- <files...>" >&2
    exit 2
fi

# Separate tool + non-file arguments from file paths. Anything starting with
# "frontend/" coming from pre-commit is a file we need to rewrite.
tool_args=()
file_args=()
for arg in "$@"; do
    if [[ "$arg" == frontend/* ]]; then
        file_args+=("${arg#frontend/}")
    else
        tool_args+=("$arg")
    fi
done

cd frontend
exec "${tool_args[@]}" "${file_args[@]}"
