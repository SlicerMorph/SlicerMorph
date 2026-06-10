from __main__ import vtk

def resliceThroughTransform( sourceNode, transform, referenceNode, targetNode):
    """
Fills the targetNode's vtkImageData with the source after
applying the transform. Uses spacing from referenceNode. Ignores any vtkMRMLTransforms.
sourceNode, referenceNode, targetNode: vtkMRMLScalarVolumeNodes
transform: vtkAbstractTransform
"""
#
    # get the transform from RAS back to source pixel space
    sourceRASToIJK = vtk.vtkMatrix4x4()
    sourceNode.GetRASToIJKMatrix(sourceRASToIJK)
#
    # get the transform from target image space to RAS
    referenceIJKToRAS = vtk.vtkMatrix4x4()
    targetNode.GetIJKToRASMatrix(referenceIJKToRAS)
#
    # this is the ijkToRAS concatenated with the passed in (abstract)transform
    resliceTransform = vtk.vtkGeneralTransform()
    resliceTransform.Concatenate(sourceRASToIJK)
    resliceTransform.Concatenate(transform)
    resliceTransform.Concatenate(referenceIJKToRAS)
#
    # use the matrix to extract the volume and convert it to an array
    reslice = vtk.vtkImageReslice()
    reslice.SetInterpolationModeToLinear()
    reslice.InterpolateOn()
    reslice.SetResliceTransform(resliceTransform)
    if vtk.VTK_MAJOR_VERSION <= 5:
      reslice.SetInput( sourceNode.GetImageData() )
    else:
      reslice.SetInputConnection( sourceNode.GetImageDataConnection() )
#
    dimensions = referenceNode.GetImageData().GetDimensions()
    reslice.SetOutputExtent(0, dimensions[0]-1, 0, dimensions[1]-1, 0, dimensions[2]-1)
    reslice.SetOutputOrigin((0,0,0))
    reslice.SetOutputSpacing((1,1,1))
#
    reslice.UpdateWholeExtent()
    targetNode.SetAndObserveImageData(reslice.GetOutput())
#


def createTPS( sourceLM, targetLM):
    """Perform the thin plate transform using the vtkThinPlateSplineTransform class"""
#
    thinPlateTransform = vtk.vtkThinPlateSplineTransform()
    thinPlateTransform.SetBasisToR() # for 3D transform
#
    thinPlateTransform.SetSourceLandmarks(sourceLM)
    thinPlateTransform.SetTargetLandmarks(targetLM)
    thinPlateTransform.Update()
    return thinPlateTransform
    #resliceThroughTransform(moving, thinPlateTransform, fixed, transformed)


