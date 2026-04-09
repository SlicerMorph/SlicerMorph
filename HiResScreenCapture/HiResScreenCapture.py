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
        self.currentScaleFactor = 1.0  # Default scale factor
        self.selectOutputFileButton = None
        self.applyButton = None
        self.resolutionSpinBox = None  # Use a QDoubleSpinBox for resolution factor
        self.outputFileLineEdit = None
        self.removeBackgroundCheckBox = None
        self.logic = None
        self.undockViewerButton = None
        self.redockViewerButton = None
        self.viewerComboBox = None
        self.widthSpinBox = None
        self.heightSpinBox = None
        self.resetSizeButton = None
        self.viewerSizeLocked = False
        self._timerUpdatingSize = False

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

        # Viewer selector
        self.viewerComboBox = qt.QComboBox()
        self.viewerComboBox.toolTip = "Select which 3D viewer to undock"
        self.viewerComboBox.setMaximumWidth(200)
        parametersFormLayout.addRow("3D Viewer:", self.viewerComboBox)

        # Undock/Redock buttons in vertical layout, left-aligned
        buttonVBox = qt.QVBoxLayout()
        buttonVBox.setAlignment(qt.Qt.AlignLeft)
        
        self.undockViewerButton = qt.QPushButton("Undock 3D Viewer")
        self.undockViewerButton.toolTip = "Undocks the 3D viewer for the user to adjust correct aspect ratios for their visualization."
        self.undockViewerButton.clicked.connect(self.onUndockViewer)
        self.undockViewerButton.setMaximumWidth(150)
        buttonVBox.addWidget(self.undockViewerButton)
        
        self.redockViewerButton = qt.QPushButton("Redock 3D Viewer")
        self.redockViewerButton.toolTip = "Redock the 3D viewer back to its original layout"
        self.redockViewerButton.clicked.connect(self.onRedockViewer)
        self.redockViewerButton.enabled = False
        self.redockViewerButton.setMaximumWidth(150)
        buttonVBox.addWidget(self.redockViewerButton)
        
        parametersFormLayout.addRow("", buttonVBox)

        # Separator
        separatorLabel = qt.QLabel("")
        parametersFormLayout.addRow(separatorLabel)

        # Screenshot Output Section
        screenshotLabel = qt.QLabel("<b>Screenshot Settings</b>")
        parametersFormLayout.addRow(screenshotLabel)

        # Resolution Scaling Factor (using QDoubleSpinBox)
        self.resolutionSpinBox = qt.QDoubleSpinBox()
        self.resolutionSpinBox.setRange(0.1, 100.0)  # Set appropriate range
        self.resolutionSpinBox.setSingleStep(0.1)
        self.resolutionSpinBox.setDecimals(2)
        self.resolutionSpinBox.setValue(self.currentScaleFactor)
        self.resolutionSpinBox.setMaximumWidth(100)
        self.resolutionSpinBox.valueChanged.connect(self.onResolutionFactorChanged)
        parametersFormLayout.addRow("Scaling Factor:", self.resolutionSpinBox)

        # Viewer size spinboxes — always editable; press Enter to lock, ↺ to resume dynamic tracking
        self.widthSpinBox = qt.QSpinBox()
        self.widthSpinBox.setRange(100, 10000)
        self.widthSpinBox.setValue(800)
        self.widthSpinBox.setSuffix(" px")
        self.widthSpinBox.setMaximumWidth(90)
        self.widthSpinBox.setToolTip("Viewer width — press Enter to lock this value")

        self.heightSpinBox = qt.QSpinBox()
        self.heightSpinBox.setRange(100, 10000)
        self.heightSpinBox.setValue(600)
        self.heightSpinBox.setSuffix(" px")
        self.heightSpinBox.setMaximumWidth(90)
        self.heightSpinBox.setToolTip("Viewer height — press Enter to lock this value")

        self.resetSizeButton = qt.QPushButton("\u21ba")
        self.resetSizeButton.setMaximumWidth(28)
        self.resetSizeButton.setToolTip("Reset to dynamic (follow window size)")
        self.resetSizeButton.enabled = False
        self.resetSizeButton.clicked.connect(self.onViewerSizeReset)

        sizeHBox = qt.QHBoxLayout()
        sizeHBox.addWidget(self.widthSpinBox)
        sizeHBox.addWidget(qt.QLabel("\u00d7"))
        sizeHBox.addWidget(self.heightSpinBox)
        sizeHBox.addWidget(self.resetSizeButton)
        sizeHBox.addStretch()
        parametersFormLayout.addRow("Viewer Size:", sizeHBox)

        self.widthSpinBox.editingFinished.connect(self.onViewerSizePinned)
        self.heightSpinBox.editingFinished.connect(self.onViewerSizePinned)

        self.finalresolutionDisplayLabel = qt.QLabel("Current Resolution: Unknown")
        parametersFormLayout.addRow("Output Size:", self.finalresolutionDisplayLabel)

        # Output file QLineEdit
        self.outputFileLineEdit = qt.QLineEdit()
        self.outputFileLineEdit.setPlaceholderText("e.g., /path/to/screenshot.png")
        self.outputFileLineEdit.setMinimumWidth(200)
        self.initialDir = slicer.mrmlScene.GetRootDirectory()
        self.selectOutputFileButton = qt.QPushButton("Select Output File")
        self.selectOutputFileButton.clicked.connect(self.selectOutputFile)
        fileHBox = qt.QHBoxLayout()
        fileHBox.addWidget(self.outputFileLineEdit)
        fileHBox.addWidget(self.selectOutputFileButton)
        parametersFormLayout.addRow("Output File:", fileHBox)

        # Remove background checkbox (only applicable for PNG output)
        self.removeBackgroundCheckBox = qt.QCheckBox("Remove background")
        self.removeBackgroundCheckBox.toolTip = ("If checked, the background will be transparent in the captured image. "
                                                 "Only available for PNG format.")
        self.removeBackgroundCheckBox.checked = False
        self.removeBackgroundCheckBox.enabled = False
        parametersFormLayout.addRow("", self.removeBackgroundCheckBox)

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

        # Populate the viewer selector and keep it in sync with layout changes
        self._populateViewerComboBox()
        slicer.app.layoutManager().layoutChanged.connect(self._populateViewerComboBox)

        # Connect signals
        self.outputFileLineEdit.textChanged.connect(self.updateApplyButtonState)

        # Set initial state for the apply button
        self.updateApplyButtonState()

    def updateResolutionDisplay(self):
        try:
            width, height = 0, 0
            if self.viewerSizeLocked:
                width = self.widthSpinBox.value
                height = self.heightSpinBox.value
            else:
                # Prefer the undocked widget if available
                if self.logic and self.logic.viewerIsUndocked and self.logic.threeDWidget:
                    view = self.logic.threeDWidget.threeDView()
                    width = view.width
                    height = view.height
                else:
                    layoutManager = slicer.app.layoutManager()
                    if layoutManager:
                        threeDWidget = layoutManager.threeDWidget(0)
                        if threeDWidget:
                            view = threeDWidget.threeDView()
                            width = view.width
                            height = view.height
                if width and height:
                    self._timerUpdatingSize = True
                    self.widthSpinBox.setValue(width)
                    self.heightSpinBox.setValue(height)
                    self._timerUpdatingSize = False

            if width and height:
                self.finalresolutionDisplayLabel.setText(
                    f"{int(round(width * self.currentScaleFactor))} x "
                    f"{int(round(height * self.currentScaleFactor))}"
                )
        except Exception:
            pass

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        if self.updateTimer:
            self.updateTimer.stop()
        try:
            slicer.app.layoutManager().layoutChanged.disconnect(self._populateViewerComboBox)
        except Exception:
            pass

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

    def onUndockViewer(self):
        """
        Undock the 3D viewer for user adjustment.
        """
        # Refresh combo in case the layout changed since setup
        self._populateViewerComboBox()
        viewerIndex = self.viewerComboBox.currentIndex
        self.logic.undockViewer(viewerIndex)
        self.undockViewerButton.enabled = False
        self.redockViewerButton.enabled = True
        print("3D Viewer undocked")

    def onRedockViewer(self):
        """
        Redock the 3D viewer back to its original layout.
        """
        self.logic.redockViewer()
        self.onViewerSizeReset()  # release any pinned size when redocking
        # Defer button state updates to allow layout changes to complete
        qt.QTimer.singleShot(100, lambda: self.updateButtonStatesAfterRedock())
        print("3D Viewer redocked")

    def onViewerSizePinned(self):
        """
        Called when the user presses Enter in a size spinbox — locks the displayed value.
        """
        if self._timerUpdatingSize:
            return
        self.viewerSizeLocked = True
        self.logic.pinnedViewerWidth = self.widthSpinBox.value
        self.logic.pinnedViewerHeight = self.heightSpinBox.value
        self.resetSizeButton.enabled = True
        # Immediately resize the undocked viewer if one is open
        if self.logic.viewerIsUndocked and self.logic.threeDWidget:
            self.logic.threeDWidget.resize(qt.QSize(self.widthSpinBox.value, self.heightSpinBox.value))

    def onViewerSizeReset(self):
        """
        Release the pinned size and resume dynamic tracking.
        """
        self.viewerSizeLocked = False
        self.logic.pinnedViewerWidth = None
        self.logic.pinnedViewerHeight = None
        self.resetSizeButton.enabled = False
    
    def _populateViewerComboBox(self):
        """
        Fill the combo box with all available 3D views.
        """
        layoutManager = slicer.app.layoutManager()
        current = self.viewerComboBox.currentIndex
        self.viewerComboBox.clear()
        for i in range(layoutManager.threeDViewCount):
            node = layoutManager.threeDWidget(i).mrmlViewNode()
            self.viewerComboBox.addItem(node.GetName() if node.GetName() else f"3D View {i+1}")
        # Restore previous selection if still valid
        if 0 <= current < self.viewerComboBox.count:
            self.viewerComboBox.currentIndex = current

    def updateButtonStatesAfterRedock(self):
        """
        Update button states after redocking completes.
        """
        self.undockViewerButton.enabled = True
        self.redockViewerButton.enabled = False

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
          ext = ext.lower()
          directoryValid = os.path.isdir(os.path.dirname(self.outputFileLineEdit.text))
          if not directoryValid:
            print("Please choose a valid directory")
          extensionValid = ext in extensionList
          if not extensionValid:
            print("Please choose a valid extension (png, bmp, jpg, tiff)")
          self.applyButton.setEnabled(extensionValid and directoryValid)
          # Remove background only works with PNG (alpha channel support)
          self.removeBackgroundCheckBox.setEnabled(ext == '.png')
          if ext != '.png':
            self.removeBackgroundCheckBox.setChecked(False)
        else:
          self.applyButton.setEnabled(False)
          self.removeBackgroundCheckBox.setEnabled(False)

    def applyButtonClicked(self):
        """
        Handles the apply button click to execute screenshot logic with the current scale factor.
        """
        outputPath = self.outputFileLineEdit.text
        # Remember the directory for next time
        self.initialDir = os.path.dirname(outputPath)
        self.logic.setOutputPath(outputPath)
        self.logic.setResolutionFactor(self.currentScaleFactor)
        self.logic.setRemoveBackground(self.removeBackgroundCheckBox.checked)
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
        self.pinnedViewerWidth = None
        self.pinnedViewerHeight = None
        self.viewerIsUndocked = False
        self.originalLayout = None
        self.threeDWidget = None
        self.removeBackground = False

    def setResolutionFactor(self, resolutionFactor: int) -> None:
        self.resolutionFactor = resolutionFactor

    def setCurrentScalFactor(self, scaleFactor: float) -> None:
        self.currentScaleFactor = scaleFactor

    def setOutputPath(self, outputPath: str) -> None:
        self.outputPath = outputPath

    def setRemoveBackground(self, removeBackground: bool) -> None:
        self.removeBackground = removeBackground

    def undockViewer(self, viewerIndex=0) -> None:
        """
        Undock the 3D viewer for user adjustment.
        """
        if self.viewerIsUndocked:
            return

        layoutManager = slicer.app.layoutManager()
        self.originalLayout = layoutManager.layout
        self.threeDWidget = layoutManager.threeDWidget(viewerIndex)

        # Undock the widget
        self.threeDWidget.setParent(None)
        self.threeDWidget.show()
        # On macOS the VTK OpenGL surface does not repaint automatically after
        # reparenting — process pending events first so the window is fully
        # created, then force a render so the view is not blank.
        slicer.app.processEvents()
        self.threeDWidget.threeDView().renderWindow().Render()
        self.viewerIsUndocked = True

        print("3D Viewer undocked")

    def redockViewer(self) -> None:
        """
        Dock the 3D viewer back to its original layout.
        """
        if not self.viewerIsUndocked:
            return

        if self.threeDWidget and self.originalLayout is not None:
            layoutManager = slicer.app.layoutManager()
            # Change layout to force reparenting
            layoutManager.layout = slicer.vtkMRMLLayoutNode.SlicerLayoutCustomView
            layoutManager.layout = self.originalLayout
            self.viewerIsUndocked = False
            self.threeDWidget = None
            self.customViewerWidth = None
            self.customViewerHeight = None
            print("3D Viewer docked back to original layout")

    def runScreenCapture(self) -> None:
        if self.resolutionFactor and self.outputPath:
            layoutManager = slicer.app.layoutManager()
            currentLayout = layoutManager.layout
            wasAlreadyUndocked = self.viewerIsUndocked

            # Use the already undocked viewer if available, otherwise undock temporarily
            if self.viewerIsUndocked and self.threeDWidget:
                threeDWidget = self.threeDWidget
                print("Using already undocked 3D viewer")
            else:
                threeDWidget = layoutManager.threeDWidget(0)
                threeDWidget.setParent(None)
                threeDWidget.show()

            # Capture current viewer dimensions (or use pinned size if set)
            originalSize = threeDWidget.size
            if self.pinnedViewerWidth and self.pinnedViewerHeight:
                threeDWidget.resize(qt.QSize(self.pinnedViewerWidth, self.pinnedViewerHeight))
                slicer.app.processEvents()
                captureWidth = self.pinnedViewerWidth
                captureHeight = self.pinnedViewerHeight
            else:
                captureWidth = originalSize.width()
                captureHeight = originalSize.height()
            self.customViewerWidth = captureWidth
            self.customViewerHeight = captureHeight
            print("Capture size:", captureWidth, "x", captureHeight)

            viewNode = threeDWidget.mrmlViewNode()
            originalScaleFactor = viewNode.GetScreenScaleFactor()
            print("Original Screen Scale Factor:", originalScaleFactor)
            
            # Scale BOTH the widget size AND the screen scale factor for true high-res rendering
            viewNode.SetScreenScaleFactor(originalScaleFactor * self.currentScaleFactor)
            
            scaledWidth = int(captureWidth * self.currentScaleFactor)
            scaledHeight = int(captureHeight * self.currentScaleFactor)
            threeDWidget.size = qt.QSize(scaledWidth, scaledHeight)
            print("Scaled image size:", scaledWidth, "x", scaledHeight)
            print("Updated Screen Scale Factor:", viewNode.GetScreenScaleFactor())

            if self.removeBackground:
                # Use the VTK rendering pipeline to capture with a transparent background
                view = threeDWidget.threeDView()
                renderWindow = view.renderWindow()

                # Save state for all renderers
                renderers = renderWindow.GetRenderers()
                rendererStates = []
                renderers.InitTraversal()
                renderer = renderers.GetNextItem()
                while renderer:
                    rendererStates.append({
                        'renderer': renderer,
                        'background': renderer.GetBackground(),
                        'background2': renderer.GetBackground2(),
                        'gradientBackground': renderer.GetGradientBackground(),
                        'backgroundAlpha': renderer.GetBackgroundAlpha(),
                    })
                    renderer.SetBackground(0, 0, 0)
                    renderer.SetBackground2(0, 0, 0)
                    renderer.SetGradientBackground(False)
                    renderer.SetBackgroundAlpha(0.0)
                    renderer = renderers.GetNextItem()

                # Enable alpha bit planes for transparent rendering
                originalAlphaBitPlanes = renderWindow.GetAlphaBitPlanes()
                renderWindow.SetAlphaBitPlanes(1)
                renderWindow.Render()

                # Capture the view with an RGBA buffer
                wti = vtk.vtkWindowToImageFilter()
                wti.SetInput(renderWindow)
                wti.SetInputBufferTypeToRGBA()
                wti.ReadFrontBufferOff()
                wti.Update()

                writer = vtk.vtkPNGWriter()
                writer.SetFileName(self.outputPath)
                writer.SetInputConnection(wti.GetOutputPort())
                writer.Write()
                print(f"Transparent screenshot saved to: {self.outputPath}")

                # Restore all renderer background settings
                for state in rendererStates:
                    r = state['renderer']
                    r.SetBackground(*state['background'])
                    r.SetBackground2(*state['background2'])
                    r.SetGradientBackground(state['gradientBackground'])
                    r.SetBackgroundAlpha(state['backgroundAlpha'])
                renderWindow.SetAlphaBitPlanes(originalAlphaBitPlanes)
                renderWindow.Render()
            else:
                # Capture the view
                threeDWidget.grab().save(self.outputPath)
                print(f"Screenshot saved to: {self.outputPath}")

            # Restore original scale factor and size
            viewNode.SetScreenScaleFactor(originalScaleFactor)
            threeDWidget.size = originalSize

            # Dock the viewer back only if it wasn't already undocked
            if not wasAlreadyUndocked:
                # Close the undocked window and force layout refresh
                threeDWidget.close()
                slicer.app.processEvents()
                # Switch layout to force recreation of the 3D widget
                layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
                slicer.app.processEvents()
                layoutManager.setLayout(currentLayout)
                slicer.app.processEvents()
                self.customViewerWidth = None
                self.customViewerHeight = None
                print("3D Viewer docked back to original layout")
            else:
                # Restore original size even if staying undocked
                threeDWidget.resize(originalSize)
                print("Keeping 3D Viewer undocked as it was before capture")

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
