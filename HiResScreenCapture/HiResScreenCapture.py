import os

import qt, ctk
import slicer
import vtk

import ScreenCapture
from slicer.ScriptedLoadableModule import *


def isActorVisible(camera, actor):
    # Create a list to store the frustum planes
    frustumPlanes = [0.0] * 24

    # Get the frustum planes from the camera
    camera.GetFrustumPlanes(1.0, frustumPlanes)

    # Create a vtkPlanes object using the frustum planes
    planes = vtk.vtkPlanes()
    planes.SetFrustumPlanes(frustumPlanes)

    # Get the bounds of the actor
    bounds = actor.GetBounds()

    # Check if the bounding box is within the view frustum
    for i in range(0, 6):
        plane = vtk.vtkPlane()
        planes.GetPlane(i, plane)
        if plane.EvaluateFunction(bounds[:3]) * plane.EvaluateFunction(bounds[3:]) > 0:
            # If the product is positive, then one of the box's corners is outside this plane
            return False
    return True


#
# HiResScreenCapture
#

class HiResScreenCapture(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "HiResScreenCapture"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["SlicerMorph.Input and Output"]  # TODO: set categories (folders where the module
        # shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Murat Maga (UW), Oshane Thomas(SCRI)"]  # TODO: replace with "Firstname Lastname
        # (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
The "High Resolution Screen Capture" module allows users to capture and save high-quality screenshots from the Slicer
application. Users specify the filename, output folder, and desired resolution, with the module ensuring all inputs are
 valid and the filename ends with .png. See more information in 
 <a href="https://github.com/oothomas/SlicerMorph/tree/master/HiResScreenCapture">module documentation</a>.
"""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """This file was originally developed by Jean-Christophe Fillion-Robin, 
        Kitware Inc., Andras Lasso, PerkLab, and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 
        3P41RR013218-12S1. We would also like to thank Steve Pieper for developing the export function used here."""


#
# HiResScreenCaptureWidget
#

class HiResScreenCaptureWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.resolutionButtons = {}
        self.resolutionMapping = {}  # Dictionary to map buttons to resolution factors
        self.selectOutputDirButton = None
        self.applyButton = None
        self.resolutionYSpinBox = None
        self.outputDirLineEdit = None
        self.filenameLineEdit = None
        self.logic = None

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Ensure layout alignment is set to top
        self.layout.setAlignment(qt.Qt.AlignTop)

        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Screen Capture Settings"
        self.layout.addWidget(parametersCollapsibleButton)

        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        # Output filename QLineEdit
        self.filenameLineEdit = qt.QLineEdit()
        self.filenameLineEdit.setPlaceholderText("Enter filename (e.g., screenshot.png)")
        parametersFormLayout.addRow("Filename:", self.filenameLineEdit)

        # Output directory selector
        self.outputDirLineEdit = qt.QLineEdit()
        self.outputDirLineEdit.setReadOnly(True)
        self.selectOutputDirButton = qt.QPushButton("Select Output Folder")
        self.selectOutputDirButton.clicked.connect(self.selectOutputDirectory)
        directoryHBox = qt.QHBoxLayout()
        directoryHBox.addWidget(self.outputDirLineEdit)
        directoryHBox.addWidget(self.selectOutputDirButton)
        parametersFormLayout.addRow("Output Folder:", directoryHBox)

        # Resolution selection
        resolutionGroupBox = qt.QGroupBox("Resolution Selection (Magnification):")
        resolutionLayout = qt.QHBoxLayout()  # Changed to QHBoxLayout for horizontal tiling
        resolutionGroupBox.setLayout(resolutionLayout)

        for resolution in ["1X", "2X", "4X", "8X", "12X", "16X", "20X"]:
            radioButton = qt.QRadioButton(resolution)
            radioButton.toggled.connect(self.onResolutionChange)
            radioButton.toggled.connect(self.updateApplyButtonState)  # Ensure state update affects the Apply button
            resolutionLayout.addWidget(radioButton)
            self.resolutionButtons[resolution] = radioButton
            self.resolutionMapping[radioButton] = int(resolution[:-1])  # Store resolution factor in the dictionary
        parametersFormLayout.addRow(resolutionGroupBox)

        # Apply button
        self.applyButton = qt.QPushButton("Export Screenshot")
        self.applyButton.clicked.connect(self.applyButtonClicked)
        self.layout.addWidget(self.applyButton)

        # Create logic class
        self.logic = HiResScreenCaptureLogic()

        # Connect signals
        self.filenameLineEdit.textChanged.connect(self.updateApplyButtonState)
        self.outputDirLineEdit.textChanged.connect(self.updateApplyButtonState)

        # Set initial state for the apply button
        self.updateApplyButtonState()

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        return

    def selectOutputDirectory(self) -> None:
        """
        Open a directory selection dialog and set the output directory.
        """
        selectedDir = qt.QFileDialog.getExistingDirectory()
        if selectedDir:
            self.outputDirLineEdit.setText(selectedDir)

    def onResolutionChange(self):
        for button, factor in self.resolutionMapping.items():
            if button.isChecked():
                self.logic.setResolutionFactor(factor)
                break

    def updateApplyButtonState(self) -> None:
        # Check conditions for enabling the button
        isFilenameSet = bool(self.filenameLineEdit.text.strip()) and self.filenameLineEdit.text.strip().endswith('.png')
        isOutputFolderSet = bool(self.outputDirLineEdit.text.strip())

        # Check if any resolution radio button is selected
        isResolutionSelected = any(button.isChecked() for button in self.resolutionMapping.keys())

        # Enable or disable the button based on the conditions
        self.applyButton.setEnabled(isFilenameSet and isOutputFolderSet and isResolutionSelected)

    def applyButtonClicked(self) -> None:
        outputPath = os.path.join(self.outputDirLineEdit.text, self.filenameLineEdit.text)
        self.logic.setOutputPath(outputPath)
        self.logic.runScreenCapture()


#
# HiResScreenCaptureLogic
#

class HiResScreenCaptureLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)
        self.resolutionFactor = None
        self.outputPath = None

    def setResolutionFactor(self, resolutionFactor: int) -> None:
        self.resolutionFactor = resolutionFactor

    def setOutputPath(self, outputPath: str) -> None:
        self.outputPath = outputPath

    def runScreenCapture(self) -> None:
        if self.resolutionFactor and self.outputPath:
            layoutManager = slicer.app.layoutManager()
            originalLayout = layoutManager.layout
            originalViewNode = layoutManager.threeDWidget(0).mrmlViewNode()
            originalCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(originalViewNode)

            # Debugging: Print original camera settings
            print("Original Camera Settings:")
            print("Position:", originalCamera.GetPosition())
            print("Focal Point:", originalCamera.GetFocalPoint())
            print("View Up:", originalCamera.GetViewUp())
            # Get original background colors
            originalBackgroundColor1 = originalViewNode.GetBackgroundColor()
            originalBackgroundColor2 = originalViewNode.GetBackgroundColor2()

            # Set the layout to include the necessary view
            layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDualMonitorFourUpView)
            viewNode = layoutManager.threeDWidget(0).mrmlViewNode()
            # viewLogic = slicer.app.applicationLogic().GetViewLogicByLayoutName("1+")
            # viewNode = viewLogic.GetViewNode()
            layoutManager.addMaximizedViewNode(viewNode)
            newCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)

            # Set and debug new camera settings
            newCamera.SetPosition(originalCamera.GetPosition())
            newCamera.SetFocalPoint(originalCamera.GetFocalPoint())
            newCamera.SetViewUp(originalCamera.GetViewUp())

            # Set new view's background to match the original
            viewNode.SetBackgroundColor(originalBackgroundColor1)
            viewNode.SetBackgroundColor2(originalBackgroundColor2)  # Ensure uniform background

            print("New Camera Settings Applied")

            # Ensure volume rendering is visible in the new view
            volumeRenderingLogic = slicer.modules.volumerendering.logic()
            volumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLVolumeNode")
            displayNode = volumeRenderingLogic.GetFirstVolumeRenderingDisplayNode(volumeNode)
            if displayNode:
                displayNode.SetVisibility(True)
                displayNode.SetViewNodeIDs([viewNode.GetID()])

            # Resize and capture the view
            viewWidget = layoutManager.viewWidget(viewNode)
            layoutDockingWidget = viewWidget.parent().parent()
            originalSize = layoutDockingWidget.size
            layoutDockingWidget.resize(originalSize.width() * self.resolutionFactor,
                                       originalSize.height() * self.resolutionFactor)

            # Force a redraw
            viewWidget.threeDView().forceRender()

            # newCamera.GetCamera().Dolly(1.001)

            # Capture the view
            cap = ScreenCapture.ScreenCaptureLogic()
            cap.captureImageFromView(viewWidget.threeDView(), self.outputPath)

            # Restore original size and layout
            layoutDockingWidget.resize(originalSize.width(), originalSize.height())
            # layoutManager.setLayout(originalLayout)

            # reset volume rendering visibility
            if displayNode:
                displayNode.SetVisibility(True)
                displayNode.SetViewNodeIDs([originalViewNode.GetID()])

            print("Capture Completed")

            # Make all other view nodes except the original one invisible
            allViewNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLViewNode")
            allViewNodes.InitTraversal()
            viewNode = allViewNodes.GetNextItemAsObject()
            while viewNode:
                if viewNode.GetID() != originalViewNode.GetID():
                    slicer.mrmlScene.RemoveNode(viewNode)
                viewNode = allViewNodes.GetNextItemAsObject()

            # Refresh the layout to reflect changes
            layoutManager.layout = originalLayout

    # def runScreenCapture(self) -> None:
    #     if self.resolution and self.outputPath:
    #         layoutManager = slicer.app.layoutManager()
    #         originalLayout = layoutManager.layout
    #         originalViewNode = layoutManager.threeDWidget(self.threeDViewIndex).mrmlViewNode()
    #         originalCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(originalViewNode)
    #
    #         # Debugging: Print original camera settings
    #         print("Original Camera Settings:")
    #         print("Position:", originalCamera.GetPosition())
    #         print("Focal Point:", originalCamera.GetFocalPoint())
    #         print("View Up:", originalCamera.GetViewUp())
    #
    #         layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDualMonitorFourUpView)
    #         viewNode = layoutManager.threeDWidget(0).mrmlViewNode()
    #         layoutManager.addMaximizedViewNode(viewNode)
    #         newCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
    #
    #         # Set and debug new camera settings
    #         newCamera.SetPosition(originalCamera.GetPosition())
    #         newCamera.SetFocalPoint(originalCamera.GetFocalPoint())
    #         newCamera.SetViewUp(originalCamera.GetViewUp())
    #         print("New Camera Settings Applied")
    #
    #         # Resize and capture the view
    #         # viewWidget = layoutManager.threeDWidget(0) # my code, which does not render whole image
    #         viewWidget = layoutManager.viewWidget(viewNode)
    #         layoutDockingWidget = viewWidget.parent().parent()
    #         originalSize = layoutDockingWidget.size
    #         layoutDockingWidget.resize(self.resolution[0], self.resolution[1])
    #
    #         # Force a redraw
    #         layoutManager.threeDWidget(0).threeDView().scheduleRender()
    #
    #         # Capture the view
    #         cap = ScreenCapture.ScreenCaptureLogic()
    #         cap.captureImageFromView(viewWidget.threeDView(), self.outputPath)
    #
    #         # Restore original size and layout
    #         layoutDockingWidget.resize(originalSize.width(), originalSize.height())
    #         layoutManager.setLayout(originalLayout)
    #
    #         print("Capture Completed")

    # def runScreenCapture(self) -> None:
    #     if self.resolution and self.outputPath:
    #         # Switch to a layout that has a window that is not in the main window
    #         layoutManager = slicer.app.layoutManager()
    #         originalLayout = layoutManager.layout
    #         layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDualMonitorFourUpView)
    #
    #         # Maximize the 3D view within this layout
    #         viewLogic = slicer.app.applicationLogic().GetViewLogicByLayoutName("1+")
    #         viewNode = viewLogic.GetViewNode()
    #         layoutManager.addMaximizedViewNode(viewNode)
    #
    #         # Resize the view
    #         viewWidget = layoutManager.viewWidget(viewNode)
    #         # Parent of the view widget is the frame, parent of the frame is the docking widget
    #         layoutDockingWidget = viewWidget.parent().parent()
    #         originalSize = layoutDockingWidget.size
    #         layoutDockingWidget.resize(self.resolution[0], self.resolution[1])
    #
    #         # Capture the view
    #         cap = ScreenCapture.ScreenCaptureLogic()
    #         cap.captureImageFromView(viewWidget.threeDView(), self.outputPath)
    #         # Restore original size and layout
    #         layoutDockingWidget.resize(originalSize)
    #         layoutManager.setLayout(originalLayout)

    # def runScreenCapture(self) -> None:
    #     if self.resolution and self.outputPath:
    #         vtk.vtkGraphicsFactory()
    #         gf = vtk.vtkGraphicsFactory()
    #         gf.SetOffScreenOnlyMode(1)
    #         gf.SetUseMesaClasses(1)
    #         rw = vtk.vtkRenderWindow()
    #         rw.SetOffScreenRendering(1)
    #         ren = vtk.vtkRenderer()
    #         rw.SetSize(self.resolution[0], self.resolution[1])
    #
    #         lm = slicer.app.layoutManager()
    #
    #         threeDViewWidget = lm.threeDWidget(self.threeDViewIndex)
    #         threeDView = threeDViewWidget.threeDView()
    #
    #         renderers = threeDView.renderWindow().GetRenderers()
    #         ren3d = renderers.GetFirstRenderer()
    #
    #         # Set the background color of the off-screen renderer to match the original
    #         backgroundColor = ren3d.GetBackground()
    #         ren.SetBackground(backgroundColor)
    #
    #         camera = ren3d.GetActiveCamera()
    #
    #         while ren3d:
    #
    #             actors = ren3d.GetActors()
    #             for index in range(actors.GetNumberOfItems()):
    #                 actor = actors.GetItemAsObject(index)
    #
    #                 actor_class_name = actor.GetClassName()  # Get the class name using VTK's method
    #                 # Alternatively, use Python's type function: actor_type = type(actor).__name__
    #                 print("Actor index:", index, "Class name:", actor_class_name)
    #
    #                 property = actor.GetProperty()
    #                 # print("Actor Property:", property)
    #                 representation = property.GetRepresentation()
    #
    #                 # vtkProperty defines three representation types:
    #                 # vtkProperty.VTK_POINTS, vtkProperty.VTK_WIREFRAME, vtkProperty.VTK_SURFACE
    #                 if representation == vtk.VTK_POINTS:
    #                     print("Actor index:", index, "is represented as points.")
    #                 elif representation == vtk.VTK_WIREFRAME:
    #                     print("Actor index:", index, "is represented as wireframe.")
    #                 elif representation == vtk.VTK_SURFACE:
    #                     print("Actor index:", index, "is represented as a surface.")
    #                 else:
    #                     print("Actor index:", index, "has an unknown representation.")
    #
    #                 print("Actor index:", index, "Visibility -", actor.GetVisibility(), "|", isActorVisible(camera, actor))
    #                 if actor.GetVisibility():  # and isActorVisible(camera, actor):
    #                     ren.AddActor(actor)  # Add only visible actors
    #
    #             lights = ren3d.GetLights()
    #             for index in range(lights.GetNumberOfItems()):
    #                 ren.AddLight(lights.GetItemAsObject(index))
    #
    #             volumes = ren3d.GetVolumes()
    #             for index in range(volumes.GetNumberOfItems()):
    #                 ren.AddVolume(volumes.GetItemAsObject(index))
    #
    #             ren3d = renderers.GetNextItem()
    #
    #         ren.SetActiveCamera(camera)
    #
    #         rw.AddRenderer(ren)
    #         rw.Render()
    #
    #         wti = vtk.vtkWindowToImageFilter()
    #         wti.SetInput(rw)
    #         wti.Update()
    #         writer = vtk.vtkPNGWriter()
    #         writer.SetInputConnection(wti.GetOutputPort())
    #         writer.SetFileName(self.outputPath)
    #         writer.Update()
    #         writer.Write()
    #         i = wti.GetOutput()

        #
# HiResScreenCaptureTest
#

# class HiResScreenCaptureTest(ScriptedLoadableModuleTest):
#     """
#     This is the test case for your scripted module.
#     Uses ScriptedLoadableModuleTest base class, available at:
#     https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
#     """
#
#     def setUp(self):
#         """ Do whatever is needed to reset the state - typically a scene clear will be enough.
#         """
#         slicer.mrmlScene.Clear()
#
#     def runTest(self):
#         """Run as few or as many tests as needed here.
#         """
#         self.setUp()
#         self.test_HiResScreenCapture1()
#
#     def test_HiResScreenCapture1(self):
#         """ Ideally you should have several levels of tests.  At the lowest level
#         tests should exercise the functionality of the logic with different inputs
#         (both valid and invalid).  At higher levels your tests should emulate the
#         way the user would interact with your code and confirm that it still works
#         the way you intended.
#         One of the most important features of the tests is that it should alert other
#         developers when their changes will have an impact on the behavior of your
#         module.  For example, if a developer removes a feature that you depend on,
#         your test should break so they know that the feature is needed.
#         """
#
#         self.delayDisplay("Starting the test")
#
#         # Get/create input data
#
#         import SampleData
#         registerSampleData()
#         inputVolume = SampleData.downloadSample('HiResScreenCapture1')
#         self.delayDisplay('Loaded test data set')
#
#         inputScalarRange = inputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(inputScalarRange[0], 0)
#         self.assertEqual(inputScalarRange[1], 695)
#
#         outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
#         threshold = 100
#
#         # Test the module logic
#
#         logic = HiResScreenCaptureLogic()
#
#         # Test algorithm with non-inverted threshold
#         logic.process(inputVolume, outputVolume, threshold, True)
#         outputScalarRange = outputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(outputScalarRange[0], inputScalarRange[0])
#         self.assertEqual(outputScalarRange[1], threshold)
#
#         # Test algorithm with inverted threshold
#         logic.process(inputVolume, outputVolume, threshold, False)
#         outputScalarRange = outputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(outputScalarRange[0], inputScalarRange[0])
#         self.assertEqual(outputScalarRange[1], inputScalarRange[1])
#
#         self.delayDisplay('Test passed')
