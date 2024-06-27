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
        self.finalresolutionDisplayLabel = None
        self.updateTimer = None
        self.resolutionDisplayLabel = None
        self.currentScaleFactor = 1.0  # Default scale factor
        self.selectOutputFileButton = None
        self.applyButton = None
        self.resolutionSpinBox = None  # Use a QDoubleSpinBox for resolution factor
        self.outputFileLineEdit = None
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

        # Output file QLineEdit
        self.outputFileLineEdit = qt.QLineEdit()
        self.outputFileLineEdit.setPlaceholderText("e.g., /path/to/screenshot.png")
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
        parametersFormLayout.addRow("Current 3D Resolution:", self.resolutionDisplayLabel)
        parametersFormLayout.addRow("Expected Screenshot 3D Resolution:", self.finalresolutionDisplayLabel)

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
        threeDWidget = slicer.app.layoutManager().threeDWidget(0)
        if threeDWidget:
            view = threeDWidget.threeDView()
            width = view.width
            height = view.height
            self.resolutionDisplayLabel.setText(f"{width} x {height}")
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
        selectedFile = qt.QFileDialog.getSaveFileName(None, "Select Output File", "", "PNG Files (*.png);;All Files (*)")
        if selectedFile:
            self.outputFileLineEdit.setText(selectedFile)

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
        isFilePathSet = bool(self.outputFileLineEdit.text.strip()) and self.outputFileLineEdit.text.strip().endswith('.png')
        self.applyButton.setEnabled(isFilePathSet)

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

    def setResolutionFactor(self, resolutionFactor: int) -> None:
        self.resolutionFactor = resolutionFactor

    def setCurrentScalFactor(self, scaleFactor: float) -> None:
        self.currentScaleFactor = scaleFactor

    def setOutputPath(self, outputPath: str) -> None:
        self.outputPath = outputPath

    def runScreenCapture(self) -> None:
        if self.resolutionFactor and self.outputPath:
            layoutManager = slicer.app.layoutManager()
            threeDWidget = layoutManager.threeDWidget(0)
            threeDView = threeDWidget.threeDView()
            viewNode = threeDView.mrmlViewNode()

            # Store the original size and scale factor
            originalSize = threeDView.size
            originalScaleFactor = viewNode.GetScreenScaleFactor()

            try:
                print("Original Image size:", originalSize)
                print("Original Markup Scale Factor:", originalScaleFactor)

                # Update the scale factor and size for high resolution capture
                viewNode.SetScreenScaleFactor(originalScaleFactor * self.currentScaleFactor)
                threeDView.resize(originalSize.width() * self.currentScaleFactor,
                                  originalSize.height() * self.currentScaleFactor)

                print("Updated Image size:", threeDView.size)
                print("Updated Markup Scale Factor:", viewNode.GetScreenScaleFactor())

                # Capture the view
                screenshot = threeDView.grab()
                screenshot.save(self.outputPath)

                print("Screenshot saved to:", self.outputPath)

            finally:
                # Restore the original size and scale factor
                viewNode.SetScreenScaleFactor(originalScaleFactor)
                threeDView.resize(originalSize)
                print("Restored Image size:", threeDView.size)
                print("Restored Markup Scale Factor:", viewNode.GetScreenScaleFactor())

            # Ensure the layout updates to reflect the changes
            layoutManager.layoutChanged()

            print("Done.")
