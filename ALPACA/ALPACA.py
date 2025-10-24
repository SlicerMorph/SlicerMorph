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
from datetime import datetime
import time
import sys
import os
import platform
import math

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
        self.parent.contributors = [
            "Arthur Porto (LSU), Sara Rolfe (UW), Chi Zhang (SCRI), Murat Maga (UW)"
        ]
        self.parent.helpText = """
      This module automatically transfers landmarks on a reference 3D model (mesh) to a target 3D model using dense correspondence and deformable registration. First optimize the parameters in single alignment analysis, then use them in batch mode to apply to all 3D models.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ALPACA">online documentation.</a>.</p>
      """
        self.parent.acknowledgementText = """
      This module was developed by Arthur Porto, Sara Rolfe, and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """

        # Define custom layouts for multi-templates selection tab in slicer global namespace
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
        needInstall = False

        try:
            from itk import Fpfh
            import cpdalp
        except ModuleNotFoundError:
            needInstall = True

        if needInstall:
            progressDialog = slicer.util.createProgressDialog(
                windowTitle="Installing...",
                labelText="Installing ALPACA Python packages. This may take a minute...",
                maximum=0,
            )
            slicer.app.processEvents()
            try:
                slicer.util.pip_install(["itk~=5.4.0"])
                slicer.util.pip_install(["scikit-learn"])
                slicer.util.pip_install(["itk-fpfh~=0.2.0"])
                slicer.util.pip_install(["itk-ransac~=0.2.1"])
                slicer.util.pip_install(f"cpdalp")
            except:
                slicer.util.infoDisplay("Issue while installing the ITK Python packages")
                progressDialog.close()
            import itk

            fpfh = itk.Fpfh.PointFeature.MF3MF3.New()
            progressDialog.close()

        try:
            import cpdalp
            import itk
            from itk import Fpfh
            from itk import Ransac
        except ModuleNotFoundError as e:
            print("Module Not found. Please restart Slicer to load packages.")

        progressDialog = slicer.util.createProgressDialog(
            windowTitle="Importing...",
            labelText="Importing ALPACA Python packages. This may take few seconds...",
            maximum=0,
        )
        slicer.app.processEvents()
        with slicer.util.WaitCursor():
            fpfh = itk.Fpfh.PointFeature.MF3MF3.New()
        progressDialog.close()

        # Import pandas if needed
        try:
          import pandas
        except:
          progressDialog = slicer.util.createProgressDialog(
              windowTitle="Installing...",
              labelText="Installing Pandas Python package...",
              maximum=0,
          )
          slicer.app.processEvents()
          try:
            slicer.util.pip_install(["pandas"])
            progressDialog.close()
          except:
            slicer.util.infoDisplay("Issue while installing Pandas Python package. Please install manually.")
            progressDialog.close()

        # Load widget from .ui file (created by Qt Designer).
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/ALPACA.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Setup checkbox stylesheets
        moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
        self.onIconPath = moduleDir + "/Resources/Icons/switch_on.png"
        self.offIconPath = moduleDir + "/Resources/Icons/switch_off.png"

        # Single Alignment connections
        self.ui.sourceModelSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelect
        )
        self.ui.sourceModelSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.sourceLandmarkSetSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelect
        )
        self.ui.sourceLandmarkSetSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.targetModelSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelect
        )
        self.ui.targetModelSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.targetLandmarkSetSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelect
        )
        self.ui.targetLandmarkSetSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.pointDensitySlider.connect(
            "valueChanged(double)", self.onChangeDensitySingle
        )
        self.ui.subsampleButton.connect("clicked(bool)", self.onSubsampleButton)
        self.ui.runALPACAButton.connect(
            "clicked(bool)", self.onRunALPACAButton
        )  # Connection for run all ALPACA steps button
        self.ui.switchSettingsButton.connect(
            "clicked(bool)", self.onSwitchSettingsButton
        )
        self.ui.showTargetPCDCheckBox.connect(
            "toggled(bool)", self.onShowTargetPCDCheckBox
        )
        self.setCheckboxStyle(self.ui.showTargetPCDCheckBox)
        self.ui.showSourcePCDCheckBox.connect(
            "toggled(bool)", self.onShowSourcePCDCheckBox
        )
        self.setCheckboxStyle(self.ui.showSourcePCDCheckBox)
        self.ui.showTargetModelCheckBox.connect(
            "toggled(bool)", self.onshowTargetModelCheckBox
        )
        self.setCheckboxStyle(self.ui.showTargetModelCheckBox)
        self.ui.showSourceModelCheckBox.connect(
            "toggled(bool)", self.onshowSourceModelCheckBox
        )
        self.setCheckboxStyle(self.ui.showSourceModelCheckBox)
        self.ui.showUnprojectLMCheckBox.connect(
            "toggled(bool)", self.onShowUnprojectLMCheckBox
        )
        self.setCheckboxStyle(self.ui.showUnprojectLMCheckBox)
        self.ui.showTPSModelCheckBox.connect(
            "toggled(bool)", self.onshowTPSModelCheckBox
        )
        self.setCheckboxStyle(self.ui.showTPSModelCheckBox)
        self.ui.showFinalLMCheckbox.connect("toggled(bool)", self.onShowFinalLMCheckbox)
        self.setCheckboxStyle(self.ui.showFinalLMCheckbox)
        self.ui.showManualLMCheckBox.connect(
            "toggled(bool)", self.onShowManualLMCheckBox
        )
        self.setCheckboxStyle(self.ui.showManualLMCheckBox)

        # Advanced Settings connections
        self.ui.projectionFactorSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.pointDensityAdvancedSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.normalSearchRadiusSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.FPFHNeighborsSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.FPFHSearchRadiusSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.maximumCPDThreshold.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.maxRANSAC.connect("valueChanged(double)", self.onChangeAdvanced)
        self.ui.poissonSubsampleCheckBox.connect("toggled(bool)", self.onChangeAdvanced)
        self.ui.ICPDistanceThresholdSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.alpha.connect("valueChanged(double)", self.onChangeAdvanced)
        self.ui.beta.connect("valueChanged(double)", self.onChangeAdvanced)
        self.ui.CPDIterationsSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.CPDToleranceSlider.connect(
            "valueChanged(double)", self.onChangeAdvanced
        )
        self.ui.accelerationCheckBox.connect("toggled(bool)", self.onChangeCPD)
        self.ui.accelerationCheckBox.connect("toggled(bool)", self.onChangeAdvanced)
        self.ui.BCPDFolder.connect("validInputChanged(bool)", self.onChangeAdvanced)
        self.ui.BCPDFolder.connect("validInputChanged(bool)", self.onChangeCPD)
        self.ui.BCPDFolder.currentPath = ALPACALogic().getBCPDPath()

        # Batch Processing connections
        self.ui.methodBatchWidget.connect(
            "currentIndexChanged(int)", self.onChangeMultiTemplate
        )
        self.ui.sourceModelMultiSelector.connect(
            "validInputChanged(bool)", self.onSelectMultiProcess
        )
        self.ui.sourceFiducialMultiSelector.connect(
            "validInputChanged(bool)", self.onSelectMultiProcess
        )
        self.ui.targetModelMultiSelector.connect(
            "validInputChanged(bool)", self.onSelectMultiProcess
        )
        self.ui.landmarkOutputSelector.connect(
            "validInputChanged(bool)", self.onSelectMultiProcess
        )
        self.ui.scalingMultiCheckBox.connect(
            "toggled(bool)", self.onSelectMultiProcess
        )
        self.ui.replicateAnalysisCheckBox.connect(
            "toggled(bool)", self.onSelectReplicateAnalysis
        )
        self.ui.meshQCCheckBox.connect(
            "toggled(bool)", self.onSelectMultiProcess
        )
        self.ui.applyLandmarkMultiButton.connect(
            "clicked(bool)", self.onApplyLandmarkMulti
        )

        # Template Selection connections
        self.ui.modelsMultiSelector.connect(
            "validInputChanged(bool)", self.onSelectKmeans
        )
        self.ui.kmeansOutputSelector.connect(
            "validInputChanged(bool)", self.onSelectKmeans
        )
        self.ui.selectRefCheckBox.connect("toggled(bool)", self.onSelectKmeans)
        self.ui.downReferenceButton.connect("clicked(bool)", self.onDownReferenceButton)
        self.ui.matchingPointsButton.connect(
            "clicked(bool)", self.onMatchingPointsButton
        )
        self.ui.multiGroupInput.connect("toggled(bool)", self.onToggleGroupInput)
        self.ui.resetTableButton.connect("clicked(bool)", self.onRestTableButton)
        self.ui.kmeansTemplatesButton.connect(
            "clicked(bool)", self.onkmeansTemplatesButton
        )

        # RMSE Table initialization
        self.col1List = []

        # Test Target cloud initialization
        self.targetCloudNodeTest = None

        # Add menu buttons
        self.addLayoutButton(
            503,
            "MALPACA multi-templates View",
            "Custom layout for MALPACA multi-templates tab",
            "LayoutSlicerMorphView.png",
            slicer.customLayoutSM,
        )
        self.addLayoutButton(
            504,
            "Table Only View",
            "Custom layout for GPA module",
            "LayoutTableOnlyView.png",
            slicer.customLayoutTableOnly,
        )
        self.addLayoutButton(
            505,
            "Plot Only View",
            "Custom layout for GPA module",
            "LayoutPlotOnlyView.png",
            slicer.customLayoutPlotOnly,
        )

        # initialize the parameter dictionary from single run parameters
        self.parameterDictionary = {
            "projectionFactor": self.ui.projectionFactorSlider.value,
            "pointDensity": self.ui.pointDensityAdvancedSlider.value,
            "normalSearchRadius": self.ui.normalSearchRadiusSlider.value,
            "FPFHNeighbors": int(self.ui.FPFHNeighborsSlider.value),
            "FPFHSearchRadius": self.ui.FPFHSearchRadiusSlider.value,
            "distanceThreshold": self.ui.maximumCPDThreshold.value,
            "maxRANSAC": int(self.ui.maxRANSAC.value),
            "ICPDistanceThreshold": float(self.ui.ICPDistanceThresholdSlider.value),
            "alpha": self.ui.alpha.value,
            "beta": self.ui.beta.value,
            "CPDIterations": int(self.ui.CPDIterationsSlider.value),
            "CPDTolerance": self.ui.CPDToleranceSlider.value,
            "Acceleration": self.ui.accelerationCheckBox.checked,
            "BCPDFolder": self.ui.BCPDFolder.currentPath,
        }

    def cleanup(self):
        pass

    def setCheckboxStyle(self, checkbox):
        checkbox.setStyleSheet(
            "QCheckBox::indicator:unchecked{image: url("
            + self.offIconPath
            + "); } \n"
            + "QCheckBox::indicator:checked{image: url("
            + self.onIconPath
            + "); } \n"
            + "QCheckBox::indicator{width: 50px;height: 25px;}\n"
        )

    def addLayoutButton(
        self, layoutID, buttonAction, toolTip, imageFileName, layoutDiscription
    ):
        layoutManager = slicer.app.layoutManager()
        layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(
            layoutID, layoutDiscription
        )

        viewToolBar = slicer.util.mainWindow().findChild("QToolBar", "ViewToolBar")
        layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
        layoutSwitchActionParent = layoutMenu
        # use `layoutMenu` to add inside layout list, use `viewToolBar` to add next the standard layout list
        layoutSwitchAction = layoutSwitchActionParent.addAction(
            buttonAction
        )  # add inside layout list

        moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
        iconPath = os.path.join(moduleDir, "Resources/Icons", imageFileName)
        layoutSwitchAction.setIcon(qt.QIcon(iconPath))
        layoutSwitchAction.setToolTip(toolTip)
        layoutSwitchAction.connect(
            "triggered()",
            lambda layoutId=layoutID: slicer.app.layoutManager().setLayout(layoutId),
        )
        layoutSwitchAction.setData(layoutID)

    def onSelect(self):
        # Enable run ALPACA button
        self.ui.scalingMultiCheckBox.checked = self.ui.scalingCheckBox.checked
        self.ui.projectionCheckBoxMulti.checked = (
            self.ui.projectionCheckBox.checked
        )
        self.ui.subsampleButton.enabled = bool(
            self.ui.sourceModelSelector.currentNode()
            and self.ui.targetModelSelector.currentNode()
            and self.ui.sourceLandmarkSetSelector.currentNode()
        )
        self.ui.runALPACAButton.enabled = bool(
            self.ui.sourceModelSelector.currentNode()
            and self.ui.targetModelSelector.currentNode()
            and self.ui.sourceLandmarkSetSelector.currentNode()
        )
        self.ui.switchSettingsButton.enabled = bool(
            self.ui.sourceModelSelector.currentNode()
            and self.ui.targetModelSelector.currentNode()
            and self.ui.sourceLandmarkSetSelector.currentNode()
        )

    def onSelectMultiProcess(self):
        self.ui.applyLandmarkMultiButton.enabled = bool(
            self.ui.sourceModelMultiSelector.currentPath
            and self.ui.sourceFiducialMultiSelector.currentPath
            and self.ui.targetModelMultiSelector.currentPath
            and self.ui.landmarkOutputSelector.currentPath
        )

    def onSelectReplicateAnalysis(self):
        self.ui.replicationNumberLabel.enabled = bool(
            self.ui.replicateAnalysisCheckBox.isChecked()
        )
        self.ui.replicationNumberSpinBox.enabled = bool(
            self.ui.replicateAnalysisCheckBox.isChecked()
        )

    def transform_numpy_points(self, points_np, transform):
        import itk

        mesh = itk.Mesh[itk.F, 3].New()
        mesh.SetPoints(
            itk.vector_container_from_array(points_np.flatten().astype("float32"))
        )
        transformed_mesh = itk.transform_mesh_filter(mesh, transform=transform)
        points_tranformed = itk.array_from_vector_container(
            transformed_mesh.GetPoints()
        )
        points_tranformed = np.reshape(points_tranformed, [-1, 3])
        return points_tranformed

    def onSubsampleButton(self):
        try:
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)
                self.targetCloudNodeTest = None
        except:
            pass
        logic = ALPACALogic()
        self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
        self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)
        # Create a copy of sourceModelNode then clone it for ALPACA steps
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(
            slicer.mrmlScene
        )
        itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig)
        clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(
            shNode, itemIDToClone
        )
        self.sourceModelNode_clone = shNode.GetItemDataNode(clonedItemID)
        self.sourceModelNode_clone.SetName("SourceModelNode_clone")
        self.sourceModelNode_clone.GetDisplayNode().SetVisibility(False)
        # slicer.mrmlScene.RemoveNode(self.sourceModelNode_copy)
        # Create target Model Node
        self.targetModelNode = self.ui.targetModelSelector.currentNode()
        self.targetModelNode.GetDisplayNode().SetVisibility(False)
        self.ui.sourceLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(
            False
        )

        (
            self.sourcePoints,
            self.targetPoints,
            self.sourceFeatures,
            self.targetFeatures,
            self.voxelSize,
            self.scalingFactor,
        ) = logic.runSubsample(
            self.sourceModelNode_clone,
            self.targetModelNode,
            self.ui.scalingCheckBox.checked,
            self.parameterDictionary,
            self.ui.poissonSubsampleCheckBox.checked,
        )
        # Convert to VTK points for visualization
        self.targetVTK = logic.convertPointsToVTK(self.targetPoints)

        slicer.mrmlScene.RemoveNode(self.sourceModelNode_clone)

        # Display target points
        blue = [0, 0, 1]
        self.targetCloudNodeTest = logic.displayPointCloud(
            self.targetVTK, self.voxelSize / 10, "Target Pointcloud_test", blue
        )
        self.targetCloudNodeTest.GetDisplayNode().SetVisibility(True)
        self.updateLayout()

        # Output information on subsampling
        self.ui.subsampleInfo.clear()
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled source pointcloud has a total of {len(self.sourcePoints)} points. \n"
        )
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled target pointcloud has a total of {len(self.targetPoints)} points. "
        )

        self.ui.runALPACAButton.enabled = True
        if bool(self.ui.targetLandmarkSetSelector.currentNode()) == True:
            self.ui.targetLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(
                False
            )
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

    # Run all button for Single Alignment ALPACA
    def onRunALPACAButton(self):
        run_counter = (
            self.runALPACACounter()
        )  # the counter for executing this function in str format
        logic = ALPACALogic()
        try:
            self.manualLMNode.GetDisplayNode().SetVisibility(False)
        except:
            pass
        try:
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(
                    self.targetCloudNodeTest
                )  # Remove targe cloud node created in the subsampling to avoid confusion
                self.targetCloudNodeTest = None
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
        # Clone the original source mesh stored in the node sourceModelNode_orig
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(
            slicer.mrmlScene
        )
        itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig)
        clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(
            shNode, itemIDToClone
        )
        self.sourceModelNode = shNode.GetItemDataNode(clonedItemID)
        self.sourceModelNode.GetDisplayNode().SetVisibility(False)
        self.sourceModelNode.SetName(
            "Source model(rigidly registered)_" + run_counter
        )  # Create a cloned source model node
        # slicer.mrmlScene.RemoveNode(self.sourceModelNode_copy)
        #
        self.targetModelNode = self.ui.targetModelSelector.currentNode()
        self.targetModelNode.GetDisplayNode().SetVisibility(False)
        self.ui.sourceLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(
            False
        )
        #
        (
            self.sourcePoints,
            self.targetPoints,
            self.sourceFeatures,
            self.targetFeatures,
            self.voxelSize,
            self.scalingFactor,
        ) = logic.runSubsample(
            self.sourceModelNode,
            self.targetModelNode,
            self.ui.scalingCheckBox.checked,
            self.parameterDictionary,
            self.ui.poissonSubsampleCheckBox.checked,
        )

        # Convert to VTK points for visualization
        self.targetVTK = logic.convertPointsToVTK(self.targetPoints)

        blue = [0, 0, 1]
        self.targetCloudNode_2 = logic.displayPointCloud(
            self.targetVTK,
            self.voxelSize / 10,
            "Target Pointcloud_" + run_counter,
            blue,
        )
        self.targetCloudNode_2.GetDisplayNode().SetVisibility(False)
        # Output information on subsampling
        self.ui.subsampleInfo.clear()
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled source pointcloud has a total of {len(self.sourcePoints)} points. \n"
        )
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled target pointcloud has a total of {len(self.targetPoints)} points. "
        )
        #
        # RANSAC & ICP transformation of source pointcloud
        self.transformMatrix, similarityFlag = logic.estimateTransform(
            self.sourcePoints,
            self.targetPoints,
            self.sourceFeatures,
            self.targetFeatures,
            self.voxelSize,
            self.ui.scalingCheckBox.checked,
            self.parameterDictionary,
        )

        vtkTransformMatrix = logic.itkToVTKTransform(
            self.transformMatrix, similarityFlag
        )
        self.ICPTransformNode = logic.convertMatrixToTransformNode(
            vtkTransformMatrix, "Rigid Transformation Matrix_" + run_counter
        )
        self.sourcePoints = logic.transform_numpy_points(
            self.sourcePoints, self.transformMatrix
        )

        # Setup source pointcloud VTK object
        self.sourceVTK = logic.convertPointsToVTK(self.sourcePoints)
        #
        red = [1, 0, 0]
        self.sourceCloudNode = logic.displayPointCloud(
            self.sourceVTK,
            self.voxelSize / 10,
            ("Source Pointcloud (rigidly registered)_" + run_counter),
            red,
        )
        self.sourceCloudNode.GetDisplayNode().SetVisibility(False)
        #
        # Transform the source model
        self.sourceModelNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceModelNode)
        #
        self.sourceModelNode.GetDisplayNode().SetColor(red)
        self.sourceModelNode.GetDisplayNode().SetVisibility(False)
        #
        # CPD registration

        print("-----------------------------------------------------------")
        print("Performing Deformable Registration ")
        self.sourceLandmarks, self.sourceLMNode = logic.loadAndScaleFiducials(
            self.ui.sourceLandmarkSetSelector.currentNode(), self.scalingFactor, scene=True
        )
        self.sourceLandmarks = logic.transform_numpy_points(
            self.sourceLandmarks, self.transformMatrix
        )
        self.sourceLMNode.SetName("Source_Landmarks_clone_" + run_counter)
        self.sourceLMNode.SetAndObserveTransformNodeID(self.ICPTransformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(self.sourceLMNode)

        # Registration
        self.registeredSourceArray = logic.runCPDRegistration(
            self.sourceLandmarks,
            self.sourcePoints,
            self.targetPoints,
            self.parameterDictionary,
        )
        self.outputPoints = logic.exportPointCloud(
            self.registeredSourceArray,
            "Initial ALPACA landmark estimate(unprojected)_" + run_counter,
        )  # outputPoints = ininital predicted LMs, non projected
        self.inputPoints = logic.exportPointCloud(
            self.sourceLandmarks, "Original Landmarks"
        )  # input points = source landmarks
        # set up output initial predicted landmarkslandmark as vtk class
        #
        outputPoints_vtk = logic.getFiducialPoints(self.outputPoints)
        inputPoints_vtk = logic.getFiducialPoints(self.inputPoints)
        #
        # Get warped source model and final predicted landmarks
        self.warpedSourceNode = logic.applyTPSTransform(
            inputPoints_vtk,
            outputPoints_vtk,
            self.sourceModelNode,
            "TPS Warped source model_" + run_counter,
        )
        self.warpedSourceNode.GetDisplayNode().SetVisibility(False)
        green = [0, 1, 0]
        self.warpedSourceNode.GetDisplayNode().SetColor(green)
        self.outputPoints.GetDisplayNode().SetPointLabelsVisibility(False)
        slicer.mrmlScene.RemoveNode(self.inputPoints)
        #
        if not self.ui.projectionCheckBox.checked:
            logic.propagateLandmarkTypes(self.sourceLMNode, self.outputPoints)
        else:
            print(":: Projecting landmarks to external surface")
            projectionFactor = self.ui.projectionFactorSlider.value / 100
            # self.projected Landmarks = "refined predicted landmarks"
            self.projectedLandmarks = logic.runPointProjection(
                self.warpedSourceNode,
                self.targetModelNode,
                self.outputPoints,
                projectionFactor,
            )
            logic.propagateLandmarkTypes(self.sourceLMNode, self.projectedLandmarks)
            self.projectedLandmarks.SetName(
                "Final ALPACA landmark estimate_" + run_counter
            )
            self.projectedLandmarks.GetDisplayNode().SetVisibility(False)
            self.outputPoints.GetDisplayNode().SetVisibility(False)
        # Other visualization
        self.sourceLMNode.GetDisplayNode().SetVisibility(False)
        self.sourceModelNode.GetDisplayNode().SetVisibility(False)
        # Enable reset
        # self.resetSceneButton.enabled = True
        # Create a folder and add all objects into the folder
        folderNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        sceneItemID = folderNode.GetSceneItemID()
        newFolder = folderNode.CreateFolderItem(
            sceneItemID, "ALPACA_output_" + run_counter
        )
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
        if self.ui.projectionCheckBox.isChecked():
            finalLMItem = folderNode.GetItemByDataNode(self.projectedLandmarks)
            folderNode.SetItemParent(finalLMItem, newFolder)
        #
        # self.ui.subsampleButton.enabled = False
        self.ui.runALPACAButton.enabled = False
        #
        # Enable visualization
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
        # Calculate rmse
        # Manual LM numpy array
        if bool(self.ui.targetLandmarkSetSelector.currentNode()) == True:
            point = [0, 0, 0]
            self.manualLMNode = self.ui.targetLandmarkSetSelector.currentNode()
            self.manualLMNode.GetDisplayNode().SetSelectedColor(green)
            self.ui.showManualLMCheckBox.enabled = True
            self.ui.showManualLMCheckBox.checked = 0
            self.manualLMNode.GetDisplayNode().SetVisibility(False)
            manualLMs = np.zeros(
                shape=(self.manualLMNode.GetNumberOfControlPoints(), 3)
            )

            for i in range(self.manualLMNode.GetNumberOfControlPoints()):
                self.manualLMNode.GetNthControlPointPosition(i, point)
                manualLMs[i, :] = point
            # Source LM numpy array
            point2 = [0, 0, 0]
            if self.ui.projectionCheckBox.isChecked():
                finalLMs = np.zeros(
                    shape=(self.projectedLandmarks.GetNumberOfControlPoints(), 3)
                )
                for i in range(self.projectedLandmarks.GetNumberOfControlPoints()):
                    self.projectedLandmarks.GetNthControlPointPosition(i, point2)
                    finalLMs[i, :] = point2
            else:
                finalLMs = np.zeros(
                    shape=(self.outputPoints.GetNumberOfControlPoints(), 3)
                )
                for i in range(self.outputPoints.GetNumberOfControlPoints()):
                    self.outputPoints.GetNthControlPointPosition(i, point2)
                    finalLMs[i, :] = point2
            #
            rmse = logic.rmse(manualLMs, finalLMs)
            print(rmse)
            self.singleRMSETable(rmse, run_counter)
        # progressDialog.close()

    def singleRMSETable(self, rmse, counter_str):
        self.rmseTableNode = slicer.mrmlScene.GetNodesByName(
            "Single Alignment RMSE table Preview"
        ).GetItemAsObject(0)
        if self.rmseTableNode is None:
            # Create rmseTableNode and add the first row of rmse
            self.rmseTableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "Single Alignment RMSE table Preview"
            )

            col1 = self.rmseTableNode.AddColumn()
            col1.SetName("ALPACA test")
            col1Item = "ALPACA_" + counter_str
            self.col1List = [col1Item]
            self.rmseTableNode.AddEmptyRow()
            self.rmseTableNode.SetCellText(0, 0, col1Item)
            #
            col2 = self.rmseTableNode.AddColumn()
            col2.SetName("RMSE")
            self.rmseTableNode.SetCellText(0, 1, format(rmse, ".6f"))
        else:
            # print(hasattr(self, 'rmseTableNode'))
            # if rmseTableNode exists
            # Add a new row of rmse
            col1Item = "ALPACA_" + counter_str
            self.col1List.append(col1Item)
            # Add col1
            self.rmseTableNode.AddEmptyRow()
            self.rmseTableNode.SetCellText(len(self.col1List) - 1, 0, col1Item)
            # Add col2
            self.rmseTableNode.SetCellText(
                len(self.col1List) - 1, 1, format(rmse, ".6f")
            )
        slicer.app.layoutManager().setLayout(35)
        slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(
            self.rmseTableNode.GetID()
        )
        slicer.app.applicationLogic().PropagateTableSelection()
        self.rmseTableNode.GetTable().Modified()

    # Count the times run ALPAACA function is executed
    def runALPACACounter(self, run_counter=[0]):
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

    def updateBatchProgress(self, message):
        """Update the batch progress text box with a new message"""
        if hasattr(self.ui, 'batchProgressInfo'):
            self.ui.batchProgressInfo.appendPlainText(message)
            # Ensure the UI updates immediately
            slicer.app.processEvents()
        # Also print to console as backup
        print(message)

    def onApplyLandmarkMulti(self):
        # Clear previous progress messages
        if hasattr(self.ui, 'batchProgressInfo'):
            self.ui.batchProgressInfo.clear()
        
        logic = ALPACALogic()
        # Pass the widget reference to logic for progress updates
        logic.setProgressCallback(self.updateBatchProgress)
        
        # Perform mesh QC ONCE before any processing if enabled
        if self.ui.meshQCCheckBox.checked:
            qc_passed = logic.performBatchMeshQC(
                self.ui.sourceModelMultiSelector.currentPath,
                self.ui.targetModelMultiSelector.currentPath
            )
            if not qc_passed:
                return  # Stop if QC failed
        
        if self.ui.projectionCheckBoxMulti.checked is False:
            projectionFactor = 0
        else:
            projectionFactor = self.ui.projectionFactorSlider.value / 100
        if not self.ui.replicateAnalysisCheckBox.checked:
            logic.runLandmarkMultiprocess(
                self.ui.sourceModelMultiSelector.currentPath,
                self.ui.sourceFiducialMultiSelector.currentPath,
                self.ui.targetModelMultiSelector.currentPath,
                self.ui.landmarkOutputSelector.currentPath,
                self.ui.scalingMultiCheckBox.checked,
                projectionFactor,
                self.ui.JSONFileFormatSelector.checked,
                self.parameterDictionary,
            )
        else:
            for i in range(0, self.ui.replicationNumberSpinBox.value):
                self.updateBatchProgress(f"Starting ALPACA replication run {i+1}/{self.ui.replicationNumberSpinBox.value}")
                dateTimeStamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
                datedOutputFolder = os.path.join(
                    self.ui.landmarkOutputSelector.currentPath, dateTimeStamp
                )
                try:
                    os.makedirs(datedOutputFolder)
                    logic.runLandmarkMultiprocess(
                        self.ui.sourceModelMultiSelector.currentPath,
                        self.ui.sourceFiducialMultiSelector.currentPath,
                        self.ui.targetModelMultiSelector.currentPath,
                        datedOutputFolder,
                        self.ui.scalingMultiCheckBox.checked,
                        projectionFactor,
                        self.ui.JSONFileFormatSelector.checked,
                        self.parameterDictionary,
                    )
                except:
                    self.updateBatchProgress(f"ERROR: Could not access output folder for replication {i+1}")
                    logging.debug(
                        "Result directory failed: Could not access output folder"
                    )

    ###Connecting function for kmeans templates selection
    def onSelectKmeans(self):
        self.ui.downReferenceButton.enabled = bool(
            self.ui.modelsMultiSelector.currentPath
            and self.ui.kmeansOutputSelector.currentPath
        )
        self.ui.referenceSelector.enabled = self.ui.selectRefCheckBox.isChecked()

    def onDownReferenceButton(self):
        logic = ALPACALogic()
        if bool(self.ui.referenceSelector.currentPath):
            referencePath = self.ui.referenceSelector.currentPath
        else:
            referenceList = [
                f
                for f in os.listdir(self.ui.modelsMultiSelector.currentPath)
                if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
            ]
            referenceFile = referenceList[0]
            referencePath = os.path.join(
                self.ui.modelsMultiSelector.currentPath, referenceFile
            )
        self.sparseTemplate, template_density, self.referenceNode = logic.downReference(
            referencePath, self.ui.spacingFactorSlider.value
        )
        self.refName = os.path.basename(referencePath)
        self.refName = os.path.splitext(self.refName)[0]
        self.ui.subsampleInfo2.clear()
        self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
        self.ui.subsampleInfo2.insertPlainText(
            f"The number of points in the downsampled reference pointcloud is {template_density}"
        )
        self.ui.matchingPointsButton.enabled = True

    def onMatchingPointsButton(self):
        # Set up folders for matching point cloud output and kmeans selected templates under self.ui.kmeansOutputSelector.currentPath
        dateTimeStamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        self.kmeansOutputFolder = os.path.join(
            self.ui.kmeansOutputSelector.currentPath, dateTimeStamp
        )
        self.pcdOutputFolder = os.path.join(
            self.kmeansOutputFolder, "matching_point_clouds"
        )
        try:
            os.makedirs(self.kmeansOutputFolder)
            os.makedirs(self.pcdOutputFolder)
        except:
            logging.debug("Result directory failed: Could not access output folder")
            print("Error creating result directory")
        # Execute functions for generating point clouds matched to the reference
        logic = ALPACALogic()
        template_density, matchedPoints, indices, files = logic.matchingPCD(
            self.ui.modelsMultiSelector.currentPath,
            self.sparseTemplate,
            self.referenceNode,
            self.pcdOutputFolder,
            self.ui.spacingFactorSlider.value,
            self.ui.JSONFileFormatSelector.checked,
            self.parameterDictionary,
        )
        # Print results
        correspondent_threshold = 0.01
        self.ui.subsampleInfo2.clear()
        self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
        self.ui.subsampleInfo2.insertPlainText(
            "The number of points in the downsampled reference pointcloud is {}. The error threshold for finding correspondent points is {}% \n".format(
                template_density, correspondent_threshold * 100
            )
        )
        if len(indices) > 0:
            self.ui.subsampleInfo2.insertPlainText(
                f"There are {len(indices)} files have points repeatedly matched with the same point(s) template, these are: \n"
            )
            for i in indices:
                self.ui.subsampleInfo2.insertPlainText(
                    f"{files[i]}: {matchedPoints[i]} unique points are sampled to match the template pointcloud \n"
                )
            indices_error = [
                i
                for i in indices
                if (template_density - matchedPoints[i])
                > template_density * correspondent_threshold
            ]
            if len(indices_error) > 0:
                self.ui.subsampleInfo2.insertPlainText(
                    "The specimens with sampling error larger than the threshold are: \n"
                )
                for i in indices_error:
                    self.ui.subsampleInfo2.insertPlainText(
                        f"{files[i]}: {matchedPoints[i]} unique points are sampled. \n"
                    )
                    self.ui.subsampleInfo2.insertPlainText(
                        "It is recommended to check the alignment of these specimens with the template or experimenting with a higher spacing factor \n"
                    )
            else:
                self.ui.subsampleInfo2.insertPlainText(
                    "All error rates smaller than the threshold \n"
                )
        else:
            self.ui.subsampleInfo2.insertPlainText(
                "{} unique points are sampled from each model to match the template pointcloud \n"
            )
        # Enable buttons for kmeans
        self.ui.noGroupInput.enabled = True
        self.ui.multiGroupInput.enabled = True
        self.ui.kmeansTemplatesButton.enabled = True
        self.ui.matchingPointsButton.enabled = False

    # If select multiple group input radiobutton, execute enterFactors function
    def onToggleGroupInput(self):
        if self.ui.multiGroupInput.isChecked():
            self.enterFactors()
            self.ui.resetTableButton.enabled = True

    # Reset input button
    def onRestTableButton(self):
        self.resetFactors()

    # Add table for entering user-defined catalogs/groups for each specimen
    def enterFactors(self):
        # If has table node, remove table node and build a new one
        if hasattr(self, "factorTableNode") == False:
            files = [
                os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)
            ]
            sortedArray = np.zeros(
                len(files),
                dtype={"names": ("filename", "procdist"), "formats": ("U50", "f8")},
            )
            sortedArray["filename"] = files
            self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "Groups Table"
            )
            col1 = self.factorTableNode.AddColumn()
            col1.SetName("ID")
            for i in range(len(files)):
                self.factorTableNode.AddEmptyRow()
                self.factorTableNode.SetCellText(i, 0, sortedArray["filename"][i])
            col2 = self.factorTableNode.AddColumn()
            col2.SetName("Group")
            # add table to new layout
            slicer.app.layoutManager().setLayout(503)
            slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(
                self.factorTableNode.GetID()
            )
            slicer.app.applicationLogic().PropagateTableSelection()
            self.factorTableNode.GetTable().Modified()

    def resetFactors(self):
        if hasattr(self, "factorTableNode"):
            slicer.mrmlScene.RemoveNode(self.factorTableNode)
        files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)]
        sortedArray = np.zeros(
            len(files),
            dtype={"names": ("filename", "procdist"), "formats": ("U50", "f8")},
        )
        sortedArray["filename"] = files
        self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLTableNode", "Groups Table"
        )
        col1 = self.factorTableNode.AddColumn()
        col1.SetName("ID")
        for i in range(len(files)):
            self.factorTableNode.AddEmptyRow()
            self.factorTableNode.SetCellText(i, 0, sortedArray["filename"][i])
        col2 = self.factorTableNode.AddColumn()
        col2.SetName("Group")
        slicer.app.layoutManager().setLayout(503)
        slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(
            self.factorTableNode.GetID()
        )
        slicer.app.applicationLogic().PropagateTableSelection()
        self.factorTableNode.GetTable().Modified()

    # Generate templates based on kmeans and catalog
    def onkmeansTemplatesButton(self):
        start = time.time()
        logic = ALPACALogic()
        PCDFiles = os.listdir(self.pcdOutputFolder)
        if len(PCDFiles) < 1:
            logging.error(f"No point cloud files read from {self.pcdOutputFolder}\n")
            return
        pcdFilePaths = [os.path.join(self.pcdOutputFolder, file) for file in PCDFiles]
        # GPA for all specimens
        self.scores, self.LM = logic.pcdGPA(pcdFilePaths)
        files = [os.path.splitext(file)[0] for file in PCDFiles]
        # Set up a seed for numpy for random results
        if self.ui.setSeedCheckBox.isChecked():
            np.random.seed(1000)
        if self.ui.noGroupInput.isChecked():
            # Generate folder for storing selected templates within the self.ui.kmeansOutputSelector.currentPath
            self.templatesOutputFolder = os.path.join(
                self.kmeansOutputFolder, "kmeans_selected_templates"
            )
            if os.path.isdir(self.templatesOutputFolder):
                pass
            else:
                try:
                    os.makedirs(self.templatesOutputFolder)
                except:
                    logging.debug(
                        "Result directory failed: Could not access templates output folder"
                    )
                    print("Error creating result directory")
            #
            templates, clusterID, templatesIndices = logic.templatesSelection(
                self.ui.modelsMultiSelector.currentPath,
                self.scores,
                pcdFilePaths,
                self.templatesOutputFolder,
                self.ui.templatesNumber.value,
                self.ui.kmeansIterations.value,
            )
            clusterID = [str(x) for x in clusterID]
            print(f"kmeans cluster ID is: {clusterID}")
            print(f"templates indices are: {templatesIndices}")
            self.ui.templatesInfo.clear()
            self.ui.templatesInfo.insertPlainText(
                f"One pooled group for all specimens. The {int(self.ui.templatesNumber.value)} selected templates are: \n"
            )
            for file in templates:
                self.ui.templatesInfo.insertPlainText(file + "\n")
            # Add cluster ID from kmeans to the table
            self.plotClusters(files, templatesIndices)
            print(f"Time: {time.time() - start}")
        # multiClusterCheckbox is checked
        else:
            if hasattr(self, "factorTableNode"):
                self.ui.templatesInfo.clear()
                factorCol = self.factorTableNode.GetTable().GetColumn(1)
                groupFactorArray = []
                for i in range(factorCol.GetNumberOfTuples()):
                    temp = factorCol.GetValue(i).rstrip()
                    temp = str(temp).upper()
                    groupFactorArray.append(temp)
                print(groupFactorArray)
                # Count the number of non-null enties in the table
                countInput = 0
                for i in range(len(groupFactorArray)):
                    if groupFactorArray[i] != "":
                        countInput += 1
                if countInput == len(
                    PCDFiles
                ):  # check if group information is input for all specimens
                    uniqueFactors = list(set(groupFactorArray))
                    groupNumber = len(uniqueFactors)
                    self.ui.templatesInfo.insertPlainText(
                        f"The sample is divided into {groupNumber} groups. The templates for each group are: \n"
                    )
                    groupClusterIDs = [None] * len(files)
                    templatesIndices = []
                    # Generate folder for storing selected templates within the self.ui.kmeansOutputSelector.currentPath
                    self.templatesOutputFolder_multi = os.path.join(
                        self.kmeansOutputFolder, "kmeans_selected_templates_multiGroups"
                    )
                    if os.path.isdir(self.templatesOutputFolder_multi):
                        pass
                    else:
                        try:
                            os.makedirs(self.templatesOutputFolder_multi)
                        except:
                            logging.debug(
                                "Result directory failed: Could not access templates output folder"
                            )
                            print("Error creating result directory")
                    for i in range(groupNumber):
                        factorName = uniqueFactors[i]
                        # Get indices for the ith cluster
                        indices = [
                            i for i, x in enumerate(groupFactorArray) if x == factorName
                        ]
                        print("indices for " + factorName + " is:")
                        print(indices)
                        key = factorName
                        paths = []
                        for i in range(len(indices)):
                            path = pcdFilePaths[indices[i]]
                            paths.append(path)
                        # PC scores of specimens belong to a specific group
                        tempScores = self.scores[indices, :]
                        #
                        templates, clusterID, tempIndices = logic.templatesSelection(
                            self.ui.modelsMultiSelector.currentPath,
                            tempScores,
                            paths,
                            self.templatesOutputFolder_multi,
                            self.ui.templatesNumber.value,
                            self.ui.kmeansIterations.value,
                        )
                        print("Kmeans-cluster IDs for " + factorName + " are:")
                        print(clusterID)
                        templatesIndices = templatesIndices + [
                            indices[i] for i in tempIndices
                        ]
                        self.ui.templatesInfo.insertPlainText(
                            "Group " + factorName + "\n"
                        )
                        for file in templates:
                            self.ui.templatesInfo.insertPlainText(file + "\n")
                        # Prepare cluster ID for each group
                        uniqueClusterID = list(set(clusterID))
                        for i in range(len(uniqueClusterID)):
                            for j in range(len(clusterID)):
                                if clusterID[j] == uniqueClusterID[i]:
                                    index = indices[j]
                                    groupClusterIDs[index] = factorName + str(i + 1)
                                    print(groupClusterIDs[index])
                    # Plot PC1 and PC 2 based on kmeans clusters
                    print(f"group cluster ID are {groupClusterIDs}")
                    print(f"Templates indices are: {templatesIndices}")
                    self.plotClustersWithFactors(
                        files, groupFactorArray, templatesIndices
                    )
                    print(f"Time: {time.time() - start}")
                else:  # if the user input a factor requiring more than 3 groups, do not use factor
                    qt.QMessageBox.critical(
                        slicer.util.mainWindow(),
                        "Error",
                        "Please enter group information for every specimen",
                    )
            else:
                qt.QMessageBox.critical(
                    slicer.util.mainWindow(),
                    "Error",
                    "Please select Multiple groups within the sample option and enter group information for each specimen",
                )

    def plotClustersWithFactors(self, files, groupFactors, templatesIndices):
        logic = ALPACALogic()
        import Support.gpa_lib as gpa_lib

        # Set up scatter plot
        pcNumber = 2
        shape = self.LM.lm.shape
        scatterDataAll = np.zeros(shape=(shape[2], pcNumber))
        for i in range(pcNumber):
            data = gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig, i, 1)
            scatterDataAll[:, i] = data[:, 0]
        factorNP = np.array(groupFactors)
        # import GPA
        logic.makeScatterPlotWithFactors(
            scatterDataAll,
            files,
            factorNP,
            "PCA Scatter Plots",
            "PC1",
            "PC2",
            pcNumber,
            templatesIndices,
        )

    def plotClusters(self, files, templatesIndices):
        logic = ALPACALogic()
        import Support.gpa_lib as gpa_lib

        # Set up scatter plot
        pcNumber = 2
        shape = self.LM.lm.shape
        scatterDataAll = np.zeros(shape=(shape[2], pcNumber))
        for i in range(pcNumber):
            data = gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig, i, 1)
            scatterDataAll[:, i] = data[:, 0]
        logic.makeScatterPlot(
            scatterDataAll,
            files,
            "PCA Scatter Plots",
            "PC1",
            "PC2",
            pcNumber,
            templatesIndices,
        )

    def updateLayout(self):
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(9)  # set layout to 3D only
        layoutManager.threeDWidget(0).threeDView().resetFocalPoint()
        layoutManager.threeDWidget(0).threeDView().resetCamera()

    def onChangeAdvanced(self):
        self.ui.pointDensitySlider.value = self.ui.pointDensityAdvancedSlider.value
        self.updateParameterDictionary()

    def onChangeDensitySingle(self):
        self.ui.pointDensityAdvancedSlider.value = self.ui.pointDensitySlider.value
        self.updateParameterDictionary()

    def onChangeMultiTemplate(self):
        if self.ui.methodBatchWidget.currentText == "Multi-Template(MALPACA)":
            self.ui.sourceModelMultiSelector.currentPath = ""
            self.ui.sourceModelMultiSelector.filters = ctk.ctkPathLineEdit.Dirs
            self.ui.sourceModelMultiSelector.toolTip = "Select a directory containing the source meshes (note: filenames must match with landmark filenames)"
            self.ui.sourceFiducialMultiSelector.currentPath = ""
            self.ui.sourceFiducialMultiSelector.filters = ctk.ctkPathLineEdit.Dirs
            self.ui.sourceFiducialMultiSelector.toolTip = "Select a directory containing the landmark files (note: filenames must match with source meshes)"
        else:
            self.ui.sourceModelMultiSelector.filters = ctk.ctkPathLineEdit().Files
            self.ui.sourceModelMultiSelector.nameFilters = ["*.ply *.obj *.vtk"]
            self.ui.sourceModelMultiSelector.toolTip = "Select the source mesh"
            self.ui.sourceFiducialMultiSelector.filters = ctk.ctkPathLineEdit().Files
            self.ui.sourceFiducialMultiSelector.nameFilters = [
                "*.json *.mrk.json *.fcsv"
            ]
            self.ui.sourceFiducialMultiSelector.toolTip = "Select the source landmarks"

    def onChangeCPD(self):
        ALPACALogic().saveBCPDPath(self.ui.BCPDFolder.currentPath)
        if self.ui.accelerationCheckBox.checked != 0:
            self.ui.BCPDFolder.enabled = True
            self.ui.subsampleButton.enabled = bool(
                self.ui.sourceModelSelector.currentNode()
                and self.ui.targetModelSelector.currentNode()
                and self.ui.sourceLandmarkSetSelector.currentNode()
                and self.ui.BCPDFolder.currentPath
            )
            self.ui.applyLandmarkMultiButton.enabled = bool(
                self.ui.sourceModelMultiSelector.currentPath
                and self.ui.sourceFiducialMultiSelector.currentPath
                and self.ui.targetModelMultiSelector.currentPath
                and self.ui.landmarkOutputSelector.currentPath
                and self.ui.BCPDFolder.currentPath
            )
        else:
            self.ui.BCPDFolder.enabled = False
            self.ui.subsampleButton.enabled = bool(
                self.ui.sourceModelSelector.currentNode
                and self.ui.targetModelSelector.currentNode
                and self.ui.sourceLandmarkSetSelector.currentNode
            )
            self.ui.applyLandmarkMultiButton.enabled = bool(
                self.ui.sourceModelMultiSelector.currentPath
                and self.ui.sourceFiducialMultiSelector.currentPath
                and self.ui.targetModelMultiSelector.currentPath
                and self.ui.landmarkOutputSelector.currentPath
            )

    def updateParameterDictionary(self):
        # update the parameter dictionary from single run parameters
        if hasattr(self, "parameterDictionary"):
            self.parameterDictionary[
                "projectionFactor"
            ] = self.ui.projectionFactorSlider.value
            self.parameterDictionary[
                "pointDensity"
            ] = self.ui.pointDensityAdvancedSlider.value
            self.parameterDictionary["normalSearchRadius"] = int(
                self.ui.normalSearchRadiusSlider.value
            )
            self.parameterDictionary["FPFHNeighbors"] = int(
                self.ui.FPFHNeighborsSlider.value
            )
            self.parameterDictionary["FPFHSearchRadius"] = int(
                self.ui.FPFHSearchRadiusSlider.value
            )
            self.parameterDictionary[
                "distanceThreshold"
            ] = self.ui.maximumCPDThreshold.value
            self.parameterDictionary["maxRANSAC"] = int(self.ui.maxRANSAC.value)
            self.parameterDictionary[
                "ICPDistanceThreshold"
            ] = self.ui.ICPDistanceThresholdSlider.value
            self.parameterDictionary["alpha"] = self.ui.alpha.value
            self.parameterDictionary["beta"] = self.ui.beta.value
            self.parameterDictionary["CPDIterations"] = int(
                self.ui.CPDIterationsSlider.value
            )
            self.parameterDictionary["CPDTolerance"] = self.ui.CPDToleranceSlider.value
            self.parameterDictionary[
                "Acceleration"
            ] = self.ui.accelerationCheckBox.checked
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
    
    def __init__(self):
        super().__init__()
        self.progressCallback = None
    
    def setProgressCallback(self, callback):
        """Set callback function for progress updates"""
        self.progressCallback = callback
    
    def updateProgress(self, message):
        """Update progress using callback or print as fallback"""
        if self.progressCallback:
            self.progressCallback(message)
        else:
            print(message)
    
    def performMeshQC(self, meshPath):
        """Perform quality control checks on a mesh file
        Returns: (is_valid, error_message)
        """
        try:
            # Load the mesh temporarily for QC
            tempNode = slicer.util.loadModel(meshPath)
            if tempNode is None:
                return False, f"Failed to load mesh: {os.path.basename(meshPath)}"
            
            polydata = tempNode.GetPolyData()
            if polydata is None:
                slicer.mrmlScene.RemoveNode(tempNode)
                return False, f"Mesh has no polydata: {os.path.basename(meshPath)}"
            
            # Check for points
            points = polydata.GetPoints()
            if points is None or points.GetNumberOfPoints() == 0:
                slicer.mrmlScene.RemoveNode(tempNode)
                return False, f"Mesh has no points: {os.path.basename(meshPath)}"
            
            # Check for NaN values in points
            import vtk.util.numpy_support as vtk_np
            points_array = vtk_np.vtk_to_numpy(points.GetData())
            
            if np.any(np.isnan(points_array)):
                slicer.mrmlScene.RemoveNode(tempNode)
                return False, f"Mesh contains NaN values in points: {os.path.basename(meshPath)}"
            
            # Check for infinite values
            if np.any(np.isinf(points_array)):
                slicer.mrmlScene.RemoveNode(tempNode)
                return False, f"Mesh contains infinite values in points: {os.path.basename(meshPath)}"
            
            # Check for cells/faces
            if polydata.GetNumberOfCells() == 0:
                slicer.mrmlScene.RemoveNode(tempNode)
                return False, f"Mesh has no faces/cells: {os.path.basename(meshPath)}"
            
            # Clean up temporary node
            slicer.mrmlScene.RemoveNode(tempNode)
            return True, ""
            
        except Exception as e:
            return False, f"QC check failed for {os.path.basename(meshPath)}: {str(e)}"
    
    def performBatchMeshQC(self, sourceModelPath, targetModelDirectory):
        """Perform quality control checks on all meshes before batch processing
        Returns: True if all meshes pass QC, False otherwise
        """
        self.updateProgress("Performing mesh quality control checks...")
        qc_failed_models = []
        
        # Check source model(s)
        if os.path.isdir(sourceModelPath):
            sourceFiles = [f for f in os.listdir(sourceModelPath) if f.endswith((".ply", ".obj", ".vtk"))]
            for sourceFile in sourceFiles:
                sourcePath = os.path.join(sourceModelPath, sourceFile)
                is_valid, error_msg = self.performMeshQC(sourcePath)
                if not is_valid:
                    qc_failed_models.append(f"SOURCE: {error_msg}")
                    self.updateProgress(f"  ⚠️  QC FAILED - SOURCE: {error_msg}")
        else:
            is_valid, error_msg = self.performMeshQC(sourceModelPath)
            if not is_valid:
                qc_failed_models.append(f"SOURCE: {error_msg}")
                self.updateProgress(f"  ⚠️  QC FAILED - SOURCE: {error_msg}")
        
        # Check target models
        targetModelFiles = [f for f in os.listdir(targetModelDirectory) if f.endswith((".ply", ".obj", ".vtk"))]
        for targetFile in targetModelFiles:
            targetPath = os.path.join(targetModelDirectory, targetFile)
            is_valid, error_msg = self.performMeshQC(targetPath)
            if not is_valid:
                qc_failed_models.append(f"TARGET: {error_msg}")
                self.updateProgress(f"  ⚠️  QC FAILED - TARGET: {error_msg}")
        
        if qc_failed_models:
            self.updateProgress(f"")
            self.updateProgress(f"🛑 BATCH PROCESSING STOPPED: {len(qc_failed_models)} mesh(es) failed QC checks")
            self.updateProgress(f"Please fix the following issues before proceeding:")
            for failed_model in qc_failed_models:
                self.updateProgress(f"  - {failed_model}")
            self.updateProgress(f"")
            self.updateProgress(f"💡 Tip: You can disable mesh QC to proceed anyway (not recommended)")
            return False
        else:
            num_source_models = len([f for f in os.listdir(sourceModelPath) if f.endswith((".ply", ".obj", ".vtk"))]) if os.path.isdir(sourceModelPath) else 1
            self.updateProgress(f"✅ All {len(targetModelFiles) + num_source_models} meshes passed QC checks")
            self.updateProgress(f"")
            return True
    
    def calculateGeometricMedian(self, landmarkList):
        """Calculate geometric median of landmark arrays using scipy optimization"""
        try:
            from scipy.optimize import minimize
        except ImportError:
            self.updateProgress("Warning: scipy not available, falling back to arithmetic median")
            return np.median(landmarkList, axis=0)
        
        # Convert list to numpy array for easier handling
        landmarks = np.array(landmarkList)  # Shape: (n_templates, n_landmarks, 3)
        n_templates, n_landmarks, n_dims = landmarks.shape
        
        # Initialize result with arithmetic median
        result = np.median(landmarks, axis=0)
        
        # Objective function: sum of Euclidean distances to all points
        def objective(x, points):
            x_reshaped = x.reshape(-1, n_dims)
            distances = np.sqrt(np.sum((points - x_reshaped[np.newaxis, :, :])**2, axis=2))
            return np.sum(distances)
        
        # Optimize for each landmark separately for better convergence
        for i in range(n_landmarks):
            landmark_coords = landmarks[:, i, :]  # Shape: (n_templates, 3)
            
            # Initial guess is the arithmetic median for this landmark
            x0 = result[i, :].flatten()
            
            # Minimize sum of distances
            try:
                res = minimize(objective, x0, args=(landmark_coords,), method='BFGS')
                if res.success:
                    result[i, :] = res.x
                else:
                    # If optimization fails, keep arithmetic median
                    self.updateProgress(f"Warning: Geometric median optimization failed for landmark {i+1}, using arithmetic median")
            except Exception as e:
                self.updateProgress(f"Warning: Error in geometric median calculation for landmark {i+1}: {str(e)}")
                # Keep arithmetic median for this landmark
                pass
        
        return result

    def runLandmarkMultiprocess(
        self,
        sourceModelPath,
        sourceLandmarkPath,
        targetModelDirectory,
        outputDirectory,
        scalingOption,
        projectionFactor,
        useJSONFormat,
        parameters,
    ):
        # extensionModel = ".ply"
        if useJSONFormat:
            extensionLM = ".mrk.json"
        else:
            extensionLM = ".fcsv"
        sourceModelList = []
        sourceLMList = []
        TargetModelList = []
        if os.path.isdir(sourceModelPath):
            specimenOutput = os.path.join(outputDirectory, "individualEstimates")
            medianOutput = os.path.join(outputDirectory, "medianEstimates")
            os.makedirs(specimenOutput, exist_ok=True)
            os.makedirs(medianOutput, exist_ok=True)
            for file in os.listdir(sourceModelPath):
                if file.endswith((".ply", ".obj", ".vtk")):
                    sourceFilePath = os.path.join(sourceModelPath, file)
                    sourceModelList.append(sourceFilePath)
        else:
            sourceModelList.append(sourceModelPath)
        if os.path.isdir(sourceLandmarkPath):
            for file in os.listdir(sourceLandmarkPath):
                if file.endswith((".json", ".fcsv")):
                    sourceFilePath = os.path.join(sourceLandmarkPath, file)
                    sourceLMList.append(sourceFilePath)
        else:
            sourceLMList.append(sourceLandmarkPath)
        
        # Get total count of target models for progress tracking
        targetModelFiles = [f for f in os.listdir(targetModelDirectory) if f.endswith((".ply", ".obj", ".vtk"))]
        totalTargetModels = len(targetModelFiles)
        currentModelIndex = 0
        
        self.updateProgress(f"Starting batch processing of {totalTargetModels} target models...")
        self.updateProgress("-----------------------------------------------------------")
        
        # Iterate through target models
        for targetFileName in targetModelFiles:
            currentModelIndex += 1
            targetFilePath = os.path.join(targetModelDirectory, targetFileName)
            TargetModelList.append(targetFilePath)
            rootName = os.path.splitext(targetFileName)[0]
            
            # Display progress message
            self.updateProgress(f"Now processing {targetFileName}, {currentModelIndex}/{totalTargetModels}")
            
            landmarkList = []
            if os.path.isdir(sourceModelPath):
                outputMedianPath = os.path.join(
                    medianOutput, f"{rootName}_median" + extensionLM
                )
                if not os.path.exists(outputMedianPath):
                    totalSourceModels = len(sourceModelList)
                    currentSourceIndex = 0
                    self.updateProgress(f"Multi-template mode: Processing {totalSourceModels} templates for {targetFileName}")
                    for file in sourceModelList:
                        currentSourceIndex += 1
                        self.updateProgress(f"    Using template {currentSourceIndex}/{totalSourceModels}: {os.path.basename(file)}")
                        sourceFilePath = os.path.join(sourceModelPath, file)
                        (baseName, ext) = os.path.splitext(os.path.basename(file))
                        sourceLandmarkFile = None
                        for lmFile in sourceLMList:
                            if baseName in lmFile:
                                sourceLandmarkFile = os.path.join(
                                    sourceLandmarkPath, lmFile
                                )
                        if sourceLandmarkFile is None:
                            print(
                                "::::Could not find the file corresponding to ",
                                file,
                            )
                            next
                        outputFilePath = os.path.join(
                            specimenOutput, f"{rootName}_{baseName}" + extensionLM
                        )
                        
                        # Display progress for multi-template mode
                        self.updateProgress(f"  Processing template {os.path.basename(file)} for target {targetFileName}, template {currentSourceIndex}/{totalSourceModels}")
                        
                        array = self.pairwiseAlignment(
                            sourceFilePath,
                            sourceLandmarkFile,
                            targetFilePath,
                            outputFilePath,
                            scalingOption,
                            projectionFactor,
                            parameters,
                        )
                        landmarkList.append(array)
                    self.updateProgress(f"Computing median landmarks for {targetFileName}...")
                    medianLandmark = np.median(landmarkList, axis=0)
                    outputMedianNode = self.exportPointCloud(
                        medianLandmark, "Median Predicted Landmarks"
                    )
                    slicer.util.saveNode(outputMedianNode, outputMedianPath)
                    slicer.mrmlScene.RemoveNode(outputMedianNode)
                    
                    # Calculate geometric median
                    self.updateProgress(f"Computing geometric median landmarks for {targetFileName}...")
                    geomedianLandmark = self.calculateGeometricMedian(landmarkList)
                    outputGeoMedianPath = os.path.join(
                        medianOutput, f"{rootName}_geomedian" + extensionLM
                    )
                    outputGeoMedianNode = self.exportPointCloud(
                        geomedianLandmark, "Geometric Median Predicted Landmarks"
                    )
                    slicer.util.saveNode(outputGeoMedianNode, outputGeoMedianPath)
                    slicer.mrmlScene.RemoveNode(outputGeoMedianNode)
                    self.updateProgress(f"  Completed processing {targetFileName}")
            elif os.path.isfile(sourceModelPath):
                self.updateProgress(f"Single template mode: Processing {targetFileName}")
                rootName = os.path.splitext(targetFileName)[0]
                outputFilePath = os.path.join(
                    outputDirectory, rootName + extensionLM
                )
                array = self.pairwiseAlignment(
                    sourceModelPath,
                    sourceLandmarkPath,
                    targetFilePath,
                    outputFilePath,
                    scalingOption,
                    projectionFactor,
                    parameters,
                )
                self.updateProgress(f"  Completed processing {targetFileName}")
            else:
                self.updateProgress(f"ERROR: Could not find the file or directory for {targetFileName}")
        extras = {
            "Source": sourceModelList,
            "SourceLandmarks": sourceLMList,
            "Target": TargetModelList,
            "Output": outputDirectory,
            "Scaling ?": bool(scalingOption),
        }
        extras.update(parameters)
        parameterFile = os.path.join(outputDirectory, "advancedParameters.txt")
        json.dump(extras, open(parameterFile, "w"), indent=2)

    def pairwiseAlignment(
        self,
        sourceFilePath,
        sourceLandmarkFile,
        targetFilePath,
        outputFilePath,
        scalingOption,
        projectionFactor,
        parameters,
        usePoisson=False,
    ):
        # Extract filename for progress display
        targetFileName = os.path.basename(targetFilePath)
        
        self.updateProgress(f"  Loading models for {targetFileName}...")
        targetModelNode = slicer.util.loadModel(targetFilePath)
        targetModelNode.GetDisplayNode().SetVisibility(False)
        sourceModelNode = slicer.util.loadModel(sourceFilePath)
        sourceModelNode.GetDisplayNode().SetVisibility(False)
        
        self.updateProgress(f"  Running subsampling for {targetFileName}...")
        (
            sourcePoints,
            targetPoints,
            sourceFeatures,
            targetFeatures,
            voxelSize,
            scalingFactor,
        ) = self.runSubsample(
            sourceModelNode, targetModelNode, scalingOption, parameters, usePoisson
        )
        
        self.updateProgress(f"  Estimating rigid transformation for {targetFileName}...")
        SimilarityTransform, similarityFlag = self.estimateTransform(
            sourcePoints,
            targetPoints,
            sourceFeatures,
            targetFeatures,
            voxelSize,
            scalingOption,
            parameters,
        )
        
        # Rigid
        sourceLandmarks, sourceLMNode = self.loadAndScaleFiducials(
            sourceLandmarkFile, scalingFactor
        )
        sourceLandmarks = self.transform_numpy_points(
            sourceLandmarks, SimilarityTransform
        )
        sourcePoints = self.transform_numpy_points(sourcePoints, SimilarityTransform)
        vtkSimilarityTransform = self.itkToVTKTransform(
            SimilarityTransform, similarityFlag
        )

        # Deformable
        self.updateProgress(f"  Running CPD registration for {targetFileName}...")
        registeredSourceLM = self.runCPDRegistration(
            sourceLandmarks, sourcePoints, targetPoints, parameters
        )
        outputPoints = self.exportPointCloud(
            registeredSourceLM, "Initial Predicted Landmarks"
        )
        if projectionFactor == 0:
            self.updateProgress(f"  Saving landmarks for {targetFileName} (no projection)")
            self.propagateLandmarkTypes(sourceLMNode, outputPoints)
            slicer.util.saveNode(outputPoints, outputFilePath)
            slicer.mrmlScene.RemoveNode(outputPoints)
            slicer.mrmlScene.RemoveNode(sourceModelNode)
            slicer.mrmlScene.RemoveNode(targetModelNode)
            slicer.mrmlScene.RemoveNode(sourceLMNode)
            return registeredSourceLM
        else:
            self.updateProgress(f"  Projecting landmarks to surface for {targetFileName}...")
            inputPoints = self.exportPointCloud(sourceLandmarks, "Original Landmarks")
            inputPoints_vtk = self.getFiducialPoints(inputPoints)
            outputPoints_vtk = self.getFiducialPoints(outputPoints)

            ICPTransformNode = self.convertMatrixToTransformNode(
                vtkSimilarityTransform, "Rigid Transformation Matrix"
            )
            sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())

            deformedModelNode = self.applyTPSTransform(
                inputPoints_vtk, outputPoints_vtk, sourceModelNode, "Warped Source Mesh"
            )
            deformedModelNode.GetDisplayNode().SetVisibility(False)

            maxProjection = (
                targetModelNode.GetPolyData().GetLength()
            ) * projectionFactor
            projectedPoints = self.projectPointsPolydata(
                deformedModelNode.GetPolyData(),
                targetModelNode.GetPolyData(),
                outputPoints_vtk,
                maxProjection,
            )
            projectedLMNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLMarkupsFiducialNode", "Refined Predicted Landmarks"
            )
            for i in range(projectedPoints.GetNumberOfPoints()):
                point = projectedPoints.GetPoint(i)
                projectedLMNode.AddControlPoint(point)
            self.propagateLandmarkTypes(sourceLMNode, projectedLMNode)
            projectedLMNode.SetLocked(True)
            projectedLMNode.SetFixedNumberOfControlPoints(True)
            
            self.updateProgress(f"  Saving projected landmarks for {targetFileName}")
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
        fiducialNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLMarkupsFiducialNode", nodeName
        )
        for point in pointCloud:
            fiducialNode.AddControlPoint(point)
        fiducialNode.SetLocked(True)
        fiducialNode.SetFixedNumberOfControlPoints(True)
        return fiducialNode

    def applyTPSTransform(self, sourcePoints, targetPoints, modelNode, nodeName):
        transform = vtk.vtkThinPlateSplineTransform()
        transform.SetSourceLandmarks(sourcePoints)
        transform.SetTargetLandmarks(targetPoints)
        transform.SetBasisToR()  # for 3D transform

        transformFilter = vtk.vtkTransformPolyDataFilter()
        transformFilter.SetInputData(modelNode.GetPolyData())
        transformFilter.SetTransform(transform)
        transformFilter.Update()

        warpedPolyData = transformFilter.GetOutput()
        warpedModelNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLModelNode", nodeName
        )
        warpedModelNode.CreateDefaultDisplayNodes()
        warpedModelNode.SetAndObservePolyData(warpedPolyData)
        # self.RAS2LPSTransform(warpedModelNode)
        return warpedModelNode

    def runCPDRegistration(self, sourceLM, sourceSLM, targetSLM, parameters):
        sourceArrayCombined = np.append(sourceSLM, sourceLM, axis=0)
        targetArray = np.asarray(targetSLM)

        cloudSize = np.max(targetArray, 0) - np.min(targetArray, 0)

        targetArray = targetArray * 25 / cloudSize
        sourceArrayCombined = sourceArrayCombined * 25 / cloudSize

        if parameters["Acceleration"] == 0:
            registrationOutput = self.cpd_registration(
                targetArray,
                sourceArrayCombined,
                parameters["CPDIterations"],
                parameters["CPDTolerance"],
                parameters["alpha"],
                parameters["beta"],
            )
            deformed_array, _ = registrationOutput.register()
        else:
            targetPath = os.path.join(slicer.app.cachePath, "target.txt")
            sourcePath = os.path.join(slicer.app.cachePath, "source.txt")
            np.savetxt(targetPath, targetArray, delimiter=",")
            np.savetxt(sourcePath, sourceArrayCombined, delimiter=",")
            path = os.path.join(parameters["BCPDFolder"], "bcpd")
            cmd = f'"{path}" -x "{targetPath}" -y "{sourcePath}" -l{parameters["alpha"]} -b{parameters["beta"]} -g0.1 -K140 -J500 -c1e-6 -p -d7 -e0.3 -f0.3 -ux -N1'
            cp = subprocess.run(
                cmd, shell=True, check=True, text=True, capture_output=True
            )
            deformed_array = np.loadtxt("output_y.txt")
            for fl in glob.glob("output*.txt"):
                os.remove(fl)
            os.remove(targetPath)
            os.remove(sourcePath)
        # Capture output landmarks from source pointcloud
        fiducial_prediction = deformed_array[-len(sourceLM) :]

        fiducialCloud = fiducial_prediction
        fiducialCloud = fiducialCloud * cloudSize / 25
        return fiducialCloud

    def RAS2LPSTransform(self, modelNode):
        matrix = vtk.vtkMatrix4x4()
        matrix.Identity()
        matrix.SetElement(0, 0, -1)
        matrix.SetElement(1, 1, -1)
        transform = vtk.vtkTransform()
        transform.SetMatrix(matrix)
        transformNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLTransformNode", "RAS2LPS"
        )
        transformNode.SetAndObserveTransformToParent(transform)
        modelNode.SetAndObserveTransformNodeID(transformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(modelNode)
        slicer.mrmlScene.RemoveNode(transformNode)

    def convertMatrixToVTK(self, matrix):
        matrix_vtk = vtk.vtkMatrix4x4()
        for i in range(4):
            for j in range(4):
                matrix_vtk.SetElement(i, j, matrix[i][j])
        return matrix_vtk

    def itkToVTKTransform(self, itkTransform, similarityFlag=False):
        matrix = itkTransform.GetMatrix()
        offset = itkTransform.GetOffset()

        matrix_vtk = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                matrix_vtk.SetElement(i, j, matrix(i, j))
        for i in range(3):
            matrix_vtk.SetElement(i, 3, offset[i])

        transform = vtk.vtkTransform()
        transform.SetMatrix(matrix_vtk)
        return transform

    def convertMatrixToTransformNode(self, vtkTransform, transformName):
        transformNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLTransformNode", transformName
        )
        transformNode.SetAndObserveTransformToParent(vtkTransform)
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
        # set up glyph for visualizing point cloud
        sphereSource = vtk.vtkSphereSource()
        sphereSource.SetRadius(pointRadius)
        glyph = vtk.vtkGlyph3D()
        glyph.SetSourceConnection(sphereSource.GetOutputPort())
        glyph.SetInputData(polydata)
        glyph.ScalingOff()
        glyph.Update()

        # display
        # modelNode=slicer.mrmlScene.GetFirstNodeByName(nodeName)
        # if modelNode is None:  # if there is no node with this name, create with display node
        modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", nodeName)
        modelNode.CreateDefaultDisplayNodes()

        modelNode.SetAndObservePolyData(glyph.GetOutput())
        modelNode.GetDisplayNode().SetColor(nodeColor)
        return modelNode

    def displayMesh(self, polydata, nodeName, nodeColor):
        modelNode = slicer.mrmlScene.GetFirstNodeByName(nodeName)
        if (
            modelNode is None
        ):  # if there is no node with this name, create with display node
            modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", nodeName)
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
        """
        Using the FPFH features find noisy corresspondes.
        These corresspondes will be used inside the RANSAC.
        """
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

    # Returns the fitness of alignment of two pointSets
    def get_fitness(
        self, movingMeshPoints, fixedMeshPoints, distanceThrehold, transform=None
    ):
        import itk

        movingPointSet = itk.Mesh.F3.New()
        movingPointSet.SetPoints(
            itk.vector_container_from_array(
                movingMeshPoints.flatten().astype("float32")
            )
        )

        fixedPointSet = itk.Mesh.F3.New()
        fixedPointSet.SetPoints(
            itk.vector_container_from_array(fixedMeshPoints.flatten().astype("float32"))
        )

        if transform is not None:
            movingPointSet = itk.transform_mesh_filter(
                movingPointSet, transform=transform
            )

        PointType = itk.Point[itk.F, 3]
        PointsContainerType = itk.VectorContainer[itk.IT, PointType]
        pointsLocator = itk.PointsLocator[PointsContainerType].New()
        pointsLocator.SetPoints(fixedPointSet.GetPoints())
        pointsLocator.Initialize()

        fitness = 0
        inlier_rmse = 0
        for i in range(movingPointSet.GetNumberOfPoints()):
            closestPoint = pointsLocator.FindClosestPoint(movingPointSet.GetPoint(i))
            distance = (
                fixedPointSet.GetPoint(closestPoint) - movingPointSet.GetPoint(i)
            ).GetNorm()
            if distance < distanceThrehold:
                fitness = fitness + 1
                inlier_rmse = inlier_rmse + distance

        return fitness / movingPointSet.GetNumberOfPoints(), inlier_rmse / fitness

    # RANSAC using package
    def ransac_using_package(
        self,
        movingMeshPoints,
        fixedMeshPoints,
        movingMeshFeaturePoints,
        fixedMeshFeaturePoints,
        number_of_iterations,
        number_of_ransac_points,
        inlier_value,
        scalingOption,
        check_edge_length,
        correspondence_distance,
    ):
        import itk

        def GenerateData(data, agreeData):
            """
            In current implementation the agreedata contains two corresponding
            points from moving and fixed mesh. However, after the subsampling step the
            number of points need not be equal in those meshes. So we randomly sample
            the points from larger mesh.
            """
            data.reserve(movingMeshFeaturePoints.shape[0])
            for i in range(movingMeshFeaturePoints.shape[0]):
                point1 = movingMeshFeaturePoints[i]
                point2 = fixedMeshFeaturePoints[i]
                input_data = [
                    point1[0],
                    point1[1],
                    point1[2],
                    point2[0],
                    point2[1],
                    point2[2],
                ]
                input_data = [float(x) for x in input_data]
                data.push_back(input_data)

            count_min = int(
                np.min([movingMeshPoints.shape[0], fixedMeshPoints.shape[0]])
            )

            mesh1_points = copy.deepcopy(movingMeshPoints)
            mesh2_points = copy.deepcopy(fixedMeshPoints)

            np.random.seed(0)
            np.random.shuffle(mesh1_points)
            np.random.seed(0)
            np.random.shuffle(mesh2_points)

            agreeData.reserve(count_min)
            for i in range(count_min):
                point1 = mesh1_points[i]
                point2 = mesh2_points[i]
                input_data = [
                    point1[0],
                    point1[1],
                    point1[2],
                    point2[0],
                    point2[1],
                    point2[2],
                ]
                input_data = [float(x) for x in input_data]
                agreeData.push_back(input_data)
            return

        data = itk.vector[itk.Point[itk.D, 6]]()
        agreeData = itk.vector[itk.Point[itk.D, 6]]()
        GenerateData(data, agreeData)

        transformParameters = itk.vector.D()
        bestTransformParameters = itk.vector.D()

        itk.MultiThreaderBase.SetGlobalDefaultThreader(
            itk.MultiThreaderBase.ThreaderTypeFromString("POOL")
        )
        maximumDistance = inlier_value
        if not scalingOption:
            print("Rigid Reg, no scaling")
            TransformType = itk.VersorRigid3DTransform[itk.D]
            RegistrationEstimatorType = itk.Ransac.LandmarkRegistrationEstimator[
                6, TransformType
            ]
        else:
            print("NonRigid Reg, with scaling")
            TransformType = itk.Similarity3DTransform[itk.D]
            RegistrationEstimatorType = itk.Ransac.LandmarkRegistrationEstimator[
                6, TransformType
            ]
        registrationEstimator = RegistrationEstimatorType.New()
        registrationEstimator.SetMinimalForEstimate(number_of_ransac_points)
        registrationEstimator.SetAgreeData(agreeData)
        registrationEstimator.SetDelta(maximumDistance)
        registrationEstimator.LeastSquaresEstimate(data, transformParameters)

        maxThreadCount = int(
            itk.MultiThreaderBase.New().GetMaximumNumberOfThreads() / 2
        )

        desiredProbabilityForNoOutliers = 0.99
        RANSACType = itk.RANSAC[itk.Point[itk.D, 6], itk.D, TransformType]
        ransacEstimator = RANSACType.New()
        ransacEstimator.SetData(data)
        ransacEstimator.SetAgreeData(agreeData)
        ransacEstimator.SetCheckCorresspondenceDistance(check_edge_length)
        if correspondence_distance > 0:
            ransacEstimator.SetCheckCorrespondenceEdgeLength(correspondence_distance)
        ransacEstimator.SetMaxIteration(int(number_of_iterations / maxThreadCount))
        ransacEstimator.SetNumberOfThreads(maxThreadCount)
        ransacEstimator.SetParametersEstimator(registrationEstimator)

        percentageOfDataUsed = ransacEstimator.Compute(
            transformParameters, desiredProbabilityForNoOutliers
        )

        transform = TransformType.New()
        p = transform.GetParameters()
        f = transform.GetFixedParameters()
        for i in range(p.GetSize()):
            p.SetElement(i, transformParameters[i])
        counter = 0
        totalParameters = p.GetSize() + f.GetSize()
        for i in range(p.GetSize(), totalParameters):
            f.SetElement(counter, transformParameters[i])
            counter = counter + 1
        transform.SetParameters(p)
        transform.SetFixedParameters(f)
        return (
            itk.dict_from_transform(transform),
            percentageOfDataUsed[0],
            percentageOfDataUsed[1],
        )

    def get_euclidean_distance(
        self, input_fixedPoints, input_movingPoints, distance_threshold
    ):
        import itk

        mesh_fixed = itk.Mesh[itk.D, 3].New()
        mesh_moving = itk.Mesh[itk.D, 3].New()

        mesh_fixed.SetPoints(
            itk.vector_container_from_array(input_fixedPoints.flatten())
        )
        mesh_moving.SetPoints(
            itk.vector_container_from_array(input_movingPoints.flatten())
        )

        MetricType = itk.EuclideanDistancePointSetToPointSetMetricv4.PSD3
        metric = MetricType.New()
        metric.SetMovingPointSet(mesh_moving)
        metric.SetDistanceThreshold(distance_threshold)
        metric.SetFixedPointSet(mesh_fixed)
        metric.Initialize()

        return metric.GetValue()

    def get_correspondence_and_fitness(
        self, fixedPoints, movingPoints, distanceThreshold, transform=None
    ):
        import itk

        movingPointSet = itk.Mesh.F3.New()
        movingPointSet.SetPoints(
            itk.vector_container_from_array(movingPoints.flatten().astype("float32"))
        )

        fixedPointSet = itk.Mesh.F3.New()
        fixedPointSet.SetPoints(
            itk.vector_container_from_array(fixedPoints.flatten().astype("float32"))
        )

        if transform is not None:
            movingPointSet = itk.transform_mesh_filter(
                movingPointSet, transform=transform
            )

        PointType = itk.Point[itk.F, 3]
        PointsContainerType = itk.VectorContainer[itk.IT, PointType]
        pointsLocator = itk.PointsLocator[PointsContainerType].New()
        pointsLocator.SetPoints(fixedPointSet.GetPoints())
        pointsLocator.Initialize()

        fixed_array = itk.VectorContainer[itk.IT, itk.Point[itk.D, 3]].New()
        moving_array = itk.VectorContainer[itk.IT, itk.Point[itk.D, 3]].New()
        index_array = []

        fitness = 0
        inlier_rmse = 0
        count = 0
        for i in range(movingPointSet.GetNumberOfPoints()):
            closestPoint = pointsLocator.FindClosestPoint(movingPointSet.GetPoint(i))
            distance = (
                fixedPointSet.GetPoint(closestPoint) - movingPointSet.GetPoint(i)
            ).GetNorm()
            if distance < distanceThreshold:
                fitness = fitness + 1
                inlier_rmse = inlier_rmse + distance
                fixed_point = fixedPointSet.GetPoint(closestPoint)
                moving_point = movingPointSet.GetPoint(i)
                index_array.append([closestPoint, i])
                fixed_array.InsertElement(count, fixed_point)
                moving_array.InsertElement(count, moving_point)
                count = count + 1

        return (
            fixed_array,
            moving_array,
            fitness,
            inlier_rmse / fitness,
            np.array(index_array),
        )

    def final_iteration_icp(
        self, fixedPoints, movingPoints, distanceThreshold, normalSearchRadius
    ):
        import itk
        fixedPointsNormal = self.extract_pca_normal_scikit(
            fixedPoints, normalSearchRadius
        )
        movingPointsNormal = self.extract_pca_normal_scikit(
            movingPoints, normalSearchRadius
        )

        _, (T, R, t) = self.point_to_plane_icp(
            movingPoints,
            fixedPoints,
            movingPointsNormal,
            fixedPointsNormal,
            distanceThreshold,
        )

        transform = itk.Rigid3DTransform.D.New()
        transform.SetMatrix(itk.matrix_from_array(R), 0.000001)
        transform.SetTranslation([t[0], t[1], t[2]])
        return movingPoints, transform

    def euler_matrix(self, ai, aj, ak):
        """Return homogeneous rotation matrix from Euler angles and axis sequence.
        ai, aj, ak : Euler's roll, pitch and yaw angles
        axes : One of 24 axis sequences as string or encoded tuple
        >>> R = euler_matrix(1, 2, 3, 'syxz')
        >>> numpy.allclose(numpy.sum(R[0]), -1.34786452)
        True
        >>> R = euler_matrix(1, 2, 3, (0, 1, 0, 1))
        """

        firstaxis, parity, repetition, frame = (0, 0, 0, 0)
        _NEXT_AXIS = [1, 2, 0, 1]

        i = firstaxis
        j = _NEXT_AXIS[i + parity]
        k = _NEXT_AXIS[i - parity + 1]

        if frame:
            ai, ak = ak, ai
        if parity:
            ai, aj, ak = -ai, -aj, -ak

        si, sj, sk = math.sin(ai), math.sin(aj), math.sin(ak)
        ci, cj, ck = math.cos(ai), math.cos(aj), math.cos(ak)
        cc, cs = ci * ck, ci * sk
        sc, ss = si * ck, si * sk

        M = np.identity(4)
        if repetition:
            M[i, i] = cj
            M[i, j] = sj * si
            M[i, k] = sj * ci
            M[j, i] = sj * sk
            M[j, j] = -cj * ss + cc
            M[j, k] = -cj * cs - sc
            M[k, i] = -sj * ck
            M[k, j] = cj * sc + cs
            M[k, k] = cj * cc - ss
        else:
            M[i, i] = cj * ck
            M[i, j] = sj * sc - cs
            M[i, k] = sj * cc + ss
            M[j, i] = cj * sk
            M[j, j] = sj * ss + cc
            M[j, k] = sj * cs - sc
            M[k, i] = -sj
            M[k, j] = cj * si
            M[k, k] = cj * ci
        return M

    def best_fit_transform_point2plane(self, A, B, normals):
        """
            reference: https://www.comp.nus.edu.sg/~lowkl/publications/lowk_point-to-plane_icp_techrep.pdf
            Input:
            A: Nx3 numpy array of corresponding points
            B: Nx3 numpy array of corresponding points
            normals: Nx3 numpy array of B's normal vectors
            Returns:
            T: (m+1)x(m+1) homogeneous transformation matrix that maps A on to B
            R: mxm rotation matrix
            t: mx1 translation vector
        """
        assert A.shape == B.shape
        assert A.shape == normals.shape

        H = []
        b = []
        for i in range(A.shape[0]):
            dx = B[i, 0]
            dy = B[i, 1]
            dz = B[i, 2]
            nx = normals[i, 0]
            ny = normals[i, 1]
            nz = normals[i, 2]
            sx = A[i, 0]
            sy = A[i, 1]
            sz = A[i, 2]

            _a1 = (nz * sy) - (ny * sz)
            _a2 = (nx * sz) - (nz * sx)
            _a3 = (ny * sx) - (nx * sy)

            _a = np.array([_a1, _a2, _a3, nx, ny, nz])
            _b = (nx * dx) + (ny * dy) + (nz * dz) - (nx * sx) - (ny * sy) - (nz * sz)

            H.append(_a)
            b.append(_b)

        H = np.array(H)
        b = np.array(b)

        tr = np.dot(np.linalg.pinv(H), b)
        T = self.euler_matrix(tr[0], tr[1], tr[2])
        T[0, 3] = tr[3]
        T[1, 3] = tr[4]
        T[2, 3] = tr[5]

        R = T[:3, :3]
        t = T[:3, 3]

        return T, R, t

    def best_fit_transform_point2point(self, A, B):
        """
        Calculates the least-squares best-fit transform that maps corresponding points A to B in m spatial dimensions
        Input:
        A: Nxm numpy array of corresponding points
        B: Nxm numpy array of corresponding points
        Returns:
        T: (m+1)x(m+1) homogeneous transformation matrix that maps A on to B
        R: mxm rotation matrix
        t: mx1 translation vector
        """

        assert A.shape == B.shape

        # get number of dimensions
        m = A.shape[1]

        # translate points to their centroids
        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)
        AA = A - centroid_A
        BB = B - centroid_B

        # rotation matrix
        H = np.dot(AA.T, BB)
        U, S, Vt = np.linalg.svd(H)
        R = np.dot(Vt.T, U.T)

        # special reflection case
        if np.linalg.det(R) < 0:
            Vt[m - 1, :] *= -1
        R = np.dot(Vt.T, U.T)

        # translation
        t = centroid_B.T - np.dot(R, centroid_A.T)

        # homogeneous transformation
        T = np.identity(m + 1)
        T[:m, :m] = R
        T[:m, m] = t

        return T, R, t

    def nearest_neighbor(self, src, dst):
        """
        Find the nearest (Euclidean) neighbor in dst for each point in src
        Input:
            src: Nxm array of points
            dst: Nxm array of points
        Output:
            distances: Euclidean distances of the nearest neighbor
            indices: dst indices of the nearest neighbor
        """
            # assert src.shape == dst.shape
        from sklearn.neighbors import NearestNeighbors
        neigh = NearestNeighbors(n_neighbors=1, algorithm="kd_tree")
        neigh.fit(dst)
        distances, indices = neigh.kneighbors(src, return_distance=True)
        return distances.ravel(), indices.ravel()

    def point_to_plane_icp(
        self,
        src_pts,
        dst_pts,
        src_pt_normals,
        dst_pt_normals,
        dist_threshold=np.inf,
        max_iterations=30,
        tolerance=0.000001,
    ):
        """
            The Iterative Closest Point method: finds best-fit transform that
                maps points A on to points B
            Input:
                A: Nxm numpy array of source mD points
                B: Nxm numpy array of destination mD point
                max_iterations: exit algorithm after max_iterations
                tolerance: convergence criteria
            Output:
                T: final homogeneous transformation that maps A on to B
                MeanError: list, report each iteration's distance mean error
        """
        A = src_pts
        A_normals = src_pt_normals
        B = dst_pts
        B_normals = dst_pt_normals

        # get number of dimensions
        m = A.shape[1]

        # make points homogeneous, copy them to maintain the originals
        src = np.ones((m + 1, A.shape[0]))
        dst = np.ones((m + 1, B.shape[0]))
        src[:m, :] = np.copy(A.T)
        dst[:m, :] = np.copy(B.T)

        prev_error = 0
        MeanError = []

        finalT = np.identity(4)

        for i in range(max_iterations):
            # find the nearest neighbors between the current source and destination points
            distances, indices = self.nearest_neighbor(src[:m, :].T, dst[:m, :].T)

            # match each point of source-set to closest point of destination-set,
            matched_src_pts = src[:m, :].T.copy()
            matched_dst_pts = dst[:m, indices].T

            # compute angle between 2 matched vertexs' normals
            matched_src_pt_normals = A_normals.copy()
            matched_dst_pt_normals = B_normals[indices, :]
            angles = np.zeros(matched_src_pt_normals.shape[0])
            for k in range(matched_src_pt_normals.shape[0]):
                v1 = matched_src_pt_normals[k, :]
                v2 = matched_dst_pt_normals[k, :]
                cos_angle = v1.dot(v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                angles[k] = np.arccos(cos_angle) / np.pi * 180

            # and reject the bad corresponding
            # dist_threshold = np.inf
            dist_bool_flag = distances < dist_threshold
            angle_threshold = 20
            angle_bool_flag = angles < angle_threshold
            reject_part_flag = dist_bool_flag  # * angle_bool_flag

            # get matched vertices and dst_vertexes' normals
            matched_src_pts = matched_src_pts[reject_part_flag, :]
            matched_dst_pts = matched_dst_pts[reject_part_flag, :]
            matched_dst_pt_normals = matched_dst_pt_normals[reject_part_flag, :]

            # compute the transformation between the current source and nearest destination points
            T, _, _ = self.best_fit_transform_point2plane(
                matched_src_pts, matched_dst_pts, matched_dst_pt_normals
            )

            finalT = np.dot(T, finalT)

            # update the current source
            src = np.dot(T, src)

            # print iteration
            # print('\ricp iteration: %d/%d ...' % (i+1, max_iterations), end='', flush=True)

            # check error
            mean_error = np.mean(distances[reject_part_flag])
            MeanError.append(mean_error)
            if tolerance is not None:
                if np.abs(prev_error - mean_error) < tolerance:
                    break
            prev_error = mean_error
        print("Refinement took ", i, " iterations")
        # calculate final transformation
        # T, R, t = self.best_fit_transform_point2point(A, src[:m, :].T)
        # return MeanError, (T, R, t)
        return MeanError, (finalT, finalT[:3, :3], finalT[:, 3])

    def get_numpy_points_from_vtk(self, vtk_polydata):
        """
        Returns the points as numpy from a vtk_polydata
        """
        import vtk
        from vtk.util import numpy_support

        points = vtk_polydata.GetPoints()
        pointdata = points.GetData()
        points_as_numpy = numpy_support.vtk_to_numpy(pointdata)
        return points_as_numpy

    def transform_points_in_vtk(self, vtk_polydata, itk_transform):
        points_as_numpy = self.get_numpy_points_from_vtk(vtk_polydata)
        transformed_points = self.transform_numpy_points(points_as_numpy, itk_transform)
        self.set_numpy_points_in_vtk(vtk_polydata, transformed_points)
        return vtk_polydata

    def transform_numpy_points(self, points_np, transform):
        import itk

        mesh = itk.Mesh[itk.F, 3].New()
        mesh.SetPoints(
            itk.vector_container_from_array(points_np.flatten().astype("float32"))
        )
        transformed_mesh = itk.transform_mesh_filter(mesh, transform=transform)
        points_tranformed = itk.array_from_vector_container(
            transformed_mesh.GetPoints()
        )
        points_tranformed = np.reshape(points_tranformed, [-1, 3])
        return points_tranformed

    def estimateTransform(
        self,
        sourcePoints,
        targetPoints,
        sourceFeatures,
        targetFeatures,
        voxelSize,
        scalingOption,
        parameters,
    ):
        import itk

        similarityFlag = False
        # Establish correspondences by nearest neighbour search in feature space
        corrs_A, corrs_B = self.find_correspondences(
            targetFeatures, sourceFeatures, mutual_filter=True
        )

        targetPoints = targetPoints.T
        sourcePoints = sourcePoints.T

        fixed_corr = targetPoints[:, corrs_A]  # np array of size 3 by num_corrs
        moving_corr = sourcePoints[:, corrs_B]  # np array of size 3 by num_corrs

        num_corrs = fixed_corr.shape[1]
        print(f"FPFH generates {num_corrs} putative correspondences.")

        targetPoints = targetPoints.T
        sourcePoints = sourcePoints.T

        # Check corner case when both meshes are same
        if np.allclose(fixed_corr, moving_corr):
            print("Same meshes therefore returning Identity Transform")
            transform = itk.VersorRigid3DTransform[itk.D].New()
            transform.SetIdentity()
            return [transform, transform]

        import time

        bransac = time.time()

        maxAttempts = 1
        attempt = 0
        best_fitness = -1
        best_rmse = np.inf
        while attempt < maxAttempts:
            # Perform Initial alignment using Ransac parallel iterations with no scaling
            transform_matrix, fitness, rmse = self.ransac_using_package(
                movingMeshPoints=sourcePoints,
                fixedMeshPoints=targetPoints,
                movingMeshFeaturePoints=moving_corr.T,
                fixedMeshFeaturePoints=fixed_corr.T,
                number_of_iterations=parameters["maxRANSAC"],
                number_of_ransac_points=3,
                inlier_value=float(parameters["distanceThreshold"]) * voxelSize,
                scalingOption=False,
                check_edge_length=True,
                correspondence_distance=0.9,
            )

            transform = itk.transform_from_dict(transform_matrix)
            fitness_forward, rmse_forward = self.get_fitness(
                sourcePoints,
                targetPoints,
                float(parameters["distanceThreshold"]) * voxelSize,
                transform,
            )

            mean_fitness = fitness_forward
            mean_rmse = rmse_forward
            print(
                "Non-Scaling Attempt = ",
                attempt,
                " Fitness = ",
                mean_fitness,
                " RMSE is ",
                mean_rmse,
            )

            if mean_fitness > 0.99:
                # Only compare RMSE if mean_fitness is greater than 0.99
                if mean_rmse < best_rmse:
                    best_fitness = mean_fitness
                    best_rmse = mean_rmse
                    best_transform = transform_matrix
            else:
                if mean_fitness > best_fitness:
                    best_fitness = mean_fitness
                    best_rmse = mean_rmse
                    best_transform = transform_matrix

            # Rigid Transform is un-fit for this use-case so perform scaling based RANSAC
            # if mean_fitness < 0.9:
            #  break
            attempt = attempt + 1

        print("Best Fitness without Scaling ", best_fitness, " RMSE is ", best_rmse)

        if scalingOption:
            maxAttempts = 10
            attempt = 0

            correspondence_distance = 0.9
            ransac_points = 3
            ransac_iterations = int(parameters["maxRANSAC"])

            while mean_fitness < 0.99 and attempt < maxAttempts:
                transform_matrix, fitness, rmse = self.ransac_using_package(
                    movingMeshPoints=sourcePoints,
                    fixedMeshPoints=targetPoints,
                    movingMeshFeaturePoints=moving_corr.T,
                    fixedMeshFeaturePoints=fixed_corr.T,
                    number_of_iterations=ransac_iterations,
                    number_of_ransac_points=ransac_points,
                    inlier_value=float(parameters["distanceThreshold"]) * voxelSize,
                    scalingOption=True,
                    check_edge_length=False,
                    correspondence_distance=correspondence_distance,
                )

                transform = itk.transform_from_dict(transform_matrix)
                fitness_forward, rmse_forward = self.get_fitness(
                    sourcePoints,
                    targetPoints,
                    float(parameters["distanceThreshold"]) * voxelSize,
                    transform,
                )

                mean_fitness = fitness_forward
                mean_rmse = rmse_forward
                print(
                    "Scaling Attempt = ",
                    attempt,
                    " Fitness = ",
                    mean_fitness,
                    " RMSE = ",
                    mean_rmse,
                )

                if (mean_fitness > best_fitness) or (
                    mean_fitness == best_fitness and mean_rmse < best_rmse
                ):
                    best_fitness = mean_fitness
                    best_rmse = mean_rmse
                    best_transform = transform_matrix
                    similarityFlag = True
                attempt = attempt + 1

        aransac = time.time()
        print("RANSAC Duraction ", aransac - bransac)
        print("Best Fitness after scaling ", best_fitness)

        first_transform = itk.transform_from_dict(best_transform)
        sourcePoints = self.transform_numpy_points(sourcePoints, first_transform)

        print("-----------------------------------------------------------")
        print(parameters)
        print("Starting Rigid Refinement")
        distanceThreshold = parameters["ICPDistanceThreshold"] * voxelSize
        inlier, rmse = self.get_fitness(sourcePoints, targetPoints, distanceThreshold)
        print("Before Inlier = ", inlier, " RMSE = ", rmse)
        _, second_transform = self.final_iteration_icp(
            targetPoints,
            sourcePoints,
            distanceThreshold,
            float(parameters["normalSearchRadius"] * voxelSize),
        )

        final_mesh_points = self.transform_numpy_points(sourcePoints, second_transform)
        inlier, rmse = self.get_fitness(
            final_mesh_points, targetPoints, distanceThreshold
        )
        print("After Inlier = ", inlier, " RMSE = ", rmse)
        first_transform.Compose(second_transform)
        return first_transform, similarityFlag

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

    def scale_vtk_point_coordinates(self, vtk_polydata, scalingFactor):
        from vtk.util import numpy_support

        points = vtk_polydata.GetPoints()
        pointdata = points.GetData()
        points_as_numpy = numpy_support.vtk_to_numpy(pointdata)
        points_as_numpy = points_as_numpy * scalingFactor
        self.set_numpy_points_in_vtk(vtk_polydata, points_as_numpy)

        return vtk_polydata

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

    def subsample_points_poisson(self, inputMesh, radius):
        """
        Return sub-sampled points as numpy array.
        The radius might need to be tuned as per the requirements.
        """
        import vtk
        from vtk.util import numpy_support

        f = vtk.vtkPoissonDiskSampler()
        f.SetInputData(inputMesh)
        f.SetRadius(radius)
        f.Update()

        sampled_points = f.GetOutput()
        return sampled_points

    def subsample_points_voxelgrid_polydata(self, inputMesh, radius):
        subsample = vtk.vtkVoxelGrid()
        subsample.SetInputData(inputMesh)
        subsample.SetConfigurationStyleToLeafSize()

        subsample.SetLeafSize(radius, radius, radius)
        subsample.Update()
        points = subsample.GetOutput()
        return points

    def extract_pca_normal_scikit(self, inputPoints, searchRadius):
        from sklearn.neighbors import KDTree
        from sklearn.decomposition import PCA

        data = inputPoints
        tree = KDTree(data, metric="minkowski")  # minkowki is p2 (euclidean)

        # Get indices and distances:
        ind, dist = tree.query_radius(data, r=searchRadius, return_distance=True)

        def PCA_unit_vector(array, pca=PCA(n_components=3)):
            pca.fit(array)
            eigenvalues = pca.explained_variance_
            return pca.components_[np.argmin(eigenvalues)]

        def calc_angle_with_xy(vectors):
            l = np.sum(vectors[:, :2] ** 2, axis=1) ** 0.5
            return np.arctan2(vectors[:, 2], l)

        normals2 = []
        for i in range(data.shape[0]):
            if len(ind[i]) < 3:
                normal_vector = np.identity(3)
            else:
                normal_vector = data[ind[i]]
            normals2.append(PCA_unit_vector(normal_vector))

        n = np.array(normals2)
        n[calc_angle_with_xy(n) < 0] *= -1
        return n

    def extract_pca_normal(self, mesh, normalNeighbourCount):
        import vtk
        from vtk.util import numpy_support

        normals = vtk.vtkPCANormalEstimation()
        normals.SetSampleSize(normalNeighbourCount)
        # normals.SetFlipNormals(True)
        normals.SetNormalOrientationToPoint()
        # normals.SetNormalOrientationToGraphTraversal()
        normals.SetInputData(mesh)
        normals.Update()
        out1 = normals.GetOutput()
        normal_array = numpy_support.vtk_to_numpy(out1.GetPointData().GetNormals())
        point_array = numpy_support.vtk_to_numpy(mesh.GetPoints().GetData())
        return point_array, normal_array

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
        fpfh.ComputeFPFHFeature(pointset, normalset, float(radius), int(neighbors))
        result = fpfh.GetFpfhFeature()

        fpfh_feats = itk.array_from_vector_container(result)
        fpfh_feats = np.reshape(fpfh_feats, [33, pointset.GetNumberOfPoints()]).T
        return fpfh_feats

    def getBoxLengths(self, inputMesh):
        import vtk

        box_filter = vtk.vtkBoundingBox()
        box_filter.SetBounds(inputMesh.GetBounds())
        diagonalLength = box_filter.GetDiagonalLength()
        fixedLengths = [0.0, 0.0, 0.0]
        box_filter.GetLengths(fixedLengths)
        return fixedLengths, diagonalLength

    def runSubsample(
        self,
        sourceModel,
        targetModel,
        scalingOption,
        parameters,
        usePoissonSubsample=False,
    ):
        print("parameters are ", parameters)
        print(":: Loading point clouds and downsampling")

        sourceModelMesh = sourceModel.GetMesh()
        targetModelMesh = targetModel.GetMesh()

        # Scale the mesh and the landmark points
        fixedBoxLengths, fixedlength = self.getBoxLengths(targetModelMesh)
        movingBoxLengths, movinglength = self.getBoxLengths(sourceModelMesh)

        # Sub-Sample the points for rigid refinement and deformable registration
        point_density = parameters["pointDensity"]

        # Voxel size is the diagonal length of cuboid in the voxelGrid
        voxel_size = np.sqrt(np.sum(np.square(np.array(fixedBoxLengths)))) / (
            55 * point_density
        )

        print("Scale length are  ", fixedlength, movinglength)
        print("Voxel Size is ", voxel_size)

        scalingFactor = fixedlength / movinglength
        if scalingOption is False:
            scalingFactor = 1
        print("Scaling factor is ", scalingFactor)

        sourceFullMesh_vtk = self.scale_vtk_point_coordinates(sourceModelMesh, scalingFactor)
        targetFullMesh_vtk = targetModelMesh

        if usePoissonSubsample:
            print("Using Poisson Point Subsampling Method")
            sourceMesh_vtk = self.subsample_points_poisson(
                sourceFullMesh_vtk, radius=voxel_size
            )
            targetMesh_vtk = self.subsample_points_poisson(
                targetFullMesh_vtk, radius=voxel_size
            )
        else:
            sourceMesh_vtk = self.subsample_points_voxelgrid_polydata(
                sourceFullMesh_vtk, radius=voxel_size
            )
            targetMesh_vtk = self.subsample_points_voxelgrid_polydata(
                targetFullMesh_vtk, radius=voxel_size
            )

        movingMeshPoints, movingMeshPointNormals = self.extract_pca_normal(
            sourceMesh_vtk, 30
        )
        fixedMeshPoints, fixedMeshPointNormals = self.extract_pca_normal(
            targetMesh_vtk, 30
        )

        print("------------------------------------------------------------")
        print("movingMeshPoints.shape ", movingMeshPoints.shape)
        print("movingMeshPointNormals.shape ", movingMeshPointNormals.shape)
        print("fixedMeshPoints.shape ", fixedMeshPoints.shape)
        print("fixedMeshPointNormals.shape ", fixedMeshPointNormals.shape)
        print("------------------------------------------------------------")

        fpfh_radius = parameters["FPFHSearchRadius"] * voxel_size
        fpfh_neighbors = parameters["FPFHNeighbors"]
        # New FPFH Code
        pcS = np.expand_dims(fixedMeshPoints, -1)
        normal_np_pcl = fixedMeshPointNormals
        target_fpfh = self.get_fpfh_feature(
            pcS, normal_np_pcl, fpfh_radius, fpfh_neighbors
        )
        # print(f"target_fpfh {target_fpfh.shape}: {target_fpfh}")

        pcS = np.expand_dims(movingMeshPoints, -1)
        normal_np_pcl = movingMeshPointNormals
        source_fpfh = self.get_fpfh_feature(
            pcS, normal_np_pcl, fpfh_radius, fpfh_neighbors
        )
        # print(f"source_fpfh {source_fpfh.shape}: {source_fpfh}")

        target_down = fixedMeshPoints
        source_down = movingMeshPoints
        return source_down, target_down, source_fpfh, target_fpfh, voxel_size, scalingFactor

    def loadAndScaleFiducials(self, fiducial, scalingFactor, scene=False):
        if not scene:
            sourceLandmarkNode = slicer.util.loadMarkups(fiducial)
        else:
            shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(
                slicer.mrmlScene
            )
            itemIDToClone = shNode.GetItemByDataNode(fiducial)
            clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(
                shNode, itemIDToClone
            )
            sourceLandmarkNode = shNode.GetItemDataNode(clonedItemID)
        sourceLandmarks = np.zeros(
            shape=(sourceLandmarkNode.GetNumberOfControlPoints(), 3)
        )
        point = [0, 0, 0]
        for i in range(sourceLandmarkNode.GetNumberOfControlPoints()):
            sourceLandmarkNode.GetNthControlPointPosition(i, point)
            sourceLandmarks[i, :] = point
        sourceLandmarks = sourceLandmarks * scalingFactor
        slicer.util.updateMarkupsControlPointsFromArray(
            sourceLandmarkNode, sourceLandmarks
        )
        sourceLandmarkNode.GetDisplayNode().SetVisibility(False)
        return sourceLandmarks, sourceLandmarkNode

    def propagateLandmarkTypes(self, sourceNode, targetNode):
        for i in range(sourceNode.GetNumberOfControlPoints()):
            pointDescription = sourceNode.GetNthControlPointDescription(i)
            targetNode.SetNthControlPointDescription(i, pointDescription)
            pointLabel = sourceNode.GetNthControlPointLabel(i)
            targetNode.SetNthControlPointLabel(i, pointLabel)

    def distanceMatrix(self, a):
        """
        Computes the euclidean distance matrix for n points in a 3D space
        Returns a nXn matrix
        """
        id, jd = a.shape
        fnx = lambda q: q - np.reshape(q, (id, 1))
        dx = fnx(a[:, 0])
        dy = fnx(a[:, 1])
        dz = fnx(a[:, 2])
        return (dx ** 2.0 + dy ** 2.0 + dz ** 2.0) ** 0.5

    def cpd_registration(
        self,
        targetArray,
        sourceArray,
        CPDIterations,
        CPDTolerance,
        alpha_parameter,
        beta_parameter,
    ):
        from cpdalp import DeformableRegistration

        output = DeformableRegistration(
            **{
                "X": targetArray,
                "Y": sourceArray,
                "max_iterations": CPDIterations,
                "tolerance": CPDTolerance,
                "low_rank": True,
            },
            alpha=alpha_parameter,
            beta=beta_parameter,
        )
        return output

    def getFiducialPoints(self, fiducialNode):
        points = vtk.vtkPoints()
        for i in range(fiducialNode.GetNumberOfControlPoints()):
            point = fiducialNode.GetNthControlPointPosition(i)
            points.InsertNextPoint(point)

        return points

    def runPointProjection(
        self, template, model, templateLandmarks, maxProjectionFactor
    ):
        maxProjection = (model.GetPolyData().GetLength()) * maxProjectionFactor
        print("Max projection: ", maxProjection)
        templatePoints = self.getFiducialPoints(templateLandmarks)

        # project landmarks from template to model
        projectedPoints = self.projectPointsPolydata(
            template.GetPolyData(), model.GetPolyData(), templatePoints, maxProjection
        )
        projectedLMNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLMarkupsFiducialNode", "Refined Predicted Landmarks"
        )
        for i in range(projectedPoints.GetNumberOfPoints()):
            point = projectedPoints.GetPoint(i)
            projectedLMNode.AddControlPoint(point)
        projectedLMNode.SetLocked(True)
        projectedLMNode.SetFixedNumberOfControlPoints(True)
        return projectedLMNode

    def projectPointsPolydata(
        self, sourcePolydata, targetPolydata, originalPoints, rayLength
    ):
        import vtk

        print("original points: ", originalPoints.GetNumberOfPoints())
        # set up polydata for projected points to return
        projectedPointData = vtk.vtkPolyData()
        projectedPoints = vtk.vtkPoints()
        projectedPointData.SetPoints(projectedPoints)

        # set up locater for intersection with normal vector rays
        obbTree = vtk.vtkOBBTree()
        obbTree.SetDataSet(targetPolydata)
        obbTree.BuildLocator()

        # set up point locator for finding surface normals and closest point
        pointLocator = vtk.vtkPointLocator()
        pointLocator.SetDataSet(sourcePolydata)
        pointLocator.BuildLocator()

        targetPointLocator = vtk.vtkPointLocator()
        targetPointLocator.SetDataSet(targetPolydata)
        targetPointLocator.BuildLocator()

        # get surface normal from each landmark point
        rayDirection = [0, 0, 0]
        normalArray = sourcePolydata.GetPointData().GetArray("Normals")
        if not normalArray:
            print("no normal array, calculating....")
            normalFilter = vtk.vtkPolyDataNormals()
            normalFilter.ComputePointNormalsOn()
            normalFilter.SetInputData(sourcePolydata)
            normalFilter.Update()
            normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
            if not normalArray:
                print("Error: no normal array")
                return projectedPointData
        for index in range(originalPoints.GetNumberOfPoints()):
            originalPoint = originalPoints.GetPoint(index)
            # get ray direction from closest normal
            closestPointId = pointLocator.FindClosestPoint(originalPoint)
            rayDirection = normalArray.GetTuple(closestPointId)
            rayEndPoint = [0, 0, 0]
            for dim in range(len(rayEndPoint)):
                rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim] * rayLength
            intersectionIds = vtk.vtkIdList()
            intersectionPoints = vtk.vtkPoints()
            obbTree.IntersectWithLine(
                originalPoint, rayEndPoint, intersectionPoints, intersectionIds
            )
            # if there are intersections, update the point to most external one.
            if intersectionPoints.GetNumberOfPoints() > 0:
                exteriorPoint = intersectionPoints.GetPoint(
                    intersectionPoints.GetNumberOfPoints() - 1
                )
                projectedPoints.InsertNextPoint(exteriorPoint)
            # if there are no intersections, reverse the normal vector
            else:
                for dim in range(len(rayEndPoint)):
                    rayEndPoint[dim] = (
                        originalPoint[dim] + rayDirection[dim] * -rayLength
                    )
                obbTree.IntersectWithLine(
                    originalPoint, rayEndPoint, intersectionPoints, intersectionIds
                )
                if intersectionPoints.GetNumberOfPoints() > 0:
                    exteriorPoint = intersectionPoints.GetPoint(0)
                    projectedPoints.InsertNextPoint(exteriorPoint)
                # if none in reverse direction, use closest mesh point
                else:
                    closestPointId = targetPointLocator.FindClosestPoint(originalPoint)
                    rayOrigin = targetPolydata.GetPoint(closestPointId)
                    projectedPoints.InsertNextPoint(rayOrigin)
        return projectedPointData

    def takeScreenshot(self, name, description, type=-1):
        # show the message even if not taking a screen shot
        slicer.util.delayDisplay(
            "Take screenshot: "
            + description
            + ".\nResult is available in the Annotations module.",
            3000,
        )

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
        slicer.qMRMLUtils().qImageToVtkImageData(qimage, imageData)

        annotationLogic = slicer.modules.annotations.logic()
        annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

    def process(
        self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True
    ):
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
        logging.info("Processing started")

        # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
        cliParams = {
            "InputVolume": inputVolume.GetID(),
            "OutputVolume": outputVolume.GetID(),
            "ThresholdValue": imageThreshold,
            "ThresholdType": "Above" if invert else "Below",
        }
        cliNode = slicer.cli.run(
            slicer.modules.thresholdscalarvolume,
            None,
            cliParams,
            wait_for_completion=True,
            update_display=showResult,
        )
        # We don't need the CLI module node anymore, remove it to not clutter the scene with it
        slicer.mrmlScene.RemoveNode(cliNode)

        stopTime = time.time()
        logging.info(f"Processing completed in {stopTime-startTime:.2f} seconds")

    ###Functions for select templates based on kmeans
    def downReference(self, referenceFilePath, spacingFactor):
        targetModelNode = slicer.util.loadModel(referenceFilePath)
        targetModelNode.GetDisplayNode().SetVisibility(False)
        templatePolydata = targetModelNode.GetPolyData()
        sparseTemplate = self.DownsampleTemplate(templatePolydata, spacingFactor)
        template_density = sparseTemplate.GetNumberOfPoints()
        return sparseTemplate, template_density, targetModelNode

    def matchingPCD(
        self,
        modelsDir,
        sparseTemplate,
        targetModelNode,
        pcdOutputDir,
        spacingFactor,
        useJSONFormat,
        parameterDictionary,
        usePoisson=False,
    ):
        if useJSONFormat:
            extensionLM = ".mrk.json"
        else:
            extensionLM = ".fcsv"
        template_density = sparseTemplate.GetNumberOfPoints()
        ID_list = list()
        logic = ALPACALogic()

        # Alignment and matching points
        referenceFileList = [
            f
            for f in os.listdir(modelsDir)
            if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
        ]
        for file in referenceFileList:
            sourceFilePath = os.path.join(modelsDir, file)
            sourceModelNode = slicer.util.loadModel(sourceFilePath)
            sourceModelNode.GetDisplayNode().SetVisibility(False)
            rootName = os.path.splitext(file)[0]
            scalingOption = True
            (
                sourcePoints,
                targetPoints,
                sourceFeatures,
                targetFeatures,
                voxelSize,
                scalingFactor,
            ) = self.runSubsample(
                sourceModelNode,
                targetModelNode,
                scalingOption,
                parameterDictionary,
                usePoisson,
            )
            ICPTransform_similarity, similarityFlag = self.estimateTransform(
                sourcePoints,
                targetPoints,
                sourceFeatures,
                targetFeatures,
                voxelSize,
                scalingOption,
                parameterDictionary,
            )

            vtkSimilarityTransform = self.itkToVTKTransform(
                ICPTransform_similarity, similarityFlag
            )
            ICPTransformNode = self.convertMatrixToTransformNode(
                vtkSimilarityTransform, "Rigid Transformation Matrix"
            )

            sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)

            alignedSubjectPolydata = sourceModelNode.GetPolyData()
            ID, correspondingSubjectPoints = self.GetCorrespondingPoints(
                sparseTemplate, alignedSubjectPolydata
            )
            ID_list.append(ID)
            subjectFiducial = slicer.vtkMRMLMarkupsFiducialNode()
            for i in range(correspondingSubjectPoints.GetNumberOfPoints()):
                subjectFiducial.AddControlPoint(correspondingSubjectPoints.GetPoint(i))
            slicer.mrmlScene.AddNode(subjectFiducial)
            subjectFiducial.SetFixedNumberOfControlPoints(True)

            ICPTransformNode.Inverse()
            subjectFiducial.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(subjectFiducial)

            sourceArray = np.zeros(shape=(correspondingSubjectPoints.GetNumberOfPoints(), 3))
            point = [0, 0, 0]
            for i in range(subjectFiducial.GetNumberOfControlPoints()):
              subjectFiducial.GetNthControlPointPosition(i, point)
              sourceArray[i, :] = point
              subjectFiducial.SetNthControlPointLocked(i, 1)

            sourceArray = sourceArray * (1/scalingFactor)

            slicer.util.updateMarkupsControlPointsFromArray(subjectFiducial, sourceArray)

            slicer.util.saveNode(
                subjectFiducial, os.path.join(pcdOutputDir, f"{rootName}" + extensionLM)
            )
            slicer.mrmlScene.RemoveNode(sourceModelNode)
            slicer.mrmlScene.RemoveNode(ICPTransformNode)
            slicer.mrmlScene.RemoveNode(subjectFiducial)
        # Remove template node
        slicer.mrmlScene.RemoveNode(targetModelNode)
        # Printing results of points matching
        matchedPoints = [len(set(x)) for x in ID_list]
        indices = [i for i, x in enumerate(matchedPoints) if x < template_density]
        files = [os.path.splitext(file)[0] for file in referenceFileList]
        return template_density, matchedPoints, indices, files

    # inputFilePaths: file paths of pcd files
    def pcdGPA(self, inputFilePaths):
        basename, extension = os.path.splitext(inputFilePaths[0])
        import GPA

        GPAlogic = GPA.GPALogic()
        LM = GPA.LMData()
        LMExclusionList = []
        LM.lmOrig, landmarkTypeArray = GPAlogic.loadLandmarks(
            inputFilePaths, LMExclusionList, extension
        )
        shape = LM.lmOrig.shape
        scalingOption = True
        try:
            LM.doGpa(scalingOption)
        except ValueError:
            print(
                "Point clouds may not have been generated correctly. Please re-run the point cloud generation step."
            )
        LM.calcEigen()
        import Support.gpa_lib as gpa_lib

        twoDcoors = gpa_lib.makeTwoDim(LM.lmOrig)
        scores = np.dot(np.transpose(twoDcoors), LM.vec)
        scores = np.real(scores)
        size = scores.shape[0] - 1
        scores = scores[:, 0:size]
        return scores, LM

    def templatesSelection(
        self,
        modelsDir,
        scores,
        inputFilePaths,
        templatesOutputDir,
        templatesNumber,
        iterations,
    ):
        templatesNumber = int(templatesNumber)
        iterations = int(iterations)
        basename, extension = os.path.splitext(inputFilePaths[0])
        files = [os.path.basename(path).split(".")[0] for path in inputFilePaths]
        from numpy import array
        from scipy.cluster.vq import vq, kmeans

        # np.random.seed(1000) #Set numpy random seed to ensure consistent Kmeans result
        centers, distortion = kmeans(scores, templatesNumber, thresh=0, iter=iterations)
        # clusterID returns the cluster allocation of each specimen
        clusterID, min_dists = vq(scores, centers)
        # distances between specimens to centers
        templatesIndices = []
        from scipy.spatial import distance_matrix

        for i in range(templatesNumber):
            indices_i = [index for index, x in enumerate(clusterID) if x == i]
            dists = [min_dists[index] for index in indices_i]
            index = dists.index(min(dists))
            templateIndex = indices_i[index]
            templatesIndices.append(templateIndex)
        templates = [files[x] for x in templatesIndices]
        # Store templates in a new folder
        for file in templates:
            modelFile = file + ".ply"
            temp_model = slicer.util.loadModel(os.path.join(modelsDir, modelFile))
            slicer.util.saveNode(
                temp_model, os.path.join(templatesOutputDir, modelFile)
            )
            slicer.mrmlScene.RemoveNode(temp_model)
        return templates, clusterID, templatesIndices

    def DownsampleTemplate(self, templatePolyData, spacingPercentage):
        import vtk

        filter = vtk.vtkCleanPolyData()
        filter.SetToleranceIsAbsolute(False)
        filter.SetTolerance(spacingPercentage)
        filter.SetInputData(templatePolyData)
        filter.Update()
        return filter.GetOutput()

    def GetCorrespondingPoints(self, templatePolyData, subjectPolydata):
        import vtk

        print(templatePolyData.GetNumberOfPoints())
        print(subjectPolydata.GetNumberOfPoints())
        templatePoints = templatePolyData.GetPoints()
        correspondingPoints = vtk.vtkPoints()
        correspondingPoint = [0, 0, 0]
        subjectPointLocator = vtk.vtkPointLocator()
        subjectPointLocator.SetDataSet(subjectPolydata)
        subjectPointLocator.BuildLocator()
        ID = list()
        # Index = list()
        for index in range(templatePoints.GetNumberOfPoints()):
            templatePoint = templatePoints.GetPoint(index)
            closestPointId = subjectPointLocator.FindClosestPoint(templatePoint)
            correspondingPoint = subjectPolydata.GetPoint(closestPointId)
            correspondingPoints.InsertNextPoint(correspondingPoint)
            ID.append(closestPointId)
            # Index.append(index)
        return ID, correspondingPoints

    def makeScatterPlotWithFactors(
        self, data, files, factors, title, xAxis, yAxis, pcNumber, templatesIndices
    ):
        # create two tables for the first two factors and then check for a third
        # check if there is a table node has been created
        numPoints = len(data)
        uniqueFactors, factorCounts = np.unique(factors, return_counts=True)
        factorNumber = len(uniqueFactors)

        # Set up chart
        plotChartNode = slicer.mrmlScene.GetFirstNodeByName(
            "Chart_PCA_cov_with_groups" + xAxis + "v" + yAxis
        )
        if plotChartNode is None:
            plotChartNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotChartNode",
                "Chart_PCA_cov_with_groups" + xAxis + "v" + yAxis,
            )
        else:
            plotChartNode.RemoveAllPlotSeriesNodeIDs()

        # Plot all series
        for factorIndex in range(len(uniqueFactors)):
            factor = uniqueFactors[factorIndex]
            tableNode = slicer.mrmlScene.GetFirstNodeByName(
                "PCA Scatter Plot Table Group " + factor
            )
            if tableNode is None:
                tableNode = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLTableNode", "PCA Scatter Plot Table Group " + factor
                )
            else:
                tableNode.RemoveAllColumns()  # clear previous data from columns

            # Set up columns for X,Y, and labels
            labels = tableNode.AddColumn()
            labels.SetName("Subject ID")
            tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

            for i in range(pcNumber):
                pc = tableNode.AddColumn()
                colName = "PC" + str(i + 1)
                pc.SetName(colName)
                tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

            factorCounter = 0
            table = tableNode.GetTable()
            table.SetNumberOfRows(factorCounts[factorIndex])
            for i in range(numPoints):
                if factors[i] == factor:
                    table.SetValue(factorCounter, 0, files[i])
                    for j in range(pcNumber):
                        table.SetValue(factorCounter, j + 1, data[i, j])
                    factorCounter += 1

            plotSeriesNode = slicer.mrmlScene.GetFirstNodeByName(factor)
            if plotSeriesNode is None:
                plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLPlotSeriesNode", factor
                )
                # GPANodeCollection.AddItem(plotSeriesNode)
            # Create data series from table
            plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
            plotSeriesNode.SetXColumnName(xAxis)
            plotSeriesNode.SetYColumnName(yAxis)
            plotSeriesNode.SetLabelColumnName("Subject ID")
            plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
            plotSeriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
            plotSeriesNode.SetMarkerStyle(
                slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare
            )
            plotSeriesNode.SetUniqueColor()
            # Add data series to chart
            plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

        # Set up plotSeriesNode for templates
        tableNode = slicer.mrmlScene.GetFirstNodeByName(
            "PCA Scatter Plot Table Templates with group input"
        )
        if tableNode is None:
            tableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "PCA Scatter Plot Table Templates with group input"
            )
        else:
            tableNode.RemoveAllColumns()  # clear previous data from columns

        labels = tableNode.AddColumn()
        labels.SetName("Subject ID")
        tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

        for i in range(pcNumber):
            pc = tableNode.AddColumn()
            colName = "PC" + str(i + 1)
            pc.SetName(colName)
            tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

        table = tableNode.GetTable()
        table.SetNumberOfRows(len(templatesIndices))
        for i in range(len(templatesIndices)):
            tempIndex = templatesIndices[i]
            table.SetValue(i, 0, files[tempIndex])
            for j in range(pcNumber):
                table.SetValue(i, j + 1, data[tempIndex, j])

        plotSeriesNode = slicer.mrmlScene.GetFirstNodeByName(
            "Templates_with_group_input"
        )
        if plotSeriesNode is None:
            plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Templates_with_group_input"
            )
        plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
        plotSeriesNode.SetXColumnName(xAxis)
        plotSeriesNode.SetYColumnName(yAxis)
        plotSeriesNode.SetLabelColumnName("Subject ID")
        plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        plotSeriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        plotSeriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
        plotSeriesNode.SetUniqueColor()
        # Add data series to chart
        plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

        # Set up view options for chart
        plotChartNode.SetTitle("PCA Scatter Plot with kmeans clusters")
        plotChartNode.SetXAxisTitle(xAxis)
        plotChartNode.SetYAxisTitle(yAxis)

        # Switch to a Slicer layout that contains a plot view for plotwidget
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(503)

        plotWidget = layoutManager.plotWidget(0)
        plotViewNode = plotWidget.mrmlPlotViewNode()
        plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

    def makeScatterPlot(
        self, data, files, title, xAxis, yAxis, pcNumber, templatesIndices
    ):
        numPoints = len(data)
        # Scatter plot for all specimens with no group input
        plotChartNode = slicer.mrmlScene.GetFirstNodeByName(
            "Chart_PCA_cov" + xAxis + "v" + yAxis
        )
        if plotChartNode is None:
            plotChartNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotChartNode", "Chart_PCA_cov" + xAxis + "v" + yAxis
            )
        else:
            plotChartNode.RemoveAllPlotSeriesNodeIDs()

        tableNode = slicer.mrmlScene.GetFirstNodeByName(
            "PCA Scatter Plot Table without group input"
        )
        if tableNode is None:
            tableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "PCA Scatter Plot Table without group input"
            )
        else:
            tableNode.RemoveAllColumns()  # clear previous data from columns

        labels = tableNode.AddColumn()
        labels.SetName("Subject ID")
        tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

        for i in range(pcNumber):
            pc = tableNode.AddColumn()
            colName = "PC" + str(i + 1)
            pc.SetName(colName)
            tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

        table = tableNode.GetTable()
        table.SetNumberOfRows(numPoints)
        for i in range(len(files)):
            table.SetValue(i, 0, files[i])
            for j in range(pcNumber):
                table.SetValue(i, j + 1, data[i, j])

        plotSeriesNode1 = slicer.mrmlScene.GetFirstNodeByName(
            "Specimens_no_group_input"
        )
        if plotSeriesNode1 is None:
            plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Specimens_no_group_input"
            )

        plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
        plotSeriesNode1.SetXColumnName(xAxis)
        plotSeriesNode1.SetYColumnName(yAxis)
        plotSeriesNode1.SetLabelColumnName("Subject ID")
        plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
        plotSeriesNode1.SetUniqueColor()
        plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())

        # Set up plotSeriesNode for templates
        tableNode = slicer.mrmlScene.GetFirstNodeByName(
            "PCA_Scatter_Plot_Table_Templates_no_group"
        )
        if tableNode is None:
            tableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "PCA_Scatter_Plot_Table_Templates_no_group"
            )
        else:
            tableNode.RemoveAllColumns()  # clear previous data from columns

        labels = tableNode.AddColumn()
        labels.SetName("Subject ID")
        tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

        for i in range(pcNumber):
            pc = tableNode.AddColumn()
            colName = "PC" + str(i + 1)
            pc.SetName(colName)
            tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

        table = tableNode.GetTable()
        table.SetNumberOfRows(len(templatesIndices))
        for i in range(len(templatesIndices)):
            tempIndex = templatesIndices[i]
            table.SetValue(i, 0, files[tempIndex])
            for j in range(pcNumber):
                table.SetValue(i, j + 1, data[tempIndex, j])

        plotSeriesNode1 = slicer.mrmlScene.GetFirstNodeByName(
            "Templates_no_group_input"
        )
        if plotSeriesNode1 is None:
            plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Templates_no_group_input"
            )
        plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
        plotSeriesNode1.SetXColumnName(xAxis)
        plotSeriesNode1.SetYColumnName(yAxis)
        plotSeriesNode1.SetLabelColumnName("Subject ID")
        plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
        plotSeriesNode1.SetUniqueColor()
        # Add data series to chart
        plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())

        plotChartNode.SetTitle("PCA Scatter Plot with templates")
        plotChartNode.SetXAxisTitle(xAxis)
        plotChartNode.SetYAxisTitle(yAxis)

        # Switch to a Slicer layout that contains a plot view for plotwidget
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(503)

        # Select chart in plot view
        plotWidget = layoutManager.plotWidget(0)
        plotViewNode = plotWidget.mrmlPlotViewNode()
        plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

    def saveBCPDPath(self, BCPDPath):
        # don't save if identical to saved
        settings = qt.QSettings()
        if settings.contains("Developer/BCPDPath"):
            BCPDPathSaved = settings.value("Developer/BCPDPath")
            if BCPDPathSaved == BCPDPath:
                return
        if not self.isValidBCPDPath(BCPDPath):
            return
        settings.setValue("Developer/BCPDPath", BCPDPath)

    def getBCPDPath(self):
        # If path is defined in settings then use that
        settings = qt.QSettings()
        if settings.contains("Developer/BCPDPath"):
            BCPDPath = settings.value("Developer/BCPDPath")
            if self.isValidBCPDPath(BCPDPath):
                return BCPDPath
        else:
            return ""

    def isValidBCPDPath(self, BCPDPath):
        if not os.path.isdir(BCPDPath):
            logging.info("BCPD path invalid: Not a directory")
            return False
        # Check if extension contains bcpd executable
        if slicer.app.os == "win":
            exePath = os.path.join(BCPDPath, "bcpd.exe")
        else:
            exePath = os.path.join(BCPDPath, "bcpd")
        if os.path.exists(exePath):
            return True
        else:
            logging.info("BCPD path invalid: No executable found")
            return False

    def rmse(self, M1, M2):
        sq_dff = np.square(M1 - M2)
        sq_LM_dist = np.sum(sq_dff, axis=1)  # squared LM distances
        RMSE = np.sqrt(np.mean(sq_LM_dist))
        # <- sqrt(mean(sq_LM_dist))
        return RMSE


class ALPACATest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_ALPACA1()

    def test_ALPACA1(self):
        """Ideally you should have several levels of tests.  At the lowest level
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

        self.delayDisplay("Test passed")
