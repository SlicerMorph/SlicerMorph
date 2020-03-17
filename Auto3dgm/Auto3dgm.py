import os
import shutil
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

import auto3dgm_nazar
from auto3dgm_nazar.mesh.meshexport import MeshExport
from auto3dgm_nazar.analysis.correspondence import Correspondence
from auto3dgm_nazar.mesh.subsample import Subsample
from auto3dgm_nazar.dataset.datasetfactory import DatasetFactory
from auto3dgm_nazar.mesh.meshfactory import MeshFactory

import numpy as np

#import web_view_mesh

#
# Auto3dgm
#

class Auto3dgm(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Auto3DGM" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph"]
    self.parent.dependencies = []
    self.parent.contributors = ["John Doe (AnyWare Corp.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
It performs a simple thresholding on the input volume and optionally captures a screenshot.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.
    slicer.app.connect("startupCompleted()", self.checkPythonPackages) 
    
  def checkPythonPackages(self):
    print('Checking for required python packages')
    try:
      import mosek
    except:
      slicer.util.pip_install('mosek')
      import mosek
    # module level data
#
# Auto3dgmModuleData
#
  """May be a temporary stand-in class, this stores module-level results and data
  not stored in MRML scene"""
class Auto3dgmData():
  def __init__(self):
    self.dataset = None
    """ To be discussed?
    1) Store all the datasets into dataset collection
    2) Add phase1 and phase2 sampled points. The idea here is that
    once we have subsampled the mesh, we dont want to access thesbased    on the slider value (that the user can change, resulting in a crash if not subsampled again). Instead: Record the keys everytime subsampling is done
    """
    self.datasetCollection = None
    self.phase1SampledPoints = None
    self.phase2SampledPoints = None
    self.aligned_meshes = []
#
# Auto3dgmWidget
#

class Auto3dgmWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    #Widget variables
    self.meshFolder = None
    self.outputFolder = None
    self.visualizationMeshFolder = None
    self.outputFolderPrepared = False
    self.Auto3dgmData = Auto3dgmData()
    self.webWidget = None
    self.serverNode = None

    # Instantiate and connect widgets ...
    tabsWidget = qt.QTabWidget()
    setupTab = qt.QWidget()
    setupTabLayout = qt.QFormLayout(setupTab)
    
    runTab = qt.QWidget()
    runTabLayout = qt.QFormLayout(runTab)
    outTab = qt.QWidget()
    outTabLayout = qt.QFormLayout(outTab)

    tabsWidget.addTab(setupTab, "Setup")
    tabsWidget.addTab(runTab, "Run")
    tabsWidget.addTab(outTab, "Visualize")
    self.layout.addWidget(tabsWidget)

    self.setupSetupTab(setupTabLayout)
    self.setupRunTab(runTabLayout)
    self.setupOutTab(outTabLayout)
  
  ### SETUP TAB WIDGETS AND BEHAVIORS ###

  def setupSetupTab(self, setupTabLayout):
    inputfolderWidget=ctk.ctkCollapsibleButton()
    inputfolderLayout=qt.QFormLayout(inputfolderWidget)
    inputfolderWidget.text = "Input and output folder"
    setupTabLayout.addRow(inputfolderWidget)

    self.meshInputText, volumeInLabel, self.inputFolderButton=self.textIn('Input folder','Choose input folder', '')

    self.inputFolderButton.connect('clicked(bool)', self.selectMeshFolder)
    self.loadButton=qt.QPushButton("Load Data")
    self.loadButton.enabled=False
    self.loadButton.connect('clicked(bool)', self.onLoad)
    self.LMText, volumeInLabel, self.LMbutton=self.textIn('Input Directory','..', '')

    self.meshOutputText, volumeOutLabel, self.outputFolderButton=self.textIn('Output folder','Choose output folder', '')
    self.outputFolderButton.connect('clicked(bool)', self.selectOutputFolder)

    inputfolderLayout.addRow(volumeInLabel)#,1,1)    
    inputfolderLayout.addRow(self.meshInputText)#,1,2)
    inputfolderLayout.addRow(self.inputFolderButton)#,1,3)
    inputfolderLayout.addRow(self.loadButton)
    inputfolderLayout.addRow(self.meshOutputText)
    inputfolderLayout.addRow(self.outputFolderButton)
    self.LMbutton.connect('clicked(bool)', self.selectMeshFolder)

    self.parameterWidget = ctk.ctkCollapsibleButton()
    self.parameterLayout = qt.QFormLayout(self.parameterWidget)
    self.parameterWidget.text = "Parameters"
    setupTabLayout.addRow(self.parameterWidget)

    self.maxIterSliderWidget = ctk.ctkSliderWidget()
    self.maxIterSliderWidget.setDecimals(0)
    self.maxIterSliderWidget.singleStep = 1
    self.maxIterSliderWidget.minimum = 1
    self.maxIterSliderWidget.maximum = 5000
    self.maxIterSliderWidget.value = 1000
    self.maxIterSliderWidget.setToolTip("Maximum possible number of iterations for pairwise alignment optimization.")
    self.parameterLayout.addRow("Maximum iterations", self.maxIterSliderWidget)

    self.reflectionCheckBox = qt.QCheckBox()
    self.reflectionCheckBox.checked = 0
    self.reflectionCheckBox.setToolTip("Whether meshes can be reflected/mirrored to achieve more optimal alignments.")
    self.parameterLayout.addRow("Allow reflection", self.reflectionCheckBox)

    self.subsampleComboBox = qt.QComboBox()
    self.subsampleComboBox.addItem("FPS (Furthest Point Sampling)")
    self.subsampleComboBox.addItem("GPL (Gaussian Process Landmarks)")
    self.subsampleComboBox.addItem("FPS/GPL Hybrid")
    self.parameterLayout.addRow("Subsampling", self.subsampleComboBox)

    self.fpsSeed = qt.QSpinBox()
    self.fpsSeed.setSpecialValueText('-')
    self.parameterLayout.addRow("Optional FPS Seed", self.fpsSeed)

    self.hybridPoints = qt.QSpinBox()
    self.hybridPoints.setSpecialValueText('-')
    self.hybridPoints.setMinimum(1)
    self.hybridPoints.setMaximum(1000)
    self.parameterLayout.addRow("Hybrid GPL Points", self.hybridPoints)

    self.phaseChoiceComboBox = qt.QComboBox()
    self.phaseChoiceComboBox.addItem("1 (Single Alignment Pass)")
    self.phaseChoiceComboBox.addItem("2 (Double Alignment Pass)")
    self.phaseChoiceComboBox.setCurrentIndex(1)
    self.parameterLayout.addRow("Analysis phases", self.phaseChoiceComboBox)

    self.phase1PointNumber = qt.QSpinBox()
    self.phase1PointNumber.setMinimum(1)
    self.phase1PointNumber.setMaximum(100000)
    self.phase1PointNumber.setValue(200)
    self.parameterLayout.addRow("Phase 1 Points", self.phase1PointNumber)

    self.phase2PointNumber = qt.QSpinBox()
    self.phase2PointNumber.setMinimum(1)
    self.phase2PointNumber.setMaximum(1000000)
    self.phase2PointNumber.setValue(1000)
    self.parameterLayout.addRow("Phase 2 Points", self.phase2PointNumber)

    self.processingComboBox = qt.QComboBox()
    self.processingComboBox.addItem("Local Single CPU Core")
    self.processingComboBox.addItem("Local Multiple CPU Cores")
    self.processingComboBox.addItem("Cluster/Grid")
    self.parameterLayout.addRow("Processing", self.processingComboBox)

  def selectMeshFolder(self):
      self.meshFolder=qt.QFileDialog().getExistingDirectory()
      self.meshInputText.setText(self.meshFolder)
      try:
        self.loadButton.enabled = bool(self.meshFolder)
      except AttributeError:
        self.loadButton.enable = False

  def selectOutputFolder(self):
    self.outputFolder=qt.QFileDialog().getExistingDirectory()
    self.meshOutputText.setText(self.outputFolder)

  def onLoad(self):
    self.Auto3dgmData.datasetCollection=Auto3dgmLogic.createDataset(self.meshFolder)
    print(self.Auto3dgmData.datasetCollection)
    try:
      self.subStepButton.enabled = bool(self.meshFolder)
    except AttributeError:
      self.subStepButton.enable = False


  def prepareOutputFolder(self):
    if (not os.path.exists(self.outputFolder+"/lowres/")):
      os.mkdir(self.outputFolder+"/lowres/")
    if (not os.path.exists(self.outputFolder+"/highres/")):
      os.mkdir(self.outputFolder+"/highres/")
    if (not os.path.exists(self.outputFolder+"/aligned/")):
      os.mkdir(self.outputFolder+"/aligned/")
    self.outputFolderPrepared=True

  ### RUN TAB WIDGETS AND BEHAVIORS ###

  def setupRunTab(self, runTabLayout):
    self.singleStepGroupBox = qt.QGroupBox("Run individual steps")
    self.singleStepGroupBoxLayout = qt.QVBoxLayout()
    self.singleStepGroupBoxLayout.setSpacing(5)
    self.singleStepGroupBox.setLayout(self.singleStepGroupBoxLayout)
    runTabLayout.addRow(self.singleStepGroupBox)

    self.subStepButton = qt.QPushButton("Subsample")
    self.subStepButton.toolTip = "Run subsample step of analysis, creating collections of subsampled points per mesh."
    self.subStepButton.connect('clicked(bool)', self.subStepButtonOnLoad)
    self.subStepButton.enabled=False
    self.singleStepGroupBoxLayout.addWidget(self.subStepButton)

    self.phase1StepButton = qt.QPushButton("Phase 1")
    self.phase1StepButton.toolTip = "Run the first analysis phase, aligning meshes based on low resolution subsampled points."
    self.phase1StepButton.connect('clicked(bool)', self.phase1StepButtonOnLoad)
    self.singleStepGroupBoxLayout.addWidget(self.phase1StepButton)

    self.phase2StepButton = qt.QPushButton("Phase 2")
    self.phase2StepButton.toolTip = "Run the second analysis phase, aligning meshes based on high resolution subsampled points."
    self.phase2StepButton.connect('clicked(bool)', self.phase2StepButtonOnLoad)
    self.singleStepGroupBoxLayout.addWidget(self.phase2StepButton)

    self.allStepsButton = qt.QPushButton("Run all steps")
    self.allStepsButton.toolTip = "Run all possible analysis steps and phases."
    self.allStepsButton.connect('clicked(bool)', self.allStepsButtonOnLoad)
    runTabLayout.addRow(self.allStepsButton)

    runTabLayout.setVerticalSpacing(15)

  def subStepButtonOnLoad(self):
    print("Mocking a call to the Logic service AL002.1")
    # Store the keys
    self.Auto3dgmData.phase1SampledPoints = self.phase1PointNumber.value
    self.Auto3dgmData.phase2SampledPoints = self.phase2PointNumber.value
    self.Auto3dgmData.fpsSeed=self.fpsSeed.value
    Auto3dgmLogic.subsample(self.Auto3dgmData,list_of_pts = [self.phase1PointNumber.value,self.phase2PointNumber.value], meshes=self.Auto3dgmData.datasetCollection.datasets[0])
    print("Dataset collection updated")
    print(self.Auto3dgmData.datasetCollection.datasets)

  def phase1StepButtonOnLoad(self):
    self.Auto3dgmData.datasetCollection.add_analysis_set(Auto3dgmLogic.correspondence(self.Auto3dgmData, self.reflectionCheckBox.checked, phase=1),"Phase 1")
    self.Auto3dgmData.phase1SampledPoints = self.phase1PointNumber.value
    print('Exporting data')
    Auto3dgmLogic.exportData(self.Auto3dgmData, self.outputFolder, phases = [1])

  def phase2StepButtonOnLoad(self):
    self.Auto3dgmData.datasetCollection.add_analysis_set(Auto3dgmLogic.correspondence(self.Auto3dgmData, self.reflectionCheckBox.checked, phase=2),"Phase 2")
    self.Auto3dgmData.phase1SampledPoints = self.phase1PointNumber.value
    Auto3dgmLogic.exportData(self.Auto3dgmData, self.outputFolder, phases = [2])

  def allStepsButtonOnLoad(self):
    self.Auto3dgmData.phase1SampledPoints = self.phase1PointNumber.value
    self.Auto3dgmData.phase2SampledPoints = self.phase2PointNumber.value
    Auto3dgmLogic.runAll(self.Auto3dgmData, self.reflectionCheckBox.checked)
    Auto3dgmLogic.exportData(self.Auto3dgmData, self.outputFolder, phases = [1, 2])

  ### OUTPUT TAB WIDGETS AND BEHAVIORS

  def setupOutTab(self, outTabLayout):
    # visualizationinputfolderWidget=ctk.ctkCollapsibleButton()
    # visualizationinputfolderLayout=qt.QFormLayout(visualizationinputfolderWidget)
    # visualizationinputfolderWidget.text = ""
    # outTabLayout.addRow(visualizationinputfolderWidget)

    # self.visualizationmeshInputText, visualizationvolumeInLabel, self.visualizationinputFolderButton=self.textIn('Input folder','Choose input folder', '')

    # visualizationinputfolderLayout.addRow(visualizationvolumeInLabel)#,1,1)    
    # visualizationinputfolderLayout.addRow(self.visualizationmeshInputText)#,1,2)
    # visualizationinputfolderLayout.addRow(self.visualizationinputFolderButton)#,1,3)

    # self.visualizationinputFolderButton.connect('clicked(bool)', self.visualizationSelectMeshFolder)

    self.visMeshGroupBox = qt.QGroupBox("Visualize aligned meshes")
    self.visMeshGroupBoxLayout = qt.QVBoxLayout()
    self.visMeshGroupBoxLayout.setSpacing(5)
    self.visMeshGroupBox.setLayout(self.visMeshGroupBoxLayout)
    outTabLayout.addRow(self.visMeshGroupBox)

    self.visStartServerButton = qt.QPushButton("Start mesh visualization server")
    self.visStartServerButton.toolTip = "Start server for visualizing aligned meshes. Be sure to stop server before quitting Slicer."
    self.visStartServerButton.connect('clicked(bool)', self.visStartServerButtonOnLoad)
    self.visMeshGroupBoxLayout.addWidget(self.visStartServerButton)

    self.visPhase1Button = qt.QPushButton("View Phase 1 alignment")
    self.visPhase1Button.toolTip = "Visualize aligned meshes with alignment based on low resolution subsampled points."
    self.visPhase1Button.connect('clicked(bool)', self.visPhase1ButtonOnLoad)
    self.visPhase1Button.enabled = False
    self.visMeshGroupBoxLayout.addWidget(self.visPhase1Button)

    self.visPhase2Button = qt.QPushButton("View Phase 2 alignment")
    self.visPhase2Button.toolTip = "Visualize aligned meshes with alignment based on high resolution subsampled points."
    self.visPhase2Button.connect('clicked(bool)', self.visPhase2ButtonOnLoad)
    self.visPhase2Button.enabled = False
    self.visMeshGroupBoxLayout.addWidget(self.visPhase2Button)

    self.visGroupBox = qt.QGroupBox("Visualize results")
    self.visGroupBoxLayout = qt.QVBoxLayout()
    self.visGroupBoxLayout.setSpacing(5)
    self.visGroupBox.setLayout(self.visGroupBoxLayout)
    outTabLayout.addRow(self.visGroupBox)

    self.visSubButton = qt.QPushButton("Subsample")
    self.visSubButton.toolTip = "Visualize collections of subsampled points per mesh."
    self.visSubButton.connect('clicked(bool)', self.visSubButtonOnLoad)
    self.visSubButton.enabled = False
    self.visGroupBoxLayout.addWidget(self.visSubButton) 

    # self.outGroupBox = qt.QGroupBox("Output results")
    # self.outGroupBoxLayout = qt.QVBoxLayout()
    # self.outGroupBoxLayout.setSpacing(5)
    # self.outGroupBox.setLayout(self.outGroupBoxLayout)
    # outTabLayout.addRow(self.outGroupBox)

    # self.outPhase1Button = qt.QPushButton("Phase 1 results to GPA")
    # self.outPhase1Button.toolTip = "Output aligned mesh results (based on low resolution subsampled points) to GPA toolkit extension for PCA and other analysis."
    # self.outPhase1Button.connect('clicked(bool)', self.outPhase1ButtonOnLoad)
    # self.outGroupBoxLayout.addWidget(self.outPhase1Button)

    # self.outPhase2Button = qt.QPushButton("Phase 2 results to GPA")
    # self.outPhase2Button.toolTip = "Output aligned mesh results (based on high resolution subsampled points)to GPA toolkit extension for PCA and other analysis."
    # self.outPhase2Button.connect('clicked(bool)', self.outPhase2ButtonOnLoad)
    # self.outGroupBoxLayout.addWidget(self.outPhase2Button)

    # self.outVisButton = qt.QPushButton("Visualization(s)")
    # self.outVisButton.toolTip = "Output all visualizations produced."
    # self.outVisButton.connect('clicked(bool)', self.outVisButtonOnLoad)
    # self.outGroupBoxLayout.addWidget(self.outVisButton)

    # self.importAlignedButton = qt.QPushButton("Export aligned meshes")
    # self.importAlignedButton.toolTip = "Export aligned meshes to be plugged to the webviewer"
    # self.importAlignedButton.connect('clicked(bool)', self.onImportAligned)
    # self.outGroupBoxLayout.addWidget(self.importAlignedButton)

    outTabLayout.setVerticalSpacing(15)

  def visSubButtonOnLoad(self):
    print("Mocking a call to the Logic service AL003.3, maybe others")

  def visStartServerButtonOnLoad(self):
    viewerTmp = os.path.join(self.outputFolder, 'viewer_tmp')
    if self.visStartServerButton.text == "Start mesh visualization server":
      self.visPhase1Button.enabled = True
      self.visPhase2Button.enabled = True
      self.visStartServerButton.setText("Stop Mesh Visualization Server")
      Auto3dgmLogic.prepareDirs(viewerTmp)
      self.serverNode = Auto3dgmLogic.serveWebViewer(viewerTmp)
    else:
      self.visPhase1Button.enabled = False
      self.visPhase2Button.enabled = False
      self.visStartServerButton.setText("Start mesh visualization server") 
      if self.serverNode:
        self.serverNode.Cancel()
      Auto3dgmLogic.removeDir(viewerTmp)

  def visPhase1ButtonOnLoad(self):
    viewerTmp = os.path.join(self.outputFolder, 'viewer_tmp')
    Auto3dgmLogic.copyAlignedMeshes(viewerTmp, self.outputFolder, phase = 1)
    self.webWidget = Auto3dgmLogic.createWebWidget()

  def visPhase2ButtonOnLoad(self):
    viewerTmp = os.path.join(self.outputFolder, 'viewer_tmp')
    Auto3dgmLogic.copyAlignedMeshes(viewerTmp, self.outputFolder, phase = 2)
    self.webWidget = Auto3dgmLogic.createWebWidget()
    
  # def outPhase1ButtonOnLoad(self):
  #   print("Mocking a call to the Logic service AL003.1")
  #   if self.outputFolderPrepared==False:
  #     self.prepareOutputFolder()
  #   meshes = self.Auto3dgmData.datasetCollection.datasets[self.Auto3dgmData.phase1SampledPoints][self.Auto3dgmData.phase1SampledPoints]
  #   rotations = self.Auto3dgmData.datasetCollection.analysis_sets["Phase 1"].globalized_alignment['r']
  #   permutations = self.Auto3dgmData.datasetCollection.analysis_sets["Phase 1"].globalized_alignment['p']
  #   meshes = Auto3dgmLogic.landmarksFromPseudoLandmarks(meshes,permutations,rotations)
  #   for mesh in meshes:
  #       cfilename = self.outputFolder+"/lowres/"+mesh.name
  #       Auto3dgmLogic.saveNumpyArrayToCsv(mesh.vertices,cfilename)

  # def outPhase2ButtonOnLoad(self):
  #   print("Mocking a call to the Logic service AL003.1")
  #   if self.outputFolderPrepared==False:
  #     self.prepareOutputFolder()
  #   meshes = self.Auto3dgmData.datasetCollection.datasets[self.Auto3dgmData.phase2SampledPoints][self.Auto3dgmData.phase2SampledPoints]
  #   rotations = self.Auto3dgmData.datasetCollection.analysis_sets["Phase 2"].globalized_alignment['r']
  #   permutations = self.Auto3dgmData.datasetCollection.analysis_sets["Phase 2"].globalized_alignment['p']
  #   meshes = Auto3dgmLogic.landmarksFromPseudoLandmarks(meshes,permutations,rotations)
  #   for mesh in meshes:
  #       cfilename = self.outputFolder+"/highres/"+mesh.name
  #       Auto3dgmLogic.saveNumpyArrayToCsv(mesh.vertices,cfilename)

  # def outVisButtonOnLoad(self):
  #   print("Mocking a call to the Logic service unnamed visualization output service")

  def textIn(self,label, dispText, toolTip):
    """ a function to set up the appearnce of a QlineEdit widget.
    the widget is returned.
    """
    # set up text line
    textInLine=qt.QLineEdit();
    textInLine.setText(dispText)
    textInLine.toolTip = toolTip
    # set up label
    lineLabel=qt.QLabel()
    lineLabel.setText(label)

    # make clickable button
    button=qt.QPushButton(dispText)
    return textInLine, lineLabel, button

  # def visualizationSelectMeshFolder(self):
  #   self.visualizationMeshFolder=qt.QFileDialog().getExistingDirectory()
  #   self.visualizationmeshInputText.setText(self.visualizationMeshFolder)
  #   slicer.app.coreIOManager().loadFile(self.visualizationMeshFolder+"/MSTmatrix.csv")
  #   slicer.app.coreIOManager().loadFile(self.visualizationMeshFolder+"/distancematrix.csv")
  #   print(self.visualizationMeshFolder)

  def cleanup(self):
    pass

  def onImportAligned(self):
    Auto3dgmLogic.alignOriginalMeshes(self.Auto3dgmData)
    # Auto3dgmLogic.saveAlignedMeshesForViewer(self.Auto3dgmData)
    Auto3dgmLogic.saveAlignedMeshes(self.Auto3dgmData, os.path.join(self.outputFolder, 'aligned'))
    print("Meshes exported")

#
# Auto3dgmLogic
#

class Auto3dgmLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def runAll(Auto3dgmData, mirror):
    Auto3dgmLogic.subsample(Auto3dgmData,[Auto3dgmData.phase1SampledPoints,Auto3dgmData.phase2SampledPoints],Auto3dgmData.datasetCollection.datasets[0])
    print("Subsampling complete.")
    Auto3dgmData.datasetCollection.add_analysis_set(Auto3dgmLogic.correspondence(Auto3dgmData, mirror, phase=1),"Phase 1")
    print("Phase 1 complete.")
    Auto3dgmData.datasetCollection.add_analysis_set(Auto3dgmLogic.correspondence(Auto3dgmData, mirror, phase=2),"Phase 2")
    print("Phase 2 complete.")

  # Logic service function AL001.001 Create dataset
  def createDataset(inputdirectory):
    dataset = DatasetFactory.ds_from_dir(inputdirectory,center_scale=True)
    return dataset

  # Logic service function AL002.1 Subsample

  # In: List of points, possibly just one
  # list of meshes
  def subsample(Auto3dgmData,list_of_pts, meshes):
    print(list_of_pts)
    for mesh in meshes:
        print(len(mesh.vertices))
    ss = Subsample(pointNumber=list_of_pts, meshes=meshes, seed={},center_scale=True)
    for point in list_of_pts:
      names = []
      meshes = []
      for key in ss.ret[point]['output']['output']:
        mesh = ss.ret[point]['output']['output'][key]
        meshes.append(mesh)
      dataset = {}
      dataset[point] = meshes
      Auto3dgmData.datasetCollection.add_dataset(dataset,point)
    return(Auto3dgmData)

  def createDatasetCollection(dataset, name):
    datasetCollection=auto3dgm_nazar.dataset.datasetcollection.DatasetCollection(datasets = [dataset],dataset_names = [name])
    return datasetCollection

  def correspondence(Auto3dgmData, mirror, phase = 1):
    if phase == 1:
      npoints = Auto3dgmData.phase1SampledPoints
    else:
      npoints = Auto3dgmData.phase2SampledPoints
    meshes = Auto3dgmData.datasetCollection.datasets[npoints][npoints]
    corr = Correspondence(meshes=meshes, mirror=mirror)
    print("Correspondence compute for Phase " + str(phase))
    return(corr)
  
  def landmarksFromPseudoLandmarks(subsampledMeshes,permutations,rotations):
    meshes = []
    for i in range(len(subsampledMeshes)):
      mesh = subsampledMeshes[i]
      perm = permutations[i]
      rot = rotations[i]
      print(perm.shape)
      print(mesh.vertices.shape)
      mesh.rotate(rot)
      V = mesh.vertices.T
      lmtranspose = V @ perm
      landmarks = lmtranspose.T
      mesh = auto3dgm_nazar.mesh.meshfactory.MeshFactory.mesh_from_data(vertices=landmarks,name=mesh.name)
      meshes.append(mesh)
    return(meshes)

  def saveNumpyArrayToCsv(array,filename):
    print(array)
    print(filename)
    np.savetxt(filename+".csv",array,delimiter = ",",fmt = "%s")
    print(str(array) + " saved to file " + str(filename))
  
  def saveNumpyArrayToFcsv(array,filename):
      #print(array)
      #print(filename)
      l = np.shape(array)[0]
      fname2 = filename + ".fcsv"
      file = open(fname2,"w")
      file.write("# Markups fiducial file version = 4.4 \n")
      file.write("# columns = id,x,y,z,vis,sel \n")
      for i in range(l):
          file.write("p" + str(i) + ",")
          file.write(str(array[i,0]) + "," + str(array[i,1]) + "," + str(array[i,2]) + ",1,1 \n")
      file.close()
      print("file " + str(filename) + ".fcsv saved \n" )


  def alignOriginalMeshes(Auto3dgmData, phase = 2):
    if 'Phase 2' in Auto3dgmData.datasetCollection.analysis_sets:
      corr = Auto3dgmData.datasetCollection.analysis_sets['Phase 2']
    elif 'Phase 1' in Auto3dgmData.datasetCollection.analysis_sets:
      corr = Auto3dgmData.datasetCollection.analysis_sets['Phase 1']
      print("Phase 2 results do not exist, computing with Phase 1")
    else:
      print("No alignment has been computed")
      return(0)
    meshes = Auto3dgmData.datasetCollection.datasets[0]
    Auto3dgmData.aligned_meshes = []
    for t in range(len(meshes)):
      R = corr.globalized_alignment['r'][t]
      verts=meshes[t].vertices
      faces=meshes[t].faces
      name=meshes[t].name
      vertices=np.transpose(np.matmul(R,np.transpose(verts)))
      faces=faces.astype('int64')
      aligned_mesh=auto3dgm_nazar.mesh.meshfactory.MeshFactory.mesh_from_data(vertices, faces=faces, name=name, center_scale=True, deep=True)
      Auto3dgmData.aligned_meshes.append(aligned_mesh)
    return(Auto3dgmData)

  def saveAlignedMeshes(Auto3dgmData,outputFolder):
    if not os.path.exists(outputFolder):
      os.makedirs(outputFolder)
    for mesh in Auto3dgmData.aligned_meshes:
      print(os.path.join(outputFolder, mesh.name))
      MeshExport.writeToFile(outputFolder, mesh, format='ply')

  def exportData(Auto3dgmData, outputFolder, phases=[1, 2]):
    acceptable_phases = [1, 2]
    for p in phases:
      if p not in acceptable_phases:
        raise ValueError('Unacceptable phase number passed to Auto3dgmLogic.exportData')
        
      exportFolder = os.path.join(outputFolder, 'phase' + str(p))
      subDirs = ['aligned_meshes', 'aligned_landmarks']

      Auto3dgmLogic.prepareDirs(exportFolder, subDirs)
      Auto3dgmLogic.exportAlignedMeshes(Auto3dgmData, os.path.join(exportFolder, subDirs[0]), p)
      Auto3dgmLogic.exportAlignedLandmarks(Auto3dgmData, os.path.join(exportFolder, subDirs[1]), p)

  def exportAlignedMeshes(Auto3dgmData, exportFolder, phase = 2):
    if phase == 1:
      label = "Phase 1"
    elif phase == 2:
      label = "Phase 2"
    else:
      raise ValueError('Unaccepted phase number passed to Auto3dgmLogic.exportAlignedMeshes')

    m = Auto3dgmData.datasetCollection.datasets[0]
    r = Auto3dgmData.datasetCollection.analysis_sets[label].globalized_alignment['r']

    for idx, mesh in enumerate(m):
      new_vertices = np.transpose(r[idx] @ np.transpose(mesh.vertices))
      new_faces = mesh.faces.astype('int64')
      new_mesh = MeshFactory.mesh_from_data(new_vertices, faces=new_faces, name=mesh.name, center_scale=True, deep=True)
      MeshExport.writeToFile(exportFolder, new_mesh, format='ply')

  def exportAlignedLandmarks(Auto3dgmData, exportFolder, phase = 2):
    if phase == 1:
      n = Auto3dgmData.phase1SampledPoints
      label = "Phase 1"
    elif phase == 2:
      n = Auto3dgmData.phase2SampledPoints
      label = "Phase 2"
    else:
      raise ValueError('Unaccepted phase number passed to Auto3dgmLogic.exportAlignedLandmarks')

    m = Auto3dgmData.datasetCollection.datasets[n][n]
    r = Auto3dgmData.datasetCollection.analysis_sets[label].globalized_alignment['r']
    p = Auto3dgmData.datasetCollection.analysis_sets[label].globalized_alignment['p']
    landmarks = Auto3dgmLogic.landmarksFromPseudoLandmarks(m, p, r)

    for l in landmarks:
      Auto3dgmLogic.saveNumpyArrayToFcsv(l.vertices, os.path.join(exportFolder, l.name))

  def prepareDirs(exportFolder, subDirs=[]):
    if not os.path.exists(exportFolder):
      os.makedirs(exportFolder)
    for subdir in subDirs:
      d = os.path.join(exportFolder, subdir)
      if not os.path.exists(d):
        os.makedirs(d)

  def removeDir(trashFolder):
    if os.path.exists(trashFolder):
      shutil.rmtree(trashFolder)

  def copyAlignedMeshes(targetFolder, outputFolder, phase = 2):
    if phase not in [1, 2]:
      raise ValueError('Unaccepted phase number passed to Auto3dgmLogic.copyAlignedMeshes')

    for item in os.listdir(targetFolder):
      s = os.path.join(targetFolder, item)
      if os.path.isfile(s):
        os.unlink(s)

    srcFolder = os.path.join(outputFolder, 'phase' + str(phase), 'aligned_meshes')
    for item in os.listdir(srcFolder):
      s = os.path.join(srcFolder, item)
      d = os.path.join(targetFolder, item)
      if os.path.isfile(s):
        shutil.copy2(s, d)

  def serveWebViewer(viewFolder):
    parameters = { 'MeshDirectory': viewFolder }
    return slicer.cli.run(slicer.modules.meshviewer, None, parameters)
  
  def createWebWidget():
    webWidget = slicer.qSlicerWebWidget()
    slicerGeometry = slicer.util.mainWindow().geometry
    webWidget.size = qt.QSize(slicerGeometry.width(),slicerGeometry.height())
    webWidget.pos = qt.QPoint(slicerGeometry.x() + 256, slicerGeometry.y() + 128)
    webWidget.url = "http://localhost:8000"
    webWidget.show()
    return webWidget

class Auto3dgmTest(ScriptedLoadableModuleTest):
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
    self.test_Auto3dgm1()

  def test_Auto3dgm1(self):
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
      uris='http://slicer.kitware.com/midas3/download?items=5767')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = Auto3dgmLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
