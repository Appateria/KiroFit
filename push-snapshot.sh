#!/bin/bash
# push-snapshot.sh
#
# Force-pushes a one-off snapshot of THIS folder (kirofit/) to a configurable
# remote git repository, then removes the local .git directory it created so
# no git history persists here afterward.
#
# This folder is normally a plain subdirectory of the parent "Susan" git repo
# (no .git of its own). This script temporarily initializes a throwaway repo
# right here, commits the current files, force-pushes them, and then deletes
# the throwaway .git. The parent Susan repo and its .git are never touched.
#
# Usage:
#   ./push-snapshot.sh <remote-url> [branch]
#
# Example:
#   ./push-snapshot.sh git@github.com:myuser/kirofit-export.git main
#
# Env vars (alternative to args):
#   REMOTE_URL   - target remote repository URL
#   BRANCH       - target branch (default: main)

set -euo pipefail

REMOTE_URL="${1:-${REMOTE_URL:-}}"
BRANCH="${2:-${BRANCH:-main}}"

if [[ -z "$REMOTE_URL" ]]; then
  echo "Error: no remote URL given." >&2
  echo "Usage: $0 <remote-url> [branch]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Safety check: make sure we are NOT inside the parent Susan git repo's
# tracked working tree (i.e. this folder must not already have a .git here
# that belongs to something else), and that this script never touches
# anything above $SCRIPT_DIR.
if [[ -e ".git" ]]; then
  echo "Error: $SCRIPT_DIR already contains a .git entry." >&2
  echo "Refusing to run to avoid clobbering an existing repository." >&2
  exit 1
fi

cleanup() {
  if [[ -d "$SCRIPT_DIR/.git" ]]; then
    echo "Cleaning up local .git directory..."
    rm -rf "$SCRIPT_DIR/.git"
  fi
}
trap cleanup EXIT

echo "Initializing throwaway git repo in $SCRIPT_DIR ..."
git init -q
git checkout -q -b "$BRANCH"

git add -A
if git diff --cached --quiet; then
  echo "Error: nothing to commit (no files staged). Aborting." >&2
  exit 1
fi

git commit -q -m "Snapshot of kirofit ($(date -u +%Y-%m-%dT%H:%M:%SZ))"

echo "Adding remote origin -> $REMOTE_URL"
git remote add origin "$REMOTE_URL"

echo "Force-pushing to $REMOTE_URL (branch: $BRANCH) ..."
git push --force origin "$BRANCH"

echo "Push complete. Removing local .git (handled by cleanup trap)."
