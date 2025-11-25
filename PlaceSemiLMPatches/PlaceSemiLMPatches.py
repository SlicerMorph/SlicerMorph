import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

import CreateSemiLMPatches
import re
import csv
#
# PlaceSemiLMPatches
#

class PlaceSemiLMPatches(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "PlaceSemiLMPatches" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module places semi-landmark patches between anatomical landmarks as described by a user-provided connectivity file.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PlaceSemiLMPatches">online documentation.</a>.</p>
      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

#
# PlaceSemiLMPatchesWidget
#

class PlaceSemiLMPatchesWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.applyButton.enabled = bool (self.meshDirectory.currentPath and self.landmarkDirectory.currentPath and self.outputDirectory.currentPath)

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

    self.meshDirectory=ctk.ctkPathLineEdit()
    self.meshDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.meshDirectory.setToolTip( "Select directory containing landmarks" )
    parametersFormLayout.addRow("Mesh directory: ", self.meshDirectory)

    self.landmarkDirectory=ctk.ctkPathLineEdit()
    self.landmarkDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.landmarkDirectory.setToolTip( "Select directory containing meshes" )
    parametersFormLayout.addRow("Landmark directory: ", self.landmarkDirectory)

    self.gridFile=ctk.ctkPathLineEdit()
    self.gridFile.filters  = ctk.ctkPathLineEdit().Files
    self.gridFile.setToolTip( "Select file specifying semi-landmark connectivity" )
    parametersFormLayout.addRow("Grid connectivity file: ", self.gridFile)

    # Select output directory
    self.outputDirectory=ctk.ctkPathLineEdit()
    self.outputDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.outputDirectory.setToolTip( "Select directory for output models: " )
    parametersFormLayout.addRow("Output directory: ", self.outputDirectory)

    #
    # set sample rate value
    #
    self.sampleRate = ctk.ctkDoubleSpinBox()
    self.sampleRate.singleStep = 1
    self.sampleRate.minimum = 1
    self.sampleRate.maximum = 100
    self.sampleRate.setDecimals(0)
    self.sampleRate.value = 10
    self.sampleRate.setToolTip("Select sample rate for semi-landmark interpolation")
    parametersFormLayout.addRow("Sample rate for interpolation:", self.sampleRate)
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate PlaceSemiLMPatchess."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.meshDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.landmarkDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.gridFile.connect('validInputChanged(bool)', self.onSelect)
    self.outputDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass


  def onApplyButton(self):
    logic = PlaceSemiLMPatchesLogic()
    logic.run(self.meshDirectory.currentPath, self.landmarkDirectory.currentPath, self.gridFile.currentPath,
      self.outputDirectory.currentPath, int(self.sampleRate.value))

#
# PlaceSemiLMPatchesLogic
#

class PlaceSemiLMPatchesLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, meshDirectory, lmDirectory, gridFileName, ouputDirectory, sampleRate):
    smoothingIterations = 75
    maximumProjectionDistance = .75
    SLLogic=CreateSemiLMPatches.CreateSemiLMPatchesLogic()
    gridVertices = []
    with open(gridFileName) as gridFile:
      gridReader = csv.reader(gridFile)
      next(gridReader) # skip header
      for row in gridReader:
        gridVertices.append([int(row[0]),int(row[1]),int(row[2])])

    for meshFileName in os.listdir(meshDirectory):
      if(not meshFileName.startswith(".")):
        print (meshFileName)
        lmFileList = os.listdir(lmDirectory)
        meshFilePath = os.path.join(meshDirectory, meshFileName)
        regex = re.compile(r'\d+')
        subjectID = [int(x) for x in regex.findall(meshFileName)][0]
        for lmFileName in lmFileList:
          if str(subjectID) in lmFileName:
            meshNode =slicer.util.loadModel(meshFilePath)
            smoothNormalArray = SLLogic.getSmoothNormals(meshNode,smoothingIterations)
            lmFilePath = os.path.join(lmDirectory, lmFileName)
            [success, landmarkNode] = slicer.util.loadMarkupsFiducialList(lmFilePath)
            landmarkNumber=landmarkNode.GetNumberOfControlPoints()
            for n in range(landmarkNumber):
              landmarkNode.SetNthControlPointLabel(n, str(n+1))
            for triangle in gridVertices:
              newNode = SLLogic.applyPatch(meshNode, landmarkNode, triangle, sampleRate, smoothNormalArray, maximumProjectionDistance)
            nodeList = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsFiducialNode")
            mergedLandmarkNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', meshFileName+'_merged')
            success = SLLogic.mergeList(nodeList, landmarkNode, meshNode, sampleRate, mergedLandmarkNode)
            print("Number of merged landmark points", mergedLandmarkNode.GetNumberOfControlPoints())
            if not success:
              print("Something went wrong in CreateSemiLMPatchesLogic.merge")
            #Set all landmarks to semilandmark type
            landmarkTypeSemi=True
            self.setAllLandmarksType(mergedLandmarkNode, landmarkTypeSemi)

            outputFileName = meshFileName + '_merged.fcsv'
            outputFilePath = os.path.join(ouputDirectory, outputFileName)
            slicer.util.saveNode(mergedLandmarkNode, outputFilePath)
            slicer.mrmlScene.Clear(0)

  def setAllLandmarksType(self,landmarkNode, setToSemiType):
    landmarkDescription = "Semi"
    if setToSemiType is False:
      landmarkDescription = "Fixed"
    for controlPointIndex in range(landmarkNode.GetNumberOfControlPoints()):
      landmarkNode.SetNthControlPointDescription(controlPointIndex, landmarkDescription)

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

  def process(self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """

    if not inputVolume or not outputVolume:
      raise ValueError("Input or output volume is invalid")

    import time
    startTime = time.time()
    logging.info('Processing started')

    # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
    cliParams = {
      'InputVolume': inputVolume.GetID(),
      'OutputVolume': outputVolume.GetID(),
      'ThresholdValue' : imageThreshold,
      'ThresholdType' : 'Above' if invert else 'Below'
      }
    cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
    # We don't need the CLI module node anymore, remove it to not clutter the scene with it
    slicer.mrmlScene.RemoveNode(cliNode)

    stopTime = time.time()
    logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')


class PlaceSemiLMPatchesTest(ScriptedLoadableModuleTest):
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
    self.test_PlaceSemiLMPatches1()

  def test_PlaceSemiLMPatches1(self):
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

    # Get/create input data

    import SampleData
    registerSampleData()
    inputVolume = SampleData.downloadSample('TemplateKey1')
    self.delayDisplay('Loaded test data set')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 695)

    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    threshold = 100

    # Test the module logic

    logic = PlaceSemiLMPatchesLogic()

    # Test algorithm with non-inverted threshold
    logic.process(inputVolume, outputVolume, threshold, True)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], threshold)

    # Test algorithm with inverted threshold
    logic.process(inputVolume, outputVolume, threshold, False)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')
