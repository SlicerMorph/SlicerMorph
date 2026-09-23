#!/usr/bin/env bash
# Print the module directories of this extension, one per line, for
# --additional-module-paths.  Slicer does not search recursively, so every module
# directory has to be named individually; deriving them from the CMakeLists means the
# CI does not need updating when a module is added or removed.
#
# Pure bash on purpose: this runs on all three runners, where a usable `python` is not
# equally reachable from the shell.
set -euo pipefail
root="${1:-.}"

# add_subdirectory(X) in the top-level file, ignoring commented-out lines, keeping only
# the subdirectories that actually declare a scripted module.
sed -e 's/#.*//' "$root/CMakeLists.txt" \
  | grep -oE 'add_subdirectory\([^)]+\)' \
  | sed -E 's/add_subdirectory\(([^)]*)\)/\1/' \
  | tr -d ' "' \
  | while read -r subdirectory; do
      [ -n "$subdirectory" ] || continue
      cmake="$root/$subdirectory/CMakeLists.txt"
      if [ -f "$cmake" ] && grep -qE '^[[:space:]]*set\([[:space:]]*MODULE_NAME' "$cmake"; then
        echo "$subdirectory"
      fi
    done
