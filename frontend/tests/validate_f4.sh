#!/usr/bin/env bash
# SHERLOCK — Sprint F4 validation script. Same shape as validate_f1-f3.sh.
set -euo pipefail

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }

echo "== Sprint F4 validation =="

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

echo "-- Voice module size --"
find src/voice -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1

echo ""
echo "All F4 checks passed."
echo "Not covered by this script (needs a browser with mic access + a live"
echo "backend — see docs/stage-f/validation/F4-VALIDATION.md):"
echo "  - Wake word / push-to-talk / continuous mode actually recognizing speech"
echo "  - Waveform/VU meter rendering against a real mic stream"
echo "  - Server-audio path (/voice/query) against a configured STT/TTS provider"
echo "  - Board voice-command retrofit end to end"
