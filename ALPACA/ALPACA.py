##BASE PYTHON
import os
import unittest
import logging
import copy
import json
import subprocess
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import glob
import vtk.util.numpy_support as vtk_np
import numpy as np
#
# ALPACA
#

class ALPACA(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ALPACA" 
    self.parent.categories = ["SlicerMorph.Geometric Morphometrics"]
    self.parent.dependencies = []
    self.parent.contributors = ["Arthur Porto (LSU), Sara Rolfe (UW), Murat Maga (UW)"] 
    self.parent.helpText = """
      This module automatically transfers landmarks on a reference 3D model (mesh) to a target 3D model using dense correspondence and deformable registration. First optimize the parameters in single alignment analysis, then use them in batch mode to apply to all 3D models. 
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ALPACA">online documentation.</a>.</p> 
      """
    self.parent.acknowledgementText = """
      This module was developed by Arthur Porto, Sara Rolfe, and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections" 
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839). 
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false 
      """      

    #Define custom layouts for multi-templates selection tab in slicer global namespace
    slicer.customLayoutSM = """
      <layout type=\"horizontal\" split=\"true\" >
       <item splitSize=\"500\">
         <item>
          <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
           <property name=\"viewlabel\" action=\"default\">1</property>
          </view>
         </item>
         <item>
          <view class=\"vtkMRMLTableViewNode\" singletontag=\"TableViewerWindow_1\">"
           <property name=\"viewlabel\" action=\"default\">T</property>"
          </view>"
         </item>"
        </layout>
       </item>
      </layout>
  """

    slicer.customLayoutTableOnly = """
      <layout type=\"horizontal\" >
       <item>
        <view class=\"vtkMRMLTableViewNode\" singletontag=\"TableViewerWindow_1\">"
         <property name=\"viewlabel\" action=\"default\">T</property>"
        </view>"
       </item>"
      </layout>
  """

    slicer.customLayoutPlotOnly = """
      <layout type=\"horizontal\" >
       <item>
        <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
         <property name=\"viewlabel\" action=\"default\">1</property>
        </view>"
       </item>"
      </layout>
  """

#
# ALPACAWidget
#

class ALPACAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Ensure that correct version of open3d Python package is installed
    needRestart = False
    needInstall = False
    Open3dVersion = "0.10.0"
    try:
      import open3d as o3d
      import cpdalp
      from packaging import version
      if version.parse(o3d.__version__) != version.parse(Open3dVersion):
        if not slicer.util.confirmOkCancelDisplay(f"ALPACA requires installation of open3d (version {Open3dVersion}).\nClick OK to upgrade open3d and restart the application."):
          self.showBrowserOnEnter = False
          return
        needRestart = True
        needInstall = True
    except ModuleNotFoundError:
      needInstall = True

    if needInstall:
      progressDialog = slicer.util.createProgressDialog(labelText='Upgrading open3d. This may take a minute...', maximum=0)
      slicer.app.processEvents()
      slicer.util.pip_install(f'open3d=={Open3dVersion}')
      slicer.util.pip_install(f'cpdalp')
      import open3d as o3d
      import cpdalp
      progressDialog.close()
    if needRestart:
      slicer.util.restart()

    # Set up tabs to split workflow
    tabsWidget = qt.QTabWidget()

    alignSingleTab = qt.QWidget()
    alignSingleTabLayout = qt.QFormLayout(alignSingleTab)

    alignMultiTab = qt.QWidget()
    alignMultiTabLayout = qt.QFormLayout(alignMultiTab)

    advancedSettingsTab = qt.QWidget()
    advancedSettingsTabLayout = qt.QFormLayout(advancedSettingsTab)
    
    #adding templates tab
    templatesTab = qt.QWidget()
    templatesTabLayout = qt.QFormLayout(templatesTab)    
    
    [self.projectionFactor,self.pointDensity, self.normalSearchRadius, self.FPFHSearchRadius, self.distanceThreshold, self.maxRANSAC, self.maxRANSACValidation, 
    self.ICPDistanceThreshold, self.alpha, self.beta, self.CPDIterations, self.CPDTolerance, self.Acceleration, self.BCPDFolder] = self.addAdvancedMenu(advancedSettingsTabLayout)

    tabsWidget.addTab(alignSingleTab, "Single Alignment")
    tabsWidget.addTab(alignMultiTab, "Batch processing")
    tabsWidget.addTab(advancedSettingsTab, "Advanced Settings")
    tabsWidget.addTab(templatesTab, "Templates Selection") 
    self.layout.addWidget(tabsWidget)
    
    # Layout within the tab
    alignSingleWidget=ctk.ctkCollapsibleButton()
    alignSingleWidgetLayout = qt.QFormLayout(alignSingleWidget)
    alignSingleWidget.text = "Align and subsample a source and target mesh "
    alignSingleTabLayout.addRow(alignSingleWidget)
  
    #
    # Select source mesh
    #
    self.sourceModelSelector = slicer.qMRMLNodeComboBox()
    self.sourceModelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.sourceModelSelector.selectNodeUponCreation = False
    self.sourceModelSelector.addEnabled = False
    self.sourceModelSelector.removeEnabled = False
    self.sourceModelSelector.noneEnabled = True
    self.sourceModelSelector.showHidden = False
    self.sourceModelSelector.setMRMLScene( slicer.mrmlScene )
    self.sourceModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    alignSingleWidgetLayout.addRow("Source Model: ", self.sourceModelSelector)
    self.sourceModelSelector.setToolTip( "Select source model" )
    
    #
    # Select source landmarks
    #

    self.sourceFiducialSelector = slicer.qMRMLNodeComboBox()
    self.sourceFiducialSelector.nodeTypes = ( ("vtkMRMLMarkupsFiducialNode"), "" )
    self.sourceFiducialSelector.selectNodeUponCreation = False
    self.sourceFiducialSelector.addEnabled = False
    self.sourceFiducialSelector.removeEnabled = False
    self.sourceFiducialSelector.noneEnabled = True
    self.sourceFiducialSelector.showHidden = False
    self.sourceFiducialSelector.setMRMLScene( slicer.mrmlScene )
    self.sourceFiducialSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    alignSingleWidgetLayout.addRow("Source Landmark Set: ", self.sourceFiducialSelector)
    self.sourceFiducialSelector.setToolTip( "Select source landmark set" )
    
    # Select target mesh
    #
    self.targetModelSelector = slicer.qMRMLNodeComboBox()
    self.targetModelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.targetModelSelector.selectNodeUponCreation = False
    self.targetModelSelector.addEnabled = False
    self.targetModelSelector.removeEnabled = False
    self.targetModelSelector.noneEnabled = True
    self.targetModelSelector.showHidden = False
    self.targetModelSelector.setMRMLScene( slicer.mrmlScene )
    self.targetModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    alignSingleWidgetLayout.addRow("Target Model: ", self.targetModelSelector)
    self.targetModelSelector.setToolTip( "Select target model" )

    # Select whether to skip scaling or not
    #
    self.skipScalingCheckBox = qt.QCheckBox()
    self.skipScalingCheckBox.checked = 0
    self.skipScalingCheckBox.setToolTip("If checked, ALPACA will skip scaling during alignment (Not recommended).")
    alignSingleWidgetLayout.addRow("Skip scaling", self.skipScalingCheckBox)
  
    # Select whether to skip projection-to-surface or not
    #
    self.skipProjectionCheckBox = qt.QCheckBox()
    self.skipProjectionCheckBox.checked = 0
    self.skipProjectionCheckBox.setToolTip("If checked, ALPACA will skip landmark projection towards the target suface.")
    alignSingleWidgetLayout.addRow("Skip projection", self.skipProjectionCheckBox)
    
   
    # Advanced tab connections
    
    self.projectionFactor.connect('valueChanged(double)', self.onChangeAdvanced)
    self.pointDensity.connect('valueChanged(double)', self.onChangeAdvanced)
    self.normalSearchRadius.connect('valueChanged(double)', self.onChangeAdvanced)
    self.FPFHSearchRadius.connect('valueChanged(double)', self.onChangeAdvanced)
    self.distanceThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
    self.maxRANSAC.connect('valueChanged(double)', self.onChangeAdvanced)
    self.maxRANSACValidation.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ICPDistanceThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
    self.alpha.connect('valueChanged(double)', self.onChangeAdvanced)
    self.beta.connect('valueChanged(double)', self.onChangeAdvanced)
    self.CPDIterations.connect('valueChanged(double)', self.onChangeAdvanced)
    self.CPDTolerance.connect('valueChanged(double)', self.onChangeAdvanced)
    self.Acceleration.connect('toggled(bool)', self.onChangeCPD)
    self.Acceleration.connect('toggled(bool)', self.onChangeAdvanced)
    self.BCPDFolder.connect('validInputChanged(bool)', self.onChangeAdvanced)
    self.BCPDFolder.connect('validInputChanged(bool)', self.onChangeCPD)


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
    self.subsampleInfo.setSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.MinimumExpanding)
    self.subsampleInfo.setMaximumHeight(100)
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
    # Coherent point drift registration
    #
    self.displayWarpedModelButton = qt.QPushButton("Show registered source model")
    self.displayWarpedModelButton.toolTip = "Show CPD warping applied to source model"
    self.displayWarpedModelButton.enabled = False
    alignSingleWidgetLayout.addRow(self.displayWarpedModelButton)

    #
    # Reset scene
    #
    self.resetSceneButton = qt.QPushButton("Reset scene")
    self.resetSceneButton.toolTip = "Reset scene"
    self.resetSceneButton.enabled = False
    alignSingleWidgetLayout.addRow(self.resetSceneButton)
    
    # connections
    self.sourceModelSelector.connect('validInputChanged(bool)', self.onSelect)
    self.sourceFiducialSelector.connect('validInputChanged(bool)', self.onSelect)
    self.targetModelSelector.connect('validInputChanged(bool)', self.onSelect)
    self.projectionFactor.connect('valueChanged(double)', self.onSelect)
    self.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)
    self.alignButton.connect('clicked(bool)', self.onAlignButton)
    self.displayMeshButton.connect('clicked(bool)', self.onDisplayMeshButton)
    self.CPDRegistrationButton.connect('clicked(bool)', self.onCPDRegistration)
    self.displayWarpedModelButton.connect('clicked(bool)', self.onDisplayWarpedModel)
    self.resetSceneButton.connect('clicked(bool)', self.onResetScene)

    

    # Layout within the multiprocessing tab
    alignMultiWidget=ctk.ctkCollapsibleButton()
    alignMultiWidgetLayout = qt.QFormLayout(alignMultiWidget)
    alignMultiWidget.text = "Transfer landmark points from one or multiple source meshes to a directory of target meshes "
    alignMultiTabLayout.addRow(alignMultiWidget)

    # Layout within the multiprocessing tab
    self.MethodBatchWidget= qt.QComboBox()
    self.MethodBatchWidget.addItems(['Single-Template(ALPACA)', 'Multi-Template(MALPACA)'])
    alignMultiWidgetLayout.addRow("Method:", self.MethodBatchWidget)


    #
    # Select source mesh
    #
    self.sourceModelMultiSelector = ctk.ctkPathLineEdit()
    self.sourceModelMultiSelector.filters  = ctk.ctkPathLineEdit().Files
    self.sourceModelMultiSelector.nameFilters=["*.ply"]
    self.sourceModelMultiSelector.toolTip = "Select the source mesh"
    alignMultiWidgetLayout.addRow("Source mesh(es): ", self.sourceModelMultiSelector)
    
    #
    # Select source landmark file
    #
    self.sourceFiducialMultiSelector = ctk.ctkPathLineEdit()
    self.sourceFiducialMultiSelector.filters  = ctk.ctkPathLineEdit().Files
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


    self.skipScalingMultiCheckBox = qt.QCheckBox()
    self.skipScalingMultiCheckBox.checked = 0
    self.skipScalingMultiCheckBox.setToolTip("If checked, ALPACA will skip scaling during the alignment.")
    alignMultiWidgetLayout.addRow("Skip scaling", self.skipScalingMultiCheckBox)    
    
    self.skipProjectionCheckBoxMulti = qt.QCheckBox()
    self.skipProjectionCheckBoxMulti.checked = 0
    self.skipProjectionCheckBoxMulti.setToolTip("If checked, ALPACA will skip final refinement step placing landmarks on the target suface.")
    alignMultiWidgetLayout.addRow("Skip projection", self.skipProjectionCheckBoxMulti)
          
    #
    # Run landmarking Button
    #
    self.applyLandmarkMultiButton = qt.QPushButton("Run auto-landmarking")
    self.applyLandmarkMultiButton.toolTip = "Align the taget meshes with the source mesh and transfer landmarks."
    self.applyLandmarkMultiButton.enabled = False
    alignMultiWidgetLayout.addRow(self.applyLandmarkMultiButton)
    
    
    # connections
    self.MethodBatchWidget.connect('currentIndexChanged(int)', self.onChangeMultiTemplate)
    self.sourceModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.sourceFiducialMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.targetModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.landmarkOutputSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.skipScalingMultiCheckBox.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.applyLandmarkMultiButton.connect('clicked(bool)', self.onApplyLandmarkMulti)
    
