##BASE PYTHON
import os
from re import S
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
from datetime import datetime
import time

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

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)

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
    Open3dVersion = "0.14.1+816263b"
    try:
      import open3d as o3d
      import cpdalp
      from packaging import version
      if version.parse(o3d.__version__) != version.parse(Open3dVersion):
        if not slicer.util.confirmOkCancelDisplay(f"ALPACA requires installation of open3d (version {Open3dVersion}).\nClick OK to upgrade open3d and restart the application."):
          self.ui.showBrowserOnEnter = False
          return
        needRestart = True
        needInstall = True
    except ModuleNotFoundError:
      needInstall = True

    if needInstall:
      progressDialog = slicer.util.createProgressDialog(labelText='Upgrading open3d. This may take a minute...', maximum=0)
      slicer.app.processEvents()
      import SampleData
      sampleDataLogic = SampleData.SampleDataLogic()
      try:
        if slicer.app.os == 'win':
          url = "https://app.box.com/shared/static/friq8fhfi8n4syklt1v47rmuf58zro75.whl"
          wheelName = "open3d-0.14.1+816263b-cp39-cp39-win_amd64.whl"
          wheelPath = sampleDataLogic.downloadFile(url, slicer.app.cachePath, wheelName)
        elif slicer.app.os == 'macosx':
          url = "https://app.box.com/shared/static/ixhac95jrx7xdxtlagwgns7vt9b3mbqu.whl"
          wheelName = "open3d-0.14.1+816263b-cp39-cp39-macosx_10_15_x86_64.whl"
          wheelPath = sampleDataLogic.downloadFile(url, slicer.app.cachePath, wheelName)
        elif slicer.app.os == 'linux':
          url = "https://app.box.com/shared/static/wyzk0f9jhefrbm4uukzym0sow5bf26yi.whl"
          wheelName = "open3d-0.14.1+816263b-cp39-cp39-manylinux_2_27_x86_64.whl"
          wheelPath = sampleDataLogic.downloadFile(url, slicer.app.cachePath, wheelName)
      except:
          slicer.util.infoDisplay('Error: please check the url of the open3d wheel in the script')
          progressDialog.close()
      slicer.util.pip_install(f'cpdalp')
      # wheelPath may contain spaces, therefore pass it as a list (that avoids splitting
      # the argument into multiple command-line arguments when there are spaces in the path)
      slicer.util.pip_install([wheelPath])
      import open3d as o3d
      import cpdalp
      progressDialog.close()
    if needRestart:
      slicer.util.restart()

    # Load widget from .ui file (created by Qt Designer).
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ALPACA.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Setup checkbox stylesheets
    moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
    self.onIconPath = moduleDir +'/Resources/Icons/switch_on.png'
    self.offIconPath = moduleDir +'/Resources/Icons/switch_off.png'

    # Single Alignment connections
    self.ui.sourceModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.ui.sourceModelSelector.setMRMLScene( slicer.mrmlScene)
    self.ui.sourceLandmarkSetSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.ui.sourceLandmarkSetSelector.setMRMLScene( slicer.mrmlScene)
    self.ui.targetModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.ui.targetModelSelector.setMRMLScene( slicer.mrmlScene)
    self.ui.targetLandmarkSetSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.ui.targetLandmarkSetSelector.setMRMLScene( slicer.mrmlScene)
    self.ui.pointDensitySlider.connect('valueChanged(double)', self.onChangeDensitySingle)
    self.ui.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)
    self.ui.runALPACAButton.connect('clicked(bool)', self.onRunALPACAButton) #Connection for run all ALPACA steps button
    self.ui.switchSettingsButton.connect('clicked(bool)', self.onSwitchSettingsButton)
    self.ui.showTargetPCDCheckBox.connect('toggled(bool)', self.onShowTargetPCDCheckBox)
    self.setCheckboxStyle(self.ui.showTargetPCDCheckBox)
    self.ui.showSourcePCDCheckBox.connect('toggled(bool)', self.onShowSourcePCDCheckBox)
    self.setCheckboxStyle(self.ui.showSourcePCDCheckBox)
    self.ui.showTargetModelCheckBox.connect('toggled(bool)', self.onshowTargetModelCheckBox)
    self.setCheckboxStyle(self.ui.showTargetModelCheckBox)
    self.ui.showSourceModelCheckBox.connect('toggled(bool)', self.onshowSourceModelCheckBox)
    self.setCheckboxStyle(self.ui.showSourceModelCheckBox)
    self.ui.showUnprojectLMCheckBox.connect('toggled(bool)', self.onShowUnprojectLMCheckBox)
    self.setCheckboxStyle(self.ui.showUnprojectLMCheckBox)
    self.ui.showTPSModelCheckBox.connect('toggled(bool)', self.onshowTPSModelCheckBox)
    self.setCheckboxStyle(self.ui.showTPSModelCheckBox)
    self.ui.showFinalLMCheckbox.connect('toggled(bool)', self.onShowFinalLMCheckbox)
    self.setCheckboxStyle(self.ui.showFinalLMCheckbox)
    self.ui.showManualLMCheckBox.connect('toggled(bool)', self.onShowManualLMCheckBox)
    self.setCheckboxStyle(self.ui.showManualLMCheckBox)

    # Advanced Settings connections
    self.ui.projectionFactorSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.pointDensityAdvancedSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.normalSearchRadiusSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.FPFHSearchRadiusSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.maximumCPDThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.maxRANSAC.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.RANSACConfidence.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.ICPDistanceThresholdSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.alpha.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.beta.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.CPDIterationsSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.CPDToleranceSlider.connect('valueChanged(double)', self.onChangeAdvanced)
    self.ui.accelerationCheckBox.connect('toggled(bool)', self.onChangeCPD)
    self.ui.accelerationCheckBox.connect('toggled(bool)', self.onChangeAdvanced)
    self.ui.BCPDFolder.connect('validInputChanged(bool)', self.onChangeAdvanced)
    self.ui.BCPDFolder.connect('validInputChanged(bool)', self.onChangeCPD)
    self.ui.BCPDFolder.currentPath = ALPACALogic().getBCPDPath()

    # Batch Processing connections
    self.ui.methodBatchWidget.connect('currentIndexChanged(int)', self.onChangeMultiTemplate)
    self.ui.sourceModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.ui.sourceFiducialMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.ui.targetModelMultiSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.ui.landmarkOutputSelector.connect('validInputChanged(bool)', self.onSelectMultiProcess)
    self.ui.skipScalingMultiCheckBox.connect('toggled(bool)', self.onSelectMultiProcess)
    self.ui.replicateAnalysisCheckBox.connect('toggled(bool)', self.onSelectReplicateAnalysis)
    self.ui.applyLandmarkMultiButton.connect('clicked(bool)', self.onApplyLandmarkMulti)

    # Template Selection connections
    self.ui.modelsMultiSelector.connect('validInputChanged(bool)', self.onSelectKmeans)
    self.ui.kmeansOutputSelector.connect('validInputChanged(bool)', self.onSelectKmeans)
    self.ui.selectRefCheckBox.connect('toggled(bool)', self.onSelectKmeans)
    self.ui.downReferenceButton.connect('clicked(bool)', self.onDownReferenceButton)
    self.ui.matchingPointsButton.connect('clicked(bool)', self.onMatchingPointsButton)
    self.ui.multiGroupInput.connect('toggled(bool)', self.onToggleGroupInput)
    self.ui.resetTableButton.connect('clicked(bool)', self.onRestTableButton)
    self.ui.kmeansTemplatesButton.connect('clicked(bool)', self.onkmeansTemplatesButton)


    #Add menu buttons
    self.addLayoutButton(503, 'MALPACA multi-templates View', 'Custom layout for MALPACA multi-templates tab', 'LayoutSlicerMorphView.png', slicer.customLayoutSM)
    self.addLayoutButton(504, 'Table Only View', 'Custom layout for GPA module', 'LayoutTableOnlyView.png', slicer.customLayoutTableOnly)
    self.addLayoutButton(505, 'Plot Only View', 'Custom layout for GPA module', 'LayoutPlotOnlyView.png', slicer.customLayoutPlotOnly)

    # initialize the parameter dictionary from single run parameters
    self.parameterDictionary = {
      "projectionFactor": self.ui.projectionFactorSlider.value,
      "pointDensity": self.ui.pointDensityAdvancedSlider.value,
      "normalSearchRadius" : self.ui.normalSearchRadiusSlider.value,
      "FPFHSearchRadius" : self.ui.FPFHSearchRadiusSlider.value,
      "distanceThreshold" : self.ui.maximumCPDThreshold.value,
      "maxRANSAC" : int(self.ui.maxRANSAC.value),
      "RANSACConfidence" : self.ui.RANSACConfidence.value,
      "ICPDistanceThreshold"  : self.ui.ICPDistanceThresholdSlider.value,
      "alpha" : self.ui.alpha.value,
      "beta" : self.ui.beta.value,
      "CPDIterations" : int(self.ui.CPDIterationsSlider.value),
      "CPDTolerance" : self.ui.CPDToleranceSlider.value,
      "Acceleration" : self.ui.accelerationCheckBox.checked,
      "BCPDFolder" : self.ui.BCPDFolder.currentPath
      }

  def cleanup(self):
    pass

  def setCheckboxStyle(self, checkbox):
    checkbox.setStyleSheet("QCheckBox::indicator:unchecked{image: url(" + self.offIconPath + "); } \n"
      + "QCheckBox::indicator:checked{image: url(" + self.onIconPath + "); } \n"
      + "QCheckBox::indicator{width: 50px;height: 25px;}\n")

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
    #Enable run ALPACA button
    self.ui.skipScalingMultiCheckBox.checked = self.ui.skipScalingCheckBox.checked
    self.ui.skipProjectionCheckBoxMulti.checked = self.ui.skipProjectionCheckBox.checked
    self.ui.subsampleButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.sourceLandmarkSetSelector.currentNode())
    self.ui.runALPACAButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.sourceLandmarkSetSelector.currentNode())
    self.ui.switchSettingsButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.sourceLandmarkSetSelector.currentNode())

  def onSelectMultiProcess(self):
    self.ui.applyLandmarkMultiButton.enabled = bool ( self.ui.sourceModelMultiSelector.currentPath and self.ui.sourceFiducialMultiSelector.currentPath
      and self.ui.targetModelMultiSelector.currentPath and self.ui.landmarkOutputSelector.currentPath )


  def onSelectReplicateAnalysis(self):
    self.ui.replicationNumberLabel.enabled = bool( self.ui.replicateAnalysisCheckBox.isChecked())
    self.ui.replicationNumberSpinBox.enabled = bool ( self.ui.replicateAnalysisCheckBox.isChecked())


  def transform_numpy_points(self, points_np, transform):
    import itk
    mesh = itk.Mesh[itk.F, 3].New()
    mesh.SetPoints(itk.vector_container_from_array(points_np.flatten().astype('float32')))
    transformed_mesh = itk.transform_mesh_filter(mesh, transform=transform)
    points_tranformed = itk.array_from_vector_container(transformed_mesh.GetPoints())
    points_tranformed = np.reshape(points_tranformed, [-1, 3])
    return points_tranformed

  def onSubsampleButton(self):
    try:
      slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)
    except:
      pass
    logic = ALPACALogic()
    self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
    self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)
    #Create a copy of sourceModelNode then clone it for ALPACA steps
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.sourceModelNode_clone = shNode.GetItemDataNode(clonedItemID)
    self.sourceModelNode_clone.SetName("SourceModelNode_clone")
    self.sourceModelNode_clone.GetDisplayNode().SetVisibility(False)
    # slicer.mrmlScene.RemoveNode(self.sourceModelNode_copy)
    #Create target Model Node
    self.targetModelNode = self.ui.targetModelSelector.currentNode()
    self.targetModelNode.GetDisplayNode().SetVisibility(False)
    self.ui.sourceLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(False)

    self.sourcePoints, self.targetPoints, self.sourceFeatures, \
      self.targetFeatures, self.voxelSize, self.scaling = logic.runSubsample(self.sourceModelNode_clone, self.targetModelNode, self.ui.skipScalingCheckBox.checked, self.parameterDictionary)
    # Convert to VTK points for visualization
    self.targetVTK = logic.convertPointsToVTK(self.targetPoints)

    slicer.mrmlScene.RemoveNode(self.sourceModelNode_clone)

    # Display target points
    blue=[0,0,1]
    self.targetCloudNodeTest = logic.displayPointCloud(self.targetVTK, self.voxelSize / 7, 'Target Pointcloud_test', blue)
    self.targetCloudNodeTest.GetDisplayNode().SetVisibility(True)
    self.updateLayout()

    print('Pranjal layout updated')

    # Output information on subsampling
    self.ui.subsampleInfo.clear()
    self.ui.subsampleInfo.insertPlainText(f':: Your subsampled source pointcloud has a total of {len(self.sourcePoints)} points. \n')
    self.ui.subsampleInfo.insertPlainText(f':: Your subsampled target pointcloud has a total of {len(self.targetPoints)} points. ')

    self.ui.runALPACAButton.enabled = True
    if bool(self.ui.targetLandmarkSetSelector.currentNode()) == True:
      self.ui.targetLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(False)
    try:
      self.manualLMNode.GetDisplayNode().SetVisibility(False)
    except:
      pass

    self.ui.showTargetPCDCheckBox.checked = 0
    self.ui.showSourcePCDCheckBox.checked = 0
    self.ui.showTargetModelCheckBox.checked = 0
    self.ui.showSourceModelCheckBox.checked = 0
    self.ui.showUnprojectLMCheckBox.checked = 0
    self.ui.showTPSModelCheckBox.checked = 0
    self.ui.showFinalLMCheckbox.checked = 0
    self.ui.showManualLMCheckBox.checked = 0


  #Run all button for Single Alignment ALPACA
  def onRunALPACAButton(self):
    run_counter = self.runALPACACounter() #the counter for executing this function in str format
    logic = ALPACALogic()
    try:
      self.manualLMNode.GetDisplayNode().SetVisibility(False)
    except:
      pass
    try:
      slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest) #Remove targe cloud node created in the subsampling to avoid confusion
      # slicer.mrmlScene.RemoveNode(self.sourceModelNode)
      self.ui.showTargetPCDCheckBox.checked = 0
      self.ui.showSourcePCDCheckBox.checked = 0
      self.ui.showTargetModelCheckBox.checked = 0
      self.ui.showSourceModelCheckBox.checked = 0
      self.ui.showUnprojectLMCheckBox.checked = 0
      self.ui.showTPSModelCheckBox.checked = 0
      self.ui.showFinalLMCheckbox.checked = 0
      self.ui.showManualLMCheckBox.checked = 0
    except:
      pass
    #
    self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
    self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)
    #Clone the original source mesh stored in the node sourceModelNode_orig
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.sourceModelNode = shNode.GetItemDataNode(clonedItemID)
    self.sourceModelNode.GetDisplayNode().SetVisibility(False)
    self.sourceModelNode.SetName("Source model(rigidly registered)_"+run_counter) #Create a cloned source model node
    # slicer.mrmlScene.RemoveNode(self.sourceModelNode_copy)
    #
    self.targetModelNode = self.ui.targetModelSelector.currentNode()
    self.targetModelNode.GetDisplayNode().SetVisibility(False)
    self.ui.sourceLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(False)
    #
    self.sourcePoints, self.targetPoints, self.sourceFeatures, \
      self.targetFeatures, self.voxelSize, self.scaling = logic.runSubsample(self.sourceModelNode, self.targetModelNode, self.ui.skipScalingCheckBox.checked, self.parameterDictionary)
    # Convert to VTK points for visualization
    self.targetVTK = logic.convertPointsToVTK(self.targetPoints)

    blue=[0,0,1]
    self.targetCloudNode_2 = logic.displayPointCloud(self.targetVTK, self.voxelSize / 10, 'Target Pointcloud_'+run_counter, blue)
    self.targetCloudNode_2.GetDisplayNode().SetVisibility(False)
    # Output information on subsampling
    self.ui.subsampleInfo.clear()
    self.ui.subsampleInfo.insertPlainText(f':: Your subsampled source pointcloud has a total of {len(self.sourcePoints)} points. \n')
    self.ui.subsampleInfo.insertPlainText(f':: Your subsampled target pointcloud has a total of {len(self.targetPoints)} points. ')
    #
    #RANSAC & ICP transformation of source pointcloud
    [self.transformMatrix, self.transformMatrix_rigid] = logic.estimateTransform(self.sourcePoints, self.targetPoints, self.sourceFeatures, self.targetFeatures, self.voxelSize, self.ui.skipScalingCheckBox.checked, self.parameterDictionary)
    self.ICPTransformNode = logic.convertMatrixToTransformNode(self.transformMatrix, 'Rigid Transformation Matrix_'+run_counter)
    self.sourcePoints = self.transform_numpy_points(self.sourcePoints, self.transformMatrix)
    self.sourcePoints = self.transform_numpy_points(self.sourcePoints, self.transformMatrix_rigid)
    #Setup source pointcloud VTK object
    self.sourceVTK = logic.convertPointsToVTK(self.sourcePoints)
    #
    red=[1,0,0]
    self.sourceCloudNode = logic.displayPointCloud(self.sourceVTK, self.voxelSize / 7, ('Source Pointcloud (rigidly registered)_'+run_counter), red)
    self.sourceCloudNode.GetDisplayNode().SetVisibility(False)
    #
    #Transform the source model
    self.sourceModelNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceModelNode)
    #
    self.sourceModelNode.GetDisplayNode().SetColor(red)
    self.sourceModelNode.GetDisplayNode().SetVisibility(False)
    #
    #CPD registration
    self.sourceLandmarks, self.sourceLMNode =  logic.loadAndScaleFiducials(self.ui.sourceLandmarkSetSelector.currentNode(), self.scaling, scene = True)
    self.sourceLandmarks = self.transform_numpy_points(self.sourceLandmarks, self.transformMatrix)
    self.sourceLandmarks = self.transform_numpy_points(self.sourceLandmarks, self.transformMatrix_rigid)
    self.sourceLMNode.SetName("Source_Landmarks_clone_"+run_counter)
    self.sourceLMNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceLMNode)
    #
    #Registration
    self.registeredSourceArray = logic.runCPDRegistration(self.sourceLandmarks, self.sourcePoints, self.targetPoints, self.parameterDictionary)
    self.outputPoints = logic.exportPointCloud(self.registeredSourceArray, "Initial ALPACA landmark estimate(unprojected)_"+run_counter) #outputPoints = ininital predicted LMs, non projected
    self.inputPoints = logic.exportPointCloud(self.sourceLandmarks, "Original Landmarks") #input points = source landmarks
    #set up output initial predicted landmarkslandmark as vtk class
    #
    outputPoints_vtk = logic.getFiducialPoints(self.outputPoints)
    inputPoints_vtk = logic.getFiducialPoints(self.inputPoints)
    #
    # Get warped source model and final predicted landmarks
    self.warpedSourceNode = logic.applyTPSTransform(inputPoints_vtk, outputPoints_vtk, self.sourceModelNode, 'TPS Warped source model_'+run_counter)
    self.warpedSourceNode.GetDisplayNode().SetVisibility(False)
    green=[0,1,0]
    self.warpedSourceNode.GetDisplayNode().SetColor(green)
    self.outputPoints.GetDisplayNode().SetPointLabelsVisibility(False)
    slicer.mrmlScene.RemoveNode(self.inputPoints)
    #
    if self.ui.skipProjectionCheckBox.checked:
      logic.propagateLandmarkTypes(self.sourceLMNode, self.outputPoints)
    else:
      print(":: Projecting landmarks to external surface")
      projectionFactor = self.ui.projectionFactorSlider.value/100
      #self.projected Landmarks = "refined predicted landmarks"
      self.projectedLandmarks = logic.runPointProjection(self.warpedSourceNode, self.targetModelNode, self.outputPoints, projectionFactor)
      logic.propagateLandmarkTypes(self.sourceLMNode, self.projectedLandmarks)
      self.projectedLandmarks.SetName('Final ALPACA landmark estimate_'+run_counter)
      self.projectedLandmarks.GetDisplayNode().SetVisibility(False)
      self.outputPoints.GetDisplayNode().SetVisibility(False)
    # Other visualization
    self.sourceLMNode.GetDisplayNode().SetVisibility(False)
    self.sourceModelNode.GetDisplayNode().SetVisibility(False)
    #Enable reset
    #self.resetSceneButton.enabled = True
    #Create a folder and add all objects into the folder
    folderNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    sceneItemID = folderNode.GetSceneItemID()
    newFolder = folderNode.CreateFolderItem(sceneItemID , 'ALPACA_output_'+run_counter)
    sourceModelItem = folderNode.GetItemByDataNode(self.sourceModelNode)
    sourceCloudItem = folderNode.GetItemByDataNode(self.sourceCloudNode)
    targetCloudItem = folderNode.GetItemByDataNode(self.targetCloudNode_2)
    ICPTransformItem = folderNode.GetItemByDataNode(self.ICPTransformNode)
    sourceLMItem = folderNode.GetItemByDataNode(self.sourceLMNode)
    nonProjectLMItem = folderNode.GetItemByDataNode(self.warpedSourceNode)
    warpedSourceItem = folderNode.GetItemByDataNode(self.outputPoints)
    #
    folderNode.SetItemParent(sourceModelItem, newFolder)
    folderNode.SetItemParent(sourceCloudItem, newFolder)
    folderNode.SetItemParent(targetCloudItem, newFolder)
    folderNode.SetItemParent(ICPTransformItem, newFolder)
    folderNode.SetItemParent(sourceLMItem, newFolder)
    folderNode.SetItemParent(nonProjectLMItem, newFolder)
    folderNode.SetItemParent(warpedSourceItem, newFolder)
    # Add projected points if they have been created
    if not self.ui.skipProjectionCheckBox.isChecked():
      finalLMItem = folderNode.GetItemByDataNode(self.projectedLandmarks)
      folderNode.SetItemParent(finalLMItem, newFolder)
    #
    # self.ui.subsampleButton.enabled = False
    self.ui.runALPACAButton.enabled = False
    #
    #Enable visualization
    self.ui.showTargetPCDCheckBox.enabled = True
    self.ui.showTargetPCDCheckBox.checked = 0
    #
    self.ui.showSourcePCDCheckBox.enabled = True
    self.ui.showSourcePCDCheckBox.checked = 0
    #
    self.ui.showTargetModelCheckBox.enabled = True
    self.ui.showTargetModelCheckBox.checked = 1
    #
    self.ui.showSourceModelCheckBox.enabled = True
    self.ui.showSourceModelCheckBox.checked = 0
    #
    self.ui.showUnprojectLMCheckBox.enabled = True
    self.ui.showUnprojectLMCheckBox.checked = 0
    #
    self.ui.showTPSModelCheckBox.enabled = True
    self.ui.showTPSModelCheckBox.checked = 0
    #
    self.ui.showFinalLMCheckbox.enabled = True
    self.ui.showFinalLMCheckbox.checked = 1
    #
    #Calculate rmse
    #Manual LM numpy array
    if bool(self.ui.targetLandmarkSetSelector.currentNode()) == True:
      self.manualLMNode = self.ui.targetLandmarkSetSelector.currentNode()
      self.manualLMNode.GetDisplayNode().SetSelectedColor(green)
      self.ui.showManualLMCheckBox.enabled = True
      self.ui.showManualLMCheckBox.checked = 0
      self.manualLMNode.GetDisplayNode().SetVisibility(False)
      manualLMs = np.zeros(shape=(self.manualLMNode.GetNumberOfControlPoints(),3))
      for i in range(self.manualLMNode.GetNumberOfControlPoints()):
        point = self.manualLMNode.GetNthControlPointPosition(i)
        manualLMs[i,:] = point
      #Source LM numpy array
      if not self.ui.skipProjectionCheckBox.isChecked():
        finalLMs = np.zeros(shape=(self.projectedLandmarks.GetNumberOfControlPoints(),3))
        for i in range(self.projectedLandmarks.GetNumberOfControlPoints()):
          point2 = self.projectedLandmarks.GetNthControlPointPosition(i)
          finalLMs[i,:] = point2
      else:
        finalLMs = np.zeros(shape=(self.outputPoints.GetNumberOfControlPoints(),3))
        for i in range(self.outputPoints.GetNumberOfControlPoints()):
          point2 = self.outputPoints.GetNthControlPointPosition(i)
          finalLMs[i,:] = point2
      #
      rmse = logic.rmse(manualLMs, finalLMs)
      print(rmse)
      self.singleRMSETable(rmse, run_counter)

  def singleRMSETable(self, rmse, counter_str):
    listTableNodes = slicer.mrmlScene.GetNodesByName("Single Alignment RMSE table")
    if listTableNodes.GetNumberOfItems() == 0:
      # print(hasattr(self, 'rmseTableNode'))
      #Create rmseTableNode and add the first row of rmse
      self.rmseTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Single Alignment RMSE table')
      #
      col1=self.rmseTableNode.AddColumn()
      col1.SetName('ALPACA test')
      col1Item = 'ALPACA_' + counter_str
      self.col1List = [col1Item]
      self.rmseTableNode.AddEmptyRow()
      self.rmseTableNode.SetCellText(0, 0, col1Item)
      #
      col2=self.rmseTableNode.AddColumn()
      col2.SetName('RMSE')
      self.rmseTableNode.SetCellText(0, 1, format(rmse, '.6f'))
    else:
      # print(hasattr(self, 'rmseTableNode'))
      #if rmseTableNode exists
      #Add a new row of rmse
      col1Item = 'ALPACA_' + counter_str
      self.col1List.append(col1Item)
      #Add col1
      self.rmseTableNode.AddEmptyRow()
      self.rmseTableNode.SetCellText(len(self.col1List)-1, 0, col1Item)
      #Add col2
      self.rmseTableNode.SetCellText(len(self.col1List)-1, 1, format(rmse, '.6f'))
    slicer.app.layoutManager().setLayout(35)
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.rmseTableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
    self.rmseTableNode.GetTable().Modified()

  #Count the times run ALPAACA function is executed
  def runALPACACounter(self, run_counter = [0]):
    run_counter[0] += 1
    return str(run_counter[0])

  def onSwitchSettingsButton(self):
    self.ui.tabsWidget.setCurrentWidget(self.ui.advancedSettingsTab)
    self.ui.runALPACAButton.enabled = True


  def onShowTargetPCDCheckBox(self):
    try:
      if self.ui.showTargetPCDCheckBox.isChecked():
        self.targetCloudNode_2.GetDisplayNode().SetVisibility(True)
      else:
        self.targetCloudNode_2.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showTargetPCDCheckBox.enabled = False

  def onShowSourcePCDCheckBox(self):
    try:
      if self.ui.showSourcePCDCheckBox.isChecked():
        self.sourceCloudNode.GetDisplayNode().SetVisibility(True)
      else:
        self.sourceCloudNode.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showSourcePCDCheckBox.enabled = False

  def onshowTargetModelCheckBox(self):
    try:
      if self.ui.showTargetModelCheckBox.isChecked():
        self.targetModelNode.GetDisplayNode().SetVisibility(True)
      else:
        self.targetModelNode.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showTargetModelCheckBox.enabled = False

  def onshowSourceModelCheckBox(self):
    try:
      if self.ui.showSourceModelCheckBox.isChecked():
        self.sourceModelNode.GetDisplayNode().SetVisibility(True)
      else:
        self.sourceModelNode.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showSourceModelCheckBox.enabled = False

  def onShowUnprojectLMCheckBox(self):
    try:
      if self.ui.showUnprojectLMCheckBox.isChecked():
        self.outputPoints.GetDisplayNode().SetVisibility(True)
      else:
        self.outputPoints.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showUnprojectLMCheckBox.enabled = False

  def onshowTPSModelCheckBox(self):
    try:
      if self.ui.showTPSModelCheckBox.isChecked():
        self.warpedSourceNode.GetDisplayNode().SetVisibility(True)
      else:
        self.warpedSourceNode.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showTPSModelCheckBox.enabled = False

  def onShowFinalLMCheckbox(self):
    try:
      if self.ui.showFinalLMCheckbox.isChecked():
        self.projectedLandmarks.GetDisplayNode().SetVisibility(True)
      else:
        self.projectedLandmarks.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showFinalLMCheckbox.enabled = False

  def onShowManualLMCheckBox(self):
    try:
      if self.ui.showManualLMCheckBox.isChecked():
        self.manualLMNode.GetDisplayNode().SetVisibility(True)
      else:
        self.manualLMNode.GetDisplayNode().SetVisibility(False)
    except:
      self.ui.showManualLMCheckBox.enabled = False


  def onApplyLandmarkMulti(self):
    logic = ALPACALogic()
    if self.ui.skipProjectionCheckBoxMulti.checked != 0:
      projectionFactor = 0
    else:
      projectionFactor = self.ui.projectionFactorSlider.value/100
    if not self.ui.replicateAnalysisCheckBox.checked:
      logic.runLandmarkMultiprocess(self.ui.sourceModelMultiSelector.currentPath,self.ui.sourceFiducialMultiSelector.currentPath,
      self.ui.targetModelMultiSelector.currentPath, self.ui.landmarkOutputSelector.currentPath, self.ui.skipScalingMultiCheckBox.checked,
      projectionFactor, self.ui.JSONFileFormatSelector.checked, self.parameterDictionary)
    else:
      for i in range(0, self.ui.replicationNumberSpinBox.value):
        print("ALPACA replication run ", i)
        dateTimeStamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
        datedOutputFolder = os.path.join(self.ui.landmarkOutputSelector.currentPath, dateTimeStamp)
        try:
          os.makedirs(datedOutputFolder)
          logic.runLandmarkMultiprocess(self.ui.sourceModelMultiSelector.currentPath,self.ui.sourceFiducialMultiSelector.currentPath,
            self.ui.targetModelMultiSelector.currentPath, datedOutputFolder, self.ui.skipScalingMultiCheckBox.checked, projectionFactor,
            self.ui.JSONFileFormatSelector.checked, self.parameterDictionary)
        except:
          logging.debug('Result directory failed: Could not access output folder')
          print("Error creating result directory")

