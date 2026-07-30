import logging
import os
import shutil
import subprocess
import tempfile

import numpy as np
import qt
import vtk
import vtk.util.numpy_support as vtk_np

import slicer
import slicer.packaging
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.i18n import tr as _


#
# FastModelAlign
#

class FastModelAlign(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "FastModelAlign"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["SlicerMorph.Utilities"]  # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Chi Zhang (SCRI), Murat Maga (UW)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """This module uses ALPACA libraries to do rigid and affine transforms of 3D Models quickly via pointcloud registration.
See the usage tutorial at <a href="https://github.com/SlicerMorph/Tutorials/tree/master/FastModelAlign">module documentation</a>."""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """The development of the module was supported by NSF/OAC grant, HDR Institute: Imageomics: A New Frontier of Biological Information Powered by Knowledge-Guided Machine Learnings" (Award #2118240)."""

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

    # FastModelAlign1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='FastModelAlign',
        sampleName='Partial photogrammetry models',
        uris= ["https://raw.githubusercontent.com/SlicerMorph/SampleData/d31deba22c620588a5f8b388a915be6759ce1116/partial_photogram_model1.obj", "https://raw.githubusercontent.com/SlicerMorph/SampleData/d31deba22c620588a5f8b388a915be6759ce1116/partial_photogram_model2.obj"],
        checksums= [None, None],
        loadFiles=[True, True],
        fileNames=['partial_photogram_model1.obj', 'partial_photogram_model2.obj'],
        nodeNames=['large_model1', 'small_model2'],
        thumbnailFileName=os.path.join(iconsPath, 'FastModelAlign1.png'),
        loadFileType=['ModelFile', 'ModelFile']

    )



# FastModelAlignWidget

class FastModelAlignWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/FastModelAlign.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = FastModelAlignLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
        # (in the selected parameter node).

        self.ui.sourceModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.sourceModelSelector.setMRMLScene( slicer.mrmlScene)
        self.ui.targetModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.targetModelSelector.setMRMLScene( slicer.mrmlScene)
        self.ui.outputSelector.setMRMLScene( slicer.mrmlScene)
        self.ui.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        # Optional output transform: receives the complete source -> target transform.
        self.ui.outputTransformSelector.setMRMLScene( slicer.mrmlScene)
        self.ui.outputTransformSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

        # Run subsampling
        self.ui.pointDensitySlider.connect('valueChanged(double)', self.onChangeDensitySingle)
        self.ui.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)

        # Main registration button
        self.ui.runRegistrationButton.connect('clicked(bool)', self.onRunRegistrationButton)

        # Registration step checkboxes
        self.ui.scalingCheckBox.connect("toggled(bool)", self.onSelect)
        self.ui.rigidCheckBox.connect("toggled(bool)", self.onSelect)
        self.ui.affineCheckBox.connect("toggled(bool)", self.onSelect)
        self.ui.deformableCheckBox.connect("toggled(bool)", self.onSelect)

        # Deformable registration parameter connections
        self.ui.alphaSlider.connect('valueChanged(double)', self.onChangeDeformable)
        self.ui.betaSlider.connect('valueChanged(double)', self.onChangeDeformable)
        self.ui.cpdIterationsSlider.connect('valueChanged(double)', self.onChangeDeformable)
        self.ui.cpdToleranceSlider.connect('valueChanged(double)', self.onChangeDeformable)

        # Advanced Settings connections
        self.ui.pointDensityAdvancedSlider.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.normalSearchRadiusSlider.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.FPFHSearchRadiusSlider.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.maximumCPDThreshold.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.maxRANSAC.connect('valueChanged(double)', self.onChangeAdvanced)
        # self.ui.RANSACConfidence.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.poissonSubsampleCheckBox.connect("toggled(bool)", self.onChangeAdvanced)
        self.ui.ICPDistanceThresholdSlider.connect('valueChanged(double)', self.onChangeAdvanced)
        self.ui.FPFHNeighborsSlider.connect("valueChanged(double)", self.onChangeAdvanced)
        self.ui.gridSpacingSlider.connect('valueChanged(double)', self.onChangeAdvanced)

        # BCPD acceleration of the deformable step (optional external binary)
        self.ui.accelerationCheckBox.connect("toggled(bool)", self.onAccelerationToggled)
        self.ui.BCPDFolder.connect("validInputChanged(bool)", self.onChangeBCPDPath)

        # Restore the persisted BCPD path (shared with ALPACA) and acceleration state.
        savedBCPDPath = self.logic.getBCPDPath()
        self.ui.BCPDFolder.currentPath = savedBCPDPath
        if savedBCPDPath and self.logic.getAccelerationEnabled():
            self.ui.accelerationCheckBox.checked = True
        self.ui.BCPDFolder.enabled = self.ui.accelerationCheckBox.checked

        # initialize the parameter dictionary from single run parameters
        self.parameterDictionary = {
            "pointDensity": self.ui.pointDensityAdvancedSlider.value,
            "normalSearchRadius": self.ui.normalSearchRadiusSlider.value,
            "FPFHNeighbors": int(self.ui.FPFHNeighborsSlider.value),
            "FPFHSearchRadius": self.ui.FPFHSearchRadiusSlider.value,
            "distanceThreshold": self.ui.maximumCPDThreshold.value,
            "maxRANSAC": int(self.ui.maxRANSAC.value),
            "ICPDistanceThreshold": float(self.ui.ICPDistanceThresholdSlider.value),
            "alpha": self.ui.alphaSlider.value,
            "beta": self.ui.betaSlider.value,
            "CPDIterations": int(self.ui.cpdIterationsSlider.value),
            "CPDTolerance": self.ui.cpdToleranceSlider.value,
            # Requested displacement-grid sample spacing, in millimeters.
            "gridSpacing": self.ui.gridSpacingSlider.value,
            "Acceleration": self.ui.accelerationCheckBox.checked,
            "BCPDFolder": self.ui.BCPDFolder.currentPath,
            }

        # Store voxel size for grid transform estimation
        self.voxelSize = None


    def onSelect(self):
        # Check if source and target are selected. Both output selectors (model and
        # transform) are optional, so they do not take part in the enablement logic.
        hasInputs = bool(self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode())

        # Check if at least one registration step is selected
        hasSteps = (self.ui.scalingCheckBox.checked or self.ui.rigidCheckBox.checked or
                    self.ui.affineCheckBox.checked or self.ui.deformableCheckBox.checked)

        # Enable subsampling preview button
        self.ui.subsampleButton.enabled = hasInputs

        # Enable run registration button only if we have inputs, output, and at least one step
        self.ui.runRegistrationButton.enabled = hasInputs and hasSteps

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

    def onChangeDeformable(self):
        self.updateParameterDictionary()

    def onAccelerationToggled(self, checked):
        """Enable/disable the BCPD path entry and persist the checkbox state."""
        self.ui.BCPDFolder.enabled = bool(checked)
        self.logic.saveAccelerationEnabled(bool(checked))
        self.updateParameterDictionary()

    def onChangeBCPDPath(self):
        """Persist the BCPD directory so it is remembered between sessions."""
        self.logic.saveBCPDPath(self.ui.BCPDFolder.currentPath)
        self.updateParameterDictionary()

    def updateParameterDictionary(self):
        # update the parameter dictionary from single run parameters
        if hasattr(self, "parameterDictionary"):
            self.parameterDictionary["pointDensity"] = self.ui.pointDensityAdvancedSlider.value
            self.parameterDictionary["normalSearchRadius"] = int(self.ui.normalSearchRadiusSlider.value)
            self.parameterDictionary["FPFHNeighbors"] = int(self.ui.FPFHNeighborsSlider.value)
            self.parameterDictionary["FPFHSearchRadius"] = int(self.ui.FPFHSearchRadiusSlider.value)
            self.parameterDictionary["distanceThreshold"] = self.ui.maximumCPDThreshold.value
            self.parameterDictionary["maxRANSAC"] = int(self.ui.maxRANSAC.value)
            self.parameterDictionary["ICPDistanceThreshold"] = self.ui.ICPDistanceThresholdSlider.value
            self.parameterDictionary["alpha"] = self.ui.alphaSlider.value
            self.parameterDictionary["beta"] = self.ui.betaSlider.value
            self.parameterDictionary["CPDIterations"] = int(self.ui.cpdIterationsSlider.value)
            self.parameterDictionary["CPDTolerance"] = self.ui.cpdToleranceSlider.value
            self.parameterDictionary["gridSpacing"] = self.ui.gridSpacingSlider.value
            self.parameterDictionary["Acceleration"] = self.ui.accelerationCheckBox.checked
            self.parameterDictionary["BCPDFolder"] = self.ui.BCPDFolder.currentPath


    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        # self.initializeParameterNode()

    def exit(self):
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
        # self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    def onSceneStartClose(self, caller, event):
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        # self.setParameterNode(None)

    def onSceneEndClose(self, caller, event):
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        # if self.parent.isEntered:
        #     self.initializeParameterNode()

    def _ensureDependencies(self):
        """Install FastModelAlign's Python dependencies if missing."""
        try:
            reqs = slicer.packaging.load_requirements(self.resourcePath("requirements_FastModelAlign.txt"))
            slicer.packaging.pip_ensure(reqs, requester="FastModelAlign")
        except RuntimeError:
            slicer.util.messageBox(
                _("FastModelAlign requires its Python packages (itk, scikit-learn, "
                  "itk-fpfh, itk-ransac, cpdalp) to run.")
            )
            return False
        return True

    def onSubsampleButton(self):
        if not self._ensureDependencies():
            return
        try:
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)
                self.targetCloudNodeTest = None
        except:
            pass
        import ALPACA
        logic = ALPACA.ALPACALogic()
        self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
        # self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)
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
        # self.sourceModelNode_clone.GetDisplayNode().SetVisibility(False)
        # slicer.mrmlScene.RemoveNode(self.sourceModelNode_copy)
        # Create target Model Node
        self.targetModelNode = self.ui.targetModelSelector.currentNode()
        # self.targetModelNode.GetDisplayNode().SetVisibility(False)

        (
            self.sourcePoints,
            self.targetPoints,
            self.sourceFeatures,
            self.targetFeatures,
            self.voxelSize,
            self.scaling,
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

        # Output information on spycpdubsampling
        self.ui.subsampleInfo.clear()
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled source pointcloud has a total of {len(self.sourcePoints)} points. \n"
        )
        self.ui.subsampleInfo.insertPlainText(
            f":: Your subsampled target pointcloud has a total of {len(self.targetPoints)} points. "
        )

    def currentNode(self):
      # TODO: this should be moved to qMRMLSubjectHierarchyComboBox::currentNode()
      if self.outputSelector.className() == "qMRMLSubjectHierarchyComboBox":
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        selectedItem = self.outputSelector.currentItem()
        outputNode = shNode.GetItemDataNode(selectedItem)
      else:
        return self.ui.outputSelector.currentNode()

    def setCurrentNode(self, node):
      if self.ui.outputSelector.className() == "qMRMLSubjectHierarchyComboBox":
        # not sure how to select in the subject hierarychy
        pass
      else:
        self.ui.outputSelector.setCurrentNode(node)

    def onRunRegistrationButton(self):
        """
        Run all selected registration steps in sequence.
        """
        if not self._ensureDependencies():
            return
        try:
            if hasattr(self, 'targetCloudNodeTest') and self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)
                self.targetCloudNodeTest = None
        except:
            pass

        # Get source and target models
        self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
        self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)
        self.sourceModelName = self.sourceModelNode_orig.GetName()
        self.targetModelNode = self.ui.targetModelSelector.currentNode()

        logic = FastModelAlignLogic()

        # Clone the source model for registration
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig)
        clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
        self.sourceModelNode = shNode.GetItemDataNode(clonedItemID)
        self.sourceModelNode.GetDisplayNode().SetVisibility(False)
        self.sourceModelNode.SetName("Source_working_copy")

        # Determine which steps to run
        doScaling = self.ui.scalingCheckBox.checked
        doRigid = self.ui.rigidCheckBox.checked
        doAffine = self.ui.affineCheckBox.checked
        doDeformable = self.ui.deformableCheckBox.checked

        # Initialize transform nodes
        self.scalingTransformNode = None
        self.ICPTransformNode = None
        affineTransformNode = None

        # ============ RIGID REGISTRATION (with optional scaling) ============
        if doRigid or doScaling:
            # Run full rigid registration with FPFH features
            self.sourcePoints, self.targetPoints, self.scalingTransformNode, self.ICPTransformNode, self.voxelSize = logic.ITKRegistration(
                self.sourceModelNode,
                self.targetModelNode,
                doScaling,
                self.parameterDictionary,
                self.ui.poissonSubsampleCheckBox.checked
            )

            # Name and handle transform nodes based on what user requested
            if doScaling:
                scalingNodeName = self.sourceModelName + "_scaling"
                self.scalingTransformNode.SetName(scalingNodeName)
            else:
                # Remove scaling transform if not explicitly requested
                slicer.mrmlScene.RemoveNode(self.scalingTransformNode)
                self.scalingTransformNode = None

            if doRigid:
                rigidNodeName = self.sourceModelName + "_rigid"
                self.ICPTransformNode.SetName(rigidNodeName)
            else:
                # Scaling only - rigid transform was needed internally but user didn't request it
                # Keep it with a different name to indicate it's part of the scaling workflow
                self.ICPTransformNode.SetName(self.sourceModelName + "_scaling_alignment")
        else:
            # No rigid/scaling - just subsample for affine/deformable
            # Models are assumed to be pre-aligned
            import ALPACA
            alpaca_logic = ALPACA.ALPACALogic()
            (
                self.sourcePoints,
                self.targetPoints,
                sourceFeatures,
                targetFeatures,
                self.voxelSize,
                scaling,
            ) = alpaca_logic.runSubsample(
                self.sourceModelNode,
                self.targetModelNode,
                False,  # No scaling
                self.parameterDictionary,
                self.ui.poissonSubsampleCheckBox.checked,
            )

        # ============ AFFINE REGISTRATION ============
        if doAffine:
            # CPDAffineTransform modifies the model vertices directly AND returns the transform
            # It also returns transformed source points for use in subsequent steps
            transformation, translation, self.sourcePoints = logic.CPDAffineTransform(
                self.sourceModelNode,
                self.sourcePoints,
                self.targetPoints
            )

            # Create affine transform node for reference (model already transformed)
            matrix_vtk = vtk.vtkMatrix4x4()
            for i in range(3):
                for j in range(3):
                    matrix_vtk.SetElement(i, j, transformation[j][i])
            for i in range(3):
                matrix_vtk.SetElement(i, 3, translation[i])
            affineTransform = vtk.vtkTransform()
            affineTransform.SetMatrix(matrix_vtk)
            affineTransformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', "Affine_transform")
            affineTransformNode.SetAndObserveTransformToParent(affineTransform)

            affineNodeName = self.sourceModelName + "_affine"
            affineTransformNode.SetName(affineNodeName)

            # Chain transforms for reference: put rigid under affine
            if self.ICPTransformNode:
                self.ICPTransformNode.SetAndObserveTransformNodeID(affineTransformNode.GetID())

        # ============ DEFORMABLE REGISTRATION ============
        deformableTransformNode = None
        deformedModelNode = None
        if doDeformable:
            # The deformable step always produces a grid transform now. "Fast mode"
            # only controls how the deformed model itself is generated (direct
            # per-vertex warp vs. hardening the model through the grid).
            useFastMode = self.ui.fastModeCheckBox.checked

            with slicer.util.WaitCursor():
                slicer.app.processEvents()

                deformableTransformNode, deformedModelNode = logic.runDeformableRegistration(
                    self.sourceModelNode,
                    self.sourcePoints,
                    self.targetPoints,
                    self.parameterDictionary,
                    useFastMode
                )

            deformableTransformNode.SetName(self.sourceModelName + "_deformable")
            deformedModelNode.SetName(self.sourceModelName + "_deformed")

            # Display the deformed model
            green = [0, 1, 0]
            deformedModelNode.GetDisplayNode().SetColor(green)
            deformedModelNode.GetDisplayNode().SetVisibility(True)

            # The grid holds ONLY the deformable residual, expressed in post-linear
            # source space. Chain it above the linear transforms so the chain reads
            #   _scaling -> _rigid -> _affine -> _deformable -> (world)
            # and the leaf becomes the complete original-source -> target transform.
            parentMostLinearNode = (affineTransformNode or self.ICPTransformNode
                                    or self.scalingTransformNode)
            if parentMostLinearNode is not None:
                parentMostLinearNode.SetAndObserveTransformNodeID(deformableTransformNode.GetID())

        # ============ COMPOSITE SOURCE -> TARGET TRANSFORM ============
        # Leaf of the chain: the node the ORIGINAL (untouched) source model can be
        # placed under to land on the target.
        leafTransformNode = (self.scalingTransformNode or self.ICPTransformNode
                             or affineTransformNode or deformableTransformNode)
        if leafTransformNode is not None:
            # Describe, but do not rename: the existing node names are part of the
            # module's established behaviour and may be relied on by scripts.
            leafTransformNode.SetDescription(
                _("Complete transform from the original source model to the target model."))
            logging.info("FastModelAlign: complete source-to-target transform is "
                         f"'{leafTransformNode.GetName()}'")

            outputTransformNode = self.ui.outputTransformSelector.currentNode()
            if outputTransformNode is not None:
                # Flatten the whole chain so that a single node holds the complete
                # source -> target transform.
                compositeTransform = vtk.vtkGeneralTransform()
                leafTransformNode.GetTransformToWorld(compositeTransform)
                # A chain of purely linear steps still arrives here as a
                # vtkGeneralTransform, which vtkMRMLLinearTransformNode refuses (it
                # requires a vtkLinearTransform) - silently, via vtkErrorMacro. So
                # extract the matrix whenever the composite is in fact linear.
                concatenatedLinear = vtk.vtkTransform()
                isLinear = slicer.vtkMRMLTransformNode.IsGeneralTransformLinear(
                    compositeTransform, concatenatedLinear)
                if isLinear:
                    outputTransformNode.SetMatrixTransformToParent(concatenatedLinear.GetMatrix())
                elif outputTransformNode.IsA("vtkMRMLLinearTransformNode"):
                    slicer.util.warningDisplay(
                        _("The selected output transform node can only hold linear transforms, "
                          "so the deformable result was not copied into it. Use the transform "
                          "chain in the scene instead, or select a generic transform node."))
                else:
                    outputTransformNode.SetAndObserveTransformToParent(compositeTransform)

        # ============ OUTPUT MODEL ============
        red = [1, 0, 0]
        green = [0, 1, 0]
        if not doDeformable:
            # For rigid/affine only, use the working copy as output
            if bool(self.ui.outputSelector.currentNode()):
                self.outputModelNode = self.ui.outputSelector.currentNode()
                self.sourcePolyData = self.sourceModelNode.GetPolyData()
                self.outputModelNode.SetAndObservePolyData(self.sourcePolyData)
                self.outputModelNode.CreateDefaultDisplayNodes()
                self.outputModelNode.GetDisplayNode().SetVisibility(True)
                self.outputModelNode.GetDisplayNode().SetColor(red)
                # Clean up working copy
                slicer.mrmlScene.RemoveNode(self.sourceModelNode)
            else:
                # Use the working copy directly as the result
                self.sourceModelNode.SetName(self.sourceModelName + "_registered")
                self.sourceModelNode.GetDisplayNode().SetVisibility(True)
                self.sourceModelNode.GetDisplayNode().SetColor(red)
        else:
            # Deformable was done - copy deformed model to output selector if specified
            if bool(self.ui.outputSelector.currentNode()):
                self.outputModelNode = self.ui.outputSelector.currentNode()
                self.outputModelNode.SetAndObservePolyData(deformedModelNode.GetPolyData())
                self.outputModelNode.CreateDefaultDisplayNodes()
                self.outputModelNode.GetDisplayNode().SetVisibility(True)
                self.outputModelNode.GetDisplayNode().SetColor(green)
                # Remove the separately created deformed model since we copied to output
                slicer.mrmlScene.RemoveNode(deformedModelNode)
            # Clean up working copy
            slicer.mrmlScene.RemoveNode(self.sourceModelNode)

        # Make sure target is visible
        self.targetModelNode.GetDisplayNode().SetVisibility(True)


    def initializeParameterNode(self):
        """
        Ensure parameter node exists and observed.
        """

    def setParameterNode(self, inputParameterNode):
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """


    def updateGUIFromParameterNode(self, caller=None, event=None):
        """
        This method is called whenever parameter node is changed.
        The module GUI is updated to show the current state of the parameter node.
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return


    def updateParameterNodeFromGUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return


