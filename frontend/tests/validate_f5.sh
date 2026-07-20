#!/usr/bin/env bash
# SHERLOCK — Sprint F5 validation script. Same shape as validate_f1-f4.sh.
set -euo pipefail

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }

echo "== Sprint F5 validation =="
echo "-- Dependency install --"; npm install --silent; pass "npm install"
echo "-- Type check --"; npx tsc -b || fail "tsc -b reported errors"; pass "tsc -b (no type errors)"
echo "-- Lint --"
LINT_OUTPUT=$(npx oxlint 2>&1) || true
if echo "$LINT_OUTPUT" | grep -q "0 errors"; then pass "oxlint (0 errors)"; else echo "$LINT_OUTPUT"; fail "oxlint reported errors"; fi
echo "-- Production build --"; npm run build || fail "vite build failed"; pass "vite build"
echo "-- Collaboration module size --"
find src/collaboration -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1
echo ""
echo "All F5 checks passed."
echo "Not covered by this script — needs a live backend with multiple"
echo "logged-in officers: presence heartbeat/TTL behavior, notification"
echo "mark-as-read, discussion replay against a session that actually ran"
echo "one. See docs/stage-f/validation/F5-VALIDATION.md."
