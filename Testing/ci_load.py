"""Open every module of this extension in a real Slicer, on every platform.

Run INSIDE Slicer by ``.github/workflows/slicer-smoke.yml``::

    Slicer --no-splash --testing \
        --additional-module-paths <module dir> ... \
        --python-script Testing/ci_load.py

For each module the extension's CMakeLists.txt declares, this checks two things:

1. Slicer registered the module.  A scripted module whose Python file fails to
   import is silently dropped by the module factory, so a missing module here
   means an import error -- a renamed Slicer/VTK/Qt API, a dependency that is
   not present on this platform, or a plain syntax error under this Python.
2. Its widget can be built.  Creating the widget representation runs the
   module's ``setup()``, which is where ``slicer.util.loadUI`` reads the .ui
   file and instantiates every widget class in it.  This is what catches a
   missing or renamed resource and Qt widgets that exist on one platform's Qt
   build but not another's.

Slicer runs WITH its main window: several modules use the layout manager in
setup(), and under ``--no-main-window`` ``slicer.app.layoutManager()`` is None,
so they raise and look broken when only the window is missing.

Nothing here installs a package or touches the network: module loading must work
before any of that is reachable, and keeping this job offline means a PyPI outage
never reds out a pull request.

Run it locally exactly as CI does::

    Testing/module_paths.sh | while read -r d; do
      printf ' --additional-module-paths %s/%s' "$PWD" "$d"
    done
    # ... pass those to:
    /Applications/Slicer.app/Contents/MacOS/Slicer --no-splash --testing \
        <those paths> --python-script <checkout>/Testing/ci_load.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_common  # noqa: E402
import cmake_manifest  # noqa: E402

import slicer  # noqa: E402

_MISSING_MODULE = re.compile(r"No module named '([^']+)'")


def requirementNames(requirements):
    """The bare distribution names in whatever pip_ensure was handed.

    It accepts a space-separated string, a Requirement, or a list of either, and the
    names may carry version specifiers ("mistune>=3.0"), so take the leading name.
    """
    if isinstance(requirements, (str, bytes)):
        items = str(requirements).split()
    elif isinstance(requirements, (list, tuple, set)):
        items = [str(item) for entry in requirements for item in str(entry).split()]
    else:
        items = str(requirements).split()
    names = set()
    for item in items:
        name = re.split(r"[<>=!~;\[]", item, maxsplit=1)[0].strip()
        if name:
            names.add(name.lower().replace("-", "_"))
    return names


class PipEnsureRecorder:
    """Record which distributions a module asks ``pip_ensure`` for.

    Under ``--testing`` Slicer refuses to install anything: pip_ensure logs and returns,
    and the module's import of that package then raises.  Excusing every
    ModuleNotFoundError would hide a genuinely broken import that happens to raise the
    same type, so the excuse has to be tied to the specific package this module just
    asked for and was refused.
    """

    def __init__(self):
        self.requested = set()
        self._packaging = getattr(slicer, "packaging", None)
        self._original = getattr(self._packaging, "pip_ensure", None)

    def __enter__(self):
        if self._original is not None:
            def recording(requirements, *args, **kwargs):
                self.requested |= requirementNames(requirements)
                return self._original(requirements, *args, **kwargs)
            self._packaging.pip_ensure = recording
        return self

    def __exit__(self, *_):
        if self._original is not None:
            self._packaging.pip_ensure = self._original

    def excuses(self, entry):
        """True if `entry` is a missing import of something pip_ensure was refused."""
        if not entry.startswith("ModuleNotFoundError") or not slicer.app.testingEnabled():
            return False
        match = _MISSING_MODULE.search(entry)
        if not match:
            return False
        missing = match.group(1).split(".")[0].lower().replace("-", "_")
        return missing in self.requested


def main():
    root = ci_common.repositoryRoot()
    declared = cmake_manifest.modules(root)
    ci_common.say(f"[ci] declared modules: {', '.join(m['name'] for m in declared) or '(none)'}")
    # An empty list would otherwise "pass" every check below without testing anything.
    ci_common.record("extension declares at least one module", bool(declared),
                     f"{len(declared)} found in CMakeLists.txt")

    recorder = PipEnsureRecorder()
    if recorder._original is None:
        ci_common.say("[ci] note: slicer.packaging.pip_ensure not available; "
                      "no pip-dependency carve-out")

    for module in declared:
        name = module["name"]

        try:
            loaded = slicer.util.getModule(name)
        except Exception as error:
            # The module factory drops a scripted module whose import raised; the
            # traceback is in the application log above this line.
            ci_common.record(f"{name} loaded", False,
                             f"not registered with Slicer ({ci_common.firstLine(error)})")
            continue
        ci_common.record(f"{name} loaded", True, loaded.title or name)

        # A hidden module is a helper library with no user interface (ITKANTsCommon is
        # one): Slicer legitimately gives it no widget, so only require that asking for
        # one does not raise.
        hidden = loaded.hidden
        try:
            # setup() runs inside here, and Slicer swallows anything it raises -- hence
            # the collector, which is what actually catches a missing .ui file.
            recorder.requested.clear()
            with recorder, ci_common.collectedExceptions() as raised:
                widget = loaded.widgetRepresentation()
            # A module that fetches a pip dependency in setup() cannot get it here:
            # pip_ensure takes skip_in_testing=True, so under --testing it logs and
            # returns without installing, and the import after it raises.  That is
            # Slicer declining to touch the environment, not a broken module -- in a
            # real session the package installs, and whether it CAN be installed is
            # what the weekly deps job answers.
            #
            # The excuse is tied to the package this module just asked pip_ensure for
            # and was refused.  Excusing ModuleNotFoundError by type alone would pass a
            # genuinely broken import -- a typo'd module name raises exactly the same
            # thing -- which is the failure this job exists to catch.
            if raised and all(recorder.excuses(entry) for entry in raised):
                ci_common.record(f"{name} widget builds", True,
                                 "; ".join(raised) + " -- pip_ensure was refused under "
                                 f"--testing (requested: {', '.join(sorted(recorder.requested))})")
            elif raised:
                ci_common.record(f"{name} widget builds", False,
                                 "; ".join(raised) + " (raised inside setup())")
            else:
                ok = hidden or widget is not None
                ci_common.record(f"{name} widget builds", ok,
                                 "hidden module, no widget expected" if hidden
                                 else ("" if ok else "widgetRepresentation() returned None"))
        except Exception as error:
            ci_common.record(f"{name} widget builds", False,
                             f"{type(error).__name__}: {ci_common.firstLine(error)}")


ci_common.run(main, "load")
