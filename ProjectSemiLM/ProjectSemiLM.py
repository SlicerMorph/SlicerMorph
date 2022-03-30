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
# ProjectSemiLM
#

class ProjectSemiLM(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ProjectSemiLM" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module takes a semi-landmark file from a template image and transfers the semi-landmarks to a group of specimen using TPS and projection.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ProjectSemiLM">online documentation.</a>.</p>
      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  # It is always recommended to provide sample data for users to make it easy to try the module,
  # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  # To ensure that the source code repository remains small (can be downloaded and installed quickly)
  # it is recommended to store data sets that are larger than a few MB in a Github release.

  # TemplateKey1
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey1',
    # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
    # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey1.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
    fileNames='TemplateKey1.nrrd',
    # Checksum to ensure file integrity. Can be computed by this command:
    #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
    checksums = 'SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey1'
  )

  # TemplateKey2
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey2',
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey2.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
    fileNames='TemplateKey2.nrrd',
    checksums = 'SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey2'
  )


#
# ProjectSemiLMWidget
#

class ProjectSemiLMWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.applyButton.enabled = bool (self.meshDirectory.currentPath and self.landmarkDirectory.currentPath and
      self.modelSelector.currentNode() and self.baseLMSelect.currentNode() and self.baseSLMSelect.currentNode()
      and self.outputDirectory.currentPath)

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
    # Select base mesh
    #
    self.modelSelector = slicer.qMRMLNodeComboBox()
    self.modelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.modelSelector.selectNodeUponCreation = False
    self.modelSelector.addEnabled = False
    self.modelSelector.removeEnabled = False
    self.modelSelector.noneEnabled = True
    self.modelSelector.showHidden = False
    self.modelSelector.setMRMLScene( slicer.mrmlScene )
    parametersFormLayout.addRow("Base mesh: ", self.modelSelector)

    #
    # Select base landmark file
    #
    #self.baseLMFile=ctk.ctkPathLineEdit()
    #self.baseLMFile.setToolTip( "Select file specifying base landmarks" )
    #parametersFormLayout.addRow("Base landmark file: ", self.baseLMFile)
    self.baseLMSelect = slicer.qMRMLNodeComboBox()
    self.baseLMSelect.nodeTypes = ( ('vtkMRMLMarkupsFiducialNode'), "" )
    self.baseLMSelect.selectNodeUponCreation = False
    self.baseLMSelect.addEnabled = False
    self.baseLMSelect.removeEnabled = False
    self.baseLMSelect.noneEnabled = True
    self.baseLMSelect.showHidden = False
    self.baseLMSelect.showChildNodeTypes = False
    self.baseLMSelect.setMRMLScene( slicer.mrmlScene )
    parametersFormLayout.addRow("Base landmarks: ", self.baseLMSelect)

    #
    # Select base semi-landmark file
    #
    #self.semiLMFile=ctk.ctkPathLineEdit()
    #self.semiLMFile.setToolTip( "Select file containing base semi-landmarks " )
    #parametersFormLayout.addRow("Base semi-landmark file: ", self.semiLMFile)
    self.baseSLMSelect = slicer.qMRMLNodeComboBox()
    self.baseSLMSelect.nodeTypes = ( ('vtkMRMLMarkupsFiducialNode'), "" )
    self.baseSLMSelect.selectNodeUponCreation = False
    self.baseSLMSelect.addEnabled = False
    self.baseSLMSelect.removeEnabled = False
    self.baseSLMSelect.noneEnabled = True
    self.baseSLMSelect.showHidden = False
    self.baseSLMSelect.showChildNodeTypes = False
    self.baseSLMSelect.setMRMLScene( slicer.mrmlScene )
    parametersFormLayout.addRow("Base semi-landmarks: ", self.baseSLMSelect)

    #
    # Select meshes directory
    #
    self.meshDirectory=ctk.ctkPathLineEdit()
    self.meshDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.meshDirectory.setToolTip( "Select directory containing meshes" )
    parametersFormLayout.addRow("Mesh directory: ", self.meshDirectory)

    #
    # Select landmarks directory
    #
    self.landmarkDirectory=ctk.ctkPathLineEdit()
    self.landmarkDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.landmarkDirectory.setToolTip( "Select directory containing landmarks" )
    parametersFormLayout.addRow("Landmark directory: ", self.landmarkDirectory)

    #
    # Select output directory
    #
    self.outputDirectory=ctk.ctkPathLineEdit()
    self.outputDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.outputDirectory.setToolTip( "Select directory for output models: " )
    parametersFormLayout.addRow("Output directory: ", self.outputDirectory)

    #
    # Set projection scale
    #
    self.scaleProjection = ctk.ctkSliderWidget()
    self.scaleProjection.singleStep = 1
    self.scaleProjection.minimum = 0
    self.scaleProjection.maximum = 100
    self.scaleProjection.value = 10
    self.scaleProjection.setToolTip("Set scale of maximum point projection")
    parametersFormLayout.addRow("Projection scale: ", self.scaleProjection)

    #
    # Select output extension
    #
    self.JSONType=qt.QRadioButton()
    self.JSONType.setChecked(True)
    parametersFormLayout.addRow("MRK.JSON output: ", self.JSONType)
    self.FCSVType=qt.QRadioButton()
    parametersFormLayout.addRow("FCSV output: ", self.FCSVType)


    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate ProjectSemiLMs."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.baseLMSelect.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.baseSLMSelect.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.meshDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.landmarkDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.outputDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass


  def onApplyButton(self):
    logic = ProjectSemiLMLogic()
    if self.JSONType.checked:
      extensionForOutput = '.mrk.json'
    else:
      extensionForOutput = '.fcsv'
    logic.run(self.modelSelector.currentNode(), self.baseLMSelect.currentNode(), self.baseSLMSelect.currentNode(), self.meshDirectory.currentPath,
      self.landmarkDirectory.currentPath, self.outputDirectory.currentPath, extensionForOutput, self.scaleProjection.value)

