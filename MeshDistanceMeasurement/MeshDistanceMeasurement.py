import os
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import  numpy as np
import vtk.util.numpy_support as vtk_np

import re
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
    self.baseSLMSelect.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelectBaseSLM)
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
  def mergeLandmarks(self, lmNode, slmNode):
    """Merge landmark and semi-landmark nodes into a new combined node."""
    mergedNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', 'MergedLandmarks')
    for i in range(lmNode.GetNumberOfControlPoints()):
      p = lmNode.GetNthControlPointPosition(i)
      mergedNode.AddControlPoint(p)
    for i in range(slmNode.GetNumberOfControlPoints()):
      p = slmNode.GetNthControlPointPosition(i)
      mergedNode.AddControlPoint(p)
    return mergedNode

  @staticmethod
  def _stripExtension(filename):
    """Strip extension, handling compound .mrk.json correctly."""
    stem, ext = os.path.splitext(filename)
    if ext.lower() == '.json' and stem.lower().endswith('.mrk'):
      stem = stem[:-4]
    return stem

  def findCorrespondingFilePath(self, searchDirectory, templateFileName):
    fileList = os.listdir(searchDirectory)
    # Extract the stem (filename without extension) for matching
    templateStem = self._stripExtension(templateFileName)
    for filename in fileList:
      fileStem = self._stripExtension(filename)
      if templateStem == fileStem:
        return os.path.join(searchDirectory, filename), templateStem
    # No exact match found - try numeric ID matching as fallback
    regex = re.compile(r'\d+')
    matches = regex.findall(templateFileName)
    if not matches:
      return None, None
    subjectID = matches[0]
    # Use word-boundary match to avoid e.g. "1" matching "10" or "11"
    idPattern = re.compile(r'(?<!\d)' + re.escape(subjectID) + r'(?!\d)')
    for filename in fileList:
      if idPattern.search(self._stripExtension(filename)):
        return os.path.join(searchDirectory, filename), subjectID
    return None, None


  def run(self, templateMesh, templateLM, templateSLM, meshDirectory, lmDirectory, slmDirectory, outDirectory, signedDistanceOption):

    if(bool(templateSLM) and bool(slmDirectory)):
      templateLMTotal = self.mergeLandmarks(templateLM, templateSLM)
    else:
      templateLMTotal = templateLM
    #get template points as vtk array
    templatePoints = vtk.vtkPoints()
    for i in range(templateLMTotal.GetNumberOfControlPoints()):
      p = templateLMTotal.GetNthControlPointPosition(i)
      templatePoints.InsertNextPoint(p)

    # write selected triangles to table
    tableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Mesh RMSE')
    col1=tableNode.AddColumn()
    col1.SetName('Subject ID')
    col2=tableNode.AddColumn()
    col2.SetName('Mesh RMSE')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)
    tableNode.SetColumnType('Mesh RMSE',vtk.VTK_STRING)

    subjectCount = 0
    for meshFileName in os.listdir(meshDirectory):
      if(not meshFileName.startswith(".")):
        #get corresponding landmarks
        result = self.findCorrespondingFilePath(lmDirectory, meshFileName)
        if result[0] is None:
          logging.warning(f"No landmark file found for {meshFileName}, skipping")
          continue
        lmFilePath, subjectID = result
        currentLMNode = slicer.util.loadMarkups(lmFilePath)
        currentSLMNode = None
        if bool(slmDirectory): # add semi-landmarks if present
          slmFilePath, sID = self.findCorrespondingFilePath(slmDirectory, meshFileName)
          if(slmFilePath):
            currentSLMNode = slicer.util.loadMarkups(slmFilePath)
            currentLMTotal = self.mergeLandmarks(currentLMNode, currentSLMNode)
          else:
            slicer.mrmlScene.RemoveNode(currentLMNode)
            if templateLMTotal is not templateLM:
              slicer.mrmlScene.RemoveNode(templateLMTotal)
            logging.error(f"No semi-landmark file found for {meshFileName}")
            return False
        else:
          currentLMTotal = currentLMNode
          # if mesh and lm file with same subject id exist, load into scene
        meshFilePath = os.path.join(meshDirectory, meshFileName)
        currentMeshNode = slicer.util.loadModel(meshFilePath)

        #get subject points into vtk array
        subjectPoints = vtk.vtkPoints()
        for i in range(currentLMTotal.GetNumberOfControlPoints()):
          p = currentLMTotal.GetNthControlPointPosition(i)
          subjectPoints.InsertNextPoint(p)

        if subjectPoints.GetNumberOfPoints() != templatePoints.GetNumberOfPoints():
          logging.warning(f"Control point count mismatch for {meshFileName}: "
            f"expected {templatePoints.GetNumberOfPoints()}, got {subjectPoints.GetNumberOfPoints()}. Skipping.")
          slicer.mrmlScene.RemoveNode(currentMeshNode)
          slicer.mrmlScene.RemoveNode(currentLMNode)
          if currentLMTotal is not currentLMNode:
            slicer.mrmlScene.RemoveNode(currentLMTotal)
          if currentSLMNode:
            slicer.mrmlScene.RemoveNode(currentSLMNode)
          continue

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
        meanDistance = self.rmse(distanceArray)

        #save output distance map
        outputNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode","ouputDistanceMap")
        outputNode.SetAndObservePolyData(distanceMap)
        outputFilename = os.path.join(outDirectory, str(subjectID) + '.vtp')
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
        if currentLMTotal is not currentLMNode:
          slicer.mrmlScene.RemoveNode(currentLMTotal)
        if bool(slmDirectory) and currentSLMNode:
          slicer.mrmlScene.RemoveNode(currentSLMNode)

    # clean up template merged node
    if templateLMTotal is not templateLM:
      slicer.mrmlScene.RemoveNode(templateLMTotal)

  def rmse(self, vtkArray):
    numpyArray = vtk_np.vtk_to_numpy(vtkArray)
    return np.sqrt(np.square(numpyArray).mean())

