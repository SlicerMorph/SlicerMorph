##BASE PYTHON
import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import glob
import copy
import multiprocessing

import vtk.util.numpy_support as vtk_np

import numpy as np

## OTHER UTILS
import Open3D_utils
#import Support.DBALib as DECA_Lib

## EXTERNAL LIBRARIES - NOT PART OF BASE PYTHON
try:
  import open3d as o3d
  print('o3d installed')
except ImportError:
  slicer.util.pip_install('open3d==0.9.0')
  import open3d as o3d
  print('trying to install o3d')
try:
  from pycpd import DeformableRegistration
  print('pycpd installed')
except ImportError:
  slicer.util.pip_install('pycpd')
  print('trying to install pycpd')
  from pycpd import DeformableRegistration

#
# ALPACA
#

class ALPACA(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ALPACA" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Arthur Porto, Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module transfers landmarks from one image to a directory of images.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Arthur Porto, Sara Rolfe, and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
      3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.      

#
# ALPACAWidget
#

class ALPACAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.applyButton.enabled = bool (self.meshDirectory.currentPath and self.landmarkDirectory.currentPath and 
      self.sourceModelSelector.currentNode() and self.baseLMSelector.currentNode() and self.baseSLMSelect.currentNode() 
      and self.outputDirectory.currentPath)
          
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    
    # Set up tabs to split workflow
    tabsWidget = qt.QTabWidget()
    alignSingleTab = qt.QWidget()
    alignSingleTabLayout = qt.QFormLayout(alignSingleTab)
    alignMultiTab = qt.QWidget()
    alignMultiTabLayout = qt.QFormLayout(alignMultiTab)


    tabsWidget.addTab(alignSingleTab, "Single Alignment")
    tabsWidget.addTab(alignMultiTab, "Multiprocessing")
    self.layout.addWidget(tabsWidget)
    
    # Layout within the tab
    alignSingleWidget=ctk.ctkCollapsibleButton()
    alignSingleWidgetLayout = qt.QFormLayout(alignSingleWidget)
    alignSingleWidget.text = "Align and subsample a source and target mesh "
    alignSingleTabLayout.addRow(alignSingleWidget)
  
    #
    # Select source mesh
    #
    self.sourceModelSelector = ctk.ctkPathLineEdit()
    self.sourceModelSelector.nameFilters=["*.ply"]
    alignSingleWidgetLayout.addRow("Source mesh: ", self.sourceModelSelector)
    
    #
    # Select source landmarks
    #
    self.sourceFiducialSelector = ctk.ctkPathLineEdit()
    self.sourceFiducialSelector.nameFilters=["*.fcsv"]
    alignSingleWidgetLayout.addRow("Source landmarks: ", self.sourceFiducialSelector)
    
    # Select target mesh
    #
    self.targetModelSelector = ctk.ctkPathLineEdit()
    self.targetModelSelector.nameFilters=["*.ply"]
    alignSingleWidgetLayout.addRow("Target mesh: ", self.targetModelSelector)
    
    #
    # set voxel size used for subsampling
    #
    self.voxelSize = ctk.ctkDoubleSpinBox()
    self.voxelSize.minimum = 0
    self.voxelSize.maximum = 100
    self.voxelSize.singleStep = .1
    self.voxelSize.setDecimals(2)
    self.voxelSize.value = 0.7
    self.voxelSize.setToolTip("Choose the voxel size( in mm) to be used to subsample the source and target meshes")
    alignSingleWidgetLayout.addRow("Select subsampling voxel size:", self.voxelSize)

    [self.normalSearchRadius, self.FPFHSearchRadius, self.distanceThreshold, self.maxRANSAC, self.maxRANSACValidation, 
    self.ICPDistanceThreshold, self.alpha, self.beta, self.CPDIterations, self.CPDTolerence] = self.addAdvancedMenu(alignSingleWidgetLayout)
    
    # Advanced tab connections
    self.normalSearchRadius.connect('valueChanged(double)', self.onChangeAdvanced)
    self.FPFHSearchRadius.connect('valueChanged(double)', self.onChangeAdvanced)
    self.distanceThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
    self.maxRANSAC.connect('valueChanged(double)', self.onChangeAdvanced)
    self.maxRANSACValidation.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ICPDistanceThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
    self.alpha.connect('valueChanged(double)', self.onChangeAdvanced)
    self.beta.connect('valueChanged(double)', self.onChangeAdvanced)
    self.CPDIterations.connect('valueChanged(double)', self.onChangeAdvanced)
    self.CPDTolerence.connect('valueChanged(double)', self.onChangeAdvanced)
    
    #
    # Subsample Button
    #
    self.subsampleButton = qt.QPushButton("Run subsampling")
    self.subsampleButton.toolTip = "Run subsampling of the source and target"
    self.subsampleButton.enabled = False
    alignSingleWidgetLayout.addRow(self.subsampleButton)
    
    #
    # Subsample Information
    #
    self.subsampleInfo = qt.QPlainTextEdit()
    self.subsampleInfo.setPlaceholderText("Subsampling information")
    self.subsampleInfo.setReadOnly(True)
    alignSingleWidgetLayout.addRow(self.subsampleInfo)
    
    #
    # Align Button
    #
    self.alignButton = qt.QPushButton("Run rigid alignment")
    self.alignButton.toolTip = "Run rigid alignment of the source and target"
    self.alignButton.enabled = False
    alignSingleWidgetLayout.addRow(self.alignButton)
    
    #
    # Plot Aligned Mesh Button
    #
    self.displayMeshButton = qt.QPushButton("Display rigidly aligned meshes")
    self.displayMeshButton.toolTip = "Display rigid alignment of the source and target meshes"
    self.displayMeshButton.enabled = False
    alignSingleWidgetLayout.addRow(self.displayMeshButton)
    
    #
    # Coherent point drift registration
    #
    self.CPDRegistrationButton = qt.QPushButton("Run CPD non-rigid registration")
    self.CPDRegistrationButton.toolTip = "Coherent point drift registration between source and target meshes"
    self.CPDRegistrationButton.enabled = False
    alignSingleWidgetLayout.addRow(self.CPDRegistrationButton)
    
    #
    # DECA registration
    #
    #self.DECAButton = qt.QPushButton("Run DeCA non-rigid registration")
    #self.DECAButton.toolTip = "DeCA registration between source and target meshes"
    #self.DECAButton.enabled = False
    #alignSingleWidgetLayout.addRow(self.DECAButton)
    
    #
    # Coherent point drift registration
    #
    self.displayWarpedModelButton = qt.QPushButton("Show registered source model")
    self.displayWarpedModelButton.toolTip = "Show CPD warping applied to source model"
    self.displayWarpedModelButton.enabled = False
    alignSingleWidgetLayout.addRow(self.displayWarpedModelButton)
    
    # connections
    self.sourceModelSelector.connect('validInputChanged(bool)', self.onSelect)
    self.sourceFiducialSelector.connect('validInputChanged(bool)', self.onSelect)
    self.targetModelSelector.connect('validInputChanged(bool)', self.onSelect)
    self.voxelSize.connect('validInputChanged(bool)', self.onVoxelSizeChange)
    self.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)
    self.alignButton.connect('clicked(bool)', self.onAlignButton)
    self.displayMeshButton.connect('clicked(bool)', self.onDisplayMeshButton)
    self.CPDRegistrationButton.connect('clicked(bool)', self.onCPDRegistration)
    #self.DECAButton.connect('clicked(bool)', self.onDECARegistration)
    self.displayWarpedModelButton.connect('clicked(bool)', self.onDisplayWarpedModel)
    
    # Layout within the multiprocessing tab
    alignMultiWidget=ctk.ctkCollapsibleButton()
    alignMultiWidgetLayout = qt.QFormLayout(alignMultiWidget)
    alignMultiWidget.text = "Transfer landmark points from a source mesh to a directory of target meshes "
    alignMultiTabLayout.addRow(alignMultiWidget)
  
    #
    # Select source mesh
    #
    self.sourceModelMultiSelector = ctk.ctkPathLineEdit()
    self.sourceModelMultiSelector.nameFilters=["*.ply"]
    self.sourceModelMultiSelector.toolTip = "Select the source mesh"
    alignMultiWidgetLayout.addRow("Source mesh: ", self.sourceModelMultiSelector)
    
    #
    # Select source landmark file
    #
    self.sourceFiducialMultiSelector = ctk.ctkPathLineEdit()
    self.sourceFiducialMultiSelector.nameFilters=["*.fcsv"]
    self.sourceFiducialMultiSelector.toolTip = "Select the source landmarks"
    alignMultiWidgetLayout.addRow("Source landmarks: ", self.sourceFiducialMultiSelector)
    
    # Select target mesh directory
    #
    self.targetModelMultiSelector = ctk.ctkPathLineEdit()
    self.targetModelMultiSelector.filters = ctk.ctkPathLineEdit.Dirs
    self.targetModelMultiSelector.toolTip = "Select the directory of meshes to be landmarked"
    alignMultiWidgetLayout.addRow("Target mesh directory: ", self.targetModelMultiSelector)
    
    # Select output landmark directory
    #
    self.landmarkOutputSelector = ctk.ctkPathLineEdit()
    self.landmarkOutputSelector.filters = ctk.ctkPathLineEdit.Dirs
    self.landmarkOutputSelector.toolTip = "Select the output directory where the landmarks will be saved"
    alignMultiWidgetLayout.addRow("Target output landmark directory: ", self.landmarkOutputSelector)
    
    #
    # set voxel size used for subsampling
    #
    self.voxelSizeMulti = ctk.ctkDoubleSpinBox()
    self.voxelSizeMulti.minimum = 0
    self.voxelSizeMulti.maximum = 100
    self.voxelSizeMulti.singleStep = .1
    self.voxelSizeMulti.setDecimals(2)
    self.voxelSizeMulti.value = 0.7
    self.voxelSizeMulti.setToolTip("Choose the voxel size( in mm) to be used to subsample the source and target meshes")
    alignMultiWidgetLayout.addRow("Select subsampling voxel size:", self.voxelSizeMulti)
    
    [self.normalSearchRadiusMulti, self.FPFHSearchRadiusMulti, self.distanceThresholdMulti, self.maxRANSACMulti, self.maxRANSACValidationMulti, 
    self.ICPDistanceThresholdMulti, self.alphaMulti, self.betaMulti, self.CPDIterationsMulti, self.CPDTolerenceMulti] = self.addAdvancedMenu(alignMultiWidgetLayout)
        
    #
    # Run landmarking Button
    #
    self.applyLandmarkMultiButton = qt.QPushButton("Run auto-landmarking")
    self.applyLandmarkMultiButton.toolTip = "Align the taget meshes with the source mesh and transfer landmarks."
    self.applyLandmarkMultiButton.enabled = False
    alignMultiWidgetLayout.addRow(self.applyLandmarkMultiButton)
    
    
    # connections
    self.sourceModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.sourceFiducialMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.targetModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.landmarkOutputSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.applyLandmarkMultiButton.connect('clicked(bool)', self.onApplyLandmarkMulti)
    
    # Add vertical spacer
    self.layout.addStretch(1)
      
    # Advanced tab connections
    self.normalSearchRadiusMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.FPFHSearchRadiusMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.distanceThresholdMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.maxRANSACMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.maxRANSACValidationMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.ICPDistanceThresholdMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.alphaMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.betaMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.CPDIterationsMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    self.CPDTolerenceMulti.connect('valueChanged(double)', self.updateParameterDictionary)
    
    # initialize the parameter dictionary from single run parameters
    self.parameterDictionary = {
      "normalSearchRadius" : self.normalSearchRadius.value,
      "FPFHSearchRadius" : self.FPFHSearchRadius.value,
      "distanceThreshold" : self.distanceThreshold.value,
      "maxRANSAC" : int(self.maxRANSAC.value),
      "maxRANSACValidation" : int(self.maxRANSACValidation.value),
      "ICPDistanceThreshold"  : self.ICPDistanceThreshold.value,
      "alpha" : self.alpha.value,
      "beta" : self.beta.value,
      "CPDIterations" : int(self.CPDIterations.value),
      "CPDTolerence" : self.CPDTolerence.value
      }
    # initialize the parameter dictionary from multi run parameters
    self.parameterDictionaryMulti = {
      "normalSearchRadius" : self.normalSearchRadiusMulti.value,
      "FPFHSearchRadius" : self.FPFHSearchRadiusMulti.value,
      "distanceThreshold" : self.distanceThresholdMulti.value,
      "maxRANSAC" : int(self.maxRANSACMulti.value),
      "maxRANSACValidation" : int(self.maxRANSACValidationMulti.value),
      "ICPDistanceThreshold"  : self.ICPDistanceThresholdMulti.value,
      "alpha" : self.alphaMulti.value,
      "beta" : self.betaMulti.value,
      "CPDIterations" : int(self.CPDIterationsMulti.value),
      "CPDTolerence" : self.CPDTolerenceMulti.value
      }
  
  def cleanup(self):
    pass
  
  def onSelect(self):
    self.subsampleButton.enabled = bool ( self.sourceModelSelector.currentPath and self.targetModelSelector.currentPath and self.sourceFiducialSelector.currentPath)
    if bool(self.sourceModelSelector.currentPath):
      self.sourceModelMultiSelector.currentPath = self.sourceModelSelector.currentPath
    if bool(self.sourceFiducialSelector.currentPath):
      self.sourceFiducialMultiSelector.currentPath = self.sourceFiducialSelector.currentPath
    if bool(self.targetModelSelector.currentPath):
      path = os.path.dirname(self.targetModelSelector.currentPath) 
      self.targetModelMultiSelector.currentPath = path

  def onVoxelSizeChange(self):
    self.voxelSizeMulti.value = self.voxelSize.value
  
  def onSelectMultiProcess(self):
    self.applyLandmarkMultiButton.enabled = bool ( self.sourceModelMultiSelector.currentPath and self.sourceFiducialMultiSelector.currentPath 
    and self.targetModelMultiSelector.currentPath and self.landmarkOutputSelector.currentPath and self.voxelSizeMulti.value)
      
  def onSubsampleButton(self):
    logic = ALPACALogic()
    self.sourceData, self.targetData, self.sourcePoints, self.targetPoints, self.sourceFeatures, self.targetFeatures = logic.runSubsample(self.sourceModelSelector.currentPath, 
                                                                   self.targetModelSelector.currentPath, self.voxelSize.value, self.parameterDictionary)
    
    # Convert to VTK points
    self.sourceSLM_vtk = logic.convertPointsToVTK(self.sourcePoints.points)
    self.targetSLM_vtk = logic.convertPointsToVTK(self.targetPoints.points)
    
    # Display target points
    blue=[0,0,1]
    targetCloudNode = logic.displayPointCloud(self.targetSLM_vtk, self.voxelSize.value/10, 'Target Points', blue)
    self.updateLayout()
    
    # Enable next step of analysis
    self.alignButton.enabled = True
    
    # Output information on subsampling
    self.subsampleInfo.clear()
    self.subsampleInfo.insertPlainText(f':: Your subsampled source pointcloud has a total of {len(self.sourcePoints.points)} points. \n')
    self.subsampleInfo.insertPlainText(f':: Your subsampled target pointcloud has a total of {len(self.targetPoints.points)} points. ')
    
  def onAlignButton(self):
    logic = ALPACALogic()
    self.transformMatrix = logic.estimateTransform(self.sourcePoints, self.targetPoints, self.sourceFeatures, self.targetFeatures, self.voxelSize.value, self.parameterDictionary)
    self.ICPTransformNode = logic.convertMatrixToTransformNode(self.transformMatrix, 'ICP Transform')

    # For later analysis, apply transform to VTK arrays directly
    transform_vtk = self.ICPTransformNode.GetMatrixTransformToParent()
    self.alignedSourceSLM_vtk = logic.applyTransform(transform_vtk, self.sourceSLM_vtk)
    
    # Display aligned source points using transorm that can be viewed/edited in the scene
    red=[1,0,0]
    sourceCloudNode = logic.displayPointCloud(self.sourceSLM_vtk, self.voxelSize.value/10, 'Aligned Source Points', red)
    sourceCloudNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(sourceCloudNode)
    self.updateLayout()
    
    # Enable next step of analysis
    self.displayMeshButton.enabled = True
    self.CPDRegistrationButton.enabled = True
    #self.DECAButton.enabled = True
    
  def onDisplayMeshButton(self):
    logic = ALPACALogic()
    # Display target points
    targetModelNode = slicer.util.loadModel(self.targetModelSelector.currentPath)
    logic.RAS2LPSTransform(targetModelNode)
    blue=[0,0,1]
    targetModelNode.GetDisplayNode().SetColor(blue)
    
    # Display aligned source points
    self.sourceModelNode = slicer.util.loadModel(self.sourceModelSelector.currentPath)
    logic.RAS2LPSTransform(self.sourceModelNode)
    self.sourceModelNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceModelNode)
    red=[1,0,0]
    self.sourceModelNode.GetDisplayNode().SetColor(red)
    
  def onCPDRegistration(self):
    logic = ALPACALogic()
    # Get source landmarks from file
    sourceLandmarkNode =  slicer.util.loadMarkups(self.sourceFiducialSelector.currentPath)
    logic.RAS2LPSTransform(sourceLandmarkNode)
    sourceLandmarkNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(sourceLandmarkNode)
    point = [0,0,0]
    self.sourceLandmarks_np=np.zeros(shape=(sourceLandmarkNode.GetNumberOfFiducials(),3))
    for i in range(sourceLandmarkNode.GetNumberOfFiducials()):
      sourceLandmarkNode.GetMarkupPoint(0,i,point)
      self.sourceLandmarks_np[i,:]=point
    slicer.mrmlScene.RemoveNode(sourceLandmarkNode)
    
    # Registration
    self.alignedSourceSLM_np = vtk_np.vtk_to_numpy(self.alignedSourceSLM_vtk.GetPoints().GetData())
    self.registeredSourceArray = logic.runCPDRegistration(self.sourceLandmarks_np, self.alignedSourceSLM_np, self.targetPoints.points, self.parameterDictionary)
    outputPoints = logic.exportPointCloud(self.registeredSourceArray)
    
    # Display point cloud of registered points
    self.registeredSourceLM_vtk = logic.convertPointsToVTK(self.registeredSourceArray)
    green=[0,1,0]
    self.registeredSourceLMNode = logic.displayPointCloud(self.registeredSourceLM_vtk, self.voxelSize.value/10, 'Warped Source Points', green)
    self.displayWarpedModelButton.enabled = True
    
  #def onDECARegistration(self):
    #print("TBD")
        
  def onDisplayWarpedModel(self):    
    logic = ALPACALogic()
    ouputPoints = logic.exportPointCloud(self.registeredSourceArray)
    self.alignedSourceLM_vtk = logic.convertPointsToVTK(self.sourceLandmarks_np)
    self.warpedSourceNode = logic.applyTPSTransform(self.alignedSourceLM_vtk, self.registeredSourceLM_vtk, self.sourceModelNode, 'Warped Source Model')
    green=[0,1,0]
    self.warpedSourceNode.GetDisplayNode().SetColor(green)
    
  def onApplyLandmarkMulti(self):
    logic = ALPACALogic()
    logic.runLandmarkMultiprocess(self.sourceModelMultiSelector.currentPath,self.sourceFiducialMultiSelector.currentPath, 
    self.targetModelMultiSelector.currentPath, self.landmarkOutputSelector.currentPath, self.voxelSizeMulti.value, self.parameterDictionaryMulti )
    
    
  def updateLayout(self):
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(9)  #set layout to 3D only
    layoutManager.threeDWidget(0).threeDView().resetFocalPoint()
    layoutManager.threeDWidget(0).threeDView().resetCamera()
    
  def onChangeAdvanced(self):
    self.normalSearchRadiusMulti.value = self.normalSearchRadius.value
    self.FPFHSearchRadiusMulti.value = self.FPFHSearchRadius.value
    self.distanceThresholdMulti.value = self.distanceThreshold.value
    self.maxRANSACMulti.value = self.maxRANSAC.value
    self.maxRANSACValidationMulti.value = self.maxRANSACValidation.value
    self.ICPDistanceThresholdMulti.value  = self.ICPDistanceThreshold.value
    self.alphaMulti.value = self.alpha.value
    self.betaMulti.value = self.beta.value
    self.CPDTolerenceMulti.value = self.CPDTolerence.value    
    
    self.updateParameterDictionary()
    
  def updateParameterDictionary(self):    
    # update the parameter dictionary from single run parameters
    if hasattr(self, 'parameterDictionary'):
      self.parameterDictionary["normalSearchRadius"] = self.normalSearchRadius.value
      self.parameterDictionary["FPFHSearchRadius"] = self.FPFHSearchRadius.value
      self.parameterDictionary["distanceThreshold"] = self.distanceThreshold.value
      self.parameterDictionary["maxRANSAC"] = int(self.maxRANSAC.value)
      self.parameterDictionary["maxRANSACValidation"] = int(self.maxRANSACValidation.value)
      self.parameterDictionary["ICPDistanceThreshold"] = self.ICPDistanceThreshold.value
      self.parameterDictionary["alpha"] = self.alpha.value
      self.parameterDictionary["beta"] = self.beta.value
      self.parameterDictionary["CPDIterations"] = int(self.CPDIterations.value)
      self.parameterDictionary["CPDTolerence"] = self.CPDTolerence.value
    
    # update the parameter dictionary from multi run parameters
    if hasattr(self, 'parameterDictionaryMulti'):
      self.parameterDictionaryMulti["normalSearchRadius"] = self.normalSearchRadiusMulti.value
      self.parameterDictionaryMulti["FPFHSearchRadius"] = self.FPFHSearchRadiusMulti.value
      self.parameterDictionaryMulti["distanceThreshold"] = self.distanceThresholdMulti.value
      self.parameterDictionaryMulti["maxRANSAC"] = int(self.maxRANSACMulti.value)
      self.parameterDictionaryMulti["maxRANSACValidation"] = int(self.maxRANSACValidationMulti.value)
      self.parameterDictionaryMulti["ICPDistanceThreshold"] = self.ICPDistanceThresholdMulti.value
      self.parameterDictionaryMulti["alpha"] = self.alphaMulti.value
      self.parameterDictionaryMulti["beta"] = self.betaMulti.value
      self.parameterDictionaryMulti["CPDIterations"] = int(self.CPDIterationsMulti.value)
      self.parameterDictionaryMulti["CPDTolerence"] = self.CPDTolerenceMulti.value
      

      
  def addAdvancedMenu(self, currentWidgetLayout):
    #
    # Advanced menu for single run
    #
    advancedCollapsibleButton = ctk.ctkCollapsibleButton()
    advancedCollapsibleButton.text = "Advanced parameter settings"
    advancedCollapsibleButton.collapsed = True
    currentWidgetLayout.addRow(advancedCollapsibleButton)
    advancedFormLayout = qt.QFormLayout(advancedCollapsibleButton)
    
    # Rigid registration label
    rigidRegistrationCollapsibleButton=ctk.ctkCollapsibleButton()
    rigidRegistrationCollapsibleButton.text = "Rigid registration"
    advancedFormLayout.addRow(rigidRegistrationCollapsibleButton)
    rigidRegistrationFormLayout = qt.QFormLayout(rigidRegistrationCollapsibleButton)
    
    # Deformable registration label
    deformableRegistrationCollapsibleButton=ctk.ctkCollapsibleButton()
    deformableRegistrationCollapsibleButton.text = "Deformable registration"
    advancedFormLayout.addRow(deformableRegistrationCollapsibleButton)
    deformableRegistrationFormLayout = qt.QFormLayout(deformableRegistrationCollapsibleButton)
    
    
    # Normal search radius slider
    
    normalSearchRadius = ctk.ctkSliderWidget()
    normalSearchRadius.singleStep = 1
    normalSearchRadius.minimum = 2
    normalSearchRadius.maximum = 12
    normalSearchRadius.value = 2
    normalSearchRadius.setToolTip("Set size of the neighborhood used when computing normals")
    rigidRegistrationFormLayout.addRow("Normal search radius: ", normalSearchRadius)
    
    #FPFH Search Radius slider
    FPFHSearchRadius = ctk.ctkSliderWidget()
    FPFHSearchRadius.singleStep = 1
    FPFHSearchRadius.minimum = 3
    FPFHSearchRadius.maximum = 20
    FPFHSearchRadius.value = 5
    FPFHSearchRadius.setToolTip("Set size of the neighborhood used when computing FPFH features")
    rigidRegistrationFormLayout.addRow("FPFH Search radius: ", FPFHSearchRadius)
    
    
    # Maximum distance threshold slider
    distanceThreshold = ctk.ctkSliderWidget()
    distanceThreshold.singleStep = .25
    distanceThreshold.minimum = 0.5
    distanceThreshold.maximum = 4
    distanceThreshold.value = 1.5
    distanceThreshold.setToolTip("Maximum correspondence points-pair distance threshold")
    rigidRegistrationFormLayout.addRow("Maximum corresponding point distance: ", distanceThreshold)

    # Maximum RANSAC iterations slider
    maxRANSAC = ctk.ctkDoubleSpinBox()
    maxRANSAC.singleStep = 1
    maxRANSAC.setDecimals(0)
    maxRANSAC.minimum = 1
    maxRANSAC.maximum = 500000000
    maxRANSAC.value = 4000000
    maxRANSAC.setToolTip("Maximum number of iterations of the RANSAC algorithm")
    rigidRegistrationFormLayout.addRow("Maximum RANSAC iterations: ", maxRANSAC)

    # Maximum RANSAC validation steps
    maxRANSACValidation = ctk.ctkDoubleSpinBox()
    maxRANSACValidation.singleStep = 1
    maxRANSACValidation.setDecimals(0)
    maxRANSACValidation.minimum = 1
    maxRANSACValidation.maximum = 500000000
    maxRANSACValidation.value = 500
    maxRANSACValidation.setToolTip("Maximum number of RANSAC validation steps")
    rigidRegistrationFormLayout.addRow("Maximum RANSAC validation steps: ", maxRANSACValidation)

    # ICP distance threshold slider
    ICPDistanceThreshold = ctk.ctkSliderWidget()
    ICPDistanceThreshold.singleStep = .1
    ICPDistanceThreshold.minimum = 0.1
    ICPDistanceThreshold.maximum = 2
    ICPDistanceThreshold.value = 0.4
    ICPDistanceThreshold.setToolTip("Maximum ICP points-pair distance threshold")
    rigidRegistrationFormLayout.addRow("Maximum ICP distance: ", ICPDistanceThreshold)

    # Alpha slider
    alpha = ctk.ctkDoubleSpinBox()
    alpha.singleStep = .1
    alpha.minimum = 0
    alpha.maximum = 100
    alpha.value = 2
    alpha.setToolTip("Parameter specifying trade-off between fit (low) and smoothness (high)")
    deformableRegistrationFormLayout.addRow("Alpha: ", alpha)

    # Beta slider
    beta = ctk.ctkDoubleSpinBox()
    beta.singleStep = 1
    beta.setDecimals(0)
    beta.minimum = 0
    beta.maximum = 100
    beta.value = 2
    beta.setToolTip("Width of gaussian filter used when applying smoothness constraint")
    deformableRegistrationFormLayout.addRow("Beta: ", beta)

    # # CPD iterations slider
    CPDIterations = ctk.ctkSliderWidget()
    CPDIterations.singleStep = 1
    CPDIterations.minimum = 100
    CPDIterations.maximum = 1000
    CPDIterations.value = 100
    CPDIterations.setToolTip("Maximum number of iterations of the CPD procedure")
    deformableRegistrationFormLayout.addRow("CPD iterations: ", CPDIterations)

    # # CPD tolerance slider
    CPDTolerence = ctk.ctkSliderWidget()
    CPDTolerence.setDecimals(4)
    CPDTolerence.singleStep = .0001
    CPDTolerence.minimum = 0.0001
    CPDTolerence.maximum = 0.01
    CPDTolerence.value = 0.001
    CPDTolerence.setToolTip("Tolerance used to assess CPD convergence")
    deformableRegistrationFormLayout.addRow("CPD tolerance: ", CPDTolerence)

    return normalSearchRadius, FPFHSearchRadius, distanceThreshold, maxRANSAC, maxRANSACValidation, ICPDistanceThreshold, alpha, beta, CPDIterations, CPDTolerence
    