#
# ProjectSemiLMLogic
#

class ProjectSemiLMLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, baseMeshNode, baseLMNode, semiLMNode, meshDirectory, lmDirectory, ouputDirectory, outputExtension, scaleProjection):
    SLLogic=CreateSemiLMPatches.CreateSemiLMPatchesLogic()
    targetPoints = vtk.vtkPoints()
    point=[0,0,0]
    # estimate a sample size usingn semi-landmark spacing
    sampleArray=np.zeros(shape=(25,3))
    for i in range(25):
      semiLMNode.GetMarkupPoint(0,i,point)
      sampleArray[i,:]=point
    sampleDistances = self.distanceMatrix(sampleArray)
    minimumMeshSpacing = sampleDistances[sampleDistances.nonzero()].min(axis=0)
    rayLength = minimumMeshSpacing * (scaleProjection)


    for i in range(baseLMNode.GetNumberOfFiducials()):
      baseLMNode.GetMarkupPoint(0,i,point)
      targetPoints.InsertNextPoint(point)


    for meshFileName in os.listdir(meshDirectory):
      if(not meshFileName.startswith(".")):
        print (meshFileName)
        lmFileList = os.listdir(lmDirectory)
        meshFilePath = os.path.join(meshDirectory, meshFileName)
        regex = re.compile(r'\d+')
        subjectID = [int(x) for x in regex.findall(meshFileName)][0]
        for lmFileName in lmFileList:
          if str(subjectID) in lmFileName:
            # if mesh and lm file with same subject id exist, load into scene
            currentMeshNode = slicer.util.loadModel(meshFilePath)
            lmFilePath = os.path.join(lmDirectory, lmFileName)
            success, currentLMNode = slicer.util.loadMarkupsFiducialList(lmFilePath)

            # set up transform between base lms and current lms
            sourcePoints = vtk.vtkPoints()
            for i in range(currentLMNode.GetNumberOfMarkups()):
              currentLMNode.GetMarkupPoint(0,i,point)
              sourcePoints.InsertNextPoint(point)

            transform = vtk.vtkThinPlateSplineTransform()
            transform.SetSourceLandmarks( sourcePoints )
            transform.SetTargetLandmarks( targetPoints )
            transform.SetBasisToR()  # for 3D transform

            transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
            transformNode.SetAndObserveTransformToParent(transform)

            # apply transform to the current surface mesh
            currentMeshNode.SetAndObserveTransformNodeID(transformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(currentMeshNode)

            # project semi-landmarks
            resampledLandmarkNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', meshFileName+'_SL_warped')
            success = SLLogic.projectPoints(baseMeshNode, currentMeshNode, semiLMNode, resampledLandmarkNode, rayLength)

            transformNode.Inverse()
            resampledLandmarkNode.SetAndObserveTransformNodeID(transformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(resampledLandmarkNode)

            # transfer point data
            for index in range(semiLMNode.GetNumberOfControlPoints()):
              fiducialLabel = semiLMNode.GetNthControlPointLabel(index)
              fiducialDescription = semiLMNode.GetNthControlPointDescription(index)
              resampledLandmarkNode.SetNthControlPointLabel(index, fiducialLabel)
              resampledLandmarkNode.SetNthControlPointDescription(index,fiducialDescription)

            # save output file
            outputFileName = meshFileName + '_SL_warped' + outputExtension
            outputFilePath = os.path.join(ouputDirectory, outputFileName)
            slicer.util.saveNode(resampledLandmarkNode, outputFilePath)

            # clean up
            slicer.mrmlScene.RemoveNode(resampledLandmarkNode)
            slicer.mrmlScene.RemoveNode(currentLMNode)
            slicer.mrmlScene.RemoveNode(currentMeshNode)
            slicer.mrmlScene.RemoveNode(transformNode)


  def distanceMatrix(self, a):
    """
    Computes the euclidean distance matrix for n points in a 3D space
    Returns a nXn matrix
     """
    id,jd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1))
    dx=fnx(a[:,0])
    dy=fnx(a[:,1])
    dz=fnx(a[:,2])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

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


class ProjectSemiLMTest(ScriptedLoadableModuleTest):
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
    self.test_ProjectSemiLM1()

  def test_ProjectSemiLM1(self):
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

    logic = ProjectSemiLMLogic()

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
