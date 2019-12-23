import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

import SemiLandmark
import re
import csv
#
# TransferSemiLandmarks
#

class TransferSemiLandmarks(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "TransferSemiLandmarks" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Labs"]
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
# TransferSemiLandmarksWidget
#

class TransferSemiLandmarksWidget(ScriptedLoadableModuleWidget):
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
    self.sampleRate.setToolTip("Select sample rate for semi-landmark interpolarion")
    parametersFormLayout.addRow("Sample rate for segmentation:", self.sampleRate)
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate TransferSemiLandmarkss."
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
    logic = TransferSemiLandmarksLogic()
    logic.run(self.meshDirectory.currentPath, self.landmarkDirectory.currentPath, self.gridFile.currentPath,
      self.outputDirectory.currentPath, int(self.sampleRate.value))
    
#
# TransferSemiLandmarksLogic
#

class TransferSemiLandmarksLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, meshDirectory, lmDirectory, gridFileName, ouputDirectory, sampleRate):
    SLLogic=SemiLandmark.SemiLandmarkLogic()
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
            lmFilePath = os.path.join(lmDirectory, lmFileName)
            landmarkNode = slicer.util.loadMarkupsFiducialList(lmFilePath)
            landmarkNumber=landmarkNode.GetNumberOfControlPoints()
            for n in range(landmarkNumber):
              landmarkNode.SetNthControlPointLabel(n, str(n+1)) 
            for triangle in gridVertices:
              newNode = SLLogic.run(meshNode, landmarkNode, triangle, sampleRate)
            nodeList = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsFiducialNode")
            mergedLandmarkNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', meshFileName+'_merged')
            success = SLLogic.mergeList(nodeList, landmarkNode, meshNode, sampleRate, mergedLandmarkNode)
            print("Number of merged landmark points", mergedLandmarkNode.GetNumberOfFiducials())
            if not success:
              print("Something went wrong in SemilandmarkLogic.merge")
            outputFileName = meshFileName + '_merged.fcsv'
            outputFilePath = os.path.join(ouputDirectory, outputFileName) 
            slicer.util.saveNode(mergedLandmarkNode, outputFilePath)
            slicer.mrmlScene.Clear(0)
          
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


class TransferSemiLandmarksTest(ScriptedLoadableModuleTest):
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
    self.test_TransferSemiLandmarks1()
  
  def test_TransferSemiLandmarks1(self):
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
    logic = TransferSemiLandmarksLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')