########Layout got templates selection #######
    #Layout of the set up section
    templatesSetupWidget=ctk.ctkCollapsibleButton()
    templatesSetupWidgetLayout = qt.QFormLayout(templatesSetupWidget)
    templatesSetupWidget.text = "Templates selection setup"
    templatesTabLayout.addRow(templatesSetupWidget)

    #Select models
    self.modelsMultiSelector = ctk.ctkPathLineEdit()
    self.modelsMultiSelector.filters  = ctk.ctkPathLineEdit().Dirs
    #self.modelsMultiSelector.nameFilters=["*.ply"]
    self.modelsMultiSelector.toolTip = "Select models in .ply format"
    templatesSetupWidgetLayout.addRow("Models directory: ", self.modelsMultiSelector)

    #Checkbox for enabling reference selection. The default is the first model.
    self.selectRefCheckBox = qt.QCheckBox()
    self.selectRefCheckBox.checked = 0
    self.selectRefCheckBox.setToolTip("Check to enable selecting a model as the reference. Unchecked = default")
    templatesSetupWidgetLayout.addRow("Enabling reference selection", self.selectRefCheckBox)

    #Optional user-defined reference
    self.referenceSelector = ctk.ctkPathLineEdit()
    self.referenceSelector.filters = ctk.ctkPathLineEdit().Files
    self.referenceSelector.nameFilters=["*.ply"]
    self.referenceSelector.enabled = False
    self.referenceSelector.toolTip = "The default reference model for downsampling point clouds with matching points will be the first specimen. Users can also manually select a reference model here "
    templatesSetupWidgetLayout.addRow("User-selected reference (optional): ", self.referenceSelector)

    #Set up an output directory for aligned pointclouds
    self.pcdOutputSelector = ctk.ctkPathLineEdit()
    self.pcdOutputSelector.filters = ctk.ctkPathLineEdit.Dirs
    self.pcdOutputSelector.toolTip = "Specify the output directory for the aligned and downsampled point clouds"
    templatesSetupWidgetLayout.addRow("Point clouds output directory: ", self.pcdOutputSelector)


    #Set up an output directory for selected templates
    self.templatesOutputSelector = ctk.ctkPathLineEdit()
    self.templatesOutputSelector.filters = ctk.ctkPathLineEdit.Dirs
    self.templatesOutputSelector.toolTip = "Specify the output directory for the selected templates"
    templatesSetupWidgetLayout.addRow("Templates output directory: ", self.templatesOutputSelector)

    #Enable matching points button
    self.modelsMultiSelector.connect('validInputChanged(bool)', self.onSelectKmeans)
    self.pcdOutputSelector.connect('validInputChanged(bool)', self.onSelectKmeans)
    self.templatesOutputSelector.connect('validInputChanged(bool)', self.onSelectKmeans)
    self.selectRefCheckBox.connect('toggled(bool)', self.onSelectKmeans)

    #Generate downsampled point clouds with matching points section layout
    downMatchingPCDWidget=ctk.ctkCollapsibleButton()
    downMatchingPCDWidgetLayout = qt.QFormLayout(downMatchingPCDWidget)
    downMatchingPCDWidget.text = "Generate downsampled point clouds with matching points"
    templatesTabLayout.addRow(downMatchingPCDWidget)  

    #User input point cloud sparsing factor
    self.spacingFactor = ctk.ctkSliderWidget()
    self.spacingFactor.singleStep = 0.001
    self.spacingFactor.minimum = 0
    self.spacingFactor.decimals = 3
    self.spacingFactor.maximum = 0.1
    self.spacingFactor.value = 0.04
    self.spacingFactor.setToolTip("Setting up spacing factor for downsampling the original pointclouds. Moving right (decreasing spacing factor) will result in sparser point clouds. Moving left (increasing spacing factor) will result in denser point clouds")
    downMatchingPCDWidgetLayout.addRow("Spacing factor: ", self.spacingFactor)


    #The button for generating downsampled template pcd
    self.downReferenceButton = qt.QPushButton("Generate downsampled reference pointcloud")
    self.downReferenceButton.toolTip = "Generate downsampled reference point clouds for downsampling all point clouds with matching points"
    self.downReferenceButton.enabled = False
    downMatchingPCDWidgetLayout.addRow(self.downReferenceButton)
    self.downReferenceButton.connect('clicked(bool)', self.onDownReferenceButton)


    #The button for running alignment and finding matching points
    self.matchingPointsButton = qt.QPushButton("Generate matching point clouds")
    self.matchingPointsButton.toolTip = "Generating point clouds from all models based on matching points to the reference point cloud"
    self.matchingPointsButton.enabled = False
    downMatchingPCDWidgetLayout.addRow(self.matchingPointsButton)
    #Connect matching points button to its function
    self.matchingPointsButton.connect('clicked(bool)', self.onMatchingPointsButton)


    #Display printing 
    self.subsampleInfo2 = qt.QPlainTextEdit()
    self.subsampleInfo2.setPlaceholderText("Point clouds information")
    self.subsampleInfo2.setReadOnly(True)
    self.subsampleInfo2.setSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.MinimumExpanding)
    self.subsampleInfo2.setMaximumHeight(100)
    downMatchingPCDWidgetLayout.addRow(self.subsampleInfo2)

    #Templates selection section layout
    templatesSelectionWidget=ctk.ctkCollapsibleButton()
    templatesSelectionWidgetLayout = qt.QFormLayout(templatesSelectionWidget)
    templatesSelectionWidget.text = "Multi-templates selection"
    templatesTabLayout.addRow(templatesSelectionWidget)  
    
    ###user defined cluster section layout
    #Radio button for selecting one or more groups, if more, diplay table node for inputting group information
    #Number of templates
    self.noGroupInput = qt.QRadioButton()
    self.noGroupInput.setChecked(True)
    self.noGroupInput.enabled = False
    templatesSelectionWidgetLayout.addRow("One group for the whole sample", self.noGroupInput)
    
    #Enable user input multi-group table
    self.multiGroupInput = qt.QRadioButton()
    self.multiGroupInput.setChecked(False)
    self.multiGroupInput.enabled = False
    templatesSelectionWidgetLayout.addRow("Multiple groups within the sample", self.multiGroupInput)
    self.multiGroupInput.connect('toggled(bool)', self.onToggleGroupInput)
    
    #reset table button
    self.resetTableButton = qt.QPushButton("Reset table for inputting group information")
    self.resetTableButton.toolTip = "Reset the table for inputting group information"
    self.resetTableButton.enabled = False
    templatesSelectionWidgetLayout.addRow(self.resetTableButton)
    self.resetTableButton.connect('clicked(bool)', self.onRestTableButton)

    #Number of templates per group
    self.templatesNumber = ctk.ctkDoubleSpinBox()
    self.templatesNumber.singleStep = 1
    self.templatesNumber.setDecimals(0)
    self.templatesNumber.minimum = 0
    self.templatesNumber.maximum = 100
    self.templatesNumber.value = 3
    self.templatesNumber.setToolTip("Input desired number of templates")
    templatesSelectionWidgetLayout.addRow("Number of templates per group: ", self.templatesNumber)

    #Rounds of iterations
    self.kmeansIterations = ctk.ctkDoubleSpinBox()
    self.kmeansIterations.singleStep = 1
    self.kmeansIterations.setDecimals(0)
    self.kmeansIterations.minimum = 0
    self.kmeansIterations.maximum = 10000000
    self.kmeansIterations.value = 10000
    self.kmeansIterations.setToolTip("Input desired number of kmeans iterations")
    templatesSelectionWidgetLayout.addRow("Kmeans iterations: ", self.kmeansIterations)

    #Check if setting up a universal numpy seed for kmeans
    self.setSeedCheckBox =  qt.QCheckBox()
    self.setSeedCheckBox.checked = 0
    self.setSeedCheckBox.setToolTip("Set up seed for Kmeans for reproducible results. For running other Slicer modules, please start a new session")
    templatesSelectionWidgetLayout.addRow("Set up seed for Kmeans", self.setSeedCheckBox)

    
    #The button for running kmeans and select templates
    self.kmeansTemplatesButton = qt.QPushButton("Kmeans-based template selection")
    self.kmeansTemplatesButton.toolTip = "Execute GPA, then using PC scores for kmeans in order to get templates"
    self.kmeansTemplatesButton.enabled = False
    templatesSelectionWidgetLayout.addRow(self.kmeansTemplatesButton)
    self.kmeansTemplatesButton.connect('clicked(bool)', self.onkmeansTemplatesButton)


    #Print out templates
    self.templatesInfo = qt.QPlainTextEdit()
    self.templatesInfo.setPlaceholderText("Templates")
    self.templatesInfo.setReadOnly(True)
    self.templatesInfo.setSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.MinimumExpanding)
    self.templatesInfo.setMaximumHeight(100)
    templatesSelectionWidgetLayout.addRow(self.templatesInfo)

    
    
    # Add vertical spacer
    self.layout.addStretch(1)
    
    #Add menu buttons
    self.addLayoutButton(503, 'MALPACA multi-templates View', 'Custom layout for MALPACA multi-templates tab', 'LayoutSlicerMorphView.png', slicer.customLayoutSM)
    self.addLayoutButton(504, 'Table Only View', 'Custom layout for GPA module', 'LayoutTableOnlyView.png', slicer.customLayoutTableOnly)
    self.addLayoutButton(505, 'Plot Only View', 'Custom layout for GPA module', 'LayoutPlotOnlyView.png', slicer.customLayoutPlotOnly)

    
    
    # initialize the parameter dictionary from single run parameters
    self.parameterDictionary = {
      "projectionFactor": self.projectionFactor.value,
      "pointDensity": self.pointDensity.value,
      "normalSearchRadius" : self.normalSearchRadius.value,
      "FPFHSearchRadius" : self.FPFHSearchRadius.value,
      "distanceThreshold" : self.distanceThreshold.value,
      "maxRANSAC" : int(self.maxRANSAC.value),
      "maxRANSACValidation" : int(self.maxRANSACValidation.value),
      "ICPDistanceThreshold"  : self.ICPDistanceThreshold.value,
      "alpha" : self.alpha.value,
      "beta" : self.beta.value,
      "CPDIterations" : int(self.CPDIterations.value),
      "CPDTolerance" : self.CPDTolerance.value,
      "Acceleration" : self.Acceleration.checked,
      "BCPDFolder" : self.BCPDFolder.currentPath
      }

  
  def cleanup(self):
    pass
  
  def addLayoutButton(self, layoutID, buttonAction, toolTip, imageFileName, layoutDiscription):
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(layoutID, layoutDiscription)

    viewToolBar = slicer.util.mainWindow().findChild('QToolBar', 'ViewToolBar')
    layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
    layoutSwitchActionParent = layoutMenu
    # use `layoutMenu` to add inside layout list, use `viewToolBar` to add next the standard layout list
    layoutSwitchAction = layoutSwitchActionParent.addAction(buttonAction) # add inside layout list

    moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
    iconPath = os.path.join(moduleDir, 'Resources/Icons', imageFileName)
    layoutSwitchAction.setIcon(qt.QIcon(iconPath))
    layoutSwitchAction.setToolTip(toolTip)
    layoutSwitchAction.connect('triggered()', lambda layoutId = layoutID: slicer.app.layoutManager().setLayout(layoutId))
    layoutSwitchAction.setData(layoutID)
  
  
  def onSelect(self):
    self.subsampleButton.enabled = bool ( self.sourceModelSelector.currentNode() and self.targetModelSelector.currentNode() and self.sourceFiducialSelector.currentNode())
    self.skipScalingMultiCheckBox.checked = self.skipScalingCheckBox.checked
    self.skipProjectionCheckBoxMulti.checked = self.skipProjectionCheckBox.checked
    

  def onSelectMultiProcess(self):
    self.applyLandmarkMultiButton.enabled = bool ( self.sourceModelMultiSelector.currentPath and self.sourceFiducialMultiSelector.currentPath 
      and self.targetModelMultiSelector.currentPath and self.landmarkOutputSelector.currentPath )

  def onSelectKmeans(self):
    self.matchingPointsButton.enabled = bool(self.modelsMultiSelector.currentPath and self.referenceSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)
    self.kmeansTemplatesButton.enabled = bool(self.modelsMultiSelector.currentPath and self.referenceSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)

  def onSubsampleButton(self):
    logic = ALPACALogic()
    self.sourceModelNode = self.sourceModelSelector.currentNode()
    self.sourceModelNode.GetDisplayNode().SetVisibility(False)
    self.targetModelNode = self.targetModelSelector.currentNode()
    self.targetModelNode.GetDisplayNode().SetVisibility(False)
    self.sourceFiducialSelector.currentNode().GetDisplayNode().SetVisibility(False)

    self.sourcePoints, self.targetPoints, self.sourceFeatures, \
      self.targetFeatures, self.voxelSize, self.scaling = logic.runSubsample(self.sourceModelNode, self.targetModelNode, self.skipScalingCheckBox.checked, self.parameterDictionary)
    # Convert to VTK points for visualization 
    self.targetVTK = logic.convertPointsToVTK(self.targetPoints.points)
    
    # Display target points
    blue=[0,0,1]
    self.targetCloudNode = logic.displayPointCloud(self.targetVTK, self.voxelSize / 10, 'Target Pointcloud', blue)
    self.targetCloudNode.GetDisplayNode().SetVisibility(True)
    self.updateLayout()
    
    # Enable next step of analysis+
    self.alignButton.enabled = True
    
    # Output information on subsampling
    self.subsampleInfo.clear()
    self.subsampleInfo.insertPlainText(f':: Your subsampled source pointcloud has a total of {len(self.sourcePoints.points)} points. \n')
    self.subsampleInfo.insertPlainText(f':: Your subsampled target pointcloud has a total of {len(self.targetPoints.points)} points. ')
    
  def onAlignButton(self):
    logic = ALPACALogic()
    self.transformMatrix = logic.estimateTransform(self.sourcePoints, self.targetPoints, self.sourceFeatures, self.targetFeatures, self.voxelSize, self.skipScalingCheckBox.checked, self.parameterDictionary)
    self.ICPTransformNode = logic.convertMatrixToTransformNode(self.transformMatrix, 'Rigid Transformation Matrix')
    self.sourcePoints.transform(self.transformMatrix)
    self.sourceVTK = logic.convertPointsToVTK(self.sourcePoints.points)

    # Display aligned source points using transform that can be viewed/edited in the scene
    red=[1,0,0]
    self.sourceCloudNode = logic.displayPointCloud(self.sourceVTK, self.voxelSize / 10, 'Source Pointcloud', red)
    self.sourceCloudNode.GetDisplayNode().SetVisibility(True)
    self.updateLayout()
    
    # Enable next step of analysis
    self.displayMeshButton.enabled = True
    
    
  def onDisplayMeshButton(self):
    logic = ALPACALogic()
    self.sourceModelNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceModelNode)

    red=[1,0,0]
    self.sourceModelNode.GetDisplayNode().SetColor(red)
    self.sourceModelNode.GetDisplayNode().SetVisibility(True)
    self.targetModelNode.GetDisplayNode().SetVisibility(True)

    # Hide Pointcloud
    self.sourceCloudNode.GetDisplayNode().SetVisibility(False)
    self.targetCloudNode.GetDisplayNode().SetVisibility(False)
   
    # Enable next step of analysis
    self.CPDRegistrationButton.enabled = True
    self.resetSceneButton.enabled = True
    
  def onCPDRegistration(self):
    logic = ALPACALogic()

    # Get source landmarks from file
    self.sourceLandmarks, self.sourceLMNode =  logic.loadAndScaleFiducials(self.sourceFiducialSelector.currentNode(), self.scaling, scene = True)
    self.sourceLandmarks.transform(self.transformMatrix)
    self.sourceLMNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceLMNode)
    
    # Registration
    self.registeredSourceArray = logic.runCPDRegistration(self.sourceLandmarks.points, self.sourcePoints.points, self.targetPoints.points, self.parameterDictionary)

    self.outputPoints = logic.exportPointCloud(self.registeredSourceArray, "Initial Predicted Landmarks")
    self.inputPoints = logic.exportPointCloud(self.sourceLandmarks.points, "Original Landmarks")
    
    green=[0,1,0]
    self.outputPoints.GetDisplayNode().SetColor(green)

    outputPoints_vtk = logic.getFiducialPoints(self.outputPoints)
    inputPoints_vtk = logic.getFiducialPoints(self.inputPoints)
    
    # Get warped source model
    self.warpedSourceNode = logic.applyTPSTransform(inputPoints_vtk, outputPoints_vtk, self.sourceModelNode, 'Warped Source Mesh')
    self.warpedSourceNode.GetDisplayNode().SetVisibility(False)
    self.outputPoints.GetDisplayNode().SetPointLabelsVisibility(False)
    slicer.mrmlScene.RemoveNode(self.inputPoints)
    
    if self.skipProjectionCheckBox.checked: 
      logic.propagateLandmarkTypes(self.sourceLMNode, self.outputPoints)

    else:
      print(":: Projecting landmarks to external surface")
      projectionFactor = self.projectionFactor.value/100
      self.projectedLandmarks = logic.runPointProjection(self.warpedSourceNode, self.targetModelNode, self.outputPoints, projectionFactor)
      logic.propagateLandmarkTypes(self.sourceLMNode, self.projectedLandmarks)
      self.projectedLandmarks.GetDisplayNode().SetPointLabelsVisibility(False)
      self.outputPoints.GetDisplayNode().SetVisibility(False)
    
    # Enable next step of analysis  
    self.displayWarpedModelButton.enabled = True
    
    # Update visualization
    self.sourceLMNode.GetDisplayNode().SetVisibility(False)
    self.sourceModelNode.GetDisplayNode().SetVisibility(False)
        
  def onDisplayWarpedModel(self):    
    logic = ALPACALogic()
    green=[0,1,0]
    self.warpedSourceNode.GetDisplayNode().SetColor(green)
    self.warpedSourceNode.GetDisplayNode().SetVisibility(True)
    
  def onApplyLandmarkMulti(self):
    logic = ALPACALogic()
    if self.skipProjectionCheckBoxMulti.checked != 0:
      projectionFactor = 0
    else:  
      projectionFactor = self.projectionFactor.value/100
      
    logic.runLandmarkMultiprocess(self.sourceModelMultiSelector.currentPath,self.sourceFiducialMultiSelector.currentPath, 
    self.targetModelMultiSelector.currentPath, self.landmarkOutputSelector.currentPath, self.skipScalingMultiCheckBox.checked, projectionFactor, self.parameterDictionary)

