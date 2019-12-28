import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

#
# VolumeToMesh
#

class VolumeToMesh(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "VolumeToMesh" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module takes a directory of volumes and segments them using a user-supplied threshold value. The output segments are converted to models and saved in the 
      output directory.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
      3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

#
# VolumeToMeshWidget
#

class VolumeToMeshWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelectInput(self):
    self.applyButton.enabled = bool (self.inputDirectory.currentPath and self.outputDirectory.currentPath)
  
  def onSelectOutput(self):
    self.applyButton.enabled = bool (self.inputDirectory.currentPath and self.outputDirectory.currentPath)
        
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
    
    self.inputDirectory=ctk.ctkPathLineEdit()
    self.inputDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.inputDirectory.setToolTip( "Select directory containing volumes" )
    parametersFormLayout.addRow("Input directory: ", self.inputDirectory)

    # Select output directory
    self.outputDirectory=ctk.ctkPathLineEdit()
    self.outputDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.outputDirectory.setToolTip( "Select directory for output models: " )
    parametersFormLayout.addRow("Output directory: ", self.outputDirectory)

    #
    # Select the extension type
    #
    self.extensionOptionGZ = qt.QRadioButton(".nii.gz")
    self.extensionOptionGZ.setChecked(True)
    parametersFormLayout.addRow("Select extension type: ", self.extensionOptionGZ)
    
    #
    # set threshold value
    #
    self.threshold = ctk.ctkDoubleSpinBox()
    self.threshold.singleStep = 1
    self.threshold.minimum = 0
    self.threshold.maximum = 100000
    self.threshold.setDecimals(0)
    self.threshold.value = 500
    self.threshold.setToolTip("Select threshold for segmentation of volume")
    parametersFormLayout.addRow("Threshold for segmentation:", self.threshold)
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate VolumeToMeshs."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)
    
    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)
    

    
    # connections
    self.inputDirectory.connect('validInputChanged(bool)', self.onSelectInput)
    self.outputDirectory.connect('validInputChanged(bool)', self.onSelectOutput)
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    
    # Add vertical spacer
    self.layout.addStretch(1)
  
  def cleanup(self):
    pass
  
  
  def onApplyButton(self):
    logic = VolumeToMeshLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    extension =""
    if self.extensionOptionGZ.checked:
      extension = ".nii.gz"
    
    logic.run(self.inputDirectory.currentPath, self.outputDirectory.currentPath, extension, int(self.threshold.value))
    
#
# VolumeToMeshLogic
#

class VolumeToMeshLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, inputDirectory, outputDirectory, extension, stepThreshold):
    renderLogic = slicer.modules.volumerendering.logic()
    for file in os.listdir(inputDirectory):
      if file.endswith(extension):
        inputFile = os.path.join(inputDirectory, file)
        volumeNode =slicer.util.loadVolume(inputFile)
        labelVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
        slicer.vtkSlicerVolumesLogic().CreateLabelVolumeFromVolume(slicer.mrmlScene, labelVolumeNode, volumeNode)
        voxelArray = slicer.util.arrayFromVolume(volumeNode)
        labelVoxelArray = slicer.util.arrayFromVolume(labelVolumeNode)
        labelVoxelArray[voxelArray >= stepThreshold] = 100
        labelVoxelArray[voxelArray < stepThreshold] = 0
        slicer.util.arrayFromVolumeModified(labelVolumeNode)
        imageName = volumeNode.GetName()
        segmentationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode', imageName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelVolumeNode, segmentationNode)
        segmentID = segmentationNode.GetSegmentation().GetNthSegmentID(0)
        polydata=vtk.vtkPolyData()
        slicer.modules.segmentations.logic().GetSegmentClosedSurfaceRepresentation(segmentationNode, segmentID, polydata,1)
        normalFilter = vtk.vtkPolyDataNormals()
        normalFilter.SetInputData(polydata)
        normalFilter.SetFlipNormals(1)
        normalFilter.Update()
        polydataFlip = normalFilter.GetOutput()
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode',imageName)
        modelNode.CreateDefaultDisplayNodes()
        modelNode.SetAndObservePolyData(polydataFlip)
        outputFilename = os.path.join(outputDirectory, imageName + '.vtk')
        slicer.util.saveNode(modelNode, outputFilename) 
        slicer.mrmlScene.RemoveNode(labelVolumeNode)
        slicer.mrmlScene.RemoveNode(volumeNode)
        slicer.mrmlScene.RemoveNode(segmentationNode)
        slicer.mrmlScene.RemoveNode(modelNode)    
  

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


class VolumeToMeshTest(ScriptedLoadableModuleTest):
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
    self.test_VolumeToMesh1()
  
  def test_VolumeToMesh1(self):
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
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767',
      checksums='SHA256:12d17fba4f2e1f1a843f0757366f28c3f3e1a8bb38836f0de2a32bb1cd476560')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = VolumeToMeshLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
