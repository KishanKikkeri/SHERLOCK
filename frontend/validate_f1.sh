#!/usr/bin/env bash
# SHERLOCK — Sprint F1 validation script.
# Mirrors the project's existing validate_stage_*.py convention, adapted
# for a frontend package (no Python equivalent makes sense here).
#
# Usage: ./validate_f1.sh   (run from frontend-v2/)
set -euo pipefail

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }

echo "== Sprint F1 validation =="

echo "-- Dependency install --"
npm install --silent
pass "npm install"

echo "-- Type check --"
npx tsc -b || fail "tsc -b reported errors"
pass "tsc -b (no type errors)"

echo "-- Lint --"
LINT_OUTPUT=$(npx oxlint 2>&1) || true
if echo "$LINT_OUTPUT" | grep -q "0 errors"; then
  pass "oxlint (0 errors)"
else
  echo "$LINT_OUTPUT"
  fail "oxlint reported errors"
fi

echo "-- Production build --"
npm run build || fail "vite build failed"
pass "vite build"

echo "-- Bundle size --"
du -sh dist/assets/*.js dist/assets/*.css 2>/dev/null | while read -r size file; do
  echo "  $file: $size"
done

echo ""
echo "All F1 checks passed."
echo "Not covered by this script (needs a browser — see docs/stage-f/validation/F1-VALIDATION.md):"
echo "  - Lighthouse performance/accessibility scores"
echo "  - Screenshots / demo GIFs"
echo "  - Manual login flow against a running backend"
