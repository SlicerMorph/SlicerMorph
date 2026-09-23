"""Load every module of this extension in a real Slicer, on every platform.

Run INSIDE Slicer by ``.github/workflows/slicer-smoke.yml``::

    Slicer --no-splash --no-main-window --testing \
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

Nothing here installs a package or touches the network: module loading must work
before any of that is reachable, and keeping this job fast and offline means a
PyPI outage never reds out a pull request.  Dependency installation is tested
separately, on a schedule, by ``ci_deps.py``.

Run it locally exactly as CI does, e.g. on macOS::

    /Applications/Slicer.app/Contents/MacOS/Slicer --no-splash --no-main-window --testing \
        --additional-module-paths <checkout>/ITKANTsCommon \
        --additional-module-paths <checkout>/ANTsRegistration \
        --python-script <checkout>/Testing/ci_load.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_common  # noqa: E402
import cmake_manifest  # noqa: E402

import slicer  # noqa: E402


def main():
    root = ci_common.repositoryRoot()
    declared = cmake_manifest.modules(root)
    ci_common.say(f"[ci] declared modules: {', '.join(m['name'] for m in declared) or '(none)'}")
    # An empty list would otherwise "pass" every check below without testing anything.
    ci_common.record("extension declares at least one module", bool(declared),
                     f"{len(declared)} found in CMakeLists.txt")

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
            with ci_common.collectedExceptions() as raised:
                widget = loaded.widgetRepresentation()
            if raised and all(entry.startswith("ModuleNotFoundError") for entry in raised):
                # Slicer is started with --testing, and slicer.packaging.pip_ensure
                # takes skip_in_testing=True: in testing mode it logs and returns
                # without installing anything, so a module that fetches a pip
                # dependency in setup() then fails on the import that follows.  That is
                # Slicer declining to touch the environment, not a broken module -- in
                # a real session the package installs.  Whether those dependencies can
                # actually be installed is what the weekly deps job answers.
                ci_common.record(f"{name} widget builds", True,
                                 "; ".join(raised) + " -- pip dependency, not installed "
                                 "under --testing")
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
