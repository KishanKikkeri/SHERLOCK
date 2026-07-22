#!/usr/bin/env bash
# SHERLOCK — Sprint F8 validation script. Same shape as validate_f1-f7.sh.
set -euo pipefail
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }
echo "== Sprint F8 validation =="
echo "-- Dependency install --"; npm install --silent; pass "npm install"
echo "-- Type check --"; npx tsc -b || fail "tsc -b reported errors"; pass "tsc -b (no type errors)"
echo "-- Lint (includes jsx_a11y, enabled this sprint) --"
LINT_OUTPUT=$(npx oxlint 2>&1) || true
if echo "$LINT_OUTPUT" | grep -q "0 errors"; then pass "oxlint (0 errors, a11y rules included)"; else echo "$LINT_OUTPUT"; fail "oxlint reported errors"; fi
echo "-- Production build --"; npm run build || fail "vite build failed"; pass "vite build"
echo "-- Route code-splitting check --"
CHUNK_COUNT=$(find dist/assets -name "*.js" | wc -l | tr -d ' ')
echo "  $CHUNK_COUNT separate JS chunks (was 1 before this sprint)"
if [ "$CHUNK_COUNT" -lt 5 ]; then fail "expected route-level code splitting to produce multiple chunks"; fi
pass "code splitting active"
echo ""
echo "All F8 checks passed."
echo "Not covered by this script — needs a browser: Lighthouse/axe scores,"
echo "actual keyboard-shortcut feel, responsive layout at real breakpoints,"
echo "screen-reader pass. See F8-VALIDATION.md for exactly what that means."
