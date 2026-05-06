"""GPA-style unbiased consensus atlas — random reference + TPS warp iterations.

Run headless:
    /Users/amaga/Desktop/Slicer.app/Contents/MacOS/Slicer \
        --no-main-window --python-script \
        /Users/amaga/Desktop/SlicerMorph/run_gpa_atlas.py
"""
import sys, os, time

LOG_PATH = "/Users/amaga/Desktop/SlicerMorph/gpa_atlas.log"
_fh = open(LOG_PATH, "w", buffering=1)

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _fh.write(line + "\n")
    _fh.flush()

def run():
    try:
        log("=" * 60)
        log("GPA consensus atlas — random init + TPS warp")
        log("=" * 60)

        for _k in list(sys.modules.keys()):
            if "ALPACA" in _k:
                del sys.modules[_k]
        sys.path.insert(0, "/Users/amaga/Desktop/SlicerMorph/ALPACA")
        import ALPACA as _mod
        logic = _mod.ALPACALogic()

        MODELS_DIR = "/Users/amaga/Desktop/Mouse_Models/2/Mouse_Models/Fewer_Models"
        OUTPUT_DIR = os.path.join(
            MODELS_DIR, f"gpa_atlas_{time.strftime('%Y-%m-%d_%H_%M_%S')}"
        )

        params = {
            "projectionFactor":     0.02,
            "pointDensity":         1.0,
            "normalSearchRadius":   2,
            "FPFHNeighbors":        100,
            "FPFHSearchRadius":     5,
            "distanceThreshold":    3.0,
            "maxRANSAC":            100000,
            "ICPDistanceThreshold": 1.5,
            "alpha":                2.0,
            "beta":                 2.0,
            "CPDIterations":        100,
            "CPDTolerance":         0.001,
            "Acceleration":         True,
            "BCPDFolder":           "/Users/amaga/bcpd",
        }

        log(f"Models dir  : {MODELS_DIR}")
        log(f"Output dir  : {OUTPUT_DIR}")
        log(f"Iterations  : 5")
        log(f"spacingFactor: 0.02")

        result = logic.buildConsensusAtlas(
            modelsDir=MODELS_DIR,
            outputDir=OUTPUT_DIR,
            spacingFactor=0.02,
            parameterDictionary=params,
            iterations=5,
            useScaling=True,
            userReferencePath=None,      # None = random
            smoothingIterations=100,
            outlierRejectFactor=3.0,
            progressCallback=log,
        )
        log(f"SUCCESS → {result}")

    except Exception as exc:
        import traceback
        log(f"ERROR: {exc}")
        _fh.write(traceback.format_exc())
        _fh.flush()
    finally:
        _fh.close()
        slicer.app.quit()

run()