#
# FastModelAlignLogic
#

class ProgressHelper:
    """Helper class for showing progress during long operations."""

    def __init__(self, title="Processing"):
        self.progressDialog = None
        self.title = title

    def start(self, message="Starting...", maxValue=100):
        """Start showing progress dialog."""
        self.progressDialog = slicer.util.createProgressDialog(
            windowTitle=self.title,
            labelText=message,
            maximum=maxValue
        )
        self.progressDialog.setCancelButton(None)  # Disable cancel for now
        slicer.app.processEvents()

    def update(self, value, message=None):
        """Update progress value and optionally the message."""
        if self.progressDialog:
            self.progressDialog.setValue(value)
            if message:
                self.progressDialog.setLabelText(message)
            slicer.app.processEvents()

    def finish(self):
        """Close the progress dialog."""
        if self.progressDialog:
            self.progressDialog.close()
            self.progressDialog = None
            slicer.app.processEvents()


class FastModelAlignLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self):
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)
        self.progress = None


    def ITKRegistration(self, sourceModelNode, targetModelNode, scalingOption, parameterDictionary, usePoisson):
        import ALPACA

        titleText = "Rigid Registration" + (" with Scaling" if scalingOption else "")
        self.progress = ProgressHelper(titleText)
        self.progress.start("Subsampling point clouds...", 100)

        logic = ALPACA.ALPACALogic()
        (
            sourcePoints,
            targetPoints,
            sourceFeatures,
            targetFeatures,
            voxelSize,
            scaling,
        ) = logic.runSubsample(
            sourceModelNode,
            targetModelNode,
            scalingOption,
            parameterDictionary,
            usePoisson,
        )

        if scalingOption:
            self.progress.update(30, f"Creating scaling transform (factor: {scaling:.4f})...")
        else:
            self.progress.update(30, "Preparing transform...")

        #Scaling transform
        print("scaling factor for the source is: " + str(scaling))
        scalingMatrix_vtk = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                scalingMatrix_vtk.SetElement(i,j,0)
        for i in range(3):
            scalingMatrix_vtk.SetElement(i, i, scaling)
        scalingTransform = vtk.vtkTransform()
        scalingTransform.SetMatrix(scalingMatrix_vtk)
        scalingTransformNode =  slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', "scaling_transform_matrix")
        scalingTransformNode.SetAndObserveTransformToParent(scalingTransform)

        self.progress.update(40, "Estimating rigid transform...")

        ICPTransform_similarity, similarityFlag = logic.estimateTransform(
            sourcePoints,
            targetPoints,
            sourceFeatures,
            targetFeatures,
            voxelSize,
            scalingOption,
            parameterDictionary,
        )

        self.progress.update(80, "Applying transform...")

        vtkSimilarityTransform = logic.itkToVTKTransform(
            ICPTransform_similarity, similarityFlag
        )

        ICPTransformNode = logic.convertMatrixToTransformNode(
            vtkSimilarityTransform, ("Rigid Transformation Matrix")
        )
        sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)
        sourceModelNode.GetDisplayNode().SetVisibility(True)
        red = [1, 0, 0]
        sourceModelNode.GetDisplayNode().SetColor(red)
        targetModelNode.GetDisplayNode().SetVisibility(True)

        sourcePoints = logic.transform_numpy_points(sourcePoints, ICPTransform_similarity)


        #Put scaling transform under ICP transform = rigid transform after scaling
        scalingTransformNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())

        self.progress.update(100, "Rigid registration complete.")
        self.progress.finish()

        return sourcePoints, targetPoints, scalingTransformNode, ICPTransformNode, voxelSize

    def CPDAffineTransform(self, sourceModelNode, sourcePoints, targetPoints):
       from cpdalp import AffineRegistration

       self.progress = ProgressHelper("Affine Registration")
       self.progress.start("Running CPD affine registration...", 100)

       polyData = sourceModelNode.GetPolyData()
       points = polyData.GetPoints()
       numpyModel = vtk_np.vtk_to_numpy(points.GetData())

       self.progress.update(20, "Optimizing affine parameters...")
       reg = AffineRegistration(**{'X': targetPoints, 'Y': sourcePoints, 'low_rank':True})
       reg.register()

       self.progress.update(70, "Transforming model vertices...")
       TY = reg.transform_point_cloud(numpyModel)
       vtkArray = vtk_np.numpy_to_vtk(TY)
       points.SetData(vtkArray)
       polyData.Modified()

       # Also transform the source points for use in subsequent steps
       transformedSourcePoints = reg.transform_point_cloud(sourcePoints)

       affine_matrix, translation = reg.get_registration_parameters()

       self.progress.update(100, "Affine registration complete.")
       self.progress.finish()

       return affine_matrix, translation, transformedSourcePoints

    # ------------------------------------------------------------------
    # Deformable registration
    # ------------------------------------------------------------------

    # Displacement-grid safety limits.
    MAX_GRID_POINTS = 5000000
    MIN_GRID_SAMPLES_PER_AXIS = 8

    # BCPD invocation. -A enables the Nystrom + KD-tree acceleration, which is what
    # makes the external binary roughly two orders of magnitude faster than cpdalp
    # (3.8 s vs 237 s on a 1.78M -> 1.01M vertex skull pair, at the same accuracy).
    # -l (lambda) and -b (beta) are driven by the module's alpha/beta sliders, the
    # same mapping ALPACA uses. The rest are the values validated on real specimen
    # data; in particular BCPD's own convergence settings (-n/-c) are used rather
    # than the CPD iteration/tolerance sliders, which only drive the cpdalp path.
    BCPD_FIXED_ARGUMENTS = ["-w0.1", "-g0.1", "-ux", "-n200", "-c1e-6", "-A"]

    # The registration runs on the main thread, so a wedged external binary would
    # otherwise hang the application with no way to cancel. Timing out raises, and
    # the caller treats any BCPD failure as a signal to fall back to cpdalp.
    BCPD_TIMEOUT_SECONDS = 600

    def runDeformableRegistration(self, sourceModelNode, sourcePoints, targetPoints,
                                  parameters, fastMode=True):
        """Run the deformable step and return (gridTransformNode, deformedModelNode).

        The returned grid transform holds ONLY the deformable residual, sampled over
        the region shared by the post-linear source and the target. It is meant to be
        chained above the linear transform nodes by the caller. Keeping the linear
        part out of the grid keeps the grid small (~1e5 samples) and keeps its
        iterative inverse well behaved, so a single node works in both directions.

        `fastMode` only selects how the deformed model is produced: True warps the
        mesh vertices directly with the RBF, False hardens the mesh through the grid.
        Both modes create the grid transform.
        """
        from scipy.interpolate import RBFInterpolator

        self.progress = ProgressHelper(_("Deformable Registration"))
        self.progress.start(_("Normalizing point clouds..."), 100)

        # Normalize point clouds for CPD (same convention as ALPACA): map the
        # combined bounding box into [0, 25].
        allPoints = np.vstack([sourcePoints, targetPoints])
        cloudMin = np.min(allPoints, axis=0)
        cloudMax = np.max(allPoints, axis=0)
        cloudSize = cloudMax - cloudMin
        cloudSize[cloudSize == 0] = 1.0  # guard against a degenerate (planar) axis

        targetNorm = (targetPoints - cloudMin) * 25 / cloudSize
        sourceNorm = (sourcePoints - cloudMin) * 25 / cloudSize

        self.progress.update(10, _("Running deformable registration on {count} source points...").format(
            count=len(sourcePoints)))
        deformedSourceNorm = self.runCPDDeformable(sourceNorm, targetNorm, parameters)

        self.progress.update(45, _("Building RBF interpolator..."))
        # thin_plate_spline is smooth and extrapolates gracefully outside the cloud.
        rbf = RBFInterpolator(
            sourceNorm,
            deformedSourceNorm - sourceNorm,
            kernel='thin_plate_spline',
            smoothing=0.1
        )

        self.progress.update(55, _("Creating deformable grid transform..."))
        # The grid has to cover the post-linear source mesh (it is what gets hardened)
        # and the target region (so the inverse is defined there as well).
        boundsList = [
            sourceModelNode.GetPolyData().GetBounds(),
            self.pointsToBounds(sourcePoints),
            self.pointsToBounds(targetPoints),
        ]
        gridTransformNode = self.createGridTransformFromRBF(
            rbf, cloudMin, cloudSize, boundsList, parameters.get("gridSpacing", 1.0)
        )

        if fastMode:
            self.progress.update(85, _("Warping model vertices..."))
            deformedModelNode = self.createDeformedModelFromRBF(
                sourceModelNode, rbf, cloudMin, cloudSize)
        else:
            self.progress.update(85, _("Creating hardened deformed model..."))
            deformedModelNode = self.createHardenedModel(sourceModelNode, gridTransformNode)

        self.progress.update(100, _("Deformable registration complete."))
        self.progress.finish()

        return gridTransformNode, deformedModelNode

    def CPDDeformableTransformDirect(self, sourceModelNode, sourcePoints, targetPoints, parameters):
        """Backward-compatible wrapper around runDeformableRegistration (fast mode).
        Returns only the deformed model node; the grid transform node is still
        created and left in the scene.
        """
        return self.runDeformableRegistration(
            sourceModelNode, sourcePoints, targetPoints, parameters, True)[1]

    def CPDDeformableTransformGrid(self, sourceModelNode, sourcePoints, targetPoints,
                                   voxelSize, parameters):
        """Backward-compatible wrapper around runDeformableRegistration (grid mode).
        `voxelSize` is unused: the grid spacing comes from parameters["gridSpacing"].
        """
        del voxelSize
        return self.runDeformableRegistration(
            sourceModelNode, sourcePoints, targetPoints, parameters, False)

    def runCPDDeformable(self, sourceNorm, targetNorm, parameters):
        """Compute the deformable correspondence for the normalized point clouds.

        Uses the external BCPD binary when acceleration is enabled and configured,
        and falls back to the pure-python cpdalp implementation otherwise, or if the
        external run fails for any reason. Returns the deformed source points in the
        same normalized space as the inputs.
        """
        useAcceleration = bool(parameters.get("Acceleration", False))
        bcpdFolder = parameters.get("BCPDFolder", "")
        if useAcceleration:
            if self.isValidBCPDPath(bcpdFolder):
                try:
                    return self.runBCPDDeformable(sourceNorm, targetNorm, bcpdFolder, parameters)
                except Exception as e:
                    logging.warning(
                        f"BCPD deformable registration failed, falling back to cpdalp: {e}")
            else:
                logging.warning(
                    "BCPD acceleration requested but the configured directory is not valid; using cpdalp")
        return self.runCpdalpDeformable(sourceNorm, targetNorm, parameters)

    def runCpdalpDeformable(self, sourceNorm, targetNorm, parameters):
        """Deformable CPD using the cpdalp python package."""
        from cpdalp import DeformableRegistration

        reg = DeformableRegistration(
            **{
                'X': targetNorm,
                'Y': sourceNorm,
                'max_iterations': parameters["CPDIterations"],
                'tolerance': parameters["CPDTolerance"],
                'low_rank': True
            },
            alpha=parameters["alpha"],
            beta=parameters["beta"]
        )
        reg.register()
        return np.asarray(reg.TY, dtype=np.float64)

    def runBCPDDeformable(self, sourceNorm, targetNorm, bcpdFolder, parameters):
        """Deformable registration using the external BCPD binary.

        BCPD requires its input files to carry a .txt extension. They are written as
        comma-delimited text into a private temporary directory that also collects
        BCPD's own output files (default 'output_' prefix, hence the cwd), and which
        is removed again afterwards.
        """
        executableName = "bcpd.exe" if slicer.app.os == "win" else "bcpd"
        executablePath = os.path.join(bcpdFolder, executableName)

        workingDirectory = tempfile.mkdtemp(prefix="FastModelAlign_bcpd_",
                                            dir=slicer.app.temporaryPath)
        try:
            targetPath = os.path.join(workingDirectory, "target.txt")
            sourcePath = os.path.join(workingDirectory, "source.txt")
            np.savetxt(targetPath, np.asarray(targetNorm, dtype=np.float64), delimiter=",")
            np.savetxt(sourcePath, np.asarray(sourceNorm, dtype=np.float64), delimiter=",")

            command = ([executablePath, "-x", targetPath, "-y", sourcePath,
                        f"-l{float(parameters['alpha']):g}",
                        f"-b{float(parameters['beta']):g}"]
                       + list(self.BCPD_FIXED_ARGUMENTS))
            logging.info("FastModelAlign: running " + " ".join(command))
            try:
                completed = subprocess.run(command, check=True, text=True,
                                           capture_output=True, cwd=workingDirectory,
                                           timeout=self.BCPD_TIMEOUT_SECONDS)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    f"BCPD exited with code {e.returncode}: {(e.stderr or '').strip()}")
            except subprocess.TimeoutExpired:
                # subprocess.run kills the child before re-raising.
                raise RuntimeError(
                    f"BCPD did not finish within {self.BCPD_TIMEOUT_SECONDS} s and was terminated")
            if completed.stderr:
                logging.info(f"BCPD stderr: {completed.stderr.strip()}")

            deformedPath = os.path.join(workingDirectory, "output_y.txt")
            if not os.path.exists(deformedPath):
                raise RuntimeError(f"BCPD did not write the expected output file {deformedPath}")
            deformed = np.loadtxt(deformedPath)
        finally:
            shutil.rmtree(workingDirectory, ignore_errors=True)

        deformed = np.asarray(deformed, dtype=np.float64).reshape(-1, 3)
        if deformed.shape[0] != np.asarray(sourceNorm).shape[0]:
            raise RuntimeError(f"BCPD returned {deformed.shape[0]} points for "
                               f"{np.asarray(sourceNorm).shape[0]} input points")
        return deformed

    @staticmethod
    def pointsToBounds(points):
        """Return VTK-style bounds (xmin, xmax, ymin, ymax, zmin, zmax) of an (n, 3) array."""
        pointsArray = np.asarray(points, dtype=np.float64)
        lower = np.min(pointsArray, axis=0)
        upper = np.max(pointsArray, axis=0)
        return (lower[0], upper[0], lower[1], upper[1], lower[2], upper[2])

    def computeGridGeometry(self, boundsList, requestedSpacing):
        """Compute (origin, dims, spacing) for an isotropic displacement grid.

        The grid spans the union of the supplied VTK-style bounds and is padded by
        3 * spacing on every side, which keeps the cubic interpolation well defined
        near the border.

        `requestedSpacing` is the sample spacing in millimeters coming from the GUI
        (the old "grid density" slider used to be mapped through int(256/value),
        which saturated at 64 samples for any value above 4 and therefore did
        nothing). It is only adjusted here when it would give a uselessly coarse
        grid (fewer than MIN_GRID_SAMPLES_PER_AXIS samples across the largest axis)
        or a grid larger than MAX_GRID_POINTS samples.
        """
        boundsArray = np.asarray(boundsList, dtype=np.float64).reshape(-1, 6)
        lower = np.min(boundsArray[:, [0, 2, 4]], axis=0)
        upper = np.max(boundsArray[:, [1, 3, 5]], axis=0)
        extentSize = np.maximum(upper - lower, 0.0)
        maxExtent = float(np.max(extentSize))
        if maxExtent <= 0.0:
            maxExtent = 1.0

        spacing = float(requestedSpacing)
        if spacing <= 0.0:
            spacing = maxExtent / 100.0
        spacing = min(spacing, maxExtent / self.MIN_GRID_SAMPLES_PER_AXIS)

        origin = lower
        dims = [2, 2, 2]
        for attempt in range(8):
            padding = 3.0 * spacing
            origin = lower - padding
            paddedSize = extentSize + 2.0 * padding
            dims = [int(np.ceil(paddedSize[i] / spacing)) + 1 for i in range(3)]
            totalPoints = dims[0] * dims[1] * dims[2]
            if totalPoints <= self.MAX_GRID_POINTS:
                break
            # Coarsen isotropically until the grid fits within the sample budget.
            spacing *= (float(totalPoints) / self.MAX_GRID_POINTS) ** (1.0 / 3.0)
            logging.warning(f"FastModelAlign: displacement grid of {totalPoints} samples exceeds "
                            f"the budget (attempt {attempt + 1}), coarsening spacing "
                            f"to {spacing:.4f} mm")

        return origin, dims, spacing

    def createGridTransformFromRBF(self, rbf, cloudMin, cloudSize, boundsList,
                                   requestedSpacing, nodeName="Deformable Transform"):
        """Create a vtkMRMLGridTransformNode holding the deformable displacement field.

        The RBF was fitted in the normalized ([0, 25]) space used by the CPD step, so
        grid samples are normalized before evaluation and the resulting displacements
        are converted back to world units.

        Layout follows Slicer's arrayFromGridTransform convention, mirroring
        GPA/Support/vtk_lib.py::buildDisplacementGridFromTPS:
          * vtkGridTransform reads the field from point-data SCALARS. Storing it as
            vectors makes it invisible and the transform an exact identity.
          * vtkImageData points are laid out x-fastest, so the numpy field is shaped
            (k, j, i, component).
          * The array is float (VTK_FLOAT), matching what Slicer/ITK produce.

        A vtkOrientedGridTransform is used instead of a plain vtkGridTransform because
        only the oriented variant can be written out by vtkMRMLGridTransformNode. It
        lives in the slicer (and vtkAddon) namespace, not in vtk.
        """
        origin, dims, spacing = self.computeGridGeometry(boundsList, requestedSpacing)
        totalGridPoints = dims[0] * dims[1] * dims[2]
        logging.info(f"FastModelAlign: displacement grid {dims[0]}x{dims[1]}x{dims[2]} "
                     f"({totalGridPoints} samples), spacing {spacing:.4f} mm")

        x = origin[0] + spacing * np.arange(dims[0], dtype=np.float64)
        y = origin[1] + spacing * np.arange(dims[1], dtype=np.float64)
        z = origin[2] + spacing * np.arange(dims[2], dtype=np.float64)

        # VTK image points are ordered x-fastest, then y, then z.
        Zg, Yg, Xg = np.meshgrid(z, y, x, indexing="ij")
        gridPoints = np.column_stack([Xg.ravel(), Yg.ravel(), Zg.ravel()])

        if self.progress:
            self.progress.update(65, _("Interpolating displacements to {count} grid samples...").format(
                count=totalGridPoints))

        gridPointsNorm = (gridPoints - cloudMin) * 25 / cloudSize
        displacements = rbf(gridPointsNorm) * cloudSize / 25

        # (k, j, i, component), i.e. the same layout slicer.util.arrayFromGridTransform uses.
        field = np.ascontiguousarray(
            displacements.reshape(dims[2], dims[1], dims[0], 3), dtype=np.float32)

        displImage = vtk.vtkImageData()
        displImage.SetDimensions(int(dims[0]), int(dims[1]), int(dims[2]))
        displImage.SetOrigin(float(origin[0]), float(origin[1]), float(origin[2]))
        displImage.SetSpacing(spacing, spacing, spacing)

        displArray = vtk_np.numpy_to_vtk(field.reshape(-1, 3), deep=True, array_type=vtk.VTK_FLOAT)
        displArray.SetName("DisplacementField")
        displImage.GetPointData().SetScalars(displArray)

        gridTransform = slicer.vtkOrientedGridTransform()
        gridTransform.SetDisplacementGridData(displImage)
        gridTransform.SetInterpolationModeToCubic()

        gridTransformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLGridTransformNode', nodeName)
        # Forward field (post-linear source -> target), so hardening a node through
        # this transform moves the data from source towards target.
        gridTransformNode.SetAndObserveTransformToParent(gridTransform)

        return gridTransformNode

    def createDeformedModelFromRBF(self, sourceModelNode, rbf, cloudMin, cloudSize):
        """Warp the model vertices directly with the RBF displacement field."""
        polyData = sourceModelNode.GetPolyData()
        numpyModel = vtk_np.vtk_to_numpy(polyData.GetPoints().GetData()).astype(np.float64)
        numpyModelNorm = (numpyModel - cloudMin) * 25 / cloudSize
        deformedModel = numpyModel + rbf(numpyModelNorm) * cloudSize / 25

        deformedPolyData = vtk.vtkPolyData()
        deformedPolyData.DeepCopy(polyData)
        deformedPoints = vtk.vtkPoints()
        deformedPoints.SetData(vtk_np.numpy_to_vtk(
            np.ascontiguousarray(deformedModel), deep=True))
        deformedPolyData.SetPoints(deformedPoints)

        deformedModelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', 'Deformed Model')
        deformedModelNode.SetAndObservePolyData(deformedPolyData)
        deformedModelNode.CreateDefaultDisplayNodes()
        self.copyDisplayProperties(sourceModelNode, deformedModelNode)

        return deformedModelNode

    def copyDisplayProperties(self, sourceModelNode, deformedModelNode):
        """Copy color/opacity from the source model display node, if there is one."""
        sourceDisplayNode = sourceModelNode.GetDisplayNode()
        deformedDisplayNode = deformedModelNode.GetDisplayNode()
        if sourceDisplayNode and deformedDisplayNode:
            deformedDisplayNode.SetColor(sourceDisplayNode.GetColor())
            deformedDisplayNode.SetOpacity(sourceDisplayNode.GetOpacity())
            deformedDisplayNode.SetVisibility(True)

    # ------------------------------------------------------------------
    # BCPD configuration (persisted in QSettings)
    # ------------------------------------------------------------------

    def saveBCPDPath(self, BCPDPath):
        """Persist the BCPD directory.

        The QSettings key is deliberately the same one ALPACA uses, so the binary
        only has to be located once for both modules.
        """
        settings = qt.QSettings()
        if settings.contains("Developer/BCPDPath"):
            if settings.value("Developer/BCPDPath") == BCPDPath:
                return
        if not self.isValidBCPDPath(BCPDPath):
            return
        settings.setValue("Developer/BCPDPath", BCPDPath)

    def getBCPDPath(self):
        """Return the persisted BCPD directory, or an empty string if unusable."""
        settings = qt.QSettings()
        if settings.contains("Developer/BCPDPath"):
            BCPDPath = settings.value("Developer/BCPDPath")
            if self.isValidBCPDPath(BCPDPath):
                return BCPDPath
        return ""

    def saveAccelerationEnabled(self, enabled):
        """Persist whether the acceleration checkbox is enabled (module-specific key)."""
        qt.QSettings().setValue("Developer/FastModelAlignAcceleration",
                                "true" if enabled else "false")

    def getAccelerationEnabled(self):
        """Return the persisted acceleration checkbox state (default False)."""
        settings = qt.QSettings()
        if settings.contains("Developer/FastModelAlignAcceleration"):
            return str(settings.value("Developer/FastModelAlignAcceleration")).lower() == "true"
        return False

    def isValidBCPDPath(self, BCPDPath):
        """Return True if BCPDPath is a directory containing the BCPD executable."""
        if not BCPDPath or not os.path.isdir(BCPDPath):
            return False
        executableName = "bcpd.exe" if slicer.app.os == "win" else "bcpd"
        return os.path.exists(os.path.join(BCPDPath, executableName))

    def createHardenedModel(self, sourceModelNode, transformNode):
        """Create a copy of the model with the transform hardened."""
        # Clone the model
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        itemIDToClone = shNode.GetItemByDataNode(sourceModelNode)
        clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
        deformedModelNode = shNode.GetItemDataNode(clonedItemID)
        deformedModelNode.SetName("Deformed Model (hardened)")

        # Apply and harden transform
        deformedModelNode.SetAndObserveTransformNodeID(transformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(deformedModelNode)

        # Ensure display node exists and copy properties from source
        if not deformedModelNode.GetDisplayNode():
            deformedModelNode.CreateDefaultDisplayNodes()
        self.copyDisplayProperties(sourceModelNode, deformedModelNode)

        return deformedModelNode





#
# FastModelAlignTest
#

class FastModelAlignTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_FastModelAlign1()

    def test_FastModelAlign1(self):
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
        SampleData.downloadSample('Partial photogrammetry models')
        self.delayDisplay('Loaded test data set')

        # Test the module logic
        try:
            self.sourceModelNode.GetDisplayNode().SetVisibility(False)
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)  # Remove targe cloud node created in the subsampling to avoid confusion
                self.targetCloudNodeTest = None
        except:
            pass

        # sourcePath_test = slicer.app.cachePath + "/partial_photogram_model2.obj"
        # self.sourceModelNode_orig_test = slicer.util.loadModel(sourcePath_test)
        self.sourceModelNode_orig_test = slicer.util.getNode("partial_photogram_model2_1")
        self.sourceModelNode_orig_test.GetDisplayNode().SetVisibility(False)
        self.sourceModelName_test = self.sourceModelNode_orig_test.GetName()

        # Clone the original source mesh stored in the node sourceModelNode_orig
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(
            slicer.mrmlScene
        )
        itemIDToClone = shNode.GetItemByDataNode(self.sourceModelNode_orig_test)
        clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(
            shNode, itemIDToClone
        )
        self.sourceModelNode_test = shNode.GetItemDataNode(clonedItemID)
        self.sourceModelNode_test.GetDisplayNode().SetVisibility(True)
        self.sourceModelNode_test.SetName(self.sourceModelName_test + "_registered")  # Create a cloned source model node

        # targetPath_test = slicer.app.cachePath + "/partial_photogram_model1.obj"
        # self.targetModelNode_test = slicer.util.loadModel(targetPath_test)
        self.targetModelNode_test = slicer.util.getNode("partial_photogram_model1_1")
        self.targetModelNode_test.GetDisplayNode().SetVisibility(True)
        logic = FastModelAlignLogic()

        self.parameterDictionary_test = {
            "pointDensity": 1.00,
            "normalSearchRadius": 2.00,
            "FPFHNeighbors": int(100),
            "FPFHSearchRadius": 5.00,
            "distanceThreshold": 3.00,
            "maxRANSAC": int(1000000),
            "ICPDistanceThreshold": float(1.50)
            }


        self.sourcePoints_test, self.targetPoints_test, self.scalingTransformNode_test, self.ICPTransformNode_test, self.voxelSize_test = logic.ITKRegistration(self.sourceModelNode_test, self.targetModelNode_test, False,
            self.parameterDictionary_test, True)

        scalingNodeName_test = self.sourceModelName_test + "_scaling_test"
        rigidNodeName_test = self.sourceModelName_test + "_rigid_test"
        self.scalingTransformNode_test.SetName(scalingNodeName_test)
        self.ICPTransformNode_test.SetName(rigidNodeName_test)

        red = [1, 0, 0]
        self.sourceModelNode_test.GetDisplayNode().SetColor(red)

        self.delayDisplay('Test passed')
