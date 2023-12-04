import logging
import os

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


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
        self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]  # TODO: set categories (folders where the module shows up in the module selector)
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

        # Install required packages by running Alpaca setup
        try:
          from itk import Fpfh
          import cpdalp
        except ModuleNotFoundError:
          slicer.util.selectModule(slicer.modules.alpaca)
          slicer.util.selectModule(slicer.modules.fastmodelalign)

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
        #run subsampling
        self.ui.pointDensitySlider.connect('valueChanged(double)', self.onChangeDensitySingle)
        self.ui.subsampleButton.connect('clicked(bool)', self.onSubsampleButton)
        # Buttons
        self.ui.runRigidRegistrationButton.connect('clicked(bool)', self.onApplyButton)
        self.ui.runCPDAffineButton.connect('clicked(bool)', self.onRunCPDAffineButton)


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
        self.ui.subsampleButton.enabled = bool(self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.outputSelector.currentNode())
        #Enable run registration button
        self.ui.runRigidRegistrationButton.enabled = bool ( self.ui.sourceModelSelector.currentNode() and self.ui.targetModelSelector.currentNode() and self.ui.outputSelector.currentNode())

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
            self.ui.skipScalingCheckBox.checked,
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

        self.sourceModelNode_orig = self.ui.sourceModelSelector.currentNode()
        self.sourceModelNode_orig.GetDisplayNode().SetVisibility(False)

        self.sourceModelName = self.sourceModelNode_orig.GetName()

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
        self.sourceModelNode.SetName("Source model(rigidly registered)")  # Create a cloned source model node

        self.targetModelNode = self.ui.targetModelSelector.currentNode()
        logic = FastModelAlignLogic()

        self.sourcePoints, self.targetPoints, self.scalingTransformNode, self.ICPTransformNode = logic.ITKRegistration(self.sourceModelNode, self.targetModelNode, self.ui.skipScalingCheckBox.checked,
            self.parameterDictionary, self.ui.poissonSubsampleCheckBox.checked)

        scalingNodeName = self.sourceModelName + "_scaling"
        rigidNodeName = self.sourceModelName + "_rigid"
        self.scalingTransformNode.SetName(scalingNodeName)
        self.ICPTransformNode.SetName(rigidNodeName)

        red = [1, 0, 0]
        if bool(self.ui.outputSelector.currentNode()):
            self.outputModelNode = self.ui.outputSelector.currentNode()
            self.sourcePolyData = self.sourceModelNode.GetPolyData()
            self.outputModelNode.SetAndObservePolyData(self.sourcePolyData)
            #Create a display node
            self.outputModelNode.CreateDefaultDisplayNodes()
            #
            self.outputModelNode.GetDisplayNode().SetVisibility(True)
            self.outputModelNode.GetDisplayNode().SetColor(red)

        slicer.mrmlScene.RemoveNode(self.sourceModelNode)

        if self.ui.skipScalingCheckBox.checked:
            slicer.mrmlScene.RemoveNode(self.scalingTransformNode)

        self.ui.runCPDAffineButton.enabled = True


    def onRunCPDAffineButton(self):
        logic = FastModelAlignLogic()
        if bool(self.ui.outputSelector.currentNode()):
            transformation, translation = logic.CPDAffineTransform(self.outputModelNode, self.sourcePoints, self.targetPoints)
        else:
            transformation, translation = logic.CPDAffineTransform(self.sourceModelNode, self.sourcePoints, self.targetPoints)
        matrix_vtk = vtk.vtkMatrix4x4()
        for i in range(3):
          for j in range(3):
            matrix_vtk.SetElement(i,j,transformation[j][i])
        for i in range(3):
          matrix_vtk.SetElement(i,3,translation[i])
        affineTransform = vtk.vtkTransform()
        affineTransform.SetMatrix(matrix_vtk)
        affineTransformNode =  slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', "Affine_transform_matrix")
        affineTransformNode.SetAndObserveTransformToParent( affineTransform )

        affineNodeName = self.sourceModelName + "_affine"
        affineTransformNode.SetName(affineNodeName)

        #Put affine transform node under scaling  transform node, which has been put under the rigid transform node
        self.ICPTransformNode.SetAndObserveTransformNodeID(affineTransformNode.GetID())
        self.ui.runCPDAffineButton.enabled = False


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


    def ITKRegistration(self, sourceModelNode, targetModelNode, skipScalingOption, parameterDictionary, usePoisson):
        import ALPACA
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
            skipScalingOption,
            parameterDictionary,
            usePoisson,
        )

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

        return sourcePoints, targetPoints, scalingTransformNode, ICPTransformNode

    def CPDAffineTransform(self, sourceModelNode, sourcePoints, targetPoints):
       from cpdalp import AffineRegistration
       import vtk.util.numpy_support as nps

       polyData = sourceModelNode.GetPolyData()
       points = polyData.GetPoints()
       numpyModel = nps.vtk_to_numpy(points.GetData())

       reg = AffineRegistration(**{'X': targetPoints, 'Y': sourcePoints, 'low_rank':True})
       reg.register()
       TY = reg.transform_point_cloud(numpyModel)
       vtkArray = nps.numpy_to_vtk(TY)
       points.SetData(vtkArray)
       polyData.Modified()

       affine_matrix, translation = reg.get_registration_parameters()

       return affine_matrix, translation





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


        self.sourcePoints_test, self.targetPoints_test, self.scalingTransformNode_test, self.ICPTransformNode_test = logic.ITKRegistration(self.sourceModelNode_test, self.targetModelNode_test, False,
            self.parameterDictionary_test, False)

        scalingNodeName_test = self.sourceModelName_test + "_scaling_test"
        rigidNodeName_test = self.sourceModelName_test + "_rigid_test"
        self.scalingTransformNode_test.SetName(scalingNodeName_test)
        self.ICPTransformNode_test.SetName(rigidNodeName_test)

        red = [1, 0, 0]
        self.sourceModelNode_test.GetDisplayNode().SetColor(red)

        self.delayDisplay('Test passed')
