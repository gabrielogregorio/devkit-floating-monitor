#!/usr/bin/env bash
# Single runner for the Floating Monitor test suite. Same commands the CI runs.
#
#   ./run-tests.sh   -> lint (ruff, shellcheck) + unit (pytest) + smoke (verify.sh reads the real sensors once)
#
# No test opens a window: the sensors read fake /proc and /sys trees and the config goes to tmp.
set -u
cd "$(dirname "$0")" || exit

PY="${PY:-.venv/bin/python}"
FAILED=0
declare -a RESULTS

bar() { printf '%s\n' "------------------------------------------------------------"; }
run_layer() {  # run_layer <name> <command...>
  local name="$1"; shift
  bar; echo ">> $name"; bar
  if "$@"; then RESULTS+=("PASS  $name"); else RESULTS+=("FAIL  $name"); FAILED=1; fi
}

# ---------- lint (ruff from the venv; shellcheck when installed) ----------
run_layer "lint   (ruff)" "$PY" -m ruff check .
if command -v shellcheck > /dev/null; then
  run_layer "lint   (shellcheck)" shellcheck --severity=warning ./*.sh
else
  RESULTS+=("SKIP  lint (shellcheck) - sudo apt install shellcheck")
fi

# ---------- unit (pytest: sensors, line, config, i18n, install.sh) ----------
run_layer "unit   (pytest)" "$PY" -m pytest --cov --cov-report=term

# ---------- smoke (the real sensors of this machine, no window) ----------
run_layer "smoke  (verify.sh)" ./verify.sh

# ---------- scoreboard ----------
echo ""; bar; echo "SCOREBOARD"; bar
for r in "${RESULTS[@]}"; do echo "  $r"; done
bar
if [ "$FAILED" -eq 0 ]; then echo "ALL GREEN ✅"; else echo "FAILURES ❌"; fi
exit "$FAILED"
