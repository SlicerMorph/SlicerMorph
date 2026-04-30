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
