import SampleData
import numpy as np
#import vtkSegmentationCorePython as vtkSegmentationCore 
#import vtkSlicerSegmentationsModuleLogicPython as vtkSlicerSegmentationsModuleLogic

# Load master volume
sampleDataLogic = SampleData.SampleDataLogic()
masterVolumeNode = sampleDataLogic.downloadMRHead()

# Create segmentation
segmentationNode = slicer.vtkMRMLSegmentationNode()
slicer.mrmlScene.AddNode(segmentationNode)
segmentationNode.CreateDefaultDisplayNodes() # only needed for display
segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)

# Create seed segment in brain
brainSeedPositions = [[39, 17.5,-12], [-35, 16.7, -12], [-5.3, -9.8, -19], [0, -43, -23], [0, -12, -23]]
append1 = vtk.vtkAppendPolyData()
for brainSeedPosition in brainSeedPositions:
  brainSeed = vtk.vtkSphereSource()
  brainSeed.SetCenter(brainSeedPosition)
  brainSeed.SetRadius(10)
  brainSeed.Update()
  append1.AddInputData(brainSeed.GetOutput())

append1.Update()
brainSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append1.GetOutput(), 'Brain', [1.0,0.0,0.0])

# Create seed segment outside brain
tissueSeedPositions = [[33,57,-11], [-29, 56.7, -11], [66,46.5,-21], [-60,44,-21], [9,105,-70], [9,59.5,-94.5], [9,-65.3,-91]]
append2 = vtk.vtkAppendPolyData()
for tissueSeedPosition in tissueSeedPositions:
  tissueSeed = vtk.vtkSphereSource()
  tissueSeed.SetCenter(tissueSeedPosition)
  tissueSeed.SetRadius(5)
  tissueSeed.Update()
  append2.AddInputData(tissueSeed.GetOutput())

append2.Update()
tissueSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append2.GetOutput(), 'Tissue', [0.0,1.0,0.0])

# Create seed segment in background
backgroundSeedPositions = [[80, 83, 0], [-73, 90, 0], [0, 123, 0.9], [0, -103, -114]]
append3 = vtk.vtkAppendPolyData()
for backgroundSeedPosition in backgroundSeedPositions:
  backgroundSeed = vtk.vtkSphereSource()
  backgroundSeed.SetCenter(backgroundSeedPosition)
  backgroundSeed.SetRadius(10)
  backgroundSeed.Update()
  append3.AddInputData(backgroundSeed.GetOutput())

append3.Update()
backgroundSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append3.GetOutput(), 'Background', [0.0,0.0,1.0])


# Perform analysis
################################################
# Get segment IDs to be processed (we will process all)
#selectedSegmentIds = vtk.vtkStringArray()
#segmentationNode.GetSegmentation().GetSegmentIDs(selectedSegmentIds)

# Create segment editor to get access to effects
segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
#segmentEditorWidget.show()
segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
slicer.mrmlScene.AddNode(segmentEditorNode)
segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
segmentEditorWidget.setSegmentationNode(segmentationNode)
segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

# Segment image
segmentEditorWidget.setActiveEffectByName("Grow from seeds")
effect = segmentEditorWidget.activeEffect()
effect.self().onPreview()
effect.self().onApply()

# Set up masking parameters
segmentEditorWidget.setActiveEffectByName("Mask volume")
effect = segmentEditorWidget.activeEffect()
# set fill value to be outside the valid intensity range
intensityRange = masterVolumeNode.GetImageData().GetScalarRange()
effect.setParameter("FillValue", str(intensityRange[0]-1))
# Blank out voxels that are outside the segment
effect.setParameter("Operation", "FILL_OUTSIDE")
# Create a volume that will store temporary masked volumes
maskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Temporary masked volume")
effect.self().outputVolumeSelector.setCurrentNode(maskedVolume)

# Mask, crop and save each segment
threshold = 0
for segmentIndex in range(segmentationNode.GetSegmentation().GetNumberOfSegments()):
  # Set active segment
  segmentID = segmentationNode.GetSegmentation().GetNthSegmentID(segmentIndex)
  segmentEditorWidget.setCurrentSegmentID(segmentID)
  # Apply mask
  effect.self().onApply()
  img = slicer.modules.segmentations.logic().CreateOrientedImageDataFromVolumeNode(maskedVolume) 
  img.UnRegister(None) 
  extent=[0,0,0,0,0,0]
  seg.vtkOrientedImageDataResample.CalculateEffectiveExtent(img, extent, threshold) 
  croppedImg = seg.vtkOrientedImageData() 
  seg.vtkOrientedImageDataResample.CopyImage(img, croppedImg, extent) slicer.modules.segmentations.logic().CopyOrientedImageDataToVolumeNode(croppedImg, volumeNode)
