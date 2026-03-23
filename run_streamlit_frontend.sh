#!/usr/bin/env bash

# Run the Streamlit frontend from src/frontend/app and always return to repo root.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_APP_DIR="$REPO_ROOT/src/frontend/app"

cleanup() {
    cd "$REPO_ROOT" || exit 1
}

trap cleanup EXIT

cd "$FRONTEND_APP_DIR" || {
    echo "Failed to change directory to: $FRONTEND_APP_DIR" >&2
    exit 1
}

run_status=0
streamlit run app.py || run_status=$?

exit "$run_status"
