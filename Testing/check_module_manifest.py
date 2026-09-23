"""Check that every source file in a module directory is listed in its CMakeLists.txt.

Runs under a plain Python interpreter -- no Slicer, no build, about a second.

WHY: a developer Slicer started with ``--additional-module-paths`` loads files
straight from the source tree, by path.  It therefore finds a new .py or .ui file
whether or not CMake knows about it, so local testing *always* passes.  The
packaged extension that users install contains only what the CMakeLists.txt
lists.  A file added without its manifest entry is invisible until someone
installs the release and the module fails to import.

This is a static stand-in for that packaging check.  It is not a substitute for a
real factory build -- it cannot verify install paths or CMake syntax -- but it
catches the common case (a file was added and the manifest was not updated)
without needing a Slicer build at all.

Usage::

    python Testing/check_module_manifest.py [repository-root]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmake_manifest  # noqa: E402

# Never expected in the packaged module: build/test scaffolding and editor droppings.
IGNORED_DIRECTORIES = {"Testing", "__pycache__", ".git"}
IGNORED_SUFFIXES = (".pyc", ".pyo", ".backup", ".orig", ".rej")
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}

problems = []


def ignored(relativePath):
    parts = relativePath.replace("\\", "/").split("/")
    if any(part in IGNORED_DIRECTORIES for part in parts):
        return True
    if parts[-1] in IGNORED_NAMES:
        return True
    return relativePath.endswith(IGNORED_SUFFIXES)


def filesUnder(directory, subdirectory=None, extensions=None):
    """Relative paths of files under `directory` (optionally only one subtree)."""
    base = os.path.join(directory, subdirectory) if subdirectory else directory
    if not os.path.isdir(base):
        return []
    collected = []
    for dirPath, dirNames, fileNames in os.walk(base):
        dirNames[:] = [d for d in dirNames if d not in IGNORED_DIRECTORIES]
        for fileName in fileNames:
            relativePath = os.path.relpath(os.path.join(dirPath, fileName), directory)
            relativePath = relativePath.replace("\\", "/")
            if ignored(relativePath):
                continue
            if extensions and not relativePath.endswith(extensions):
                continue
            collected.append(relativePath)
    return sorted(collected)


def main(root):
    found = cmake_manifest.modules(root)
    if not found:
        problems.append("no scripted modules found -- is this an extension repository root?")
        return

    for module in found:
        directory = os.path.join(root, module["directory"])
        listed = {path.replace("\\", "/") for path in module["scripts"] + module["resources"]}

        # Python sources the module ships, and everything under Resources/.
        onDisk = set(filesUnder(directory, extensions=(".py",)))
        onDisk |= set(filesUnder(directory, subdirectory="Resources"))

        for path in sorted(onDisk - listed):
            problems.append(
                f"{module['name']}: {module['directory']}/{path} exists but is not listed in "
                f"{module['cmake']} -- it will be missing from the installed extension")

        for path in sorted(listed - onDisk):
            problems.append(
                f"{module['name']}: {module['cmake']} lists {path}, which does not exist "
                f"in {module['directory']}/ -- the build will fail")

        print(f"[manifest] {module['name']}: {len(listed)} files listed, "
              f"{len(onDisk)} on disk")


if __name__ == "__main__":
    repositoryRoot = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    main(repositoryRoot)
    for problem in problems:
        print(f"[manifest] FAIL  {problem}")
    print(f"[manifest] {'FAILED' if problems else 'OK'}: {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
