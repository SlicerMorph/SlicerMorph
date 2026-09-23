#!/usr/bin/env bash
# Decide whether the Slicer run passed, from the script's own verdict line rather
# than the application's exit code.
#
# Slicer in --testing mode exits non-zero if ANY Python traceback was logged during
# the session -- including ones a module caught, and ones testing mode itself causes
# (slicer.packaging.pip_ensure refuses to install under --testing, so a module that
# fetches a dependency in setup() always leaves a traceback behind).  So the exit code
# cannot tell "a check failed" from "something printed a traceback".
#
# The script prints its result as the last thing it does.  A crash or a hang truncates
# the log before that, so a missing verdict fails too.
set -uo pipefail
log="${1:?usage: verdict.sh <log file>}"

if [ ! -s "$log" ]; then
  echo "::error::Slicer wrote no log -- it exited before the script produced any output."
  exit 1
fi

echo "---------------- Slicer log ----------------"
cat "$log"
echo "--------------------------------------------"

verdict="$(grep -E '^\[ci\] VERDICT:' "$log" | tail -1 || true)"
if [ -z "$verdict" ]; then
  echo "::error::The script never reported a verdict -- it crashed or hung part way through."
  exit 1
fi
echo "$verdict"
case "$verdict" in
  *"VERDICT: PASS"*) exit 0 ;;
  *) echo "::error::${verdict#*VERDICT: }"; exit 1 ;;
esac
