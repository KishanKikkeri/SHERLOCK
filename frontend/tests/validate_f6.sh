#!/usr/bin/env bash
# SHERLOCK — Sprint F6 validation script. Same shape as validate_f1-f5.sh.
set -euo pipefail

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }

echo "== Sprint F6 validation =="
echo "-- Dependency install --"; npm install --silent; pass "npm install"
echo "-- Type check --"; npx tsc -b || fail "tsc -b reported errors"; pass "tsc -b (no type errors)"
echo "-- Lint --"
LINT_OUTPUT=$(npx oxlint 2>&1) || true
if echo "$LINT_OUTPUT" | grep -q "0 errors"; then pass "oxlint (0 errors)"; else echo "$LINT_OUTPUT"; fail "oxlint reported errors"; fi
echo "-- Production build --"; npm run build || fail "vite build failed"; pass "vite build"
echo "-- Findings module size --"
find src/findings -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1
echo ""
echo "All F6 checks passed."
echo "Not covered by this script — needs a live backend with a session that"
echo "has real findings: the expand chain against actual hypotheses,"
echo "graph-link deep-linking to a real person. See"
echo "docs/stage-f/validation/F6-VALIDATION.md."
