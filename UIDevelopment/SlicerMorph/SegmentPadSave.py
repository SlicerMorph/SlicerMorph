import os
import unittest
import sys
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
import vtkSegmentationCorePython as vtkSegmentationCore
import SimpleITK as sitk
import sitkUtils


#
# SegmentPadSave
#

class SegmentPadSave(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SegmentPadSave" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (SCRI)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
It performs a simple thresholding on the input volume and optionally captures a screenshot.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# SegmentPadSaveWidget
#

class SegmentPadSaveWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input volume selector
    #
    self.inputSelector = slicer.qMRMLNodeComboBox()
    self.inputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.inputSelector.selectNodeUponCreation = True
    self.inputSelector.addEnabled = False
    self.inputSelector.removeEnabled = False
    self.inputSelector.noneEnabled = False
    self.inputSelector.showHidden = False
    self.inputSelector.showChildNodeTypes = False
    self.inputSelector.setMRMLScene( slicer.mrmlScene )
    self.inputSelector.setToolTip( "Pick the input to the algorithm." )
    parametersFormLayout.addRow("Input Volume: ", self.inputSelector)
    
    #
    # output directory selector
    #
    self.outputDirectory = ctk.ctkDirectoryButton()
    self.outputDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Output Directory:", self.outputDirectory)

    #
    # threshold value
    #
    self.imageThresholdSliderWidget = ctk.ctkSliderWidget()
    self.imageThresholdSliderWidget.singleStep = 0.1
    self.imageThresholdSliderWidget.minimum = -1
    self.imageThresholdSliderWidget.maximum = 50
    self.imageThresholdSliderWidget.value = 10
    self.imageThresholdSliderWidget.setToolTip("Set threshold value for cropping effective extent of segmented regions")
    parametersFormLayout.addRow("Cropping Threshold", self.imageThresholdSliderWidget)
    #
    # pad region
    #
    self.imagePadSliderWidget = ctk.ctkSliderWidget()
    self.imagePadSliderWidget.singleStep = 1
    self.imagePadSliderWidget.minimum = 0
    self.imagePadSliderWidget.maximum = 25
    self.imagePadSliderWidget.value = 10
    self.imagePadSliderWidget.setToolTip("Number of voxels to pad output images on each edge")
    parametersFormLayout.addRow("Pad borders", self.imagePadSliderWidget)
    
    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode()

  def onApplyButton(self):
    logic = SegmentPadSaveLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    imageThreshold = self.imageThresholdSliderWidget.value
    imagePad = self.imagePadSliderWidget.value
    logic.run(
	  self.inputSelector.currentNode(),  
	  imageThreshold, 
	  imagePad, 
	  self.outputDirectory.directory,
	  enableScreenshotsFlag)

#
# SegmentPadSaveLogic
#

class SegmentPadSaveLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def hasImageData(self,volumeNode):
    """This is an example logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      logging.debug('hasImageData failed: no volume node')
      return False
    if volumeNode.GetImageData() is None:
      logging.debug('hasImageData failed: no image data in volume node')
      return False
    return True

  def isValidInputData(self, inputVolumeNode):
    """Validates if input is valid
    """
    if not inputVolumeNode:
      logging.debug('isValidInputData failed: no input volume node defined')
      return False
    return True

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def run(self, inputVolume, imageThreshold, imagePad, outputDir, enableScreenshots=0):
    """
    Run the actual algorithm
    """

    if not self.isValidInputData(inputVolume):
      slicer.util.errorDisplay('Input volume is not valid. Choose another volume.')
      return False

    logging.info('Processing started')

    # Create segmentation
    segmentationNode = slicer.vtkMRMLSegmentationNode()
    slicer.mrmlScene.AddNode(segmentationNode)
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(inputVolume)

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

    #Create seed segment outside brain
    tissueSeedPositions = [[33,57,-11], [-29, 56.7, -11], [66,46.5,-21], [-60,44,-21], [9,105,-70], [9,59.5,-94.5], [9,-65.3,-91]]
    append2 = vtk.vtkAppendPolyData()
    for tissueSeedPosition in tissueSeedPositions:
      tissueSeed = vtk.vtkSphereSource()
      tissueSeed.SetCenter(tissueSeedPosition)
      tissueSeed.SetRadius(10)
      tissueSeed.Update()
      append2.AddInputData(tissueSeed.GetOutput())

    append2.Update()
    tissueSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append2.GetOutput(), 'Tissue', [0.0,1.0,0.0])

    #Create seed segment in background
    backgroundSeedPositions = [[80, 83, 0], [-73, 90, 0], [0, 123, 0.9], [0, -103, -114], [59, 7, 100], [-60, 7, 101], [-3, 124, 83], [-3, -106, 83]]
    append3 = vtk.vtkAppendPolyData()
    for backgroundSeedPosition in backgroundSeedPositions:
        backgroundSeed = vtk.vtkSphereSource()
        backgroundSeed.SetCenter(backgroundSeedPosition)
        backgroundSeed.SetRadius(15)
        backgroundSeed.Update()
    
    append3.AddInputData(backgroundSeed.GetOutput())
    append3.Update()
    backgroundSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append3.GetOutput(), 'Background', [0.0,0.0,1.0])

    #Analysis
    ################################################
    #Create segment editor to get access to effects
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    #segmentEditorWidget.show()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
    slicer.mrmlScene.AddNode(segmentEditorNode)
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setMasterVolumeNode(inputVolume)


    #Segment image
    segmentEditorWidget.setActiveEffectByName('Grow from seeds')
    effect = segmentEditorWidget.activeEffect()
    effect.self().onPreview()
    effect.self().onApply()

    #Set up masking parameters
    segmentEditorWidget.setActiveEffectByName('Mask volume')
    effect = segmentEditorWidget.activeEffect()
    # set fill value to be outside the valid intensity range
    intensityRange = inputVolume.GetImageData().GetScalarRange()
    effect.setParameter("FillValue", str(intensityRange[0]-1))
    # Blank out voxels that are outside the segment
    effect.setParameter("Operation", "FILL_OUTSIDE")
    # Create a volume that will store temporary masked volumes
    maskedVolume = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode', 'Temporary masked volume')
    effect.self().outputVolumeSelector.setCurrentNode(maskedVolume)

    # Mask, crop with threshold, and save each segment
    #set threshold for 
    threshold = 0
    padValue = 30
    padRegion = [10,10,10]
    for segmentIndex in range(segmentationNode.GetSegmentation().GetNumberOfSegments()):
        # Set active segment
        segmentID = segmentationNode.GetSegmentation().GetNthSegmentID(segmentIndex)
        segmentEditorWidget.setCurrentSegmentID(segmentID)
        # Apply mask
        effect.self().onApply()
        # Crop to region greater than threshold
        img = slicer.modules.segmentations.logic().CreateOrientedImageDataFromVolumeNode(maskedVolume) 
        img.UnRegister(None) 
        extent=[0,0,0,0,0,0]
        vtkSegmentationCore.vtkOrientedImageDataResample.CalculateEffectiveExtent(img, extent, threshold) 
        croppedImg = vtkSegmentationCore.vtkOrientedImageData() 
        vtkSegmentationCore.vtkOrientedImageDataResample.CopyImage(img, croppedImg, extent) 
        slicer.modules.segmentations.logic().CopyOrientedImageDataToVolumeNode(croppedImg, maskedVolume)
        #Apply pad
        inputImage = sitkUtils.PullVolumeFromSlicer(maskedVolume)
        padFilter = sitk.ConstantPadImageFilter()
        padFilter.SetPadUpperBound(padRegion)
        padFilter.SetPadLowerBound(padRegion)
        padFilter.SetConstant(padValue)
        outputImage = padFilter.Execute(inputImage)
        sitkUtils.PushVolumeToSlicer(outputImage,maskedVolume)
        #Save cropped, padded segment
        filename = outputDir + "/" + segmentID + '.nrrd'
        slicer.util.saveNode(maskedVolume, filename)
  
    #Clean up
    slicer.mrmlScene.RemoveNode(segmentEditorNode)
    slicer.mrmlScene.RemoveNode(maskedVolume)

    # Capture screenshot
    if enableScreenshots:
      self.takeScreenshot('SegmentPadSaveTest-Start','MyScreenshot',-1)

    logging.info('Processing completed')

    return True


class SegmentPadSaveTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SegmentPadSave1()

  def test_SegmentPadSave1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = SegmentPadSaveLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
