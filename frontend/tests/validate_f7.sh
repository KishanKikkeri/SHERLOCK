#!/usr/bin/env bash
# SHERLOCK — Sprint F7 validation script. Same shape as validate_f1-f6.sh.
set -euo pipefail
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }
echo "== Sprint F7 validation =="
echo "-- Dependency install --"; npm install --silent; pass "npm install"
echo "-- Type check --"; npx tsc -b || fail "tsc -b reported errors"; pass "tsc -b (no type errors)"
echo "-- Lint --"
LINT_OUTPUT=$(npx oxlint 2>&1) || true
if echo "$LINT_OUTPUT" | grep -q "0 errors"; then pass "oxlint (0 errors)"; else echo "$LINT_OUTPUT"; fail "oxlint reported errors"; fi
echo "-- Production build --"; npm run build || fail "vite build failed"; pass "vite build"
echo "-- Analytics module size --"
find src/analytics -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1
echo ""
echo "All F7 checks passed."
echo "Not covered by this script — needs a live backend: whether each"
echo "topic query actually returns the finding_type it targets (depends"
echo "on real case data existing to analyze). See F7-VALIDATION.md."