###Connecting function for kmeans templates selection
  def onSelectKmeans(self):
    self.downReferenceButton.enabled = bool(self.modelsMultiSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)
    self.kmeansTemplatesButton.enabled = bool(self.modelsMultiSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)
    self.noGroupInput.enabled = bool(self.modelsMultiSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)
    self.multiGroupInput.enabled = bool(self.modelsMultiSelector.currentPath and self.pcdOutputSelector.currentPath and self.templatesOutputSelector.currentPath)
    self.referenceSelector.enabled = self.selectRefCheckBox.isChecked()

  def onDownReferenceButton(self):
    logic = ALPACALogic()
    if bool(self.referenceSelector.currentPath):
      referencePath = self.referenceSelector.currentPath
    else:
      referenceFile = os.listdir(self.modelsMultiSelector.currentPath)[0]
      referencePath = os.path.join(self.modelsMultiSelector.currentPath, referenceFile)
    self.sparseTemplate, template_density, self.referenceNode = logic.downReference(referencePath, self.spacingFactor.value)
    self.refName = os.path.basename(referencePath)
    self.refName = os.path.splitext(self.refName)[0]
    self.subsampleInfo2.clear()
    self.subsampleInfo2.insertPlainText("The reference is {} \n".format(self.refName))
    self.subsampleInfo2.insertPlainText("The number of points in the downsampled reference pointcloud is {}".format(template_density))
    self.matchingPointsButton.enabled = True
  
  def onMatchingPointsButton(self):
    logic = ALPACALogic()
    template_density, matchedPoints, indices, files = logic.matchingPCD(self.modelsMultiSelector.currentPath, self.sparseTemplate, self.referenceNode, self.pcdOutputSelector.currentPath, self.spacingFactor.value, self.parameterDictionary)
    # Print results
    correspondent_threshold = 0.01
    self.subsampleInfo2.clear()
    self.subsampleInfo2.insertPlainText("The reference is {} \n".format(self.refName))
    self.subsampleInfo2.insertPlainText("The number of points in the downsampled reference pointcloud is {}. The error threshold for finding correspondent points is {}% \n".format(template_density, 
      correspondent_threshold*100))
    if len(indices) >0:
      self.subsampleInfo2.insertPlainText("There are {} files have points repeatedly matched with the same point(s) template, these are: \n".format(len(indices)))
      for i in indices:
        self.subsampleInfo2.insertPlainText("{}: {} unique points are sampled to match the template pointcloud \n".format(files[i], matchedPoints[i]))
      indices_error = [i for i in indices if (template_density - matchedPoints[i]) > template_density*correspondent_threshold]
      if len(indices_error) > 0:
        self.subsampleInfo2.insertPlainText("The specimens with sampling error larger than the threshold are: \n")
        for i in indices_error:
          self.subsampleInfo2.insertPlainText("{}: {} unique points are sampled. \n".format(files[i], matchedPoints[i]))
          self.subsampleInfo2.insertPlainText("It is recommended to check the alignment of these specimens with the template or experimenting with a higher spacing factor \n")
      else:
        self.subsampleInfo2.insertPlainText("All error rates smaller than the threshold \n")
    else:
      self.subsampleInfo2.insertPlainText("{} unique points are sampled from each model to match the template pointcloud \n")

  #If select multiple group input radiobutton, execute enterFactors function
  def onToggleGroupInput(self):
    if self.multiGroupInput.isChecked():
      self.enterFactors()
      # if hasattr(self, 'factorTableNode2'):
      #   self.factorTableNode2.GetDisplayNode().SetVisibility(False)
      self.resetTableButton.enabled = True
  
  #Reset input button
  def onRestTableButton(self):
    self.resetFactors()


  #Add table for entering user-defined catalogs/groups for each speciimen
  def enterFactors(self):
    #If has table node, remove table node and build a new one
    if hasattr(self, 'factorTableNode') == False:
      files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputSelector.currentPath)]
      sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
      sortedArray['filename']=files
      self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Groups Table')
      col1=self.factorTableNode.AddColumn()
      col1.SetName('ID')
      for i in range(len(files)):
        self.factorTableNode.AddEmptyRow()
        self.factorTableNode.SetCellText(i,0,sortedArray['filename'][i])
      col2=self.factorTableNode.AddColumn()
      col2.SetName('Group')
      #add table to new layout
      # slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
      # slicer.app.applicationLogic().PropagateTableSelection()
      # slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpPlotTableView)
      slicer.app.layoutManager().setLayout(503)
      slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
      slicer.app.applicationLogic().PropagateTableSelection()
      self.factorTableNode.GetTable().Modified()
    # else:
    #   slicer.app.layoutManager().setLayout(503)

  def resetFactors(self):
    if hasattr(self, 'factorTableNode'):
      slicer.mrmlScene.RemoveNode(self.factorTableNode) 
    files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputSelector.currentPath)]
    sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    sortedArray['filename']=files
    self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Groups Table')
    col1=self.factorTableNode.AddColumn()
    col1.SetName('ID')
    for i in range(len(files)):
      self.factorTableNode.AddEmptyRow()
      self.factorTableNode.SetCellText(i,0,sortedArray['filename'][i])
    col2=self.factorTableNode.AddColumn()
    col2.SetName('Group')
    #add table to new layout
    #add table to new layout
    # slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
    # slicer.app.applicationLogic().PropagateTableSelection()
    # slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpPlotTableView)
    slicer.app.layoutManager().setLayout(503)
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
    self.factorTableNode.GetTable().Modified()

