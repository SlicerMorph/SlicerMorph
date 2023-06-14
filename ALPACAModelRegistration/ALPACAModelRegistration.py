import logging
import os

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


#
# ALPACAModelRegistration
#

class ALPACAModelRegistration(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "ALPACAModelRegistration"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["Examples"]  # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Chi Zhang (SCRI)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#ALPACAModelRegistration">module documentation</a>.
"""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

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

    # ALPACAModelRegistration1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='ALPACAModelRegistration',
        sampleName='ALPACAModelRegistration1',
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, 'ALPACAModelRegistration1.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames='ALPACAModelRegistration1.nrrd',
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums='SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
        # This node name will be used when the data set is loaded
        nodeNames='ALPACAModelRegistration1'
    )

    # ALPACAModelRegistration2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='ALPACAModelRegistration',
        sampleName='ALPACAModelRegistration2',
        thumbnailFileName=os.path.join(iconsPath, 'ALPACAModelRegistration2.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames='ALPACAModelRegistration2.nrrd',
        checksums='SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
        # This node name will be used when the data set is loaded
        nodeNames='ALPACAModelRegistration2'
    )


#
# ALPACAModelRegistrationWidget
#

class ALPACAModelRegistrationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/ALPACAModelRegistration.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = ALPACAModelRegistrationLogic()

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
        #run subsampling
        self.ui.pointDensitySlider.connect('valueChanged(double)', self.onChangeDensitySingle)
        self.ui.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)
        # Buttons
        self.ui.runRegistrationButton.connect('clicked(bool)', self.onApplyButton)

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

        # initialize the parameter dictionary from single run parameters
        self.parameterDictionary = {
            "pointDensity": self.ui.pointDensityAdvancedSlider.value,
            "normalSearchRadius": self.ui.normalSearchRadiusSlider.value,
            "FPFHNeighbors": int(self.ui.FPFHNeighborsSlider.value),
            "FPFHSearchRadius": self.ui.FPFHSearchRadiusSlider.value,
            "distanceThreshold": self.ui.maximumCPDThreshold.value,
            "maxRANSAC": int(self.ui.maxRANSAC.value),
            "ICPDistanceThreshold": float(self.ui.ICPDistanceThresholdSlider.value)
            }


    def onSelect(self):
        #Enable subsampling pointcloud button
        self.ui.subsampleButton.enabled = bool(self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode())
        #Enable run registration button
        self.ui.runRegistrationButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode())

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

    def onSubsampleButton(self):
        try:
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)
                self.targetCloudNodeTest = None
        except:
            pass
        import ALPACA_preview
        logic = ALPACA_preview.ALPACALogic()
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
        # self.ui.sourceLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(
        #     False
        # )

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
            self.ui.skipScalingCheckBox.checked,
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

        # self.ui.runALPACAButton.enabled = True
        # if bool(self.ui.targetLandmarkSetSelector.currentNode()) == True:
        #     self.ui.targetLandmarkSetSelector.currentNode().GetDisplayNode().SetVisibility(
        #         False
        #     )
        # try:
        #     self.manualLMNode.GetDisplayNode().SetVisibility(False)
        # except:
        #     pass

    def runALPACACounter(self, run_counter=[0]):
        run_counter[0] += 1
        return str(run_counter[0])


    def onApplyButton(self):
        """
        Run processing when user clicks "Apply" button.
        """
        try:
            self.sourceModelNode.GetDisplayNode().SetVisibility(False)
            if self.targetCloudNodeTest is not None:
                slicer.mrmlScene.RemoveNode(self.targetCloudNodeTest)  # Remove targe cloud node created in the subsampling to avoid confusion
                self.targetCloudNodeTest = None
        except:
            pass

        run_counter = self.runALPACACounter()
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

        self.targetModelNode = self.ui.targetModelSelector.currentNode()
        logic = ALPACAModelRegistrationLogic()
        
        # if self.ui.methodComboBox.currentText == "Open3D":
        #   logic.o3dRegistration(self.sourceModelNode, self.targetModelNode)
        
        # else:
        print("skip scaling option is: " + str(self.ui.skipScalingCheckBox.checked))
        logic.ITKRegistration(self.sourceModelNode, self.targetModelNode, self.ui.skipScalingCheckBox.checked,
            self.parameterDictionary, self.ui.poissonSubsampleCheckBox.checked, run_counter)


    def initializeParameterNode(self):
        """
        Ensure parameter node exists and observed.
        """
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        # self.setParameterNode(self.logic.getParameterNode())
        # 
        # # Select default input nodes if nothing is selected yet to save a few clicks for the user
        # if not self._parameterNode.GetNodeReference("InputVolume"):
        #     firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
        #     if firstVolumeNode:
        #         self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())

    def setParameterNode(self, inputParameterNode):
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        # if inputParameterNode:
        #     self.logic.setDefaultParameters(inputParameterNode)
        # 
        # # Unobserve previously selected parameter node and add an observer to the newly selected.
        # # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
        # # those are reflected immediately in the GUI.
        # if self._parameterNode is not None and self.hasObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode):
        #     self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
        # self._parameterNode = inputParameterNode
        # if self._parameterNode is not None:
        #     self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
        # 
        # # Initial GUI update
        # self.updateGUIFromParameterNode()

    def updateGUIFromParameterNode(self, caller=None, event=None):
        """
        This method is called whenever parameter node is changed.
        The module GUI is updated to show the current state of the parameter node.
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        # self._updatingGUIFromParameterNode = True
        # 
        # # Update node selectors and sliders
        # self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
        # self.ui.outputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolume"))
        # self.ui.invertedOutputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolumeInverse"))
        # self.ui.imageThresholdSliderWidget.value = float(self._parameterNode.GetParameter("Threshold"))
        # self.ui.invertOutputCheckBox.checked = (self._parameterNode.GetParameter("Invert") == "true")
        # 
        # # Update buttons states and tooltips
        # if self._parameterNode.GetNodeReference("InputVolume") and self._parameterNode.GetNodeReference("OutputVolume"):
        #     self.ui.applyButton.toolTip = "Compute output volume"
        #     self.ui.applyButton.enabled = True
        # else:
        #     self.ui.applyButton.toolTip = "Select input and output volume nodes"
        #     self.ui.applyButton.enabled = False
        # 
        # # All the GUI updates are done
        # self._updatingGUIFromParameterNode = False

    def updateParameterNodeFromGUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch
        # 
        # self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
        # self._parameterNode.SetNodeReferenceID("OutputVolume", self.ui.outputSelector.currentNodeID)
        # self._parameterNode.SetParameter("Threshold", str(self.ui.imageThresholdSliderWidget.value))
        # self._parameterNode.SetParameter("Invert", "true" if self.ui.invertOutputCheckBox.checked else "false")
        # self._parameterNode.SetNodeReferenceID("OutputVolumeInverse", self.ui.invertedOutputSelector.currentNodeID)
        # 
        # self._parameterNode.EndModify(wasModified)
          

#
# ALPACAModelRegistrationLogic
#

class ALPACAModelRegistrationLogic(ScriptedLoadableModuleLogic):
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

    def o3dRegistration(self, sourceModelNode, targetModelNode):
        import ALPACA
        logic = ALPACA.ALPACALogic()
        parameterDictionary = ALPACA.ALPACAWidget().parameterDictionary
        skipScalingOption = False
        sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, scaling = logic.runSubsample(sourceModelNode, targetModelNode,
          skipScalingOption, parameterDictionary)
        ICPTransform = logic.estimateTransform(sourcePoints, targetPoints, sourceFeatures, targetFeatures, voxelSize, skipScalingOption, parameterDictionary)
        ICPTransformNode = logic.convertMatrixToTransformNode(ICPTransform, 'Rigid Transformation Matrix')
        sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)


    def ITKRegistration(self, sourceModelNode, targetModelNode, skipScalingOption, parameterDictionary, usePoisson, run_counter):
        import ALPACA_preview
        logic = ALPACA_preview.ALPACALogic()
        # parameterDictionary = ALPACA_preview.ALPACA_previewWidget().parameterDictionary
        # skipScalingOption = False
        # usePoisson = False
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
            skipScalingOption,
            parameterDictionary,
            usePoisson,
        )
        ICPTransform_similarity, similarityFlag = logic.estimateTransform(
            sourcePoints,
            targetPoints,
            sourceFeatures,
            targetFeatures,
            voxelSize,
            skipScalingOption,
            parameterDictionary,
        )
    
        vtkSimilarityTransform = logic.itkToVTKTransform(
            ICPTransform_similarity, similarityFlag
        )
        ICPTransformNode = logic.convertMatrixToTransformNode(
            vtkSimilarityTransform, ("Rigid Transformation Matrix " + run_counter)
        )
        # slicer.mrmlScene.AddNode(ICPTransformNode)
        sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
        slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)
        sourceModelNode.GetDisplayNode().SetVisibility(True)
        red = [1, 0, 0]
        sourceModelNode.GetDisplayNode().SetColor(red)
        targetModelNode.GetDisplayNode().SetVisibility(True)

#
# ALPACAModelRegistrationTest
#

class ALPACAModelRegistrationTest(ScriptedLoadableModuleTest):
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
        self.test_ALPACAModelRegistration1()

    def test_ALPACAModelRegistration1(self):
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
        inputVolume = SampleData.downloadSample('ALPACAModelRegistration1')
        self.delayDisplay('Loaded test data set')

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = ALPACAModelRegistrationLogic()

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