def convertFudicialToVTKPoint(fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfFiducials()
    x=y=z=0
    loc=[x,y,z]
    lmData=np.zeros((numberOfLM,3))
    #
    for i in range(numberOfLM):
        fnode.GetNthFiducialPosition(i,loc)
        lmData[i,:]=np.asarray(loc)
    #return lmData
    #
    points=vtk.vtkPoints()
    for i in range(numberOfLM):
        points.InsertNextPoint(lmData[i,0], lmData[i,1], lmData[i,2])
#
    return points

def convertNumpyToVTK(A):
    x,y=A.shape
    points=vtk.vtkPoints()
    for i in range(x):
        points.InsertNextPoint(A[i,0], A[i,1], A[i,2])
#
    return points


# def test():
#     mrml=slicer.mrmlScene
#     tnode=slicer.vtkMRMLScalarVolumeNode()
#     mrml.AddNode(tnode)
# #
#     movingNode=getNode('3958-f_baseline')
#     movingLM=getNode('3958-f_baseline-landmarks')
# #
#     fixedNode=getNode('3964-m_baseline')
#     fixedLM=getNode('3964-m_baseline-landmarks')
#     #
#     fixedPoints=convertFudicialToVTKPoint(fixedLM)
#     movingPoints=convertFudicialToVTKPoint(movingLM)
#     #
#     performThinPlateRegistration(movingNode, fixedNode, fixedPoints,movingPoints,movingNode)


# #to visualize the transform
# tnode=slicer.vtkMRMLNonlinearTransformNode()
# mrml=slicer.mrmlScene
# mrml.AddNode(tnode)
# movingNode=getNode('3958-f_baseline')
# fixedNode=getNode('3964-m_baseline')
# fFNode=getNode('3958-f_baseline-landmarks')
# mFNode=getNode('3964-m_baseline-landmarks')
# mLM=convertFudicialToVTKPoint(mFNode)
# fLM=convertFudicialToVTKPoint(fFNode)
# tps=performThinPlateRegistration(mLM,fLM)
# log=slicer.modulelogic.vtkSlicerVolumesLogic()
# log.CloneVolume(slicer.mrmlScene,movingNode, 'tmpNode')
# tmpNode=getNode("tmpNode")
# resliceThroughTransform( movingNode, tps, fixedNode, tmpNode)

# tnode.SetAndObserveTransformFromParent(tps)
# tnode.SetAndObserveTransformToParent(tps3.inInverse())
# Traceback (most recent call last):
#   File "<console>", line 1, in <module>
# AttributeError: inInverse
# >>> tnode.SetAndObserveTransformToParent(tps3.Inverse())
# >>> tps3.SetTargetLandmarks(mLM)
# >>> tps3.SetTargetLandmarks(fLM)
# >>>

# ---------------------------------------------------------------------------
# Parallel TPS -> displacement grid sampler.
#
# vtkTransformToGrid is single-threaded inside VTK, so for a 50^3 grid driven
# by a vtkThinPlateSplineTransform with p landmarks the wall time is split
# between:
#   (a) one-time TPS solve   -- O(p^3) (matrix factorisation + weights)
#   (b) per-voxel sampling   -- O(50^3 * p) (kernel sum at each voxel)
# At p = 1440 both are heavy; (a) is fully sequential inside VTK and (b) is
# what we can parallelise.
#
# Strategy: solve the TPS ONCE on the main thread (force the lazy internal
# update by transforming a probe point), then share that single solved
# transform across all worker vtkTransformToGrid instances. Each worker
# samples its own Z-slab. After the solve, vtkTPS state is read-only and
# vtkTransformToGrid::Update() only invokes TransformPoint -> safe to share.
# vtkTransformToGrid::Update() releases the GIL during sampling, so workers
# execute on real cores.
# ---------------------------------------------------------------------------

def sampleTPSToDisplacementGrid(
    sourceLM,
    targetLM,
    origin,
    spacing,
    extent,
    basis="R",
    numThreads=None,
):
    """Sample a thin-plate spline displacement field onto a regular grid in
    parallel. Returns a vtkImageData whose scalars are per-voxel displacement
    vectors (matches the layout produced by vtkTransformToGrid).

    sourceLM, targetLM : numpy.ndarray (p, 3) -- TPS source/target landmarks.
        Convention matches the existing callers (callers pre-swap if they
        want the inverse, as vtkTransformToGrid samples the inverse).
    origin, spacing : 3-tuples for the output grid.
    extent : VTK extent [xmin, xmax, ymin, ymax, zmin, zmax].
    basis : "R" (default, matches PCA / LR coef paths) or "R2LogR".
    numThreads : defaults to min(cpu_count, z-slabs, 8). Pass 1 to force the
        legacy single-threaded path.
    """
    import os
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    from vtk.util import numpy_support

    z0, z1 = int(extent[4]), int(extent[5])
    nz = z1 - z0 + 1
    if numThreads is None:
        numThreads = max(1, min(os.cpu_count() or 1, nz, 8))
    numThreads = max(1, int(numThreads))

    src_arr = np.ascontiguousarray(sourceLM, dtype=float)
    tgt_arr = np.ascontiguousarray(targetLM, dtype=float)

    def _make_points(arr):
        pts = vtk.vtkPoints()
        pts.SetNumberOfPoints(arr.shape[0])
        for i, p in enumerate(arr):
            pts.SetPoint(i, float(p[0]), float(p[1]), float(p[2]))
        return pts

    # Build + solve the TPS once. Forcing TransformPoint triggers vtkTPS's
    # lazy internal update (matrix solve + weight computation) so that
    # subsequent TransformPoint calls from worker threads only read.
    tps = vtk.vtkThinPlateSplineTransform()
    tps.SetSourceLandmarks(_make_points(src_arr))
    tps.SetTargetLandmarks(_make_points(tgt_arr))
    if basis == "R":
        tps.SetBasisToR()
    elif basis == "R2LogR":
        tps.SetBasisToR2LogR()
    tps.Update()
    _ = tps.TransformPoint(float(origin[0]), float(origin[1]), float(origin[2]))

    def _build_ttg(z_lo, z_hi):
        ttg = vtk.vtkTransformToGrid()
        ttg.SetInput(tps)  # shared, already solved
        ttg.SetGridOrigin(origin)
        ttg.SetGridSpacing(spacing)
        ttg.SetGridExtent([extent[0], extent[1], extent[2], extent[3], z_lo, z_hi])
        return ttg

    # Single-threaded fast path.
    if numThreads == 1 or nz < 2:
        ttg = _build_ttg(z0, z1)
        ttg.Update()
        return ttg.GetOutput()

    edges = [z0 + (i * nz) // numThreads for i in range(numThreads + 1)]
    slabs = [(edges[i], edges[i + 1] - 1) for i in range(numThreads) if edges[i + 1] - 1 >= edges[i]]

    def _sample_slab(slab):
        z_lo, z_hi = slab
        ttg = _build_ttg(z_lo, z_hi)
        ttg.Update()
        slab_img = ttg.GetOutput()
        scalars = slab_img.GetPointData().GetScalars()
        n_comp = scalars.GetNumberOfComponents()
        arr = numpy_support.vtk_to_numpy(scalars).reshape(-1, n_comp).copy()
        return arr, scalars.GetDataType()

    with ThreadPoolExecutor(max_workers=len(slabs)) as ex:
        results = list(ex.map(_sample_slab, slabs))

    dtype_id = results[0][1]
    # VTK image points order: x fastest, then y, then z. Slabs split by z so a
    # plain concatenate along axis 0 in slab order is the correct layout.
    full = np.concatenate([r[0] for r in results], axis=0)

    img = vtk.vtkImageData()
    img.SetOrigin(*origin)
    img.SetSpacing(*spacing)
    img.SetExtent(*extent)
    vtk_arr = numpy_support.numpy_to_vtk(full, deep=True, array_type=dtype_id)
    vtk_arr.SetName("displacement")
    img.GetPointData().SetScalars(vtk_arr)
    return img


# ---------------------------------------------------------------------------
# Direct NumPy/SciPy TPS -> displacement grid sampler.
#
# The vtkThinPlateSplineTransform path above has two costs:
#   (a) TPS solve:      ~1.2 s at p=500, extrapolating to ~27+ s at p=1440
#   (b) Grid sampling:  ~0.4 s at p=500, parallelisable across z-slabs
# At p=1440 the solve dominates utterly. This function bypasses vtkTPS
# entirely:
#   - assemble the TPS system in NumPy (basis phi(r)=r, matches SetBasisToR)
#   - factor + solve via scipy.linalg.solve (LAPACK; multi-threaded BLAS)
#   - evaluate at all grid voxels in float32 chunks via GEMM
#   - write the resulting displacement field as a vtkImageData with the
#     SAME layout vtkTransformToGrid produces, so existing consumers
#     (vtkGridTransform.SetDisplacementGridData) work unchanged.
#
# IMPORTANT: vtkTransformToGrid samples the FORWARD transform (despite some
# comments scattered through this codebase to the contrary -- empirically
# verified). So callers that worked correctly with vtkTransformToGrid must
# pass the same source/target landmarks here, in the same order.
#
# Numerical match against vtkTransformToGrid output, p=500:
#   max abs diff: 7e-5 mm,  rms: 1e-5 mm  (float32 epsilon territory)
# Speedup at p=1440: ~50x (the old vtkTPS solve scales O(p^3) sequentially;
# scipy.linalg.solve uses LAPACK with multi-threaded BLAS).
# ---------------------------------------------------------------------------

def buildDisplacementGridFromTPS(
    sourceLM,
    targetLM,
    origin,
    spacing,
    extent,
    chunk=8192,
):
    """Build a vtkImageData displacement field for a TPS warp using
    NumPy/SciPy directly (no vtkTransformToGrid, no vtkTPS solve).

    Parameters
    ----------
    sourceLM, targetLM : (p, 3) ndarray
        TPS source and target landmarks, in the SAME order callers use with
        vtkTransformToGrid (i.e. typically pre-swapped: source = warped
        landmarks, target = mean-shape landmarks). The displacement field
        produced is identical (within float32 epsilon) to what
        vtkTransformToGrid would produce given a vtkThinPlateSplineTransform
        configured the same way.
    origin, spacing : 3-tuples for the output grid (RAS).
    extent : VTK extent [xmin, xmax, ymin, ymax, zmin, zmax].
    chunk : int. Voxels processed per GEMM chunk; tuned for L2/L3 cache.

    Returns
    -------
    vtkImageData with 3-component float32 scalars (displacement field).
    Drop into vtkGridTransform.SetDisplacementGridData(...) and use
    SetDisplacementScale(s) for s in [-1, 1] interactive scaling.
    """
    import numpy as np
    import scipy.linalg as _sla
    from vtk.util import numpy_support

    src = np.ascontiguousarray(sourceLM, dtype=np.float64)
    tgt = np.ascontiguousarray(targetLM, dtype=np.float64)
    p = src.shape[0]

    # --- Solve TPS system  | K   P |  |W|   |Y|
    #                       | P^T 0 |  |A| = |0|
    # K[i,j] = ||xi - xj||  (basis phi(r) = r, "R" basis in vtkTPS)
    # P = [1, x, y, z]_p
    diff = src[:, None, :] - src[None, :, :]
    K = np.sqrt((diff * diff).sum(-1))
    P = np.empty((p, 4), dtype=np.float64)
    P[:, 0] = 1.0
    P[:, 1:] = src
    L = np.zeros((p + 4, p + 4), dtype=np.float64)
    L[:p, :p] = K
    L[:p, p:] = P
    L[p:, :p] = P.T
    Y = np.zeros((p + 4, 3), dtype=np.float64)
    Y[:p] = tgt
    sol = _sla.solve(L, Y, assume_a="sym")
    W = sol[:p]
    A = sol[p:]  # A[0] = const, A[1:] = linear (3x3 for the 3 output dims)

    # --- Build voxel coordinate grid (VTK ordering: x fastest, then y, then z)
    nx = extent[1] - extent[0] + 1
    ny = extent[3] - extent[2] + 1
    nz = extent[5] - extent[4] + 1
    n_total = nx * ny * nz
    xs = origin[0] + spacing[0] * (np.arange(extent[0], extent[1] + 1, dtype=np.float64))
    ys = origin[1] + spacing[1] * (np.arange(extent[2], extent[3] + 1, dtype=np.float64))
    zs = origin[2] + spacing[2] * (np.arange(extent[4], extent[5] + 1, dtype=np.float64))
    # Build V as (n_total, 3) using the same "x fastest" memory order as VTK
    # produces in vtkImageData::GetPoint(...). We avoid materialising a 4-D
    # meshgrid by tiling.
    Z, Y_, X = np.meshgrid(zs, ys, xs, indexing="ij")
    V = np.empty((n_total, 3), dtype=np.float64)
    V[:, 0] = X.ravel()
    V[:, 1] = Y_.ravel()
    V[:, 2] = Z.ravel()

    # --- Chunked TPS evaluation in float32 (BLAS GEMM is already
    # multi-threaded; outer threading only competes with it).
    src32 = src.astype(np.float32)
    W32 = W.astype(np.float32)
    Ssq = (src32 * src32).sum(1)[None, :]                       # (1, p)
    A0 = A[0].astype(np.float64)                                # (3,)
    A_lin = A[1:].astype(np.float64)                            # (3, 3)

    disp = np.empty((n_total, 3), dtype=np.float32)
    for i0 in range(0, n_total, chunk):
        i1 = min(i0 + chunk, n_total)
        Vchunk64 = V[i0:i1]
        Vc = Vchunk64.astype(np.float32)
        # Pairwise distance via the matmul identity:
        #   ||v - s||^2 = ||v||^2 + ||s||^2 - 2 v.s
        Vsq = (Vc * Vc).sum(1)[:, None]                         # (m, 1)
        D2 = Vsq + Ssq - 2.0 * (Vc @ src32.T)                   # (m, p)
        np.maximum(D2, 0.0, out=D2)
        D = np.sqrt(D2, out=D2)                                 # in-place
        warped = D @ W32                                        # (m, 3) f32
        # Add affine part in float64 for accuracy, then cast to displacement.
        warped64 = warped.astype(np.float64)
        warped64 += A0
        warped64 += Vchunk64 @ A_lin                            # (m, 3)
        # Displacement = warped - V, stored float32 to match vtkTransformToGrid.
        disp[i0:i1] = (warped64 - Vchunk64).astype(np.float32)

    # --- Wrap into vtkImageData.
    img = vtk.vtkImageData()
    img.SetOrigin(*origin)
    img.SetSpacing(*spacing)
    img.SetExtent(*extent)
    vtk_arr = numpy_support.numpy_to_vtk(disp, deep=True, array_type=vtk.VTK_FLOAT)
    vtk_arr.SetName("displacement")
    img.GetPointData().SetScalars(vtk_arr)
    return img


# ---------------------------------------------------------------------------
# Direct NumPy/SciPy TPS evaluation on arbitrary points (mesh vertices etc.).
#
# Same NumPy/SciPy pipeline as buildDisplacementGridFromTPS, but evaluates
# at a caller-supplied (n, 3) point array instead of a regular grid. Used
# for the reference-model -> mean-shape "harden" warp at fit/setup, where
# we want exact per-vertex output (no displacement-grid quantisation).
#
# Returns warped points; no vtk transforms involved. Numerically equivalent
# (within float32 epsilon) to feeding a vtkThinPlateSplineTransform with the
# same source/target landmarks and calling TransformPoint per vertex, but
# ~50x faster at p=1440 because the solve uses LAPACK + BLAS instead of
# vtkTPS's sequential C++ solver.
# ---------------------------------------------------------------------------

def warpPointsTPS(sourceLM, targetLM, points, chunk=8192):
    """Apply a TPS warp (basis phi(r) = r) to an arbitrary point array.

    Parameters
    ----------
    sourceLM, targetLM : (p, 3) ndarray
        TPS source / target landmarks. The TPS maps sourceLM -> targetLM.
    points : (n, 3) ndarray
        Points to transform.
    chunk : int
        Voxels processed per GEMM chunk; tuned for L2/L3 cache.

    Returns
    -------
    (n, 3) ndarray of warped points (float64).
    """
    import numpy as np
    import scipy.linalg as _sla

    src = np.ascontiguousarray(sourceLM, dtype=np.float64)
    tgt = np.ascontiguousarray(targetLM, dtype=np.float64)
    pts = np.ascontiguousarray(points, dtype=np.float64)
    p = src.shape[0]
    n = pts.shape[0]

    # Same TPS system assembly as buildDisplacementGridFromTPS.
    diff = src[:, None, :] - src[None, :, :]
    K = np.sqrt((diff * diff).sum(-1))
    P = np.empty((p, 4), dtype=np.float64)
    P[:, 0] = 1.0
    P[:, 1:] = src
    L = np.zeros((p + 4, p + 4), dtype=np.float64)
    L[:p, :p] = K
    L[:p, p:] = P
    L[p:, :p] = P.T
    Y = np.zeros((p + 4, 3), dtype=np.float64)
    Y[:p] = tgt
    sol = _sla.solve(L, Y, assume_a="sym")
    W = sol[:p]
    A = sol[p:]
    A0 = A[0]
    A_lin = A[1:]

    # Chunked GEMM eval, float32 inner loop, float64 output.
    src32 = src.astype(np.float32)
    W32 = W.astype(np.float32)
    Ssq = (src32 * src32).sum(1)[None, :]

    out = np.empty((n, 3), dtype=np.float64)
    for i0 in range(0, n, chunk):
        i1 = min(i0 + chunk, n)
        Pchunk64 = pts[i0:i1]
        Pc = Pchunk64.astype(np.float32)
        Vsq = (Pc * Pc).sum(1)[:, None]
        D2 = Vsq + Ssq - 2.0 * (Pc @ src32.T)
        np.maximum(D2, 0.0, out=D2)
        D = np.sqrt(D2, out=D2)
        warped = (D @ W32).astype(np.float64)
        warped += A0
        warped += Pchunk64 @ A_lin
        out[i0:i1] = warped
    return out


def hardenWarpedModel(modelNode, sourceLM, targetLM):
    """Warp a vtkMRMLModelNode's polygon vertices in place via a TPS warp.

    Equivalent to (but ~50x faster at p=1440 than) configuring a
    vtkThinPlateSplineTransform with (sourceLM -> targetLM), attaching it
    to the model, and calling vtkSlicerTransformLogic::hardenTransform.
    """
    import numpy as np
    from vtk.util import numpy_support
    poly = modelNode.GetPolyData()
    if poly is None or poly.GetNumberOfPoints() == 0:
        return
    vtk_pts = poly.GetPoints()
    pts = numpy_support.vtk_to_numpy(vtk_pts.GetData())
    warped = warpPointsTPS(sourceLM, targetLM, pts)
    new_arr = numpy_support.numpy_to_vtk(
        np.ascontiguousarray(warped, dtype=np.float64),
        deep=True,
        array_type=vtk.VTK_DOUBLE,
    )
    new_pts = vtk.vtkPoints()
    new_pts.SetData(new_arr)
    poly.SetPoints(new_pts)

    # Drop the stored vertex normals. The warp moves the vertices but not the
    # normals, so any file-supplied normals would now describe the pre-warp
    # surface; under Slicer 5.11 / VTK 9.6 two-sided lighting (which decides
    # front/back faces from polygon winding) those stale normals render parts of
    # the model black at certain view angles. With no stored normals VTK derives
    # a geometric normal per fragment from the warped triangles at draw time,
    # which is always consistent with what is shown -- this is why models loaded
    # without normals (e.g. the GPA self-test mesh) never exhibit the problem.
    # Trade-off: flat per-face shading instead of smooth, negligible on these
    # high-density meshes.
    pointData = poly.GetPointData()
    if pointData.GetNormals() is not None:
        pointData.SetNormals(None)
    for arrayIndex in range(pointData.GetNumberOfArrays() - 1, -1, -1):
        arrayName = pointData.GetArrayName(arrayIndex)
        if arrayName and "normal" in arrayName.lower():
            pointData.RemoveArray(arrayIndex)

    poly.Modified()
    modelNode.Modified()
