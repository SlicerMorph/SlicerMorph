"""Shared PASS/FAIL harness for the CI scripts in this directory.

The scripts here are run INSIDE Slicer by the workflows in ``.github/workflows``
(``Slicer --python-script Testing/<script>.py``).  Each one records a series of
named checks and exits non-zero if any of them failed, which is what turns a
broken platform into a red CI job.

On Windows ``Slicer.exe`` is a GUI-subsystem launcher: the app's console output
never reaches the calling shell.  So everything printed here is also appended to
the file named by the ``SLICER_CI_LOG`` environment variable, which the workflow
prints after the app exits.
"""

import contextlib
import os
import sys
import traceback

import slicer

LOG_PATH = os.environ.get("SLICER_CI_LOG")

_results = []


def firstLine(value):
    """The first line of an exception's message, for a one-line PASS/FAIL detail.

    Plenty of exceptions carry no message at all -- ``raise RuntimeError()``, a bare
    ``assert``, much of what the Qt bindings raise -- and ``"".splitlines()`` is ``[]``,
    so taking ``[0]`` off it is an IndexError thrown while reporting someone else's
    failure.  Inside ``collectedExceptions`` that would be silent and backwards: the
    swallowed exception this module exists to notice would go unrecorded and the check
    would pass.
    """
    lines = str(value).strip().splitlines()
    return lines[0] if lines else f"(no message: {type(value).__name__})"


@contextlib.contextmanager
def collectedExceptions():
    """Collect exceptions that Slicer catches on the C++ side instead of re-raising.

    Slicer calls a scripted module's ``setup()`` from C++.  When it raises, the C++
    wrapper prints the traceback and carries on, so the Python code that asked for the
    widget sees a perfectly ordinary return value and a test that only looks at that
    return value reports a pass over a module that is visibly broken.

    Those exceptions do reach ``sys.excepthook``, so borrowing it for the duration of
    the call is a dependable way to notice them.  Yields a list that fills with one
    short description per exception; the original hook still runs, so the full
    traceback is in the CI log either way.
    """
    collected = []
    original = sys.excepthook

    def hook(exceptionType, value, tb):
        collected.append(f"{exceptionType.__name__}: {firstLine(value)}")
        original(exceptionType, value, tb)

    sys.excepthook = hook
    try:
        yield collected
    finally:
        sys.excepthook = original


def say(line):
    """Print a line to stdout and, when set, to the log file CI reads afterwards."""
    print(line, flush=True)
    if LOG_PATH:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except Exception:
            pass


def record(name, ok, detail=""):
    """Record one named check.  Any failure fails the job."""
    _results.append((name, ok, detail))
    say(f"[ci] {'PASS' if ok else 'FAIL'}  {name}{(': ' + detail) if detail else ''}")


def repositoryRoot():
    """The checkout root, derived from this file's location (``<root>/Testing``)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(main, tag):
    """Run ``main``, summarize the recorded checks, and exit Slicer with the verdict.

    Slicer must be told to quit explicitly: ``--python-script`` leaves the
    application running afterwards, and a CI job that never exits just burns its
    timeout instead of reporting a result.
    """
    say(f"[ci] {tag}: platform={sys.platform} slicer={slicer.app.applicationVersion} "
        f"python={sys.version.split()[0]}")
    exitCode = 1
    verdict = "FAIL (script did not finish)"
    try:
        main()
        failed = [name for name, ok, _ in _results if not ok]
        say(f"[ci] {len(_results) - len(failed)}/{len(_results)} checks passed"
            + (f"; FAILED: {', '.join(failed)}" if failed else ""))
        # No checks at all means the script died before testing anything: also a failure.
        exitCode = 1 if (failed or not _results) else 0
        verdict = "PASS" if exitCode == 0 else f"FAIL ({', '.join(failed) or 'no checks ran'})"
    except Exception:
        say("[ci] FAIL  unexpected error:\n" + traceback.format_exc())
        verdict = "FAIL (unexpected error)"
    finally:
        # The workflow judges the run on THIS line, not on the application's exit code.
        # Slicer in --testing mode exits non-zero if any Python traceback was logged
        # during the session, including ones a module handled and ones that are the
        # expected consequence of testing mode itself -- pip_ensure refuses to install
        # under --testing, so a module that fetches a dependency in setup() always
        # leaves a traceback behind.  The exit code therefore cannot distinguish "a
        # check failed" from "something printed a traceback".  This line can.
        #
        # A crash or a hang truncates the log before this is written, so a missing
        # verdict is a failure too; only a crash AFTER it is reported passes.
        say(f"[ci] VERDICT: {verdict}")
        sys.stdout.flush()
        slicer.util.exit(exitCode)
