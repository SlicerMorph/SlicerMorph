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