###Connecting function for kmeans templates selection
  def onSelectKmeans(self):
    self.ui.downReferenceButton.enabled = bool(self.ui.modelsMultiSelector.currentPath and self.ui.kmeansOutputSelector.currentPath)
    self.ui.referenceSelector.enabled = self.ui.selectRefCheckBox.isChecked()

  def onDownReferenceButton(self):
    logic = ALPACALogic()
    if bool(self.ui.referenceSelector.currentPath):
      referencePath = self.ui.referenceSelector.currentPath
    else:
      referenceList = [f for f in os.listdir(self.ui.modelsMultiSelector.currentPath) if f.endswith(('.ply', '.stl', '.obj', '.vtk', '.vtp'))]
      referenceFile = referenceList[0]
      referencePath = os.path.join(self.ui.modelsMultiSelector.currentPath, referenceFile)
    self.sparseTemplate, template_density, self.referenceNode = logic.downReference(referencePath, self.ui.spacingFactorSlider.value)
    self.refName = os.path.basename(referencePath)
    self.refName = os.path.splitext(self.refName)[0]
    self.ui.subsampleInfo2.clear()
    self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
    self.ui.subsampleInfo2.insertPlainText(f"The number of points in the downsampled reference pointcloud is {template_density}")
    self.ui.matchingPointsButton.enabled = True

  def onMatchingPointsButton(self):
    #Set up folders for matching point cloud output and kmeans selected templates under self.ui.kmeansOutputSelector.currentPath
    dateTimeStamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
    self.kmeansOutputFolder = os.path.join(self.ui.kmeansOutputSelector.currentPath, dateTimeStamp)
    self.pcdOutputFolder = os.path.join(self.kmeansOutputFolder, "matching_point_clouds")
    try:
      os.makedirs(self.kmeansOutputFolder)
      os.makedirs(self.pcdOutputFolder)
    except:
      logging.debug('Result directory failed: Could not access output folder')
      print("Error creating result directory")
    #Execute functions for generating point clouds matched to the reference
    logic = ALPACALogic()
    template_density, matchedPoints, indices, files = logic.matchingPCD(self.ui.modelsMultiSelector.currentPath, self.sparseTemplate, self.referenceNode, self.pcdOutputFolder, self.ui.spacingFactorSlider.value,
    self.ui.JSONFileFormatSelector.checked, self.parameterDictionary)
    # Print results
    correspondent_threshold = 0.01
    self.ui.subsampleInfo2.clear()
    self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
    self.ui.subsampleInfo2.insertPlainText("The number of points in the downsampled reference pointcloud is {}. The error threshold for finding correspondent points is {}% \n".format(template_density,
      correspondent_threshold*100))
    if len(indices) >0:
      self.ui.subsampleInfo2.insertPlainText(f"There are {len(indices)} files have points repeatedly matched with the same point(s) template, these are: \n")
      for i in indices:
        self.ui.subsampleInfo2.insertPlainText(f"{files[i]}: {matchedPoints[i]} unique points are sampled to match the template pointcloud \n")
      indices_error = [i for i in indices if (template_density - matchedPoints[i]) > template_density*correspondent_threshold]
      if len(indices_error) > 0:
        self.ui.subsampleInfo2.insertPlainText("The specimens with sampling error larger than the threshold are: \n")
        for i in indices_error:
          self.ui.subsampleInfo2.insertPlainText(f"{files[i]}: {matchedPoints[i]} unique points are sampled. \n")
          self.ui.subsampleInfo2.insertPlainText("It is recommended to check the alignment of these specimens with the template or experimenting with a higher spacing factor \n")
      else:
        self.ui.subsampleInfo2.insertPlainText("All error rates smaller than the threshold \n")
    else:
      self.ui.subsampleInfo2.insertPlainText("{} unique points are sampled from each model to match the template pointcloud \n")
    #Enable buttons for kmeans
    self.ui.noGroupInput.enabled = True
    self.ui.multiGroupInput.enabled = True
    self.ui.kmeansTemplatesButton.enabled = True
    self.ui.matchingPointsButton.enabled = False


  #If select multiple group input radiobutton, execute enterFactors function
  def onToggleGroupInput(self):
    if self.ui.multiGroupInput.isChecked():
      self.enterFactors()
      self.ui.resetTableButton.enabled = True

  #Reset input button
  def onRestTableButton(self):
    self.resetFactors()


  #Add table for entering user-defined catalogs/groups for each specimen
  def enterFactors(self):
    #If has table node, remove table node and build a new one
    if hasattr(self, 'factorTableNode') == False:
      files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)]
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
      slicer.app.layoutManager().setLayout(503)
      slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
      slicer.app.applicationLogic().PropagateTableSelection()
      self.factorTableNode.GetTable().Modified()

  def resetFactors(self):
    if hasattr(self, 'factorTableNode'):
      slicer.mrmlScene.RemoveNode(self.factorTableNode)
    files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)]
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
    slicer.app.layoutManager().setLayout(503)
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
    self.factorTableNode.GetTable().Modified()


  #Generate templates based on kmeans and catalog
  def onkmeansTemplatesButton(self):
    start = time.time()
    logic = ALPACALogic()
    PCDFiles = os.listdir(self.pcdOutputFolder)
    if len(PCDFiles)<1:
      logging.error(f'No point cloud files read from {self.pcdOutputFolder}\n')
      return
    pcdFilePaths = [os.path.join(self.pcdOutputFolder, file) for file in PCDFiles]
    #GPA for all specimens
    self.scores, self.LM = logic.pcdGPA(pcdFilePaths)
    files = [os.path.splitext(file)[0] for file in PCDFiles]
    #Set up a seed for numpy for random results
    if self.ui.setSeedCheckBox.isChecked():
      np.random.seed(1000)
    if self.ui.noGroupInput.isChecked():
      #Generate folder for storing selected templates within the self.ui.kmeansOutputSelector.currentPath
      self.templatesOutputFolder = os.path.join(self.kmeansOutputFolder, "kmeans_selected_templates")
      if os.path.isdir(self.templatesOutputFolder):
        pass
      else:
        try:
          os.makedirs(self.templatesOutputFolder)
        except:
          logging.debug('Result directory failed: Could not access templates output folder')
          print("Error creating result directory")
      #
      templates, clusterID, templatesIndices = logic.templatesSelection(self.ui.modelsMultiSelector.currentPath, self.scores, pcdFilePaths, self.templatesOutputFolder, self.ui.templatesNumber.value, self.ui.kmeansIterations.value)
      clusterID = [str(x) for x in clusterID]
      print(f"kmeans cluster ID is: {clusterID}")
      print(f"templates indices are: {templatesIndices}")
      self.ui.templatesInfo.clear()
      self.ui.templatesInfo.insertPlainText(f"One pooled group for all specimens. The {int(self.ui.templatesNumber.value)} selected templates are: \n")
      for file in templates:
        self.ui.templatesInfo.insertPlainText(file + "\n")
      #Add cluster ID from kmeans to the table
      self.plotClusters(files, templatesIndices)
      print(f'Time: {time.time() - start}')
    # multiClusterCheckbox is checked
    else:
      if hasattr(self, 'factorTableNode'):
        self.ui.templatesInfo.clear()
        factorCol = self.factorTableNode.GetTable().GetColumn(1)
        groupFactorArray=[]
        for i in range(factorCol.GetNumberOfTuples()):
          temp = factorCol.GetValue(i).rstrip()
          temp = str(temp).upper()
          groupFactorArray.append(temp)
        print(groupFactorArray)
        #Count the number of non-null enties in the table
        countInput = 0
        for i in range(len(groupFactorArray)):
          if groupFactorArray[i] != '':
            countInput += 1
        if countInput == len(PCDFiles): #check if group information is input for all specimens
          uniqueFactors = list(set(groupFactorArray))
          groupNumber = len(uniqueFactors)
          self.ui.templatesInfo.insertPlainText(f"The sample is divided into {groupNumber} groups. The templates for each group are: \n")
          groupClusterIDs = [None]*len(files)
          templatesIndices = []
          #Generate folder for storing selected templates within the self.ui.kmeansOutputSelector.currentPath
          self.templatesOutputFolder_multi = os.path.join(self.kmeansOutputFolder, "kmeans_selected_templates_multiGroups")
          if os.path.isdir(self.templatesOutputFolder_multi):
            pass
          else:
            try:
              os.makedirs(self.templatesOutputFolder_multi)
            except:
              logging.debug('Result directory failed: Could not access templates output folder')
              print("Error creating result directory")
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
            #PC scores of specimens belong to a specific group
            tempScores = self.scores[indices, :]
            #
            templates, clusterID, tempIndices = logic.templatesSelection(self.ui.modelsMultiSelector.currentPath, tempScores, paths, self.templatesOutputFolder_multi, self.ui.templatesNumber.value, self.ui.kmeansIterations.value)
            print("Kmeans-cluster IDs for " + factorName + " are:")
            print(clusterID)
            templatesIndices = templatesIndices + [indices[i] for i in tempIndices]
            self.ui.templatesInfo.insertPlainText("Group " + factorName + "\n")
            for file in templates:
              self.ui.templatesInfo.insertPlainText(file + "\n")
            #Prepare cluster ID for each group
            uniqueClusterID = list(set(clusterID))
            for i in range(len(uniqueClusterID)):
              for j in range(len(clusterID)):
                if clusterID[j] == uniqueClusterID[i]:
                  index = indices[j]
                  groupClusterIDs[index] = factorName + str(i + 1)
                  print(groupClusterIDs[index])
          #Plot PC1 and PC 2 based on kmeans clusters
          print(f"group cluster ID are {groupClusterIDs}")
          print(f"Templates indices are: {templatesIndices}")
          self.plotClustersWithFactors(files, groupFactorArray, templatesIndices)
          print(f'Time: {time.time() - start}')
        else:   #if the user input a factor requiring more than 3 groups, do not use factor
          qt.QMessageBox.critical(slicer.util.mainWindow(),
          'Error', 'Please enter group information for every specimen')
      else:
        qt.QMessageBox.critical(slicer.util.mainWindow(),
          'Error', 'Please select Multiple groups within the sample option and enter group information for each specimen')

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
    logic.makeScatterPlot(scatterDataAll, files,
      'PCA Scatter Plots',"PC1","PC2", pcNumber, templatesIndices)

  def updateLayout(self):
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(9)  #set layout to 3D only
    layoutManager.threeDWidget(0).threeDView().resetFocalPoint()
    layoutManager.threeDWidget(0).threeDView().resetCamera()

  def onChangeAdvanced(self):
    self.ui.pointDensitySlider.value = self.ui.pointDensityAdvancedSlider.value
    self.updateParameterDictionary()

  def onChangeDensitySingle(self):
    self.ui.pointDensityAdvancedSlider.value = self.ui.pointDensitySlider.value
    self.updateParameterDictionary()

  def onChangeMultiTemplate(self):
    if self.ui.methodBatchWidget.currentText == 'Multi-Template(MALPACA)':
      self.ui.sourceModelMultiSelector.currentPath = ''
      self.ui.sourceModelMultiSelector.filters  = ctk.ctkPathLineEdit.Dirs
      self.ui.sourceModelMultiSelector.toolTip = "Select a directory containing the source meshes (note: filenames must match with landmark filenames)"
      self.ui.sourceFiducialMultiSelector.currentPath = ''
      self.ui.sourceFiducialMultiSelector.filters  = ctk.ctkPathLineEdit.Dirs
      self.ui.sourceFiducialMultiSelector.toolTip = "Select a directory containing the landmark files (note: filenames must match with source meshes)"
    else:
      self.ui.sourceModelMultiSelector.filters  = ctk.ctkPathLineEdit().Files
      self.ui.sourceModelMultiSelector.nameFilters  = ["*.ply"]
      self.ui.sourceModelMultiSelector.toolTip = "Select the source mesh"
      self.ui.sourceFiducialMultiSelector.filters  = ctk.ctkPathLineEdit().Files
      self.ui.sourceFiducialMultiSelector.nameFilters  = ["*.json *.mrk.json *.fcsv"]
      self.ui.sourceFiducialMultiSelector.toolTip = "Select the source landmarks"


  def onChangeCPD(self):
    ALPACALogic().saveBCPDPath(self.ui.BCPDFolder.currentPath)
    if self.ui.accelerationCheckBox.checked != 0:
      self.ui.BCPDFolder.enabled = True
      self.ui.subsampleButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.sourceLandmarkSetSelector.currentNode() and self.ui.BCPDFolder.currentPath)
      self.ui.applyLandmarkMultiButton.enabled = bool ( self.ui.sourceModelMultiSelector.currentPath and self.ui.sourceFiducialMultiSelector.currentPath
      and self.ui.targetModelMultiSelector.currentPath and self.ui.landmarkOutputSelector.currentPath and self.ui.BCPDFolder.currentPath)
    else:
      self.ui.BCPDFolder.enabled = False
      self.ui.subsampleButton.enabled = bool ( self.ui.sourceModelSelector.currentNode and self.ui.targetModelSelector.currentNode and self.ui.sourceLandmarkSetSelector.currentNode)
      self.ui.applyLandmarkMultiButton.enabled = bool ( self.ui.sourceModelMultiSelector.currentPath and self.ui.sourceFiducialMultiSelector.currentPath
      and self.ui.targetModelMultiSelector.currentPath and self.ui.landmarkOutputSelector.currentPath)

  def updateParameterDictionary(self):
    # update the parameter dictionary from single run parameters
    if hasattr(self, 'parameterDictionary'):
      self.parameterDictionary["projectionFactor"] = self.ui.projectionFactorSlider.value
      self.parameterDictionary["pointDensity"] = self.ui.pointDensityAdvancedSlider.value
      self.parameterDictionary["normalSearchRadius"] = int(self.ui.normalSearchRadiusSlider.value)
      self.parameterDictionary["FPFHSearchRadius"] = int(self.ui.FPFHSearchRadiusSlider.value)
      self.parameterDictionary["distanceThreshold"] = self.ui.maximumCPDThreshold.value
      self.parameterDictionary["maxRANSAC"] = int(self.ui.maxRANSAC.value)
      self.parameterDictionary["RANSACConfidence"] = self.ui.RANSACConfidence.value
      self.parameterDictionary["ICPDistanceThreshold"] = self.ui.ICPDistanceThresholdSlider.value
      self.parameterDictionary["alpha"] = self.ui.alpha.value
      self.parameterDictionary["beta"] = self.ui.beta.value
      self.parameterDictionary["CPDIterations"] = int(self.ui.CPDIterationsSlider.value)
      self.parameterDictionary["CPDTolerance"] = self.ui.CPDToleranceSlider.value
      self.parameterDictionary["Acceleration"] = self.ui.accelerationCheckBox.checked
      self.parameterDictionary["BCPDFolder"] = self.ui.BCPDFolder.currentPath



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

  def runLandmarkMultiprocess(self, sourceModelPath, sourceLandmarkPath, targetModelDirectory, outputDirectory, skipScaling, projectionFactor, useJSONFormat, parameters):
    extensionModel = ".ply"
    if useJSONFormat:
      extensionLM = ".mrk.json"
    else:
      extensionLM = ".fcsv"
    sourceModelList = []
    sourceLMList = []
    TargetModelList = []
    if os.path.isdir(sourceModelPath):
        specimenOutput = os.path.join(outputDirectory,'individualEstimates')
        medianOutput = os.path.join(outputDirectory,'medianEstimates')
        os.makedirs(specimenOutput, exist_ok=True)
        os.makedirs(medianOutput, exist_ok=True)
        for file in os.listdir(sourceModelPath):
          if file.endswith(extensionModel):
            sourceFilePath = os.path.join(sourceModelPath,file)
            sourceModelList.append(sourceFilePath)
    else:
      sourceModelList.append(sourceModelPath)
    if os.path.isdir(sourceLandmarkPath):
      for file in os.listdir(sourceLandmarkPath):
          if file.endswith((".json", ".fcsv")):
            sourceFilePath = os.path.join(sourceLandmarkPath,file)
            sourceLMList.append(sourceFilePath)
    else:
      sourceLMList.append(sourceLandmarkPath)
    # Iterate through target models
    for targetFileName in os.listdir(targetModelDirectory):
      if targetFileName.endswith(extensionModel):
        targetFilePath = os.path.join(targetModelDirectory, targetFileName)
        TargetModelList.append(targetFilePath)
        rootName = os.path.splitext(targetFileName)[0]
        landmarkList = []
        if os.path.isdir(sourceModelPath):
          outputMedianPath = os.path.join(medianOutput, f'{rootName}_median' + extensionLM)
          if not os.path.exists(outputMedianPath):
            for file in sourceModelList:
              sourceFilePath = os.path.join(sourceModelPath,file)
              (baseName, ext) = os.path.splitext(os.path.basename(file))
              sourceLandmarkFile = None
              for lmFile in sourceLMList:
                if baseName in lmFile:
                  sourceLandmarkFile = os.path.join(sourceLandmarkPath, lmFile)
              if sourceLandmarkFile is None:
                print('::::Could not find the file corresponding to ', file)
                next
              outputFilePath = os.path.join(specimenOutput, f'{rootName}_{baseName}' + extensionLM)
              array = self.pairwiseAlignment(sourceFilePath, sourceLandmarkFile, targetFilePath, outputFilePath, skipScaling, projectionFactor, parameters)
              landmarkList.append(array)
            medianLandmark = np.median(landmarkList, axis=0)
            outputMedianNode = self.exportPointCloud(medianLandmark, "Median Predicted Landmarks")
            slicer.util.saveNode(outputMedianNode, outputMedianPath)
            slicer.mrmlScene.RemoveNode(outputMedianNode)
        elif os.path.isfile(sourceModelPath):
            rootName = os.path.splitext(targetFileName)[0]
            outputFilePath = os.path.join(outputDirectory, rootName + extensionLM)
            array = self.pairwiseAlignment(sourceModelPath, sourceLandmarkPath, targetFilePath, outputFilePath, skipScaling, projectionFactor, parameters)
        else:
            print('::::Could not find the file or directory in question')
    extras = {"Source" : sourceModelList, "SourceLandmarks" : sourceLMList, "Target" : TargetModelList, "Output" : outputDirectory, 'Skip scaling ?' : bool(skipScaling)}
    extras.update(parameters)
    parameterFile = os.path.join(outputDirectory, 'advancedParameters.txt')
    json.dump(extras, open(parameterFile,'w'), indent = 2)


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
            projectedLMNode.AddControlPoint(point)
        self.propagateLandmarkTypes(sourceLMNode, projectedLMNode)
        projectedLMNode.SetLocked(True)
        projectedLMNode.SetFixedNumberOfControlPoints(True)
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
      fiducialNode.AddControlPoint(point)
    fiducialNode.SetLocked(True)
    fiducialNode.SetFixedNumberOfControlPoints(True)
    return fiducialNode

    #node.AddControlPoint(point)
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
      targetPath = os.path.join(slicer.app.cachePath,'target.txt')
      sourcePath = os.path.join(slicer.app.cachePath,'source.txt')
      np.savetxt (targetPath, targetArray, delimiter=',')
      np.savetxt (sourcePath, sourceArrayCombined, delimiter=',')
      path = os.path.join(parameters["BCPDFolder"], 'bcpd')
      cmd = f'"{path}" -x "{targetPath}" -y "{sourcePath}" -l{parameters["alpha"]} -b{parameters["beta"]} -g0.1 -K140 -J500 -c1e-6 -p -d7 -e0.3 -f0.3 -ux -N1'
      cp = subprocess.run(cmd, shell = True, check = True,text=True, capture_output=True)
      deformed_array = np.loadtxt('output_y.txt')
      for fl in glob.glob("output*.txt"):
        os.remove(fl)
      os.remove(targetPath)
      os.remove(sourcePath)
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

  def itkToVTKTransform(self, itkTransform):
    translation = itkTransform.GetTranslation()
    matrix = itkTransform.GetMatrix()
    matrix_vtk = vtk.vtkMatrix4x4()
    for i in range(3):
      for j in range(3):
        matrix_vtk.SetElement(i, j, matrix(i, j))
    for i in range(3):
      matrix_vtk.SetElement(i, 3, translation[i])

    transform = vtk.vtkTransform()
    transform.SetMatrix(matrix_vtk)
    return transform
  
  def convertMatrixToTransformNode(self, itkTransform, transformName):
    transform = self.itkToVTKTransform(itkTransform)
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
    # modelNode=slicer.mrmlScene.GetFirstNodeByName(nodeName)
    #if modelNode is None:  # if there is no node with this name, create with display node
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

  def find_knn_cpu(self, feat0, feat1, knn=1, return_distance=False):
    from scipy.spatial import cKDTree
    feat1tree = cKDTree(feat1)
    dists, nn_inds = feat1tree.query(feat0, k=knn)
    if return_distance:
        return nn_inds, dists
    else:
        return nn_inds

  def find_correspondences(self, feats0, feats1, mutual_filter=True):
    '''
        Using the FPFH features find noisy corresspondes.
        These corresspondes will be used inside the RANSAC.
    '''
    nns01, dists1 = self.find_knn_cpu(feats0, feats1, knn=1, return_distance=True)
    corres01_idx0 = np.arange(len(nns01))
    corres01_idx1 = nns01

    if not mutual_filter:
        return corres01_idx0, corres01_idx1

    nns10, dists2 = self.find_knn_cpu(feats1, feats0, knn=1, return_distance=True)
    corres10_idx1 = np.arange(len(nns10))
    corres10_idx0 = nns10

    mutual_filter = corres10_idx0[corres01_idx1] == corres01_idx0
    corres_idx0 = corres01_idx0[mutual_filter]
    corres_idx1 = corres01_idx1[mutual_filter]

    return corres_idx0, corres_idx1
  
  # RANSAC using package
  def ransac_using_package(self, 
    movingMeshPoints,
    fixedMeshPoints,
    movingMeshFeaturePoints,
    fixedMeshFeaturePoints,
    number_of_iterations,
    number_of_ransac_points,
    inlier_value):
    import itk
    def GenerateData(data, agreeData):
        """
            In current implmentation the agreedata contains two corressponding 
            points from moving and fixed mesh. However, after the subsampling step the 
            number of points need not be equal in those meshes. So we randomly sample 
            the points from larger mesh.
        """
        data.reserve(movingMeshFeaturePoints.shape[0])
        for i in range(movingMeshFeaturePoints.shape[0]):
            point1 = movingMeshFeaturePoints[i]
            point2 = fixedMeshFeaturePoints[i]
            input_data = [point1[0], point1[1], point1[2], point2[0], point2[1], point2[2]]
            input_data = [float(x) for x in input_data]
            data.push_back(input_data)
    
        count_min = int(np.min([movingMeshPoints.shape[0], fixedMeshPoints.shape[0]]))

        mesh1_points  = copy.deepcopy(movingMeshPoints)
        mesh2_points  = copy.deepcopy(fixedMeshPoints)

        agreeData.reserve(count_min)
        for i in range(count_min):
            point1 = mesh1_points[i]
            point2 = mesh2_points[i]
            input_data = [point1[0], point1[1], point1[2], point2[0], point2[1], point2[2]]
            input_data = [float(x) for x in input_data]
            agreeData.push_back(input_data)
        return

    data = itk.vector[itk.Point[itk.D, 6]]()
    agreeData = itk.vector[itk.Point[itk.D, 6]]()
    GenerateData(data, agreeData)

    transformParameters = itk.vector.D()
    bestTransformParameters = itk.vector.D()

    maximumDistance = inlier_value
    RegistrationEstimatorType = itk.Ransac.LandmarkRegistrationEstimator[6]
    registrationEstimator = RegistrationEstimatorType.New()
    registrationEstimator.SetMinimalForEstimate(number_of_ransac_points)
    registrationEstimator.SetAgreeData(agreeData)
    registrationEstimator.SetDelta(maximumDistance)
    registrationEstimator.LeastSquaresEstimate(data, transformParameters)

    bestPercentage = 0
    bestParameters = None

    desiredProbabilityForNoOutliers = 0.99
    RANSACType = itk.RANSAC[itk.Point[itk.D, 6], itk.D]
    ransacEstimator = RANSACType.New()
    ransacEstimator.SetData(data)
    ransacEstimator.SetAgreeData(agreeData)
    ransacEstimator.SetMaxIteration(number_of_iterations)
    ransacEstimator.SetNumberOfThreads(16)
    ransacEstimator.SetParametersEstimator(registrationEstimator)
    
    for i in range(1):    
        percentageOfDataUsed = ransacEstimator.Compute( transformParameters, desiredProbabilityForNoOutliers )
        print(i, ' Percentage of data used is ', percentageOfDataUsed)
        if percentageOfDataUsed > bestPercentage:
            bestPercentage = percentageOfDataUsed
            bestParameters = transformParameters

    print("Percentage of points used ", bestPercentage)
    transformParameters = bestParameters
    transform = itk.Similarity3DTransform.D.New()
    p = transform.GetParameters()
    f = transform.GetFixedParameters()
    for i in range(7):
        p.SetElement(i, transformParameters[i])
    counter = 0
    for i in range(7, 10):
        f.SetElement(counter, transformParameters[i])
        counter = counter + 1
    transform.SetParameters(p)
    transform.SetFixedParameters(f)
    return itk.dict_from_transform(transform), bestPercentage, bestPercentage
  
  def get_euclidean_distance(self, input_fixedPoints, input_movingPoints):
    import itk
    mesh_fixed = itk.Mesh[itk.D, 3].New()
    mesh_moving = itk.Mesh[itk.D, 3].New()

    mesh_fixed.SetPoints(itk.vector_container_from_array(input_fixedPoints.flatten()))
    mesh_moving.SetPoints(itk.vector_container_from_array(input_movingPoints.flatten()))

    MetricType = itk.EuclideanDistancePointSetToPointSetMetricv4.PSD3
    metric = MetricType.New()
    metric.SetMovingPointSet(mesh_moving)
    metric.SetFixedPointSet(mesh_fixed)
    metric.Initialize()

    return metric.GetValue()

  def final_iteration(self, fixedPoints, movingPoints, transform_type):
    import itk
    """
    Perform the final iteration of alignment.
    Args:
        fixedPoints, movingPoints, transform_type: 0 or 1 or 2
    Returns:
        (tranformed movingPoints, tranform)
    """
    mesh_fixed = itk.Mesh[itk.D, 3].New()
    mesh_moving = itk.Mesh[itk.D, 3].New()
    mesh_fixed.SetPoints(itk.vector_container_from_array(fixedPoints.flatten()))
    mesh_moving.SetPoints(itk.vector_container_from_array(movingPoints.flatten()))

    if transform_type == 0:
        TransformType = itk.Euler3DTransform[itk.D]
    elif transform_type == 1:
        TransformType = itk.ScaleVersor3DTransform[itk.D]
    elif transform_type == 2:
        TransformType = itk.Rigid3DTransform[itk.D]

    transform = TransformType.New()
    transform.SetIdentity()

    MetricType = itk.EuclideanDistancePointSetToPointSetMetricv4.PSD3
    metric = MetricType.New()
    metric.SetMovingPointSet(mesh_moving)
    metric.SetFixedPointSet(mesh_fixed)
    metric.SetMovingTransform(transform)
    metric.Initialize()

    number_of_epochs = 1000
    optimizer = itk.GradientDescentOptimizerv4Template[itk.D].New()
    optimizer.SetNumberOfIterations(number_of_epochs)
    optimizer.SetLearningRate(0.00001)
    optimizer.SetMinimumConvergenceValue(0.0)
    optimizer.SetConvergenceWindowSize(number_of_epochs)
    optimizer.SetMetric(metric)

    def print_iteration():
        if optimizer.GetCurrentIteration()%100 == 0:
            print(
                f"It: {optimizer.GetCurrentIteration()}"
                f" metric value: {optimizer.GetCurrentMetricValue():.6f} "
            )
    optimizer.AddObserver(itk.IterationEvent(), print_iteration)
    optimizer.StartOptimization()

    # Get the correct transform and perform the final alignment
    current_transform = metric.GetMovingTransform().GetInverseTransform()
    itk_transformed_mesh = itk.transform_mesh_filter(
        mesh_moving, transform=current_transform
    )

    return (
        itk.array_from_vector_container(itk_transformed_mesh.GetPoints()),
        current_transform,
    )
  
  def estimateTransform(self, sourcePoints, targetPoints, sourceFeatures, targetFeatures, 
  voxelSize, skipScaling, parameters):
    print('Inside estimateTransform')
    import itk
    # Establish correspondences by nearest neighbour search in feature space
    corrs_A, corrs_B = self.find_correspondences(
        targetFeatures, sourceFeatures, mutual_filter=True
    )

    targetPoints = targetPoints.T
    sourcePoints = sourcePoints.T

    fixed_corr = targetPoints[:, corrs_A]    # np array of size 3 by num_corrs
    moving_corr = sourcePoints[:, corrs_B]  # np array of size 3 by num_corrs

    num_corrs = fixed_corr.shape[1]
    print(f"FPFH generates {num_corrs} putative correspondences.")

    print(fixed_corr.shape, moving_corr.shape)
    import time
    bransac = time.time()
    print('Before RANSAC ', bransac)
    # Perform Initial alignment using Ransac parallel iterations
    transform_matrix, _, value = self.ransac_using_package(
        movingMeshPoints=sourcePoints.T,
        fixedMeshPoints=targetPoints.T,
        movingMeshFeaturePoints=moving_corr.T,
        fixedMeshFeaturePoints=fixed_corr.T,
        number_of_iterations=parameters["maxRANSAC"],
        number_of_ransac_points=100,
        inlier_value=parameters["distanceThreshold"],
    )
    aransac = time.time()
    print('After RANSAC ', aransac)
    print('Total Duraction ', aransac - bransac)

    first_transform = itk.transform_from_dict(transform_matrix)

    sourcePoints = sourcePoints.T
    targetPoints = targetPoints.T

    print("movingMeshPoints.shape ", sourcePoints.shape)
    print("fixedMeshPoints.shape ", targetPoints.shape)

    print('-----------------------------------------------------------')
    print("Starting Rigid Refinement")
    print("Before Distance ", self.get_euclidean_distance(targetPoints, sourcePoints))
    transform_type = 0
    final_mesh_points, second_transform = self.final_iteration(
        targetPoints, sourcePoints, transform_type
    )
    print("After Distance ", self.get_euclidean_distance(targetPoints, final_mesh_points))
    print(first_transform)
    print(second_transform)
    return [first_transform, second_transform]
    #ransac = self.execute_global_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize,
    #  parameters["distanceThreshold"], parameters["maxRANSAC"], parameters["RANSACConfidence"], skipScaling)
    # Refine the initial registration using an Iterative Closest Point (ICP) registration
    #import time
    #icp = self.refine_registration(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, ransac, parameters["ICPDistanceThreshold"])
    #return icp.transformation

  # def getVolume(pmax, pmin):
  #   volume = (pmax[0] - pmin[0]) * (pmax[1] - pmin[1]) * (pmax[2] - pmin[2])
  #   return volume
  
  def cleanMesh(self, vtk_mesh):
    # Get largest connected component and clean the mesh to remove un-used points
    connectivityFilter = vtk.vtkPolyDataConnectivityFilter()
    connectivityFilter.SetInputData(vtk_mesh)
    connectivityFilter.SetExtractionModeToLargestRegion()
    connectivityFilter.Update()
    vtk_mesh_out = connectivityFilter.GetOutput()

    filter1 = vtk.vtkCleanPolyData()
    filter1.SetInputData(vtk_mesh_out)
    filter1.Update()
    vtk_mesh_out_clean = filter1.GetOutput()

    triangle_filter = vtk.vtkTriangleFilter()
    triangle_filter.SetInputData(vtk_mesh_out_clean)
    triangle_filter.SetPassLines(False)
    triangle_filter.SetPassVerts(False)
    triangle_filter.Update()
    vtk_mesh_out_clean = triangle_filter.GetOutput()
    return vtk_mesh_out_clean

  def set_numpy_points_in_vtk(self, vtk_polydata, points_as_numpy):
    """
    Sets the numpy points to a vtk_polydata
    """
    import vtk
    from vtk.util import numpy_support
    vtk_data_array = numpy_support.numpy_to_vtk(
        num_array=points_as_numpy, deep=True, array_type=vtk.VTK_FLOAT
    )
    points2 = vtk.vtkPoints()
    points2.SetData(vtk_data_array)
    vtk_polydata.SetPoints(points2)
    return
  
  def get_numpy_points_from_vtk(self, vtk_polydata):
    import vtk
    from vtk.util import numpy_support
    """
    Returns the points as numpy from a vtk_polydata
    """
    points = vtk_polydata.GetPoints()
    pointdata = points.GetData()
    points_as_numpy = numpy_support.vtk_to_numpy(pointdata)
    return points_as_numpy
  
  def getnormals(self, inputmesh):
    """
    To obtain the normal for each point from the triangle mesh.
    """
    normals = vtk.vtkTriangleMeshPointNormals()
    normals.SetInputData(inputmesh)
    normals.Update()
    return normals.GetOutput()

  def subsample_points_poisson_polydata(self, inputMesh, radius):
    '''
        Subsamples the points and returns vtk points so 
        that it has normal data also in it.
    '''
    import vtk
    from vtk.util import numpy_support

    f = vtk.vtkPoissonDiskSampler()
    f.SetInputData(inputMesh)
    f.SetRadius(radius)
    f.Update()
    sampled_points = f.GetOutput()
    return sampled_points
  
  def extract_normal_from_tuple(self, input_mesh):
    """
    Extracts the normal data from the sampled points.
    Returns points and normals for the points.
    """
    import vtk
    from vtk.util import numpy_support
    t1 = input_mesh.GetPointData().GetArray("Normals")
    n1_array = []
    for i in range(t1.GetNumberOfTuples()):
        n1_array.append(t1.GetTuple(i))
    n1_array = np.array(n1_array)

    points = input_mesh.GetPoints()
    pointdata = points.GetData()
    as_numpy = numpy_support.vtk_to_numpy(pointdata)

    return as_numpy, n1_array
  
  def get_fpfh_feature(self, points_np, normals_np, radius, neighbors):
    import itk
    pointset = itk.PointSet[itk.F, 3].New()
    pointset.SetPoints(
        itk.vector_container_from_array(points_np.flatten().astype("float32"))
    )

    normalset = itk.PointSet[itk.F, 3].New()
    normalset.SetPoints(
        itk.vector_container_from_array(normals_np.flatten().astype("float32"))
    )

    fpfh = itk.Fpfh.PointFeature.MF3MF3.New()
    fpfh.ComputeFPFHFeature(pointset, normalset, int(radius), int(neighbors))
    result = fpfh.GetFpfhFeature()

    fpfh_feats = itk.array_from_vector_container(result)
    fpfh_feats = np.reshape(fpfh_feats, [33, pointset.GetNumberOfPoints()]).T
    return fpfh_feats

  def runSubsample(self, sourceModel, targetModel, skipScaling, parameters):
    import copy
    import vtk
    from vtk.util import numpy_support
    print("parameters are ", parameters)
    print(":: Loading point clouds and downsampling")
    
    sourceModelMesh = sourceModel.GetMesh()
    targetModelMesh = targetModel.GetMesh()

    sourceModelMesh = self.cleanMesh(sourceModelMesh)
    targetModelMesh = self.cleanMesh(targetModelMesh)

    vtk_meshes = []
    vtk_meshes.append(targetModelMesh)
    vtk_meshes.append(sourceModelMesh)

    # Scale the mesh and the landmark points
    box_filter = vtk.vtkBoundingBox()
    box_filter.SetBounds(vtk_meshes[0].GetBounds())
    fixedlength = box_filter.GetDiagonalLength()
    fixedLengths = [0.0, 0.0, 0.0]
    box_filter.GetLengths(fixedLengths)
    fixedVolume = np.prod(fixedLengths)

    box_filter = vtk.vtkBoundingBox()
    box_filter.SetBounds(vtk_meshes[1].GetBounds())
    movinglength = box_filter.GetDiagonalLength()
    movingLengths = [0.0, 0.0, 0.0]
    box_filter.GetLengths(movingLengths)
    movingVolume = np.prod(movingLengths)

    print("Scale length are  ", fixedlength, movinglength)
    scaling = fixedlength / movinglength

    points = vtk_meshes[1].GetPoints()
    pointdata = points.GetData()
    points_as_numpy = numpy_support.vtk_to_numpy(pointdata)

    if skipScaling != 0:
        scaling = 1
    points_as_numpy = points_as_numpy * scaling
    self.set_numpy_points_in_vtk(vtk_meshes[1], points_as_numpy)

    # Get the offsets to align the minimum of moving and fixed mesh
    vtk_mesh_offsets = []
    for i, mesh in enumerate(vtk_meshes):
        mesh_points = self.get_numpy_points_from_vtk(mesh)
        vtk_mesh_offset = np.min(mesh_points, axis=0)
        vtk_mesh_offsets.append(vtk_mesh_offset)
    
    # Only move the moving mesh
    mesh_points = self.get_numpy_points_from_vtk(vtk_meshes[1])
    offset_amount = (vtk_mesh_offsets[1] - vtk_mesh_offsets[0])
    mesh_points = mesh_points - offset_amount
    self.set_numpy_points_in_vtk(vtk_meshes[1], mesh_points)

    sourceModel.SetAndObserveMesh(vtk_meshes[1])

    sourceFullMesh_vtk = self.getnormals(vtk_meshes[1])
    targetFullMesh_vtk = self.getnormals(vtk_meshes[0])

    print('movingMesh_vtk.GetNumberOfPoints() ', sourceFullMesh_vtk.GetNumberOfPoints())
    print('fixedMesh_vtk.GetNumberOfPoints() ', targetFullMesh_vtk.GetNumberOfPoints())
    
    # Sub-Sample the points for rigid refinement and deformable registration
    subsample_radius_moving = 0.25*((movingVolume/(4.19*5000)) ** (1./3.))
    print('Initial estimate of subsample_radius_moving is ', subsample_radius_moving)

    point_density = parameters['pointDensity']
    increment_radius = 0.25*subsample_radius_moving
    while (True):
      sourceMesh_vtk = self.subsample_points_poisson_polydata(
          sourceFullMesh_vtk, radius=subsample_radius_moving
      )
      print('Resampling moving with radius = ', subsample_radius_moving, sourceMesh_vtk.GetNumberOfPoints())
      if sourceMesh_vtk.GetNumberOfPoints() < 5500:
          break
      else:
          subsample_radius_moving = subsample_radius_moving + increment_radius
    if point_density != 1:
        print('point density is not 1 ', point_density)
        subsample_radius_moving = subsample_radius_moving - (point_density-1)*increment_radius
        sourceMesh_vtk = self.subsample_points_poisson_polydata(sourceFullMesh_vtk, radius=subsample_radius_moving)
    
    subsample_radius_fixed = 0.25*((fixedVolume/(4.19*5000)) ** (1./3.))
    print('Initial estimate of subsample_radius_fixed is ', subsample_radius_fixed)
    increment_radius = 0.3*subsample_radius_fixed
    while (True):
        targetMesh_vtk = self.subsample_points_poisson_polydata(
            targetFullMesh_vtk, radius=subsample_radius_fixed
        )
        print('Resampling fixed with radius = ', subsample_radius_fixed, targetMesh_vtk.GetNumberOfPoints())
        if targetMesh_vtk.GetNumberOfPoints() < 5500:
            break
        else:
            subsample_radius_fixed = subsample_radius_fixed + increment_radius
    if point_density != 1:
        print('point density is not 1 ', point_density)
        subsample_radius_fixed = subsample_radius_fixed - (point_density-1)*increment_radius
        targetMesh_vtk = self.subsample_points_poisson_polydata(targetFullMesh_vtk, radius=subsample_radius_fixed)
    
    movingMeshPoints, movingMeshPointNormals = self.extract_normal_from_tuple(sourceMesh_vtk)
    fixedMeshPoints, fixedMeshPointNormals = self.extract_normal_from_tuple(targetMesh_vtk)

    print('------------------------------------------------------------')
    print("movingMeshPoints.shape ", movingMeshPoints.shape)
    print("movingMeshPointNormals.shape ", movingMeshPointNormals.shape)
    print("fixedMeshPoints.shape ", fixedMeshPoints.shape)
    print("fixedMeshPointNormals.shape ", fixedMeshPointNormals.shape)
    print('------------------------------------------------------------')

    fpfh_radius = parameters['FPFHSearchRadius']
    fpfh_neighbors = 100
    # New FPFH Code
    pcS = np.expand_dims(fixedMeshPoints, -1)
    normal_np_pcl = fixedMeshPointNormals
    target_fpfh = self.get_fpfh_feature(pcS, normal_np_pcl, fpfh_radius, fpfh_neighbors)

    pcS = np.expand_dims(movingMeshPoints, -1)
    normal_np_pcl = movingMeshPointNormals
    source_fpfh = self.get_fpfh_feature(pcS, normal_np_pcl, fpfh_radius, fpfh_neighbors)

    voxel_size = subsample_radius_moving
    target_down = fixedMeshPoints
    source_down = movingMeshPoints
    return source_down, target_down, source_fpfh, target_fpfh, voxel_size, scaling

  def loadAndScaleFiducials (self, fiducial, scaling, scene = False):
    if not scene:
      sourceLandmarkNode =  slicer.util.loadMarkups(fiducial)
    else:
      shNode= slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      itemIDToClone = shNode.GetItemByDataNode(fiducial)
      clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
      sourceLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    sourceLandmarks = np.zeros(shape=(sourceLandmarkNode.GetNumberOfControlPoints(),3))
    for i in range(sourceLandmarkNode.GetNumberOfControlPoints()):
      point = sourceLandmarkNode.GetNthControlPointPosition(i)
      sourceLandmarks[i,:] = point
    sourceLandmarks = sourceLandmarks * scaling
    slicer.util.updateMarkupsControlPointsFromArray(sourceLandmarkNode, sourceLandmarks)
    sourceLandmarkNode.GetDisplayNode().SetVisibility(False)
    return sourceLandmarks, sourceLandmarkNode

  def propagateLandmarkTypes(self,sourceNode, targetNode):
     for i in range(sourceNode.GetNumberOfControlPoints()):
       pointDescription = sourceNode.GetNthControlPointDescription(i)
       targetNode.SetNthControlPointDescription(i,pointDescription)
       pointLabel = sourceNode.GetNthControlPointLabel(i)
       targetNode.SetNthControlPointLabel(i, pointLabel)

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
    #from open3d import geometry
    #from open3d import pipelines
    registration = pipelines.registration
    #print(":: Downsample with a voxel size %.3f." % voxel_size)
    #pcd_down = pcd.voxel_down_sample(voxel_size)
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
                                target_fpfh, voxel_size, distance_threshold_factor, maxIter, confidence, skipScaling):
    from open3d import pipelines
    registration = pipelines.registration
    distance_threshold = voxel_size * distance_threshold_factor
    print(":: RANSAC registration on downsampled point clouds.")
    print("   Since the downsampling voxel size is %.3f," % voxel_size)
    print("   we use a liberal distance threshold %.3f." % distance_threshold)

    no_scaling = registration.registration_ransac_based_on_feature_matching(
          source_down, target_down, source_fpfh, target_fpfh, True, distance_threshold,
          registration.TransformationEstimationPointToPoint(False), 3, [
              registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
              registration.CorrespondenceCheckerBasedOnDistance(
                  distance_threshold)
          ], registration.RANSACConvergenceCriteria(maxIter, confidence))
    no_scaling_eval = registration.evaluate_registration(target_down, source_down, distance_threshold, np.linalg.inv(no_scaling.transformation))
    best_result = no_scaling
    fitness = (no_scaling.fitness + no_scaling_eval.fitness)/2
    if skipScaling == 0:
      count = 0
      maxAttempts = 10
      while fitness < 0.99 and count < maxAttempts:
        result = registration.registration_ransac_based_on_feature_matching(
            source_down, target_down, source_fpfh, target_fpfh, True, distance_threshold,
            registration.TransformationEstimationPointToPoint(skipScaling == 0), 3, [
                registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
                registration.CorrespondenceCheckerBasedOnDistance(
                    distance_threshold)
            ], registration.RANSACConvergenceCriteria(maxIter, confidence))
        evaluation = registration.evaluate_registration(target_down, source_down, distance_threshold, np.linalg.inv(result.transformation))
        mean_fitness = (result.fitness + evaluation.fitness)/2
        if mean_fitness > fitness:
          fitness = mean_fitness
          best_result = result
        count += 1
    return best_result


  def refine_registration(self, source, target, source_fpfh, target_fpfh, voxel_size, result_ransac, ICPThreshold_factor):
    from open3d import pipelines
    registration = pipelines.registration
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
    for i in range(fiducialNode.GetNumberOfControlPoints()):
      point = fiducialNode.GetNthControlPointPosition(i)
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
      projectedLMNode.AddControlPoint(point)
    projectedLMNode.SetLocked(True)
    projectedLMNode.SetFixedNumberOfControlPoints(True)
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