#Display a table with Kmeans cluster labels without user-input group information
  def clusterTable(self, files, clusterID):
    # if hasattr(self, 'factorTableNode'):
    #   self.factorTableNode.GetDisplayNode().SetVisibility(False)
    if hasattr(self, 'factorTableNode2'):
      slicer.mrmlScene.RemoveNode(self.factorTableNode2) 
    sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    sortedArray['filename']=files
    self.factorTableNode2 = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Cluster table no group input')
    col1=self.factorTableNode2.AddColumn()
    col1.SetName('ID')
    for i in range(len(files)):
      self.factorTableNode2.AddEmptyRow()
      self.factorTableNode2.SetCellText(i,0, sortedArray['filename'][i])
      print(sortedArray['filename'][i])
    #Add cluster ID from kmeans to the table
    col2 = self.factorTableNode2.AddColumn()
    col2.SetName('Cluster ID')
    clusterID = np.array(clusterID)
    for i in range(len(files)):
      #self.factorTableNode2.AddEmptyRow()
      self.factorTableNode2.SetCellText(i, 1, clusterID[i])
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode2.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
    self.factorTableNode2.GetTable().Modified()    

#Display a table with Kmeans cluster labels with user-input group information
  def clusterTableWithGroups(self, files, groupFactorArray, groupClusterIDs):
    if hasattr(self, 'factorTableNode'):
    # self.factorTableNode.RemoveAllColumns()
      slicer.mrmlScene.RemoveNode(self.factorTableNode)
    # sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    # sortedArray['filename']=files
    self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Table with input groups')
    col1=self.factorTableNode.AddColumn()
    col1.SetName('ID')
    for i in range(len(files)):
      self.factorTableNode.AddEmptyRow()
      self.factorTableNode.SetCellText(i, 0, files[i])
    col2=self.factorTableNode.AddColumn()
    col2.SetName('Group')
    for i in range(len(files)):
      #self.factorTableNode.AddEmptyRow()
      self.factorTableNode.SetCellText(i, 1, groupFactorArray[i])
    #self.factorTableNode.RemoveColumn(2)
    col3 = self.factorTableNode.AddColumn()
    col3.SetName('Cluster ID')
    for i in range(len(files)):
      #self.factorTableNode.AddEmptyRow()
      self.factorTableNode.SetCellText(i, 2, groupClusterIDs[i])
    #add table to new layout
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
    self.factorTableNode.GetTable().Modified()


  #Generate templates based on kmeans and catalog
  def onkmeansTemplatesButton(self):
    import time
    start = time.time()
    logic = ALPACALogic()
    PCDFiles = os.listdir(self.pcdOutputSelector.currentPath)
    pcdFilePaths = [os.path.join(self.pcdOutputSelector.currentPath, file) for file in PCDFiles]
    #GPA for all specimens
    self.scores, self.LM = logic.pcdGPA(pcdFilePaths)
    files = [os.path.splitext(file)[0] for file in PCDFiles]
    #Set up a seed for numpy for random results 
    if self.setSeedCheckBox.isChecked():
      np.random.seed(1000)
    if self.noGroupInput.isChecked():
      templates, clusterID, templatesIndices = logic.templatesSelection(self.modelsMultiSelector.currentPath, self.scores, pcdFilePaths, self.templatesOutputSelector.currentPath, self.templatesNumber.value, self.kmeansIterations.value)
      clusterID = [str(x) for x in clusterID]
      print("kmeans cluster ID is: {}".format(clusterID))
      #groupFactorArray = ['1']*len(files)
      # groupFactorArray2 = groupFactorArray[:]
      # for index in templatesIndices:
      #   groupFactorArray2[index] = "Template"
      # print("templates indices are: ")
      print("templates indices are: {}".format(templatesIndices))
      #print(templates)
      self.templatesInfo.clear()
      self.templatesInfo.insertPlainText("One pooled group for all specimens. The {} selected templates are: \n".format(int(self.templatesNumber.value)))
      for file in templates:
        self.templatesInfo.insertPlainText(file + "\n")
      #Add cluster ID from kmeans to the table
      #self.clusterTable(files, clusterID)
      self.plotClusters(files, templatesIndices)
      print(f'Time: {time.time() - start}')
    # multiClusterCheckbox is checked
    else:
      if hasattr(self, 'factorTableNode'):
        self.templatesInfo.clear()
        factorCol = self.factorTableNode.GetTable().GetColumn(1)
        groupFactorArray=[]
        for i in range(factorCol.GetNumberOfTuples()):
          temp = factorCol.GetValue(i).rstrip()
          temp = str(temp).upper()
          groupFactorArray.append(temp)
        print(groupFactorArray)
        # groupFactorArray2 = groupFactorArray[:]
        #Count the number of non-null enties in the table
        countInput = 0
        for i in range(len(groupFactorArray)):
          if groupFactorArray[i] != '':
            countInput += 1
        if countInput == len(PCDFiles): #check if group information is input for all specimens
          uniqueFactors = list(set(groupFactorArray))
          groupNumber = len(uniqueFactors)
          self.templatesInfo.insertPlainText("The sample is divided into {} groups. The templates for each group are: \n".format(groupNumber))
          #clustersPaths = {}
          #groupIndices = {}
          #groupIDs = {}
          groupClusterIDs = [None]*len(files)
          templatesIndices = []
          for i in range(groupNumber):
            factorName = uniqueFactors[i]
            #Get indices for the ith cluster
            indices = [i for i, x in enumerate(groupFactorArray) if x == factorName]
            print("indices for " + factorName + " is:")
            print(indices)
            key = factorName
            paths = []
            for i in range(len(indices)):
              path = pcdFilePaths[indices[i]]
              paths.append(path)
            #clustersPaths[key] = paths
            #groupIndices[key] = indices
            #PC scores of specimens belong to a specific group
            tempScores = self.scores[indices, :]
            #print("tempScores.shape="+str(tempScores.shape))
            templates, clusterID, tempIndices = logic.templatesSelection(self.modelsMultiSelector.currentPath, tempScores, paths, self.templatesOutputSelector.currentPath, self.templatesNumber.value, self.kmeansIterations.value)
            print("Kmeans-cluster IDs for " + factorName + " are:")
            print(clusterID)
            templatesIndices = templatesIndices + [indices[i] for i in tempIndices]
            # for index in templatesIndices:
            #   groupFactorArray2[index] = "Template"
            #groupIDs[key] = clusterID
            self.templatesInfo.insertPlainText("Group " + factorName + "\n")
            for file in templates:
              self.templatesInfo.insertPlainText(file + "\n")
            #Prepare cluster ID for each group
            uniqueClusterID = list(set(clusterID))
            for i in range(len(uniqueClusterID)):
              for j in range(len(clusterID)):
                if clusterID[j] == uniqueClusterID[i]:
                  index = indices[j]
                  groupClusterIDs[index] = factorName + str(i + 1)
                  print(groupClusterIDs[index])
          #Plot PC1 and PC 2 based on kmeans clusters
          print("group cluster ID are {}".format(groupClusterIDs))
          print("Templates indices are: {}".format(templatesIndices))
          #self.clusterTableWithGroups(files, groupFactorArray, groupClusterIDs)
          self.plotClustersWithFactors(files, groupFactorArray, templatesIndices)
          print(f'Time: {time.time() - start}')
        else:   #if the user input a factor requiring more than 3 groups, do not use factor
          qt.QMessageBox.critical(slicer.util.mainWindow(),
          'Error', 'Please enter group information for every specimen')          
      else:
        qt.QMessageBox.critical(slicer.util.mainWindow(),
          'Error', 'Please select Multiple groups within the sample option and enter group information for each specimen')
      # print(f'Time: {time.time() - start}')
      
  def plotClustersWithFactors(self, files, groupFactors, templatesIndices):
    logic = ALPACALogic()
    import Support.gpa_lib as gpa_lib
    #Set up scatter plot
    pcNumber = 2
    shape = self.LM.lm.shape
    scatterDataAll= np.zeros(shape=(shape[2], pcNumber))    
    for i in range(pcNumber):
      data=gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig,i,1)
      scatterDataAll[:,i] = data[:,0]    
    factorNP = np.array(groupFactors)
    #import GPA
    #GPALogic = GPA.GPALogic()    
    logic.makeScatterPlotWithFactors(scatterDataAll, files, factorNP,
      'PCA Scatter Plots',"PC1","PC2", pcNumber, templatesIndices)
  
  def plotClusters(self, files, templatesIndices):
    logic = ALPACALogic()
    import Support.gpa_lib as gpa_lib
    #Set up scatter plot
    pcNumber = 2
    shape = self.LM.lm.shape
    scatterDataAll= np.zeros(shape=(shape[2], pcNumber))    
    for i in range(pcNumber):
      data=gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig,i,1)
      scatterDataAll[:,i] = data[:,0]    
    #import GPA
    #GPALogic = GPA.GPALogic()    
    logic.makeScatterPlot(scatterDataAll, files,
      'PCA Scatter Plots',"PC1","PC2", pcNumber, templatesIndices)    
      
  def updateLayout(self):
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(9)  #set layout to 3D only
    layoutManager.threeDWidget(0).threeDView().resetFocalPoint()
    layoutManager.threeDWidget(0).threeDView().resetCamera()
    
  def onChangeAdvanced(self):
    self.updateParameterDictionary()
  
  def onChangeMultiTemplate(self):
    if self.MethodBatchWidget.currentText == 'Multi-Template(MALPACA)':
      self.sourceModelMultiSelector.currentPath = ''
      self.sourceModelMultiSelector.filters  = ctk.ctkPathLineEdit.Dirs
      self.sourceModelMultiSelector.toolTip = "Select a directory containing the source meshes (note: filenames must match with landmark filenames)"
      self.sourceFiducialMultiSelector.currentPath = ''
      self.sourceFiducialMultiSelector.filters  = ctk.ctkPathLineEdit.Dirs
      self.sourceFiducialMultiSelector.toolTip = "Select a directory containing the landmark files (note:filenames must match with source meshes)"
    else:
      self.sourceModelMultiSelector.filters  = ctk.ctkPathLineEdit().Files
      self.sourceModelMultiSelector.nameFilters  = ["*.ply"]
      self.sourceModelMultiSelector.toolTip = "Select the source mesh"
      self.sourceFiducialMultiSelector.filters  = ctk.ctkPathLineEdit().Files
      self.sourceFiducialMultiSelector.nameFilters  = ["*.fcsv"]
      self.sourceFiducialMultiSelector.toolTip = "Select the source landmarks"
  
  def onResetScene(self):
    try:
      self.ICPTransformNode.Inverse()
      self.sourceModelNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceModelNode)
      self.sourceModelNode.GetDisplayNode().SetVisibility(True)
      self.targetModelNode.GetDisplayNode().SetVisibility(True)
      self.sourceModelNode.GetDisplayNode().SetColor([1,1,0])
    except:
      pass
    try:
      slicer.mrmlScene.RemoveNode(self.targetCloudNode)
      slicer.mrmlScene.RemoveNode(self.sourceCloudNode)
      slicer.mrmlScene.RemoveNode(self.outputPoints)
      slicer.mrmlScene.RemoveNode(self.ICPTransformNode)
      slicer.mrmlScene.RemoveNode(self.warpedSourceNode)
      slicer.mrmlScene.RemoveNode(self.sourceLMNode)
      slicer.mrmlScene.RemoveNode(self.projectedLandmarks)
    except:
      pass
    self.alignButton.enabled = False
    self.displayMeshButton.enabled = False
    self.CPDRegistrationButton.enabled = False
    self.displayWarpedModelButton.enabled = False
    self.resetSceneButton.enabled = False


  def onChangeCPD(self):
    if self.Acceleration.checked != 0:
      self.BCPDFolder.enabled = True
      self.subsampleButton.enabled = bool ( self.sourceModelSelector.currentNode() and self.targetModelSelector.currentNode() and self.sourceFiducialSelector.currentNode() and self.BCPDFolder.currentPath)
      self.applyLandmarkMultiButton.enabled = bool ( self.sourceModelMultiSelector.currentPath and self.sourceFiducialMultiSelector.currentPath 
      and self.targetModelMultiSelector.currentPath and self.landmarkOutputSelector.currentPath and self.BCPDFolder.currentPath)
    else:
      self.BCPDFolder.enabled = False
      self.subsampleButton.enabled = bool ( self.sourceModelSelector.currentPath and self.targetModelSelector.currentPath and self.sourceFiducialSelector.currentPath)
      self.applyLandmarkMultiButton.enabled = bool ( self.sourceModelMultiSelector.currentPath and self.sourceFiducialMultiSelector.currentPath 
      and self.targetModelMultiSelector.currentPath and self.landmarkOutputSelector.currentPath)
    
  def updateParameterDictionary(self):    
    # update the parameter dictionary from single run parameters
    if hasattr(self, 'parameterDictionary'):
      self.parameterDictionary["projectionFactor"] = self.projectionFactor.value
      self.parameterDictionary["pointDensity"] = self.pointDensity.value
      self.parameterDictionary["normalSearchRadius"] = int(self.normalSearchRadius.value)
      self.parameterDictionary["FPFHSearchRadius"] = int(self.FPFHSearchRadius.value)
      self.parameterDictionary["distanceThreshold"] = self.distanceThreshold.value
      self.parameterDictionary["maxRANSAC"] = int(self.maxRANSAC.value)
      self.parameterDictionary["maxRANSACValidation"] = int(self.maxRANSACValidation.value)
      self.parameterDictionary["ICPDistanceThreshold"] = self.ICPDistanceThreshold.value
      self.parameterDictionary["alpha"] = self.alpha.value
      self.parameterDictionary["beta"] = self.beta.value
      self.parameterDictionary["CPDIterations"] = int(self.CPDIterations.value)
      self.parameterDictionary["CPDTolerance"] = self.CPDTolerance.value
      self.parameterDictionary["Acceleration"] = self.Acceleration.checked
      self.parameterDictionary["BCPDFolder"] = self.BCPDFolder.currentPath
      

      
  def addAdvancedMenu(self, currentWidgetLayout):

    # Point density label
    pointDensityCollapsibleButton=ctk.ctkCollapsibleButton()
    pointDensityCollapsibleButton.text = "Point density and max projection"
    currentWidgetLayout.addRow(pointDensityCollapsibleButton)
    pointDensityFormLayout = qt.QFormLayout(pointDensityCollapsibleButton)

    # Rigid registration label
    rigidRegistrationCollapsibleButton=ctk.ctkCollapsibleButton()
    rigidRegistrationCollapsibleButton.text = "Rigid registration"
    currentWidgetLayout.addRow(rigidRegistrationCollapsibleButton)
    rigidRegistrationFormLayout = qt.QFormLayout(rigidRegistrationCollapsibleButton)
    
    # Deformable registration label
    deformableRegistrationCollapsibleButton=ctk.ctkCollapsibleButton()
    deformableRegistrationCollapsibleButton.text = "Deformable registration"
    currentWidgetLayout.addRow(deformableRegistrationCollapsibleButton)
    deformableRegistrationFormLayout = qt.QFormLayout(deformableRegistrationCollapsibleButton)

    # Point Density slider
    pointDensity = ctk.ctkSliderWidget()
    pointDensity.singleStep = 0.1
    pointDensity.minimum = 0.1
    pointDensity.maximum = 3
    pointDensity.value = 1
    pointDensity.setToolTip("Adjust the density of the pointclouds. Larger values increase the number of points, and vice versa.")
    pointDensityFormLayout.addRow("Point Density Adjustment: ", pointDensity)

    # Set max projection factor
    projectionFactor = ctk.ctkSliderWidget()
    projectionFactor.enabled = True
    projectionFactor.singleStep = 1
    projectionFactor.minimum = 0
    projectionFactor.maximum = 10
    projectionFactor.value = 1
    projectionFactor.setToolTip("Set maximum point projection as a percentage of the image diagonal. Point projection is used to make sure predicted landmarks are placed on the target mesh.")
    pointDensityFormLayout.addRow("Maximum projection factor : ", projectionFactor)

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
    alpha.setDecimals(1)
    alpha.minimum = 0.1
    alpha.maximum = 10
    alpha.value = 2
    alpha.setToolTip("Parameter specifying trade-off between fit and smoothness. Low values induce fluidity, while higher values impose rigidity")
    deformableRegistrationFormLayout.addRow("Rigidity (alpha): ", alpha)

    # Beta slider
    beta = ctk.ctkDoubleSpinBox()
    beta.singleStep = 0.1
    beta.setDecimals(1)
    beta.minimum = 0.1
    beta.maximum = 10
    beta.value = 2
    beta.setToolTip("Width of gaussian filter used when applying smoothness constraint")
    deformableRegistrationFormLayout.addRow("Motion coherence (beta): ", beta)

    # CPD iterations slider
    CPDIterations = ctk.ctkSliderWidget()
    CPDIterations.singleStep = 1
    CPDIterations.minimum = 100
    CPDIterations.maximum = 1000
    CPDIterations.value = 100
    CPDIterations.setToolTip("Maximum number of iterations of the CPD procedure")
    deformableRegistrationFormLayout.addRow("CPD iterations: ", CPDIterations)

    # CPD tolerance slider
    CPDTolerance = ctk.ctkSliderWidget()
    CPDTolerance.setDecimals(4)
    CPDTolerance.singleStep = .0001
    CPDTolerance.minimum = 0.0001
    CPDTolerance.maximum = 0.01
    CPDTolerance.value = 0.001
    CPDTolerance.setToolTip("Tolerance used to assess CPD convergence")
    deformableRegistrationFormLayout.addRow("CPD tolerance: ", CPDTolerance)

    # Acceleration checkbox
    Acceleration = qt.QCheckBox()
    Acceleration.checked = 0
    Acceleration.setToolTip("If checked, ALPACA will accelerate the deformable step using VBI.")
    deformableRegistrationFormLayout.addRow("Acceleration", Acceleration)  

    # Compiled BCPD directory
    BCPDFolder = ctk.ctkPathLineEdit()
    BCPDFolder.filters = ctk.ctkPathLineEdit.Dirs
    BCPDFolder.toolTip = "Select the directory of containing the compiled BCPD"
    BCPDFolder.enabled = False
    deformableRegistrationFormLayout.addRow("BCPD directory: ", BCPDFolder)
  

    return projectionFactor, pointDensity, normalSearchRadius, FPFHSearchRadius, distanceThreshold, maxRANSAC, maxRANSACValidation, ICPDistanceThreshold, alpha, beta, CPDIterations, CPDTolerance, Acceleration, BCPDFolder
    
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
 
  def runLandmarkMultiprocess(self, sourceModelPath, sourceLandmarkPath, targetModelDirectory, outputDirectory, skipScaling, projectionFactor, parameters):
    extras = {"Source" : sourceModelPath, "SourceLandmarks" : sourceLandmarkPath, "Target" : targetModelDirectory, "Output" : outputDirectory, 'Skip scaling ?' : bool(skipScaling)}
    extras.update(parameters)
    parameterFile = os.path.join(outputDirectory, 'advancedParameters.txt')
    json.dump(extras, open(parameterFile,'w'), indent = 2)
    extensionModel = ".ply"
    if os.path.isdir(sourceModelPath):
        specimenOutput = os.path.join(outputDirectory,'individualEstimates')
        medianOutput = os.path.join(outputDirectory,'medianEstimates')
        os.makedirs(specimenOutput, exist_ok=True)
        os.makedirs(medianOutput, exist_ok=True)
    # Iterate through target models
    for targetFileName in os.listdir(targetModelDirectory):
      if targetFileName.endswith(extensionModel):
        targetFilePath = os.path.join(targetModelDirectory, targetFileName)
        rootName = os.path.splitext(targetFileName)[0]  
        landmarkList = []
        if os.path.isdir(sourceModelPath):
          outputMedianPath = os.path.join(medianOutput, f'{rootName}_median.fcsv')
          if not os.path.exists(outputMedianPath):
            for file in os.listdir(sourceModelPath):
              if file.endswith(extensionModel):
                sourceFilePath = os.path.join(sourceModelPath,file)
                (baseName, ext) = os.path.splitext(file)
                sourceLandmarkFile = os.path.join(sourceLandmarkPath, f'{baseName}.fcsv')
                outputFilePath = os.path.join(specimenOutput, f'{rootName}_{baseName}.fcsv')
                array = self.pairwiseAlignment(sourceFilePath, sourceLandmarkFile, targetFilePath, outputFilePath, skipScaling, projectionFactor, parameters)
                landmarkList.append(array)
            medianLandmark = np.median(landmarkList, axis=0)
            outputMedianNode = self.exportPointCloud(medianLandmark, "Median Predicted Landmarks")     
            slicer.util.saveNode(outputMedianNode, outputMedianPath)
            slicer.mrmlScene.RemoveNode(outputMedianNode)
        elif os.path.isfile(sourceModelPath):
            rootName = os.path.splitext(targetFileName)[0]
            outputFilePath = os.path.join(outputDirectory, rootName + ".fcsv")
            array = self.pairwiseAlignment(sourceModelPath, sourceLandmarkPath, targetFilePath, outputFilePath, skipScaling, projectionFactor, parameters)
        else:
            print('::::Could not find the file or directory in question')


  def pairwiseAlignment (self, sourceFilePath, sourceLandmarkFile, targetFilePath, outputFilePath, skipScaling, projectionFactor, parameters):
    targetModelNode = slicer.util.loadModel(targetFilePath)
    targetModelNode.GetDisplayNode().SetVisibility(False)
    sourceModelNode = slicer.util.loadModel(sourceFilePath)
    sourceModelNode.GetDisplayNode().SetVisibility(False)
    sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, scaling = self.runSubsample(sourceModelNode, 
        targetModelNode, skipScaling, parameters)
    ICPTransform = self.estimateTransform(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, skipScaling, parameters)
    #Rigid
    sourceLandmarks, sourceLMNode = self.loadAndScaleFiducials(sourceLandmarkFile, scaling)
    sourceLandmarks.transform(ICPTransform)
    sourcePoints.transform(ICPTransform)
    #Deformable
    registeredSourceLM = self.runCPDRegistration(sourceLandmarks.points, sourcePoints.points, targetPoints.points, parameters)
    outputPoints = self.exportPointCloud(registeredSourceLM, "Initial Predicted Landmarks")
    if projectionFactor == 0:
        self.propagateLandmarkTypes(sourceLMNode, outputPoints)
        slicer.util.saveNode(outputPoints, outputFilePath)
        slicer.mrmlScene.RemoveNode(outputPoints)
        slicer.mrmlScene.RemoveNode(sourceModelNode)
        slicer.mrmlScene.RemoveNode(targetModelNode)
        slicer.mrmlScene.RemoveNode(sourceLMNode)
        return registeredSourceLM
    else: 
        inputPoints = self.exportPointCloud(sourceLandmarks.points, "Original Landmarks")
        inputPoints_vtk = self.getFiducialPoints(inputPoints)
        outputPoints_vtk = self.getFiducialPoints(outputPoints)

        ICPTransformNode = self.convertMatrixToTransformNode(ICPTransform, 'Rigid Transformation Matrix')
        sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
        deformedModelNode = self.applyTPSTransform(inputPoints_vtk, outputPoints_vtk, sourceModelNode, 'Warped Source Mesh')
        deformedModelNode.GetDisplayNode().SetVisibility(False)

        maxProjection = (targetModelNode.GetPolyData().GetLength()) * projectionFactor
        projectedPoints = self.projectPointsPolydata(deformedModelNode.GetPolyData(), targetModelNode.GetPolyData(), outputPoints_vtk, maxProjection)
        projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"Refined Predicted Landmarks")
        for i in range(projectedPoints.GetNumberOfPoints()):
            point = projectedPoints.GetPoint(i)
            projectedLMNode.AddFiducialFromArray(point)
        self.propagateLandmarkTypes(sourceLMNode, projectedLMNode) 
        slicer.util.saveNode(projectedLMNode, outputFilePath)
        slicer.mrmlScene.RemoveNode(projectedLMNode)
        slicer.mrmlScene.RemoveNode(outputPoints)
        slicer.mrmlScene.RemoveNode(sourceModelNode)
        slicer.mrmlScene.RemoveNode(targetModelNode)
        slicer.mrmlScene.RemoveNode(deformedModelNode)
        slicer.mrmlScene.RemoveNode(sourceLMNode)
        slicer.mrmlScene.RemoveNode(ICPTransformNode)
        slicer.mrmlScene.RemoveNode(inputPoints)
        np_array = vtk_np.vtk_to_numpy(projectedPoints.GetPoints().GetData())
        return np_array
          

  def exportPointCloud(self, pointCloud, nodeName):
    fiducialNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',nodeName)
    for point in pointCloud:
      fiducialNode.AddFiducialFromArray(point) 
    return fiducialNode

    #node.AddFiducialFromArray(point)
  def applyTPSTransform(self, sourcePoints, targetPoints, modelNode, nodeName):
    transform=vtk.vtkThinPlateSplineTransform()  
    transform.SetSourceLandmarks( sourcePoints)
    transform.SetTargetLandmarks( targetPoints )
    transform.SetBasisToR() # for 3D transform
    
    transformFilter = vtk.vtkTransformPolyDataFilter()
    transformFilter.SetInputData(modelNode.GetPolyData())
    transformFilter.SetTransform(transform)
    transformFilter.Update()
    
    warpedPolyData = transformFilter.GetOutput()
    warpedModelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', nodeName)
    warpedModelNode.CreateDefaultDisplayNodes()
    warpedModelNode.SetAndObservePolyData(warpedPolyData)
    #self.RAS2LPSTransform(warpedModelNode)
    return warpedModelNode
      
  def runCPDRegistration(self, sourceLM, sourceSLM, targetSLM, parameters):
    from open3d import geometry
    from open3d import utility
    sourceArrayCombined = np.append(sourceSLM, sourceLM, axis=0)
    targetArray = np.asarray(targetSLM)
    #Convert to pointcloud for scaling
    sourceCloud = geometry.PointCloud()
    sourceCloud.points = utility.Vector3dVector(sourceArrayCombined)
    targetCloud = geometry.PointCloud()
    targetCloud.points = utility.Vector3dVector(targetArray)
    cloudSize = np.max(targetCloud.get_max_bound() - targetCloud.get_min_bound())
    targetCloud.scale(25 / cloudSize, center = (0,0,0))
    sourceCloud.scale   (25 / cloudSize, center = (0,0,0))
    #Convert back to numpy for cpd
    sourceArrayCombined = np.asarray(sourceCloud.points,dtype=np.float32)
    targetArray = np.asarray(targetCloud.points,dtype=np.float32)
    if parameters['Acceleration'] == 0:
      registrationOutput = self.cpd_registration(targetArray, sourceArrayCombined, parameters["CPDIterations"], parameters["CPDTolerance"], parameters["alpha"], parameters["beta"])
      deformed_array, _ = registrationOutput.register()
    else:
      np.savetxt ('target.txt', targetArray, delimiter=',')
      np.savetxt ('source.txt', sourceArrayCombined, delimiter=',')
      path = os.path.join(parameters["BCPDFolder"], 'bcpd') 
      cmd = f'{path} -x target.txt -y source.txt -l{parameters["alpha"]} -b{parameters["beta"]} -g0.1 -K140 -J500 -c1e-6 -p -d7 -e0.3 -f0.3 -ux -N1'
      subprocess.run(cmd, shell = True, check = True)
      deformed_array = np.loadtxt('output_y.txt')
      for fl in glob.glob("output*.txt"):
        os.remove(fl)
      os.remove('target.txt')
      os.remove('source.txt')
    #Capture output landmarks from source pointcloud
    fiducial_prediction = deformed_array[-len(sourceLM):]
    fiducialCloud = geometry.PointCloud()
    fiducialCloud.points = utility.Vector3dVector(fiducial_prediction)
    fiducialCloud.scale(cloudSize/25, center = (0,0,0))
    return np.asarray(fiducialCloud.points)
    
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
    
  def estimateTransform(self, sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, skipScaling, parameters):
    ransac = self.execute_global_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize * 2.5, 
      parameters["distanceThreshold"], parameters["maxRANSAC"], parameters["maxRANSACValidation"], skipScaling)
    
    # Refine the initial registration using an Iterative Closest Point (ICP) registration
    #import time
    #start = time.time()
    icp = self.refine_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize * 2.5, ransac, parameters["ICPDistanceThreshold"]) 
    #print(f'Time: {time.time() - start}')
    return icp.transformation                                    
  
  def runSubsample(self, sourceModel, targetModel, skipScaling, parameters):
    from open3d import io
    from open3d import geometry
    from open3d import utility
    print(":: Loading point clouds and downsampling")
    sourcePoints = slicer.util.arrayFromModelPoints(sourceModel)
    source = geometry.PointCloud()
    source.points = utility.Vector3dVector(sourcePoints)
    targetPoints = slicer.util.arrayFromModelPoints(targetModel)
    target = geometry.PointCloud()
    target.points = utility.Vector3dVector(targetPoints)
    sourceSize = np.linalg.norm(np.asarray(source.get_max_bound()) - np.asarray(source.get_min_bound())) 
    targetSize = np.linalg.norm(np.asarray(target.get_max_bound()) - np.asarray(target.get_min_bound()))
    voxel_size = targetSize/(55*parameters["pointDensity"])
    scaling = (targetSize)/sourceSize
    if skipScaling != 0:
        scaling = 1
    source.scale(scaling, center = (0,0,0)) 
    points = slicer.util.arrayFromModelPoints(sourceModel)
    points[:] = np.asarray(source.points)
    sourceModel.GetPolyData().GetPoints().GetData().Modified()
    source_down, source_fpfh = self.preprocess_point_cloud(source, voxel_size, parameters["normalSearchRadius"], parameters["FPFHSearchRadius"])
    target_down, target_fpfh = self.preprocess_point_cloud(target, voxel_size, parameters["normalSearchRadius"], parameters["FPFHSearchRadius"])
    return source_down, target_down, source_fpfh, target_fpfh, voxel_size, scaling
  
  def loadAndScaleFiducials (self, fiducial, scaling, scene = False): 
    from open3d import geometry
    from open3d import utility
    if not scene:
      sourceLandmarkNode =  slicer.util.loadMarkups(fiducial)
    else:
      shNode= slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      itemIDToClone = shNode.GetItemByDataNode(fiducial)
      clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
      sourceLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    point = [0,0,0]
    sourceLandmarks = np.zeros(shape=(sourceLandmarkNode.GetNumberOfFiducials(),3))
    for i in range(sourceLandmarkNode.GetNumberOfFiducials()):
      sourceLandmarkNode.GetMarkupPoint(0,i,point)
      sourceLandmarks[i,:] = point
    cloud = geometry.PointCloud()
    cloud.points = utility.Vector3dVector(sourceLandmarks)
    cloud.scale(scaling, center = (0,0,0))
    slicer.util.updateMarkupsControlPointsFromArray(sourceLandmarkNode,np.asarray(cloud.points))
    sourceLandmarkNode.GetDisplayNode().SetVisibility(False)
    return cloud, sourceLandmarkNode
  
  def propagateLandmarkTypes(self,sourceNode, targetNode):
     for i in range(sourceNode.GetNumberOfControlPoints()):
       pointDescription = sourceNode.GetNthControlPointDescription(i)
       targetNode.SetNthControlPointDescription(i,pointDescription)
       pointLabel = sourceNode.GetNthFiducialLabel(i)
       targetNode.SetNthFiducialLabel(i, pointLabel)
               
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
    
  def preprocess_point_cloud(self, pcd, voxel_size, radius_normal_factor, radius_feature_factor):
    from open3d import geometry
    from open3d import registration
    print(":: Downsample with a voxel size %.3f." % voxel_size)
    pcd_down = pcd.voxel_down_sample(voxel_size)
    radius_normal = voxel_size * radius_normal_factor
    print(":: Estimate normal with search radius %.3f." % radius_normal)
    pcd_down.estimate_normals(
        geometry.KDTreeSearchParamHybrid(radius=radius_normal, max_nn=30))
    radius_feature = voxel_size * radius_feature_factor
    print(":: Compute FPFH feature with search radius %.3f." % radius_feature)
    pcd_fpfh = registration.compute_fpfh_feature(
        pcd_down,
        geometry.KDTreeSearchParamHybrid(radius=radius_feature, max_nn=100))
    return pcd_down, pcd_fpfh



  def execute_global_registration(self, source_down, target_down, source_fpfh,
                                target_fpfh, voxel_size, distance_threshold_factor, maxIter, maxValidation, skipScaling):
    from open3d import registration
    distance_threshold = voxel_size * distance_threshold_factor
    print(":: RANSAC registration on downsampled point clouds.")
    print("   Since the downsampling voxel size is %.3f," % voxel_size)
    print("   we use a liberal distance threshold %.3f." % distance_threshold)
    #registration = piplines.registration
    result = registration.registration_ransac_based_on_feature_matching(
        source_down, target_down, source_fpfh, target_fpfh, distance_threshold,
        registration.TransformationEstimationPointToPoint(skipScaling == 0), 4, [
            registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
            registration.CorrespondenceCheckerBasedOnDistance(
                distance_threshold)
        ], registration.RANSACConvergenceCriteria(maxIter, maxValidation))
    return result


  def refine_registration(self, source, target, source_fpfh, target_fpfh, voxel_size, result_ransac, ICPThreshold_factor):
    from open3d import registration
    distance_threshold = voxel_size * ICPThreshold_factor
    print(":: Point-to-plane ICP registration is applied on original point")
    print("   clouds to refine the alignment. This time we use a strict")
    print("   distance threshold %.3f." % distance_threshold)
    result = registration.registration_icp(
        source, target, distance_threshold, result_ransac.transformation,
        registration.TransformationEstimationPointToPlane())
    return result
    
  def cpd_registration(self, targetArray, sourceArray, CPDIterations, CPDTolerance, alpha_parameter, beta_parameter):
    from cpdalp import DeformableRegistration
    output = DeformableRegistration(**{'X': targetArray, 'Y': sourceArray,'max_iterations': CPDIterations, 'tolerance': CPDTolerance, 'low_rank':True}, alpha = alpha_parameter, beta  = beta_parameter)
    return output
    
  def getFiducialPoints(self,fiducialNode):
    points = vtk.vtkPoints()
    point=[0,0,0]
    for i in range(fiducialNode.GetNumberOfFiducials()):
      fiducialNode.GetNthFiducialPosition(i,point)
      points.InsertNextPoint(point)
    
    return points
    
  def runPointProjection(self, template, model, templateLandmarks, maxProjectionFactor):
    maxProjection = (model.GetPolyData().GetLength()) * maxProjectionFactor
    print("Max projection: ", maxProjection)
    templatePoints = self.getFiducialPoints(templateLandmarks)
      
    # project landmarks from template to model
    projectedPoints = self.projectPointsPolydata(template.GetPolyData(), model.GetPolyData(), templatePoints, maxProjection)
    projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"Refined Predicted Landmarks")
    for i in range(projectedPoints.GetNumberOfPoints()):
      point = projectedPoints.GetPoint(i)
      projectedLMNode.AddFiducialFromArray(point)
    return projectedLMNode
  
  def projectPointsPolydata(self, sourcePolydata, targetPolydata, originalPoints, rayLength):
    print("original points: ", originalPoints.GetNumberOfPoints())
    #set up polydata for projected points to return
    projectedPointData = vtk.vtkPolyData()
    projectedPoints = vtk.vtkPoints()
    projectedPointData.SetPoints(projectedPoints)
    
    #set up locater for intersection with normal vector rays
    obbTree = vtk.vtkOBBTree()
    obbTree.SetDataSet(targetPolydata)
    obbTree.BuildLocator()
    
    #set up point locator for finding surface normals and closest point
    pointLocator = vtk.vtkPointLocator()
    pointLocator.SetDataSet(sourcePolydata)
    pointLocator.BuildLocator()
    
    targetPointLocator = vtk.vtkPointLocator()
    targetPointLocator.SetDataSet(targetPolydata)
    targetPointLocator.BuildLocator()
    
    #get surface normal from each landmark point
    rayDirection=[0,0,0]
    normalArray = sourcePolydata.GetPointData().GetArray("Normals")
    if(not normalArray):
      print("no normal array, calculating....")
      normalFilter=vtk.vtkPolyDataNormals()
      normalFilter.ComputePointNormalsOn()
      normalFilter.SetInputData(sourcePolydata)
      normalFilter.Update()
      normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
      if(not normalArray):
        print("Error: no normal array")
        return projectedPointData
    for index in range(originalPoints.GetNumberOfPoints()):
      originalPoint= originalPoints.GetPoint(index)
      # get ray direction from closest normal
      closestPointId = pointLocator.FindClosestPoint(originalPoint)
      rayDirection = normalArray.GetTuple(closestPointId)
      rayEndPoint=[0,0,0]
      for dim in range(len(rayEndPoint)):
        rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* rayLength
      intersectionIds=vtk.vtkIdList()
      intersectionPoints=vtk.vtkPoints()
      obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
      #if there are intersections, update the point to most external one.
      if intersectionPoints.GetNumberOfPoints() > 0:
        exteriorPoint = intersectionPoints.GetPoint(intersectionPoints.GetNumberOfPoints()-1)
        projectedPoints.InsertNextPoint(exteriorPoint)
      #if there are no intersections, reverse the normal vector
      else: 
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* -rayLength
        obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(0)
          projectedPoints.InsertNextPoint(exteriorPoint)
        #if none in reverse direction, use closest mesh point
        else:
          closestPointId = targetPointLocator.FindClosestPoint(originalPoint)
          rayOrigin = targetPolydata.GetPoint(closestPointId)
          projectedPoints.InsertNextPoint(rayOrigin)
    return projectedPointData
    
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

