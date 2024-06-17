import os

import qt, ctk
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter


#
# Python Editor
#

class SlicerEditor(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "SlicerEditor"
        self.parent.categories = ["SlicerMorph.Input and Output"]
        self.parent.dependencies = []
        self.parent.contributors = ["Murat Maga (UW), Oshane Thomas(SCRI)"]
        self.parent.helpText = """ """
        self.parent.acknowledgementText = """ """


#
# SlicerEditorWidget
#

class SlicerEditorWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.logic = SlicerEditorLogic()
        self.formatter = HtmlFormatter(full=True, style='colorful')
        self.currentFilePath = None

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Collapsible button
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Python Editor"
        self.layout.addWidget(parametersCollapsibleButton)

        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        # Toolbar with file operations
        self.toolbar = qt.QToolBar()
        parametersFormLayout.addWidget(self.toolbar)

        newFileAction = qt.QAction("New File", self.toolbar)
        newFileAction.triggered.connect(self.newFile)
        self.toolbar.addAction(newFileAction)

        openFileAction = qt.QAction("Open File", self.toolbar)
        openFileAction.triggered.connect(self.openFile)
        self.toolbar.addAction(openFileAction)

        saveFileAction = qt.QAction("Save File", self.toolbar)
        saveFileAction.triggered.connect(self.saveFile)
        self.toolbar.addAction(saveFileAction)

        saveAsFileAction = qt.QAction("Save File As", self.toolbar)
        saveAsFileAction.triggered.connect(self.saveFileAs)
        self.toolbar.addAction(saveAsFileAction)

        # Editor area
        self.editor = qt.QTextEdit()
        self.editor.setAcceptRichText(True)
        parametersFormLayout.addWidget(self.editor)
        self.editor.textChanged.connect(self.onTextChanged)

    def newFile(self):
        self.currentFilePath = None
        self.editor.clear()

    def openFile(self):
        fileDialog = qt.QFileDialog()
        fileDialog.setNameFilter("Python files (*.py)")
        fileDialog.setFileMode(qt.QFileDialog.ExistingFile)
        if fileDialog.exec_():
            filePath = fileDialog.selectedFiles()[0]
            with open(filePath, 'r') as file:
                fileContent = file.read()
                self.editor.setPlainText(fileContent)
                self.displayHighlightedContent(fileContent)
                self.currentFilePath = filePath

    def saveFile(self):
        if self.currentFilePath:
            with open(self.currentFilePath, 'w') as file:
                file.write(self.editor.toPlainText())
        else:
            self.saveFileAs()

    def saveFileAs(self):
        fileDialog = qt.QFileDialog()
        fileDialog.setNameFilter("Python files (*.py)")
        fileDialog.setAcceptMode(qt.QFileDialog.AcceptSave)
        if fileDialog.exec_():
            filePath = fileDialog.selectedFiles()[0]
            with open(filePath, 'w') as file:
                file.write(self.editor.toPlainText())
            self.currentFilePath = filePath

    def onTextChanged(self):
        plainText = self.editor.toPlainText()
        self.displayHighlightedContent(plainText)

    def displayHighlightedContent(self, content):
        lexer = PythonLexer()
        highlightedContent = highlight(content, lexer, self.formatter)

        css = self.formatter.get_style_defs()
        html = f"<html><head><style>{css}</style></head><body>{highlightedContent}</body></html>"

        cursor = self.editor.textCursor()
        pos = cursor.position()

        self.editor.blockSignals(True)
        self.editor.setHtml(html)
        cursor.setPosition(pos)
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        pass


#
# SlicerEditorLogic
#

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
