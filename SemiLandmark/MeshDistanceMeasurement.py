import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

import re
import csv
#
# MeshDistanceMeasurement
#

class MeshDistanceMeasurement(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "MeshDistanceMeasurement" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module takes a semi-landmark file from a template image and transfers the semi-landmarks to a group of specimen using TPS and projection.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
      3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

#
# MeshDistanceMeasurementWidget
#

class MeshDistanceMeasurementWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.applyButton.enabled = bool (self.meshDirectory.currentPath and self.landmarkDirectory.currentPath and self.modelSelector.currentNode() and self.baseLMSelect.currentNode()) and (bool(self.semilandmarkDirectory.currentPath)==bool(self.baseSLMSelect.currentNode()))
  
  def onSelectBaseSLM(self):
    self.semilandmarkDirectory.enabled = bool(self.baseSLMSelect.currentNode())
    self.applyButton.enabled = bool (self.meshDirectory.currentPath and self.landmarkDirectory.currentPath and self.modelSelector.currentNode() and self.baseLMSelect.currentNode()) and (bool(self.semilandmarkDirectory.currentPath)==bool(self.baseSLMSelect.currentNode()))
    
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
    #self.baseLMFile=ctk.ctkPathLineEdit()
    #self.baseLMFile.setToolTip( "Select file specifying base landmarks" )
    #parametersFormLayout.addRow("Base landmark file: ", self.baseLMFile)
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
    # Select semi-landmarks directory
    #
    self.semilandmarkDirectory=ctk.ctkPathLineEdit()
    self.semilandmarkDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.semilandmarkDirectory.setToolTip( "Select directory containing semi-landmarks" )
    self.semilandmarkDirectory.enabled = False
    parametersFormLayout.addRow("Semi-landmark directory: ", self.semilandmarkDirectory)
    
    #
    # Select output directory
    #
    self.outputDirectory=ctk.ctkPathLineEdit()
    self.outputDirectory.filters = ctk.ctkPathLineEdit.Dirs
    self.outputDirectory.currentPath = slicer.app.temporaryPath
    self.outputDirectory.setToolTip( "Select directory to save output distance maps" )
    parametersFormLayout.addRow("Output directory: ", self.outputDirectory)
    
    #
    # Select distance metric
    #
    self.unSignedDistanceOption=qt.QRadioButton()
    self.unSignedDistanceOption.setChecked(True)
    parametersFormLayout.addRow("Unsigned Distance: ", self.unSignedDistanceOption)
    self.signedDistanceOption=qt.QRadioButton()
    self.signedDistanceOption.setChecked(False)
    parametersFormLayout.addRow("Signed Distance: ", self.signedDistanceOption)
    
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate MeshDistanceMeasurements."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)
    
    # connections
    self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.baseLMSelect.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.meshDirectory.connect('validInputChanged(bool)', self.onSelect)
    self.baseSLMSelect.connect('currentNodeChanged(bool)', self.onSelectBaseSLM) 
    self.semilandmarkDirectory.connect('validInputChanged(bool)', self.onSelect)
    
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    
    # Add vertical spacer
    self.layout.addStretch(1)
  
  def cleanup(self):
    pass
  
  
  def onApplyButton(self):
    logic = MeshDistanceMeasurementLogic()
    logic.run(self.modelSelector.currentNode(), self.baseLMSelect.currentNode(), self.baseSLMSelect.currentNode(), self.meshDirectory.currentPath,
      self.landmarkDirectory.currentPath, self.semilandmarkDirectory.currentPath, self.outputDirectory.currentPath, self.signedDistanceOption.checked)
    
#
# MeshDistanceMeasurementLogic
#

class MeshDistanceMeasurementLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def mergeLandmarks(self, templateLM, templateSLM):
    landmarkPoint = [0,0,0]
    for landmarkIndex in range(templateLM.GetNumberOfMarkups()):
      templateLM.GetMarkupPoint(0,landmarkIndex,landmarkPoint)
      templateSLM.AddFiducialFromArray(landmarkPoint)
    return templateSLM
    
  def findCorrespondingFilePath(self, searchDirectory, templateFileName):
    fileList = os.listdir(searchDirectory)  
    regex = re.compile(r'\d+')
    subjectID = [int(x) for x in regex.findall(templateFileName)][0]
    for filename in fileList:
      if str(subjectID) in filename:
        return os.path.join(searchDirectory, filename)
        
        
  def run(self, templateMesh, templateLM, templateSLM, meshDirectory, lmDirectory, slmDirectory, outDirectory, signedDistanceOption):
    
    if(bool(templateSLM) and bool(slmDirectory)):
      templateLMTotal = self.mergeLandmarks(templateLM, templateSLM)
    else:
      templateLMTotal = templateLM
    #get template points as vtk array
    templatePoints = vtk.vtkPoints()
    p=[0,0,0]
    for i in range(templateLMTotal.GetNumberOfMarkups()):
      templateLMTotal.GetMarkupPoint(0,i,p)
      templatePoints.InsertNextPoint(p)
     
    # write selected triangles to table
    tableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Mean Mesh Distances')
    col1=tableNode.AddColumn()
    col1.SetName('Subject ID')
    col2=tableNode.AddColumn()
    col2.SetName('Mesh RMSE')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)
    tableNode.SetColumnType('Mean Mesh Distance',vtk.VTK_STRING)
     
    subjectCount = 0
    for meshFileName in os.listdir(meshDirectory):
      if(not meshFileName.startswith(".")):
        #get corresponding landmarks
        lmFilePath = self.findCorrespondingFilePath(lmDirectory, meshFileName)
        if(lmFilePath):
          currentLMNode = slicer.util.loadMarkupsFiducialList(lmFilePath)
          if bool(slmDirectory): # add semi-landmarks if present
            slmFilePath = self.findCorrespondingFilePath(slmDirectory, meshFileName)
            if(slmFilePath):
              currentSLMNode = slicer.util.loadMarkupsFiducialList(slmFilePath)
              currentLMTotal = self.mergeLandmarks(templateLM, currentSLMNode)
            else:
              print("problem with reading semi-landmarks")
              return False
          else:
            currentLMTotal = currentLMNode
        else:
          print("problem with reading landmarks")
          return False
          # if mesh and lm file with same subject id exist, load into scene
        meshFilePath = os.path.join(meshDirectory, meshFileName)
        currentMeshNode = slicer.util.loadModel(meshFilePath)
                
        #get subject points into vtk array
        subjectPoints = vtk.vtkPoints()
        p=[0,0,0]
        for i in range(currentLMTotal.GetNumberOfMarkups()):
          currentLMTotal.GetMarkupPoint(0,i,p)
          subjectPoints.InsertNextPoint(p)
          
        transform = vtk.vtkThinPlateSplineTransform()
        transform.SetSourceLandmarks( subjectPoints )
        transform.SetTargetLandmarks( templatePoints )
        transform.SetBasisToR()  # for 3D transform
        
        transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
        transformNode.SetAndObserveTransformToParent(transform)
        
        currentMeshNode.SetAndObserveTransformNodeID(transformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(currentMeshNode)
        
        distanceFilter = vtk.vtkDistancePolyDataFilter()
        distanceFilter.SetInputData(0,templateMesh.GetPolyData())
        distanceFilter.SetInputData(1,currentMeshNode.GetPolyData())
        distanceFilter.SetSignedDistance(signedDistanceOption)
        distanceFilter.Update()

        distanceMap = distanceFilter.GetOutput()
        distanceArray = distanceMap.GetPointData().GetArray('Distance')
        #meanDistance = np.average(distanceArray)
        meanDistance = self.rmse(distanceArray)
        
        #save output distance map
        outputNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode","ouputDistanceMap")
        outputNode.SetAndObservePolyData(distanceMap)
        outputFilename = os.path.join(outDirectory, str(subjectID) + '.ply') 
        slicer.util.saveNode(outputNode, outputFilename) 
        
        #update table and subjectCount
        tableNode.AddEmptyRow()
        tableNode.SetCellText(subjectCount,0,str(subjectID))
        tableNode.SetCellText(subjectCount,1,str(meanDistance))
        subjectCount+=1
        
        # clean up
        slicer.mrmlScene.RemoveNode(outputNode)
        slicer.mrmlScene.RemoveNode(transformNode)
        slicer.mrmlScene.RemoveNode(currentMeshNode)
        slicer.mrmlScene.RemoveNode(currentLMNode)

  def rmse(self, signedDistanceArray):
    return np.sqrt((np.square(signedDistanceArray).mean()))
    
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


class MeshDistanceMeasurementTest(ScriptedLoadableModuleTest):
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
    self.test_MeshDistanceMeasurement1()
  
  def test_MeshDistanceMeasurement1(self):
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
    logic = MeshDistanceMeasurementLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')



