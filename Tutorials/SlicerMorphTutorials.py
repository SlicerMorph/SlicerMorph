import os
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import mistune
import requests
import webbrowser

class SlicerMorphTutorials(ScriptedLoadableModule):

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "SlicerMorph Tutorials"
        self.parent.categories = ["SlicerMorph.Documentation"]
        self.parent.dependencies = []
        self.parent.contributors = ["Murat Maga (SCRI)"]
        self.parent.helpText = """Provides direct links to the SlicerMorph Tutorials repo."""
        self.parent.acknowledgementText = """This file was originally developed by Murat Maga, SCRI."""

class SlicerMorphTutorialsWidget(ScriptedLoadableModuleWidget):

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # URL of the Markdown file
        markdown_url = "https://raw.githubusercontent.com/SlicerMorph/Tutorials/main/README.md"

        # Fetch the Markdown content
        response = requests.get(markdown_url)
        markdown_text = response.text

        # Create a Markdown renderer
        renderer = mistune.create_markdown()

        # Convert Markdown to HTML
        html_content = renderer(markdown_text)

        # Add some basic styling for better display
        styled_html_content = f"""
        <html>
        <head>
        <style>
        body {{ font-family: Arial, sans-serif; }}
        h1 {{ color: #333; }}
        ul {{ list-style-type: disc; padding-left: 20px; }}
        li {{ margin: 5px 0; }}
        </style>
        </head>
        <body>
        {html_content}
        </body>
        </html>
        """

        # Create a QTextBrowser widget
        self.textWidget = qt.QTextBrowser()
        self.textWidget.setReadOnly(True)
        self.textWidget.setOpenExternalLinks(True)  # Ensure external links open in the default web browser

        # Set the styled HTML content in the QTextBrowser widget
        self.textWidget.setHtml(styled_html_content)

        # Create a vertical layout for the widget
        layout = qt.QVBoxLayout()

        # Add the QTextBrowser widget with full stretch factor
        layout.addWidget(self.textWidget)

        # Set the layout for the module
        self.layout.addLayout(layout)

    def cleanup(self):
        pass

class SlicerMorphTutorialsLogic(ScriptedLoadableModuleLogic):
    pass

class SlicerMorphTutorialsTest(ScriptedLoadableModuleTest):
    def runTest(self):
        self.setUp()
        self.test_SlicerMorphTutorials1()

    def test_SlicerMorphTutorials1(self):
        self.delayDisplay("Starting the test")
        self.delayDisplay('Test passed!')
