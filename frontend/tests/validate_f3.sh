#!/usr/bin/env bash
# SHERLOCK — Sprint F3 validation script. Same shape as validate_f1.sh/f2.sh.
set -euo pipefail

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }

echo "== Sprint F3 validation =="

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

echo "-- Board module size --"
find src/board -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1

echo ""
echo "All F3 checks passed."
echo "Not covered by this script (needs a browser + live backend with a"
echo "real session that has findings — see docs/stage-f/validation/F3-VALIDATION.md):"
echo "  - Drag/pan/zoom feel and grouped-card move correctness"
echo "  - AI suggestions panel against a session with real findings"
echo "  - Comment + @mention delivery, review approve/reject flow end to end"