###Functions for select templates based on kmeans
  def downReference(self, referenceFilePath, spacingFactor):
    targetModelNode = slicer.util.loadModel(referenceFilePath)
    targetModelNode.GetDisplayNode().SetVisibility(False)
    templatePolydata = targetModelNode.GetPolyData()
    sparseTemplate = self.DownsampleTemplate(templatePolydata, spacingFactor)
    template_density = sparseTemplate.GetNumberOfPoints()
    return sparseTemplate, template_density, targetModelNode

  def matchingPCD(self, modelsDir, sparseTemplate, targetModelNode, pcdOutputDir, spacingFactor, parameterDictionary):
    template_density = sparseTemplate.GetNumberOfPoints()
    ID_list = list()
    #Alignment and matching points
    for file in os.listdir(modelsDir):
      sourceFilePath = os.path.join(modelsDir, file)
      sourceModelNode = slicer.util.loadModel(sourceFilePath)
      sourceModelNode.GetDisplayNode().SetVisibility(False)
      rootName = os.path.splitext(file)[0]
      skipScalingOption = False
      sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, scaling = self.runSubsample(sourceModelNode, targetModelNode, 
        skipScalingOption, parameterDictionary)
      ICPTransform = self.estimateTransform(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, skipScalingOption, parameterDictionary)
      ICPTransformNode = self.convertMatrixToTransformNode(ICPTransform, 'Rigid Transformation Matrix')
      sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)
      #Save aligned models
      #slicer.util.saveNode(sourceModelNode, "C:/Users/czhan2/Desktop/Mouse MALPACA/Mouse data/Aligned_models/{}.ply".format(rootName))
      alignedSubjectPolydata = sourceModelNode.GetPolyData()
      ID, correspondingSubjectPoints = self.GetCorrespondingPoints(sparseTemplate, alignedSubjectPolydata)
      ID_list.append(ID)
      subjectFiducial = slicer.vtkMRMLMarkupsFiducialNode()
      for i in range(correspondingSubjectPoints.GetNumberOfPoints()):
        subjectFiducial.AddFiducial(correspondingSubjectPoints.GetPoint(i)[0],
          correspondingSubjectPoints.GetPoint(i)[1], correspondingSubjectPoints.GetPoint(i)[2]) 
      slicer.mrmlScene.AddNode(subjectFiducial)
      slicer.util.saveNode(subjectFiducial, os.path.join(pcdOutputDir, "{}.fcsv".format(rootName)))
      slicer.mrmlScene.RemoveNode(sourceModelNode)
      slicer.mrmlScene.RemoveNode(ICPTransformNode)
      slicer.mrmlScene.RemoveNode(subjectFiducial)
    #Remove template node  
    slicer.mrmlScene.RemoveNode(targetModelNode)  
    #Printing results of points matching
    matchedPoints = [len(set(x)) for x in ID_list]
    indices = [i for i, x in enumerate(matchedPoints) if x < template_density]
    files = [os.path.splitext(file)[0] for file in os.listdir(modelsDir)]
    return template_density, matchedPoints, indices, files

  #inputFilePaths: file paths of pcd files
  def pcdGPA(self, inputFilePaths):
    basename, extension = os.path.splitext(inputFilePaths[0])
    import GPA
    GPAlogic = GPA.GPALogic()
    LM = GPA.LMData()
    LMExclusionList = []
    LM.lmOrig, landmarkTypeArray = GPAlogic.loadLandmarks(inputFilePaths, LMExclusionList, extension)
    shape = LM.lmOrig.shape
    skipScalingOption = 0
    LM.doGpa(skipScalingOption)
    LM.calcEigen()
    import Support.gpa_lib as gpa_lib
    twoDcoors=gpa_lib.makeTwoDim(LM.lmOrig)
    scores=np.dot(np.transpose(twoDcoors),LM.vec)
    scores=np.real(scores)
    size = scores.shape[0]-1
    scores = scores[:, 0:size]
    return scores, LM
  
  def templatesSelection(self, modelsDir, scores, inputFilePaths, templatesOutputDir, templatesNumber, iterations):
    templatesNumber = int(templatesNumber)
    iterations = int(iterations)
    # import GPA
    # GPAlogic = GPA.GPALogic()
    # LM = GPA.LMData()
    # LMExclusionList = []
    basename, extension = os.path.splitext(inputFilePaths[0])
    files = [os.path.basename(path).split('.')[0] for path in inputFilePaths]
    # LM.lmOrig, landmarkTypeArray = GPAlogic.loadLandmarks(inputFilePaths, LMExclusionList, extension)
    # shape = LM.lmOrig.shape
    # skipScalingOption = 0
    # LM.doGpa(skipScalingOption)
    # LM.calcEigen()
    # # calc PC scores
    # import Support.gpa_lib as gpa_lib
    # twoDcoors=gpa_lib.makeTwoDim(LM.lmOrig)
    # scores=np.dot(np.transpose(twoDcoors),LM.vec)
    # scores=np.real(scores) 
    # size = scores.shape[0]-1
    # scores = scores[:, 0:size]
    #kmeans based templates selection
    from numpy import array
    from scipy.cluster.vq import vq, kmeans
    #np.random.seed(1000) #Set numpy random seed to ensure consistent Kmeans result
    centers, distortion = kmeans(scores, templatesNumber, thresh = 0, iter = iterations)
    #clusterID returns the cluster allocation of each specimen
    clusterID, min_dists = vq(scores, centers)  
    #distances between specimens to centers
    templatesIndices = []
    from scipy.spatial import distance_matrix
    for i in range(templatesNumber):
      indices_i = [index for index, x in enumerate(clusterID) if x == i]
      dists = [min_dists[index] for index in indices_i]
      index = dists.index(min(dists))
      templateIndex = indices_i[index]
      templatesIndices.append(templateIndex)
    templates = [files[x] for x in templatesIndices]
    #Store templates in a new folder
    for file in templates:
      modelFile = file + ".ply"
      temp_model = slicer.util.loadModel(os.path.join(modelsDir, modelFile))
      slicer.util.saveNode(temp_model, os.path.join(templatesOutputDir, modelFile))
      slicer.mrmlScene.RemoveNode(temp_model) 
    return templates, clusterID, templatesIndices

  def DownsampleTemplate(self, templatePolyData, spacingPercentage):
    filter=vtk.vtkCleanPolyData()
    filter.SetToleranceIsAbsolute(False)
    filter.SetTolerance(spacingPercentage)
    filter.SetInputData(templatePolyData)
    filter.Update()
    return filter.GetOutput()

  def GetCorrespondingPoints(self, templatePolyData, subjectPolydata):
    print(templatePolyData.GetNumberOfPoints())
    print(subjectPolydata.GetNumberOfPoints())
    templatePoints = templatePolyData.GetPoints()
    correspondingPoints = vtk.vtkPoints()
    correspondingPoint = [0, 0, 0]
    subjectPointLocator = vtk.vtkPointLocator() 
    subjectPointLocator.SetDataSet(subjectPolydata)
    subjectPointLocator.BuildLocator()
    ID = list()
    #Index = list()
    for index in range(templatePoints.GetNumberOfPoints()):
      templatePoint= templatePoints.GetPoint(index)
      #a = vtk.vtkMinimalStandardRandomSequence()
      #a.SetSeed(1)
      closestPointId = subjectPointLocator.FindClosestPoint(templatePoint)
      correspondingPoint = subjectPolydata.GetPoint(closestPointId)
      correspondingPoints.InsertNextPoint(correspondingPoint)
      ID.append(closestPointId)
      #Index.append(index)
    return ID, correspondingPoints


    

  def makeScatterPlotWithFactors(self, data, files, factors, title, xAxis, yAxis, pcNumber, templatesIndices):
    #create two tables for the first two factors and then check for a third
    #check if there is a table node has been created
    numPoints = len(data)
    uniqueFactors, factorCounts = np.unique(factors, return_counts=True)
    factorNumber = len(uniqueFactors)

    #Set up chart
    plotChartNode=slicer.mrmlScene.GetFirstNodeByName("Chart_PCA_cov_with_groups" + xAxis + "v" +yAxis)
    if plotChartNode is None:
      plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode", "Chart_PCA_cov_with_groups" + xAxis + "v" +yAxis)
      #GPANodeCollection.AddItem(plotChartNode)
    else:
      plotChartNode.RemoveAllPlotSeriesNodeIDs()

    # Plot all series
    for factorIndex in range(len(uniqueFactors)):
      factor = uniqueFactors[factorIndex]
      tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table Group ' + factor)
      if tableNode is None:
        tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table Group ' + factor)
        #GPANodeCollection.AddItem(tableNode)
      else:
        tableNode.RemoveAllColumns()    #clear previous data from columns

      # Set up columns for X,Y, and labels
      labels=tableNode.AddColumn()
      labels.SetName('Subject ID')
      tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

      for i in range(pcNumber):
        pc=tableNode.AddColumn()
        colName="PC" + str(i+1)
        pc.SetName(colName)
        tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

      factorCounter=0
      table = tableNode.GetTable()
      table.SetNumberOfRows(factorCounts[factorIndex])
      for i in range(numPoints):
        if (factors[i] == factor):
          table.SetValue(factorCounter, 0,files[i])
          for j in range(pcNumber):
            table.SetValue(factorCounter, j+1, data[i,j])
          factorCounter+=1

      plotSeriesNode=slicer.mrmlScene.GetFirstNodeByName(factor)
      if plotSeriesNode is None:
        plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", factor)
        #GPANodeCollection.AddItem(plotSeriesNode)
      # Create data series from table
      plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
      plotSeriesNode.SetXColumnName(xAxis)
      plotSeriesNode.SetYColumnName(yAxis)
      plotSeriesNode.SetLabelColumnName('Subject ID')
      plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
      plotSeriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
      plotSeriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
      plotSeriesNode.SetUniqueColor()
      # Add data series to chart
      plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

    #Set up plotSeriesNode for templates
    tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table Templates with group input')
    if tableNode is None:
      tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table Templates with group input')
    else:
      tableNode.RemoveAllColumns()    #clear previous data from columns

    labels=tableNode.AddColumn()
    labels.SetName('Subject ID')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

    for i in range(pcNumber):
      pc=tableNode.AddColumn()
      colName="PC" + str(i+1)
      pc.SetName(colName)
      tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

    table = tableNode.GetTable()
    table.SetNumberOfRows(len(templatesIndices))
    for i in range(len(templatesIndices)):
      tempIndex = templatesIndices[i]
      table.SetValue(i, 0, files[tempIndex])
      for j in range(pcNumber):
        table.SetValue(i, j+1, data[tempIndex, j])

    plotSeriesNode=slicer.mrmlScene.GetFirstNodeByName("Templates_with_group_input")
    if plotSeriesNode is None:
      plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Templates_with_group_input")
    plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode.SetXColumnName(xAxis)
    plotSeriesNode.SetYColumnName(yAxis)
    plotSeriesNode.SetLabelColumnName('Subject ID')
    plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
    plotSeriesNode.SetUniqueColor()
    # Add data series to chart
    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())     
  
    # Set up view options for chart
    plotChartNode.SetTitle('PCA Scatter Plot with kmeans clusters')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)
    
    #Switch to a Slicer layout that contains a plot view for plotwidget
    # layoutManager = slicer.app.layoutManager()
    layoutManager = slicer.app.layoutManager()
    # layoutWithPlot = slicer.modules.plots.logic().GetLayoutWithPlot(layoutManager.layout)
    # layoutManager.setLayout(layoutWithPlot)
    layoutManager.setLayout(503)

    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())



  def makeScatterPlot(self, data, files, title, xAxis, yAxis, pcNumber, templatesIndices):
    numPoints = len(data)
    #Scatter plot for all specimens with no group input
    plotChartNode=slicer.mrmlScene.GetFirstNodeByName("Chart_PCA_cov" + xAxis + "v" +yAxis)
    if plotChartNode is None:
      plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode", "Chart_PCA_cov" + xAxis + "v" +yAxis)
    else:
      plotChartNode.RemoveAllPlotSeriesNodeIDs()
    
    tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table without group input')
    if tableNode is None:
      tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table without group input')
    else:
      tableNode.RemoveAllColumns()    #clear previous data from columns
    
    labels=tableNode.AddColumn()
    labels.SetName('Subject ID')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

    for i in range(pcNumber):
      pc=tableNode.AddColumn()
      colName="PC" + str(i+1)
      pc.SetName(colName)
      tableNode.SetColumnType(colName, vtk.VTK_FLOAT)    
    
    table = tableNode.GetTable()
    table.SetNumberOfRows(numPoints)
    for i in range(len(files)):
      table.SetValue(i, 0, files[i])
      for j in range(pcNumber):
        table.SetValue(i, j+1, data[i, j])    

    plotSeriesNode1=slicer.mrmlScene.GetFirstNodeByName("Specimens_no_group_input")
    if plotSeriesNode1 is None:
      plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Specimens_no_group_input")

    plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode1.SetXColumnName(xAxis)
    plotSeriesNode1.SetYColumnName(yAxis)
    plotSeriesNode1.SetLabelColumnName('Subject ID')
    plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
    plotSeriesNode1.SetUniqueColor()
    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())

    
    #Set up plotSeriesNode for templates
    tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA_Scatter_Plot_Table_Templates_no_group')
    if tableNode is None:
      tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA_Scatter_Plot_Table_Templates_no_group')
    else:
      tableNode.RemoveAllColumns()    #clear previous data from columns

    labels=tableNode.AddColumn()
    labels.SetName('Subject ID')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

    for i in range(pcNumber):
      pc=tableNode.AddColumn()
      colName="PC" + str(i+1)
      pc.SetName(colName)
      tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

    table = tableNode.GetTable()
    table.SetNumberOfRows(len(templatesIndices))
    for i in range(len(templatesIndices)):
      tempIndex = templatesIndices[i]
      table.SetValue(i, 0, files[tempIndex])
      for j in range(pcNumber):
        table.SetValue(i, j+1, data[tempIndex, j])

    plotSeriesNode1=slicer.mrmlScene.GetFirstNodeByName("Templates_no_group_input")
    if plotSeriesNode1 is None:
      plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Templates_no_group_input")
    plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode1.SetXColumnName(xAxis)
    plotSeriesNode1.SetYColumnName(yAxis)
    plotSeriesNode1.SetLabelColumnName('Subject ID')
    plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
    plotSeriesNode1.SetUniqueColor()
    # Add data series to chart
    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())     

    
    plotChartNode.SetTitle('PCA Scatter Plot with templates')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)
    
    #Switch to a Slicer layout that contains a plot view for plotwidget
    # layoutManager = slicer.app.layoutManager()
    layoutManager = slicer.app.layoutManager()
    # layoutWithPlot = slicer.modules.plots.logic().GetLayoutWithPlot(layoutManager.layout)
    # layoutManager.setLayout(layoutWithPlot)
    layoutManager.setLayout(503)

    #Select chart in plot view
    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

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
