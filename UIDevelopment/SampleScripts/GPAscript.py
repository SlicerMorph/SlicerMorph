import numpy as np
#import vtkSegmentationCorePython as vtkSegmentationCore 
#import vtkSlicerSegmentationsModuleLogicPython as vtkSlicerSegmentationsModuleLogic

## Find Volume Data
#masterVolumeNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLScalarVolumeNode')
#
## Create segmentation
#segmentationNode = slicer.vtkMRMLSegmentationNode()
#slicer.mrmlScene.AddNode(segmentationNode)
#segmentationNode.CreateDefaultDisplayNodes() # only needed for display
#segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)
#
## Find landmark positions loaded
#markupNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLMarkupsFiducialNode')
#numberOfLandmarks = markupNode.GetNumberOfFiducials()
#
## Create seed segments from landmark postions
#points = np.zeros([3,numberOfLandmarks])
#appendPoints1 = vtk.vtkAppendPolyData()
#for i in range(0, numberOfLandmarks):
#  markupNode.GetNthFiducialPosition(i, points[:,i])
#  seed = vtk.vtkSphereSource()
#  seed.SetCenter(points[:,i])
#  seed.SetRadius(.01)
#  seed.Update()
#  appendPoints1.AddInputData(seed.GetOutput())
#
#appendPoints1.Update()
#surfaceSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(appendPoints1.GetOutput(), 'Surface', [1.0,0.0,0.0])
#
## Use extent to create background seeds
## extent[6] = [ x_min, y_max, z_min, x_max, y_min, z_max ];
#extent = masterVolumeNode.GetImageData().GetExtent()
#backroundSeedPositions = [[extent[0],extent[1],extent[2]],[extent[3],extent[4],extent[5]]]
#appendPoints2 = vtk.vtkAppendPolyData()
#for backroundSeedPosition in backroundSeedPositions:
#  seed = vtk.vtkSphereSource()
#  seed.SetCenter(backroundSeedPosition)
#  seed.SetRadius(0.01)
#  seed.Update()
#  appendPoints2.AddInputData(seed.GetOutput())
#
#appendPoints2.Update()
#tissueSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(appendPoints2.GetOutput(), 'Background', [0.0,0.0,1.0])
#
#
## Create segment editor to get access to effects
#segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
##segmentEditorWidget.show()
#segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
#segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
#slicer.mrmlScene.AddNode(segmentEditorNode)
#segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
#segmentEditorWidget.setSegmentationNode(segmentationNode)
#segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)
#
## Segment image
#segmentEditorWidget.setActiveEffectByName("Grow from seeds")
#effect = segmentEditorWidget.activeEffect()
#effect.self().onPreview()
#effect.self().onApply()
segmentationNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLSegmentationNode')
# Get model and display node
modelHierarchyNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelHierarchyNode')
slicer.modules.segmentations.logic().ExportAllSegmentsToModelHierarchy(segmentationNode, modelHierarchyNode)
modelNode = slicer.mrmlScene.GetFirstNodeByName('Surface')

displayNode = modelNode.GetDisplayNode()

#Set up TPS
sourcePoints = vtk.vtkPoints()
targetPoints = vtk.vtkPoints()

for i in range(0, numberOfLandmarks):
  point = np.zeros(3)
  markupNode.GetNthFiducialPosition(i, point)
  sourcePoints.InsertNextPoint(point)
  point[2] = point[2] * 2
  targetPoints.InsertNextPoint(point)

transformNode=slicer.vtkMRMLTransformNode()
transformNode.SetName("TPSTransformNode")
slicer.mrmlScene.AddNode(transformNode)

VTKTPS = vtk.vtkThinPlateSplineTransform()
VTKTPS.SetSourceLandmarks( sourcePoints )
VTKTPS.SetTargetLandmarks( targetPoints )
VTKTPS.SetBasisToR()  # for 3D transform

#Connect transform to model
transformNode.SetAndObserveTransformToParent( VTKTPS )
modelNode.SetAndObserveTransformNodeID(transformNode.GetID())

