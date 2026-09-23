"""Read the extension's module list out of its CMakeLists.txt files.

The CMake files are the authoritative manifest: a packaged extension contains
exactly the files they list, with the install paths they give.  A Slicer started
with ``--additional-module-paths`` loads straight from the source tree instead,
so it happily finds files CMake was never told about -- which is why a module or
resource missing from a CMakeLists.txt passes every local test and then ships
broken.  Reading the manifest here lets CI compare the two.

Deliberately free of any ``slicer`` import: ``check_module_manifest.py`` runs
this under a plain Python interpreter, with no Slicer installed.
"""

import os
import re

# The subset of CMake we need: `set(VAR a b c)` and `add_subdirectory(name)`.
_SET_RE = r"set\s*\(\s*{name}\s+(?P<body>[^)]*)\)"
_SUBDIR_RE = re.compile(r"add_subdirectory\s*\(\s*([^)\s]+)\s*\)")


def _stripComments(text):
    return re.sub(r"#[^\n]*", "", text)


def _setValues(text, name, substitutions=None):
    """Return the whitespace-separated values of `set(<name> ...)`, or [] if absent."""
    match = re.search(_SET_RE.format(name=name), text, re.IGNORECASE)
    if not match:
        return []
    values = match.group("body").split()
    for key, value in (substitutions or {}).items():
        values = [item.replace("${%s}" % key, value) for item in values]
    return values


def modules(root):
    """Every scripted module the extension declares, in declaration order.

    Each entry is a dict with ``directory`` (relative to `root`), ``name`` (the
    module name Slicer will register), ``scripts`` and ``resources`` (paths
    relative to the module directory, as CMake lists them), plus ``cmake`` (the
    CMakeLists.txt path, for error messages).
    """
    topPath = os.path.join(root, "CMakeLists.txt")
    with open(topPath, encoding="utf-8") as fp:
        top = _stripComments(fp.read())

    found = []
    for subdirectory in _SUBDIR_RE.findall(top):
        cmakePath = os.path.join(root, subdirectory, "CMakeLists.txt")
        if not os.path.isfile(cmakePath):
            continue
        with open(cmakePath, encoding="utf-8") as fp:
            body = _stripComments(fp.read())
        names = _setValues(body, "MODULE_NAME")
        if not names:
            continue  # a subdirectory that is not a scripted module
        name = names[0]
        substitutions = {"MODULE_NAME": name}
        found.append({
            "directory": subdirectory,
            "name": name,
            "scripts": _setValues(body, "MODULE_PYTHON_SCRIPTS", substitutions),
            "resources": _setValues(body, "MODULE_PYTHON_RESOURCES", substitutions),
            "cmake": os.path.relpath(cmakePath, root),
        })
    return found
