import os
import sys
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import *


class SlicerEditorWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)
        self.setupSlicerPythonEnvironment()

        # Create and set up the qSlicerWebWidget
        self.editorView = slicer.qSlicerWebWidget()
        self.editorView.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
        self.editorView.setMinimumSize(qt.QSize(450, 500))

        # Create a run button
        self.runButton = qt.QPushButton("Run All")
        self.runButton.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        self.runButton.clicked.connect(self.runButtonClicked)

        # Create a run selected button
        self.runSelectedButton = qt.QPushButton("Run Selected")
        self.runSelectedButton.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        self.runSelectedButton.clicked.connect(self.runSelectedButtonClicked)

        # Create a layout to place the buttons next to each other
        self.buttonLayout = qt.QHBoxLayout()
        self.buttonLayout.addWidget(self.runButton)
        self.buttonLayout.addWidget(self.runSelectedButton)
        self.buttonLayout.addStretch()  # Add stretch to push buttons to the left

        self.buttonWidget = qt.QWidget()
        self.buttonWidget.setLayout(self.buttonLayout)

        self.mainLayout = qt.QVBoxLayout()
        self.mainLayout.addWidget(self.buttonWidget)
        self.mainLayout.addWidget(self.editorView)

        # Set the layout to the module widget
        self.layout.addLayout(self.mainLayout)

        # Load the Monaco Editor HTML
        editorHtmlPath = "/home/oshane/Downloads/offline/index.html"  # change me! [temporary]
        self.editorView.url = qt.QUrl.fromLocalFile(editorHtmlPath)

        # Connect the evalResult signal to the slot
        self.editorView.connect("evalResult(QString,QString)", self.onEvalResult)

    def runButtonClicked(self):
        # Execute the JavaScript to get the code from the editor
        self.editorView.evalJS("window.editor.getModel().getValue()")

    def runSelectedButtonClicked(self):
        # Execute the JavaScript to get the selected code from the editor
        self.editorView.evalJS("window.editor.getModel().getValueInRange(window.editor.getSelection())")

    def onEvalResult(self, request, result):
        if request == "window.editor.getModel().getValue()":
            self.processEditorCode(result)
        elif request == "window.editor.getModel().getValueInRange(window.editor.getSelection())":
            self.processEditorCode(result)

    @staticmethod
    def processEditorCode(code):
        if not code:
            print("No code to execute.")
            return
        elif code:
            exec(code, globals())
        else:
            print("In Slicer you would have executed this code:")
            print(code)

    @staticmethod
    def setupSlicerPythonEnvironment():
        import platform
        slicer_paths = []
        if platform.system() == 'Windows':
            slicer_paths = [
                os.path.join(slicer.app.slicerHome, 'bin', 'Python',
                             f'lib\\python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
            ]
        else:
            slicer_paths = [
                os.path.join(slicer.app.slicerHome, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}',
                             'site-packages')
            ]
        for path in slicer_paths:
            if path not in sys.path:
                sys.path.append(path)
        os.environ['PYTHONPATH'] = os.pathsep.join(slicer_paths)




class SlicerEditorLogic(ScriptedLoadableModuleLogic):
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
