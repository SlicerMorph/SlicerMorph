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
        self.parent.title = "HiRes Screen Capture"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]  # TODO: set categories (folders where the module
        # shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Murat Maga (UW), Oshane Thomas(SCRI)"]  # TODO: replace with "Firstname Lastname
        # (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
The "High Resolution Screen Capture" module allows users to capture and save high-quality screenshots from the Slicer application. Decorate the 3D viewer in exactly how you would like the screenshot. Then, specify the filename, output folder, and a scaling factor to give the desired output resolution.
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
        self.finalresolutionDisplayLabel = None
        self.updateTimer = None
        self.resolutionDisplayLabel = None
        self.currentScaleFactor = 1.0  # Default scale factor
        self.selectOutputFileButton = None
        self.applyButton = None
        self.resolutionSpinBox = None  # Use a QDoubleSpinBox for resolution factor
        self.outputFileLineEdit = None
        self.logic = None
        self.viewerWidthSpinBox = None
        self.viewerHeightSpinBox = None
        self.setViewerSizeButton = None

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

        # 3D Viewer Size Section
        viewerSizeLabel = qt.QLabel("<b>3D Viewer Size Settings</b>")
        parametersFormLayout.addRow(viewerSizeLabel)

        # Viewer Width spin box
        self.viewerWidthSpinBox = qt.QSpinBox()
        self.viewerWidthSpinBox.setRange(100, 4000)
        self.viewerWidthSpinBox.setSingleStep(10)
        self.viewerWidthSpinBox.setValue(500)
        parametersFormLayout.addRow("Viewer Width:", self.viewerWidthSpinBox)

        # Viewer Height spin box
        self.viewerHeightSpinBox = qt.QSpinBox()
        self.viewerHeightSpinBox.setRange(100, 4000)
        self.viewerHeightSpinBox.setSingleStep(10)
        self.viewerHeightSpinBox.setValue(500)
        parametersFormLayout.addRow("Viewer Height:", self.viewerHeightSpinBox)

        # Set Viewer Size button
        self.setViewerSizeButton = qt.QPushButton("Set Viewer Size")
        self.setViewerSizeButton.toolTip = "Undock and resize the 3D viewer to the specified dimensions"
        self.setViewerSizeButton.clicked.connect(self.onSetViewerSize)
        parametersFormLayout.addRow("", self.setViewerSizeButton)

        # Separator
        separatorLabel = qt.QLabel("")
        parametersFormLayout.addRow(separatorLabel)
        
        # Screenshot Output Section
        screenshotLabel = qt.QLabel("<b>Screenshot Settings</b>")
        parametersFormLayout.addRow(screenshotLabel)

        # Output file QLineEdit
        self.outputFileLineEdit = qt.QLineEdit()
        self.outputFileLineEdit.setPlaceholderText("e.g., /path/to/screenshot.png")
        self.initialDir = slicer.mrmlScene.GetRootDirectory()
        self.selectOutputFileButton = qt.QPushButton("Select Output File")
        self.selectOutputFileButton.clicked.connect(self.selectOutputFile)
        fileHBox = qt.QHBoxLayout()
        fileHBox.addWidget(self.outputFileLineEdit)
        fileHBox.addWidget(self.selectOutputFileButton)
        parametersFormLayout.addRow("Output File:", fileHBox)

        # Resolution Scaling Factor (using QDoubleSpinBox)
        self.resolutionSpinBox = qt.QDoubleSpinBox()
        self.resolutionSpinBox.setRange(0.1, 100.0)  # Set appropriate range
        self.resolutionSpinBox.setSingleStep(0.1)
        self.resolutionSpinBox.setDecimals(2)
        self.resolutionSpinBox.setValue(self.currentScaleFactor)
        self.resolutionSpinBox.valueChanged.connect(self.onResolutionFactorChanged)
        parametersFormLayout.addRow("Resolution Scaling Factor:", self.resolutionSpinBox)

        self.resolutionDisplayLabel = qt.QLabel("Current Resolution: Unknown")
        self.finalresolutionDisplayLabel = qt.QLabel("Current Resolution: Unknown")
        parametersFormLayout.addRow("3D Viewer Size:", self.resolutionDisplayLabel)
        parametersFormLayout.addRow("Screenshot Output Resolution:", self.finalresolutionDisplayLabel)

        # Initialize the timer for updating the resolution display
        self.updateTimer = qt.QTimer()
        self.updateTimer.timeout.connect(self.updateResolutionDisplay)
        self.updateTimer.start(100)  # update every second

        # Apply button
        self.applyButton = qt.QPushButton("Export Screenshot")
        self.applyButton.clicked.connect(self.applyButtonClicked)
        self.layout.addWidget(self.applyButton)

        # Create logic class
        self.logic = HiResScreenCaptureLogic()
        self.logic.setCurrentScalFactor(self.currentScaleFactor)  # set default scale factor

        # Connect signals
        self.outputFileLineEdit.textChanged.connect(self.updateApplyButtonState)

        # Set initial state for the apply button
        self.updateApplyButtonState()

    def updateResolutionDisplay(self):
        # If viewer is undocked and using custom size, show that
        if self.logic and self.logic.viewerIsUndocked and self.logic.customViewerWidth and self.logic.customViewerHeight:
            width = self.logic.customViewerWidth
            height = self.logic.customViewerHeight
            self.resolutionDisplayLabel.setText(f"{width} x {height} (custom)")
        else:
            threeDWidget = slicer.app.layoutManager().threeDWidget(0)
            if threeDWidget:
                view = threeDWidget.threeDView()
                width = view.width
                height = view.height
                self.resolutionDisplayLabel.setText(f"{width} x {height}")
        
        # Calculate final output resolution
        if self.logic and self.logic.customViewerWidth and self.logic.customViewerHeight:
            width = self.logic.customViewerWidth
            height = self.logic.customViewerHeight
        else:
            threeDWidget = slicer.app.layoutManager().threeDWidget(0)
            if threeDWidget:
                view = threeDWidget.threeDView()
                width = view.width
                height = view.height
            else:
                width = 0
                height = 0
        
        self.finalresolutionDisplayLabel.setText(f"{int(round(width*self.currentScaleFactor))} x "
                                                 f"{int(round(height*self.currentScaleFactor))}")

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        if self.updateTimer:
            self.updateTimer.stop()

        # Properly call super with the current class name and `self`
        super().cleanup()

    def selectOutputFile(self) -> None:
        """
        Open a file selection dialog and set the output file path.
        """
        selectedFile = qt.QFileDialog.getSaveFileName(None, "Select Output File", self.initialDir, "PNG Files (*.png);;BMP Files (*.bmp);;JPG Files (*.jpg *.jpeg);;TIFF Files (*.tiff);;All Files (*)")
        if selectedFile:
            self.outputFileLineEdit.setText(selectedFile)
            self.initialDir = os.path.dirname(selectedFile)

    def onSetViewerSize(self):
        """
        Undock and resize the 3D viewer to the user-specified dimensions.
        """
        width = self.viewerWidthSpinBox.value
        height = self.viewerHeightSpinBox.value
        self.logic.setViewerSize(width, height)
        print(f"3D Viewer resized to: {width} x {height}")

    def onResolutionFactorChanged(self, value):
        """
        Updates the current resolution scaling factor based on user input from the spin box.
        """
        self.logic.setCurrentScalFactor(value)
        self.currentScaleFactor = value
        # print("Resolution scaling factor set to:", self.currentScaleFactor)

    def updateApplyButtonState(self):
        """
        Updates the state of the apply button based on the input fields and resolution factor.
        """
        if self.outputFileLineEdit.text:
          extensionList = ['.png', '.bmp', '.jpg', '.jpeg', '.tiff']
          root, ext = os.path.splitext(self.outputFileLineEdit.text)
          directoryValid = os.path.isdir(os.path.dirname(self.outputFileLineEdit.text))
          if not directoryValid:
            print("Please choose a valid directory")
          extensionValid = ext in extensionList
          if not extensionValid:
            print("Please choose a valid extension (png, bmp, jpg, tiff)")
          self.applyButton.setEnabled(extensionValid and directoryValid)
        else:
          self.applyButton.setEnabled(False)

    def applyButtonClicked(self):
        """
        Handles the apply button click to execute screenshot logic with the current scale factor.
        """
        outputPath = self.outputFileLineEdit.text
        self.logic.setOutputPath(outputPath)
        self.logic.setResolutionFactor(self.currentScaleFactor)
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
        self.currentScaleFactor = None
        self.resolutionFactor = None
        self.outputPath = None
        self.customViewerWidth = None
        self.customViewerHeight = None
        self.viewerIsUndocked = False
        self.originalLayout = None
        self.threeDWidget = None

    def setResolutionFactor(self, resolutionFactor: int) -> None:
        self.resolutionFactor = resolutionFactor

    def setCurrentScalFactor(self, scaleFactor: float) -> None:
        self.currentScaleFactor = scaleFactor

    def setOutputPath(self, outputPath: str) -> None:
        self.outputPath = outputPath

    def setViewerSize(self, width: int, height: int) -> None:
        """
        Undock the 3D viewer and resize it to the specified dimensions.
        """
        self.customViewerWidth = width
        self.customViewerHeight = height
        
        layoutManager = slicer.app.layoutManager()
        self.originalLayout = layoutManager.layout
        self.threeDWidget = layoutManager.threeDWidget(0)
        
        # Undock the widget
        self.threeDWidget.setParent(None)
        self.threeDWidget.show()
        
        # Resize to custom dimensions
        self.threeDWidget.resize(width, height)
        self.viewerIsUndocked = True
        
        print(f"3D Viewer undocked and resized to: {width} x {height}")

    def redockViewer(self) -> None:
        """
        Dock the 3D viewer back to its original layout.
        """
        if self.viewerIsUndocked and self.threeDWidget and self.originalLayout is not None:
            layoutManager = slicer.app.layoutManager()
            # Change layout to force reparenting
            layoutManager.layout = slicer.vtkMRMLLayoutNode.SlicerLayoutCustomView
            layoutManager.layout = self.originalLayout
            self.viewerIsUndocked = False
            print("3D Viewer docked back to original layout")

    def runScreenCapture(self) -> None:
        if self.resolutionFactor and self.outputPath:
            layoutManager = slicer.app.layoutManager()
            currentLayout = layoutManager.layout
            
            # Use the already undocked viewer if available, otherwise undock now
            if self.viewerIsUndocked and self.threeDWidget:
                threeDWidget = self.threeDWidget
                print("Using already undocked 3D viewer")
            else:
                threeDWidget = layoutManager.threeDWidget(0)
                threeDWidget.setParent(None)
                threeDWidget.show()
                
                # Resize to custom dimensions if specified
                if self.customViewerWidth and self.customViewerHeight:
                    threeDWidget.resize(self.customViewerWidth, self.customViewerHeight)
                    print(f"3D Viewer resized to custom size: {self.customViewerWidth} x {self.customViewerHeight}")
            
            originalSize = threeDWidget.size
            print("Current viewer size:", threeDWidget.size)

            viewNode = threeDWidget.mrmlViewNode()
            originalScaleFactor = viewNode.GetScreenScaleFactor()
            print("Original Markup Scale Factor:", originalScaleFactor)
            viewNode.SetScreenScaleFactor(originalScaleFactor * self.currentScaleFactor)

            threeDWidget.size = qt.QSize(originalSize.width() * self.currentScaleFactor,
                                         originalSize.height() * self.currentScaleFactor)
            print("Scaled Image size:", threeDWidget.size)

            print("Updated Markup Scale Factor:", viewNode.GetScreenScaleFactor())

            # Capture the view
            threeDWidget.grab().save(self.outputPath)
            print(f"Screenshot saved to: {self.outputPath}")

            # Restore original scale factor
            viewNode.SetScreenScaleFactor(originalScaleFactor)

            # Dock the viewer back to original layout
            layoutManager.layout = slicer.vtkMRMLLayoutNode.SlicerLayoutCustomView
            layoutManager.layout = currentLayout
            
            # Reset undocked state
            self.viewerIsUndocked = False
            self.threeDWidget = None
            print("3D Viewer docked back to original layout")

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