#
# ALPACALogic
#

class ALPACALogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def runLandmarkMultiprocess(self, sourceModelPath, sourceLandmarkPath, targetModelDirectory, outputDirectory, voxelSize, parameters):
    extensionModel = ".ply"
    
    # Get source landmarks from file
    sourceLandmarkNode =  slicer.util.loadMarkups(sourceLandmarkPath)
    self.RAS2LPSTransform(sourceLandmarkNode)
    point = [0,0,0]
    sourcePoints = vtk.vtkPoints()
    for i in range(sourceLandmarkNode.GetNumberOfFiducials()):
      sourceLandmarkNode.GetMarkupPoint(0,i,point)
      sourcePoints.InsertNextPoint(point)
    
    sourceLM_vtk = vtk.vtkPolyData()
    sourceLM_vtk.SetPoints(sourcePoints)
    slicer.mrmlScene.RemoveNode(sourceLandmarkNode)
    
    # Iterate through target models
    for targetFileName in os.listdir(targetModelDirectory):
      if targetFileName.endswith(extensionModel):
        targetFilePath = os.path.join(targetModelDirectory, targetFileName)
        # Subsample source and target models
        sourceData, targetData, sourcePoints, targetPoints, sourceFeatures, targetFeatures = self.runSubsample(sourceModelPath, targetFilePath, voxelSize, parameters)
        # Rigid registration of source sampled points and landmarks
        ICPTransform = self.estimateTransform(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, parameters)
        ICPTransform_vtk = self.convertMatrixToVTK(ICPTransform)
        sourceSLM_vtk = self.convertPointsToVTK(sourcePoints.points)
        alignedSourceSLM_vtk = self.applyTransform(ICPTransform_vtk, sourceSLM_vtk)
        alignedSourceLM_vtk = self.applyTransform(ICPTransform_vtk, sourceLM_vtk)
    
        # Non-rigid Registration
        alignedSourceSLM_np = vtk_np.vtk_to_numpy(alignedSourceSLM_vtk.GetPoints().GetData())
        alignedSourceLM_np = vtk_np.vtk_to_numpy(alignedSourceLM_vtk.GetPoints().GetData())
        registeredSourceLM_np = self.runCPDRegistration(alignedSourceLM_np, alignedSourceSLM_np, targetPoints.points, parameters)
        outputFiducialNode = self.exportPointCloud(registeredSourceLM_np)
        
        # Save output landmarks
        self.RAS2LPSTransform(outputFiducialNode)
        rootName = os.path.splitext(targetFileName)[0]
        outputFilePath = os.path.join(outputDirectory, rootName + ".fcsv")
        slicer.util.saveNode(outputFiducialNode, outputFilePath)
        slicer.mrmlScene.RemoveNode(outputFiducialNode)
        
     
  def exportPointCloud(self, pointCloud):
    fiducialNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode','outputFiducials')
    for point in pointCloud:
      fiducialNode.AddFiducialFromArray(point) 
    return fiducialNode

    node.AddFiducialFromArray(point)
  def applyTPSTransform(self, sourcePoints, targetPoints, modelNode, nodeName):
    transform=vtk.vtkThinPlateSplineTransform()  
    transform.SetSourceLandmarks( sourcePoints.GetPoints() )
    transform.SetTargetLandmarks( targetPoints.GetPoints() )
    transform.SetBasisToR() # for 3D transform
    
    transformFilter = vtk.vtkTransformPolyDataFilter()
    transformFilter.SetInputData(modelNode.GetPolyData())
    transformFilter.SetTransform(transform)
    transformFilter.Update()
    
    warpedPolyData = transformFilter.GetOutput()
    warpedModelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', nodeName)
    warpedModelNode.CreateDefaultDisplayNodes()
    warpedModelNode.SetAndObservePolyData(warpedPolyData)
    
    return warpedModelNode
      
  def runCPDRegistration(self, sourceLM, sourceSLM, targetSLM, parameters):
    sourceArrayCombined = np.append(sourceSLM, sourceLM, axis=0)

    #Convert target to numpy arrays for deformable registration
    targetArray = np.asarray(targetSLM)

    #Convert to float32 to increase speed (if selected)
    sourceArrayCombined = np.float32(sourceArrayCombined)
    targetArray = np.float32(targetArray)    
    registrationOutput = DeformableRegistration(**{'X': targetArray, 'Y': sourceArrayCombined,'max_iterations': parameters["CPDIterations"], 'tolerance':parameters["CPDTolerence"]}, alpha = parameters["alpha"], beta  = parameters["beta"])
    deformed_array, _ = registrationOutput.register()
    poi_prediction = deformed_array[-len(sourceLM):]
    return poi_prediction
      
  
  def RAS2LPSTransform(self, modelNode):
    matrix=vtk.vtkMatrix4x4()
    matrix.Identity()
    matrix.SetElement(0,0,-1)
    matrix.SetElement(1,1,-1)
    transform=vtk.vtkTransform()
    transform.SetMatrix(matrix)
    transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'RAS2LPS')
    transformNode.SetAndObserveTransformToParent( transform )
    modelNode.SetAndObserveTransformNodeID(transformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(modelNode)
    slicer.mrmlScene.RemoveNode(transformNode)
       
  def convertMatrixToVTK(self, matrix):
    matrix_vtk = vtk.vtkMatrix4x4()
    for i in range(4):
      for j in range(4):
        matrix_vtk.SetElement(i,j,matrix[i][j])
    return matrix_vtk
         
  def convertMatrixToTransformNode(self, matrix, transformName):
    matrix_vtk = vtk.vtkMatrix4x4()
    for i in range(4):
      for j in range(4):
        matrix_vtk.SetElement(i,j,matrix[i][j])

    transform = vtk.vtkTransform()
    transform.SetMatrix(matrix_vtk)
    transformNode =  slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', transformName)
    transformNode.SetAndObserveTransformToParent( transform )
    
    return transformNode
    
  def applyTransform(self, matrix, polydata):
    transform = vtk.vtkTransform()
    transform.SetMatrix(matrix)
    
    transformFilter = vtk.vtkTransformPolyDataFilter()
    transformFilter.SetTransform(transform)
    transformFilter.SetInputData(polydata)
    transformFilter.Update()
    return transformFilter.GetOutput()
  
  def convertPointsToVTK(self, points): 
    array_vtk = vtk_np.numpy_to_vtk(points, deep=True, array_type=vtk.VTK_FLOAT)
    points_vtk = vtk.vtkPoints()
    points_vtk.SetData(array_vtk)
    polydata_vtk = vtk.vtkPolyData()
    polydata_vtk.SetPoints(points_vtk)
    return polydata_vtk
      
  def displayPointCloud(self, polydata, pointRadius, nodeName, nodeColor):
    #set up glyph for visualizing point cloud
    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetRadius(pointRadius)
    glyph = vtk.vtkGlyph3D()
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)
    glyph.ScalingOff()
    glyph.Update() 
    
    #display
    modelNode=slicer.mrmlScene.GetFirstNodeByName(nodeName)
    if modelNode is None:  # if there is no node with this name, create with display node
      modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', nodeName)
      modelNode.CreateDefaultDisplayNodes()
    
    modelNode.SetAndObservePolyData(glyph.GetOutput())
    modelNode.GetDisplayNode().SetColor(nodeColor) 
    return modelNode
    
  def displayMesh(self, polydata, nodeName, nodeColor):
    modelNode=slicer.mrmlScene.GetFirstNodeByName(nodeName)
    if modelNode is None:  # if there is no node with this name, create with display node
      modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', nodeName)
      modelNode.CreateDefaultDisplayNodes()
    
    modelNode.SetAndObservePolyData(polydata)
    modelNode.GetDisplayNode().SetColor(nodeColor) 
    return modelNode
    
  def estimateTransform(self, sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, parameters):
    ransac = Open3D_utils.execute_global_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize * 2.5, 
      parameters["distanceThreshold"], parameters["maxRANSAC"], parameters["maxRANSACValidation"])
    
    # Refine the initial registration using an Iterative Closest Point (ICP) registration
    icp = Open3D_utils.refine_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize * 2.5, ransac, parameters["ICPDistanceThreshold"]) 
    return icp.transformation                                     
  
  def runSubsample(self, sourcePath, targetPath, voxelSize, parameters):
    source, source_down, source_fpfh = \
        Open3D_utils.prepare_source_dataset(voxelSize, sourcePath, parameters["normalSearchRadius"], parameters["FPFHSearchRadius"])
    source.estimate_normals()
    
    target, target_down, target_fpfh = \
        Open3D_utils.prepare_target_dataset(voxelSize, targetPath, parameters["normalSearchRadius"], parameters["FPFHSearchRadius"])
    target.estimate_normals()
    return source, target, source_down, target_down, source_fpfh, target_fpfh
          
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


class ALPACATest(ScriptedLoadableModuleTest):
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
    self.test_ALPACA1()
  
  def test_ALPACA1(self):
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
    logic = ALPACALogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')



