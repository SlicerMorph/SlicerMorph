# --- NumPy 2.0 compat shim for pyRserve (must come before importing pyRserve) ---
import numpy as _np
from types import SimpleNamespace as _SimpleNamespace
if not hasattr(_np, "string_"):  _np.string_  = _np.bytes_
if not hasattr(_np, "unicode_"): _np.unicode_ = str
if not hasattr(_np, "int"):      _np.int      = int
if not hasattr(_np, "bool"):     _np.bool     = bool
if not hasattr(_np, "float"):    _np.float    = float
if not hasattr(_np, "object"):   _np.object   = object
if not hasattr(_np, "compat"):   _np.compat   = _SimpleNamespace(long=int)
elif not hasattr(_np.compat, "long"):
    _np.compat.long = int
# -------------------------------------------------------------------------------

import pyRserve
import pandas as pd
import numpy as np
import slicer
import Support.gpa_lib as gpa_lib

# Connect to an already-running Rserve (start it in R with: library(Rserve); Rserve(debug=TRUE, args="--no-save"))
conn = pyRserve.connect(host='127.0.0.1', port=6311)
conn.r.ls()

# -------------------------------------------------------------------------
# Pull GPA results directly from SlicerMorph GPA widget (no CSV needed)
# -------------------------------------------------------------------------
gpaWidget = slicer.modules.gpa.widgetRepresentation().self()
lmData = gpaWidget.LM  # SlicerMorph's LMData object (post-GPA)

# Aligned landmarks are in lmData.lm with shape (p, 3, n)
arr = np.asarray(lmData.lm)  # p × 3 × n
assert arr.ndim == 3 and arr.shape[1] == 3, f"Unexpected LM.lm shape: {arr.shape}"
p, _, n = arr.shape

# Build coords as n × (3p): x1,y1,z1,x2,y2,z2,…
coords_mat = arr.transpose(2, 0, 1).reshape(n, 3 * p, order="C")

# Centroid sizes (vector of length n) — attribute name is 'centriodSize'
size = np.asarray(lmData.centriodSize, dtype=float).reshape(-1)
if size.shape[0] != n:
    raise RuntimeError(f"centroid size length {size.shape[0]} != number of specimens {n}")

# Send to R
conn.r.coords = coords_mat
conn.r.size = size

conn.eval('require(geomorph)')

# arrayspecs expects coords as n × (k*p)
conn.eval(f'arr=arrayspecs(coords,p={p},k=3)')

# Build geomorph data frame and model
conn.voidEval('gdf=geomorph.data.frame(Size=size,Coords=arr)')
conn.voidEval('mod=as.formula(Coords~Size)')
conn.voidEval('outlm=procD.lm(mod, data=gdf)')
model = conn.eval('outlm')

conn.shutdown()

# --- Extract regression coefficients ---
# modelCoeffs: shape (2, 3p) -> [0]=intercept, [1]=slope (Size)
modelCoeffs  = model[2]
intercept_row = modelCoeffs[0]
slope_row     = modelCoeffs[1]

print("modelCoeffs.shape", modelCoeffs.shape)
print("intercept_row.shape", intercept_row.shape)
print("slope_row.shape",   slope_row.shape)

print("Before adding slope:")
print("  pcNumber:", gpaWidget.pcNumber)
print("  lmData.vec:", lmData.vec.shape)
print("  lmData.val:", lmData.val.shape)

# Confirm p and reshape slope to (3p,)
print("GPA says #landmarks p =", p, "; slope_row =", slope_row.shape)
size_slope_flat = slope_row.reshape(p, 3, order='C').ravel(order='C')
size_slope_flat *= 1000  # exaggerate for visibility (tune as needed)

# --- Append as a new “vector” (not a true PC), then update UI ---
lmData.vec = np.column_stack((lmData.vec, size_slope_flat))
dummy_eigenvalue = 1.0
lmData.val = np.append(lmData.val, dummy_eigenvalue)

print("After adding slope:")
print("  lmData.vec:", lmData.vec.shape)
print("  lmData.val:", lmData.val.shape)

# Sync counts and refresh lists
gpaWidget.pcNumber = lmData.vec.shape[1]
lmData.sortedEig = gpa_lib.pairEig(lmData.val, lmData.vec)
gpaWidget.updateList()

# --- IMPORTANT: recompute scatterDataAll for all components/vectors ---
numPC = gpaWidget.pcNumber                 # total vectors now (PCs + Allometry slope)
n_spec = lmData.lm.shape[2]
gpaWidget.scatterDataAll = np.zeros((n_spec, numPC))
for i in range(numPC):
    scores = gpa_lib.plotTanProj(lmData.lm, lmData.sortedEig, i, 1)  # (n x ?), scores in col 0
    gpaWidget.scatterDataAll[:, i] = scores[:, 0]

# Rename the last entry everywhere to avoid calling it a “PC”
try:
    # Internal list used by UI population
    if hasattr(gpaWidget, "PCList") and len(gpaWidget.PCList) > 0:
        gpaWidget.PCList[-1] = "Allometry slope"

    # Rename last item in the relevant combo boxes
    idx_last = gpaWidget.XcomboBox.count - 1
    for cb in [gpaWidget.XcomboBox, gpaWidget.YcomboBox,
               gpaWidget.vectorOne, gpaWidget.vectorTwo, gpaWidget.vectorThree]:
        if cb.count > 0 and idx_last >= 0:
            cb.setItemText(idx_last, "Allometry slope")

    # Refresh the slider-group dropdown too
    if hasattr(gpaWidget, "slider1"):
        if hasattr(gpaWidget, "PCList"):
            gpaWidget.slider1.populateComboBox(gpaWidget.PCList)
        # Ensure rename even if populate path differs
        if gpaWidget.slider1.comboBox.count > 1:
            gpaWidget.slider1.comboBox.setItemText(
                gpaWidget.slider1.comboBox.count - 1, "Allometry slope"
            )
except Exception as e:
    print("Rename UI entries warning:", e)

print("All done. New vector ‘Allometry slope’ has been added.")

# --- Debug: compare norms ---
newVec = lmData.vec[:, -1]
pc1    = lmData.vec[:, 0]
print("Norm of new vector (Allometry slope):", np.linalg.norm(newVec))
print("Norm of PC1:", np.linalg.norm(pc1))