###Functions for select templates based on kmeans
  def downReference(self, referenceFilePath, spacingFactor):
    targetModelNode = slicer.util.loadModel(referenceFilePath)
    targetModelNode.GetDisplayNode().SetVisibility(False)
    templatePolydata = targetModelNode.GetPolyData()
    sparseTemplate = self.DownsampleTemplate(templatePolydata, spacingFactor)
    template_density = sparseTemplate.GetNumberOfPoints()
    return sparseTemplate, template_density, targetModelNode

  def matchingPCD(self, modelsDir, sparseTemplate, targetModelNode, pcdOutputDir, spacingFactor, useJSONFormat, parameterDictionary):
    if useJSONFormat:
      extensionLM = ".mrk.json"
    else:
      extensionLM = ".fcsv"
    template_density = sparseTemplate.GetNumberOfPoints()
    ID_list = list()
    #Alignment and matching points
    referenceFileList = [f for f in os.listdir(modelsDir) if f.endswith(('.ply', '.stl', '.obj', '.vtk', '.vtp'))]
    for file in referenceFileList:
      sourceFilePath = os.path.join(modelsDir, file)
      sourceModelNode = slicer.util.loadModel(sourceFilePath)
      sourceModelNode.GetDisplayNode().SetVisibility(False)
      rootName = os.path.splitext(file)[0]
      skipScalingOption = False
      sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, scaling = self.runSubsample(sourceModelNode, targetModelNode,
        skipScalingOption, parameterDictionary)
      [ICPTransform_similarity, ICPTransform_rigid] = self.estimateTransform(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, skipScalingOption, parameterDictionary)
      ICPTransformNode = self.convertMatrixToTransformNode(ICPTransform_rigid, 'Rigid Transformation Matrix')
      sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)
      alignedSubjectPolydata = sourceModelNode.GetPolyData()
      ID, correspondingSubjectPoints = self.GetCorrespondingPoints(sparseTemplate, alignedSubjectPolydata)
      ID_list.append(ID)
      subjectFiducial = slicer.vtkMRMLMarkupsFiducialNode()
      for i in range(correspondingSubjectPoints.GetNumberOfPoints()):
        subjectFiducial.AddControlPoint(correspondingSubjectPoints.GetPoint(i))
      slicer.mrmlScene.AddNode(subjectFiducial)
      subjectFiducial.SetLocked(True)
      subjectFiducial.SetFixedNumberOfControlPoints(True)
      slicer.util.saveNode(subjectFiducial, os.path.join(pcdOutputDir, f"{rootName}" + extensionLM))
      slicer.mrmlScene.RemoveNode(sourceModelNode)
      slicer.mrmlScene.RemoveNode(ICPTransformNode)
      slicer.mrmlScene.RemoveNode(subjectFiducial)
    #Remove template node
    slicer.mrmlScene.RemoveNode(targetModelNode)
    #Printing results of points matching
    matchedPoints = [len(set(x)) for x in ID_list]
    indices = [i for i, x in enumerate(matchedPoints) if x < template_density]
    files = [os.path.splitext(file)[0] for file in referenceFileList]
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
    try:
      LM.doGpa(skipScalingOption)
    except ValueError:
      print("Point clouds may not have been generated correctly. Please re-run the point cloud generation step.")
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
    basename, extension = os.path.splitext(inputFilePaths[0])
    files = [os.path.basename(path).split('.')[0] for path in inputFilePaths]
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
    else:
      plotChartNode.RemoveAllPlotSeriesNodeIDs()

    # Plot all series
    for factorIndex in range(len(uniqueFactors)):
      factor = uniqueFactors[factorIndex]
      tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table Group ' + factor)
      if tableNode is None:
        tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table Group ' + factor)
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
    layoutManager = slicer.app.layoutManager()
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
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(503)

    #Select chart in plot view
    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

  def saveBCPDPath(self, BCPDPath):
    # don't save if identical to saved
    settings = qt.QSettings()
    if settings.contains('Developer/BCPDPath'):
      BCPDPathSaved = settings.value('Developer/BCPDPath')
      if BCPDPathSaved == BCPDPath:
        return
    if not self.isValidBCPDPath(BCPDPath):
      return
    settings.setValue('Developer/BCPDPath',BCPDPath)

  def getBCPDPath(self):
    # If path is defined in settings then use that
    settings = qt.QSettings()
    if settings.contains('Developer/BCPDPath'):
      BCPDPath = settings.value('Developer/BCPDPath')
      if self.isValidBCPDPath(BCPDPath):
        return BCPDPath
    else:
        return ""

  def isValidBCPDPath(self, BCPDPath):
    if not os.path.isdir(BCPDPath):
      logging.info("BCPD path invalid: Not a directory")
      return False
    # Check if extension contains bcpd executable
    if slicer.app.os == 'win':
      exePath = os.path.join(BCPDPath, 'bcpd.exe')
    else:
      exePath = os.path.join(BCPDPath, 'bcpd')
    if os.path.exists(exePath):
      return True
    else:
      logging.info("BCPD path invalid: No executable found")
      return False

  def rmse(self, M1, M2):
    sq_dff = np.square(M1-M2)
    sq_LM_dist = np.sum(sq_dff,axis=1) #squared LM distances
    RMSE = np.sqrt(np.mean(sq_LM_dist))
    #<- sqrt(mean(sq_LM_dist))
    return RMSE


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

    logic = ALPACALogic()

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
