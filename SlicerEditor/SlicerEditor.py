import os
import sys
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import *


#
# SlicerEditor
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

        # Attempt to import packages, and install if not present
        try:
            import jedi
        except ImportError:
            slicer.util.pip_install('jedi')
            import jedi

        try:
            from pygments import highlight
            from pygments.lexers import PythonLexer
            from pygments.formatters import HtmlFormatter
        except ImportError:
            slicer.util.pip_install('pygments')
            from pygments import highlight
            from pygments.lexers import PythonLexer
            from pygments.formatters import HtmlFormatter

        self.PythonLexer = PythonLexer
        self.jedi = jedi
        self.highlight = highlight
        self.saveOpenComboBox = None
        self.editor = None
        self.logic = SlicerEditorLogic()
        self.formatter = HtmlFormatter(full=True, style='colorful')
        self.currentFilePath = None
        self.eventFilter = EventFilter(self)

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        self.setupSlicerPythonEnvironment()

        # Collapsible button
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Python Editor"
        self.layout.addWidget(parametersCollapsibleButton)

        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        # Label for the combo box
        self.comboBoxLabel = qt.QLabel("Python File Node:")
        self.saveOpenComboBox = qt.QComboBox()
        self.saveOpenComboBox.addItem("Choose a .py Node")
        self.saveOpenComboBox.addItem("Create New Node")
        self.saveOpenComboBox.addItem("Save Node to Scene")
        self.saveOpenComboBox.addItem("Open Node from Scene")
        parametersFormLayout.addRow(self.comboBoxLabel, self.saveOpenComboBox)

        self.saveOpenComboBox.currentIndexChanged.connect(self.onComboBoxIndexChanged)

        # Editor area
        self.editor = qt.QTextEdit()
        self.editor.setTextInteractionFlags(qt.Qt.TextEditorInteraction)
        self.editor.setAcceptRichText(False)  # Use plain text for editing
        parametersFormLayout.addRow(self.editor)
        self.editor.textChanged.connect(self.onTextChanged)

        # Corrected Event Filter Installation (Slicer-specific)
        self.editor.installEventFilter(self.eventFilter)

    @staticmethod
    def setupSlicerPythonEnvironment():

        # Get the paths from the Slicer application
        slicer_paths = [
            os.path.join(slicer.app.slicerHome, 'bin/Python',
                         f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
        ]

        for path in slicer_paths:
            if path not in sys.path:
                sys.path.append(path)

        # Set PYTHONPATH environment variable
        os.environ['PYTHONPATH'] = os.pathsep.join(slicer_paths)

    def newFile(self):
        self.currentFilePath = None
        self.editor.clear()

    def saveToScene(self):
        # Prompt user for a name
        textNodeName = qt.QInputDialog.getText(slicer.util.mainWindow(), 'Save to Scene', 'Enter name for the script:')
        if textNodeName:
            textNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTextNode")
            textNode.SetName(textNodeName)
            textNode.SetText(self.editor.toPlainText())

    def openFromScene(self):
        # Get all text nodes in the scene
        textNodes = slicer.util.getNodesByClass("vtkMRMLTextNode")
        if not textNodes:
            qt.QMessageBox.information(slicer.util.mainWindow(), 'SlicerEditor', 'No text nodes found in the scene.')
            return

        # Let the user select a node
        items = [''] + [node.GetName() for node in textNodes]
        item = qt.QInputDialog.getItem(slicer.util.mainWindow(), 'Select Text Node', 'Select a text node to open:',
                                       items, 0, False)

        if item == '':
            pass
        else:
            selectedNode = next(node for node in textNodes if node.GetName() == item)
            fileContent = selectedNode.GetText()
            self.editor.setPlainText(fileContent)
            self.displayHighlightedContent(fileContent)

    def onTextChanged(self):
        plainText = self.editor.toPlainText()
        self.displayHighlightedContent(plainText)

    def displayHighlightedContent(self, content):
        lexer = self.PythonLexer()
        highlightedContent = self.highlight(content, lexer, self.formatter)

        css = self.formatter.get_style_defs()
        html = f"<html><head><style>{css}</style></head><body>{highlightedContent}</body></html>"

        cursor = self.editor.textCursor()
        pos = cursor.position()

        self.editor.blockSignals(True)
        self.editor.setHtml(html)
        self.editor.blockSignals(False)

        # Adjust the cursor position if it's out of range
        newPlainTextLength = len(self.editor.toPlainText())
        cursor.setPosition(min(pos, newPlainTextLength))

        self.editor.setTextCursor(cursor)

    def showCompletion(self):
        cursor = self.editor.textCursor()
        line_number = cursor.blockNumber() + 1
        column = cursor.positionInBlock()

        # Pass the entire code from the editor as a positional argument to jedi.Script
        script = self.jedi.Script(
            self.editor.toPlainText(),
        )
        completions = script.complete(line=line_number, column=column)

        if completions:
            completion_menu = qt.QMenu(self.editor)
            for completion in completions:
                action = qt.QAction(completion.name, completion_menu)
                action.triggered.connect(
                    lambda checked, text=completion.name: self.insertCompletion(text)
                )
                completion_menu.addAction(action)

            # Use cursorRect to get the rectangle of the cursor's current position
            cursor_rect = self.editor.cursorRect(cursor)
            completion_menu.exec_(self.editor.mapToGlobal(cursor_rect.bottomRight()))

    def insertCompletion(self, text):
        cursor = self.editor.textCursor()
        # Select the text from the current cursor position to the start of the current word
        cursor.movePosition(qt.QTextCursor.StartOfWord, qt.QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    def onComboBoxIndexChanged(self, index):
        if index == 1:
            self.newFile()
        elif index == 2:
            self.saveToScene()
        elif index == 3:
            self.openFromScene()

        # Reset to the default option after selection
        self.saveOpenComboBox.setCurrentIndex(0)

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        pass


class EventFilter(qt.QObject):
    def __init__(self, parentWidget):
        super(EventFilter, self).__init__()
        self.parentWidget = parentWidget

    def eventFilter(self, watched, event):
        if watched == self.parentWidget.editor and event.type() == qt.QEvent.KeyPress:
            if event.key() == qt.Qt.Key_Tab:
                self.parentWidget.showCompletion()
                return True
            elif event.key() in (qt.Qt.Key_Return, qt.Qt.Key_Enter):
                return False
        return qt.QObject.eventFilter(self, watched, event)


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
