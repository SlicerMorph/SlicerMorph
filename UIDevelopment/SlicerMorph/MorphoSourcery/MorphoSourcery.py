import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# MorphoSourcery
#

class MorphoSourcery(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "MorphoSourcery" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
Access to the MorphoSource web site via the Web Engine in Slicer.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This module was developed by Steve Pieper with Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.

#
# MorphoSourceryWidget
#

class MorphoSourceryWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...
    self.webWidget = None
    self.logic = MorphoSourceryLogic()

    # Collapsible button
    self.loginCollapsibleButton = ctk.ctkCollapsibleButton()
    self.loginCollapsibleButton.text = "MorphoSource Login"
    self.layout.addWidget(self.loginCollapsibleButton)
    self.formLayout = qt.QFormLayout(self.loginCollapsibleButton)

    #
    # Login info
    #
    username,password = self.logic.getLogin()
    self.username = qt.QLineEdit()
    self.username.text = username
    self.formLayout.addRow("Username", self.username)
    self.password = qt.QLineEdit()
    self.password.setEchoMode(qt.QLineEdit.Password)
    self.password.text = password
    self.formLayout.addRow("Password", self.password)

    #
    # Open Button
    #
    self.applyButton = qt.QPushButton("Open MorphoSource")
    self.applyButton.toolTip = "Open the MorphoSource site."
    self.formLayout.addWidget(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onOpen)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    if hasattr(self, "webWidget") and self.webWidget:
      del self.webWidget

  def onOpen(self):
    username = self.username.text
    password = self.password.text
    self.webWidget = self.logic.open(username, password)

#
# MorphoSourceryLogic
#

class MorphoSourceryLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def getLogin(self):
    username = slicer.util.settingsValue("MorphoSourcery/username", "")
    password = slicer.util.settingsValue("MorphoSourcery/password", "")
    return username,password

  def setLogin(self, username="", password=""):
    settings = qt.QSettings()
    settings.setValue("MorphoSourcery/username", username)
    settings.setValue("MorphoSourcery/password", password)

  def onEvalResult(self, js, result):
    self.webWidget.disconnect("evalResult(QString,QString)", self.onEvalResult)

  def onFinishLoading(self, username, password):
    loginJS = """
        function fillInLogin() {
          document.querySelector('input[name="username"]').value = "%s";
          document.querySelector('input[name="password"]').value = "%s";
        }

        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", fillInLogin);
        } else {
          fillInLogin();
        }
    """ % (username,password)

    self.webWidget.connect("evalResult(QString,QString)", self.onEvalResult)
    self.webWidget.evalJS(loginJS)

  def open(self, username = "", password = ""):
    """Open the MorphoSource page and fill in or capture the url
    """
    if username != "":
      self.setLogin(username, password)

    webWidget = slicer.qSlicerWebWidget()
    slicerGeometry = slicer.util.mainWindow().geometry
    webWidget.size = qt.QSize(slicerGeometry.width(),slicerGeometry.height())
    webWidget.pos = qt.QPoint(slicerGeometry.x() + 256, slicerGeometry.y() + 128)
    webWidget.url = "https://www.morphosource.org/LoginReg/form"
    webWidget.show()

    self.webWidget = webWidget
    # TODO: need to expose loadFinished signal from QWebEngine via qSlicerWebWidget
    # so that we will know when to send this (current 2 second delay is a hack
    # that may not always work).
    qt.QTimer.singleShot(2000, lambda : self.onFinishLoading(username, password))

    return self.webWidget

class MorphoSourceryTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_MorphoSourcery1()

  def test_MorphoSourcery1(self):
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

    logic = MorphoSourceryLogic()
    webWidget = logic.open()

    self.delayDisplay('Test passed!')
