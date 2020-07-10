import logging
import math
import numpy
import os
import unittest

import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# MarkupEditor
#

class MarkupEditor(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "MarkupEditor"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph", "Labs"]  # TODO: set categories (folders where the module shows up in the module selector)
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"]  # TODO: replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
A tool to manipulate Markups using the Segment Editor as a geometry backend
"""  # TODO: update with short description of the module
    self.parent.helpText += self.getDefaultModuleDocumentationLink()  # TODO: verify that the default URL is correct or change it to the actual documentation
    self.parent.acknowledgementText = """
This module was developed by Steve Pieper, Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""  # TODO: replace with organization, grant and thanks.

#
# MarkupEditorWidget
#

class MarkupEditorWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Markups"
    self.layout.addWidget(parametersCollapsibleButton)
    self.parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    self.fiducialsSelector = slicer.qMRMLNodeComboBox()
    self.fiducialsSelector.nodeTypes = ["vtkMRMLMarkupsFiducialNode"]
    self.fiducialsSelector.setMRMLScene(slicer.mrmlScene)
    self.fiducialsSelector.setToolTip("Select fiducials to edit")
    self.parametersFormLayout.addRow("Fiducials: ", self.fiducialsSelector)

    self.curveSelector = slicer.qMRMLNodeComboBox()
    self.curveSelector.nodeTypes = ["vtkMRMLMarkupsClosedCurveNode"]
    self.curveSelector.setMRMLScene(slicer.mrmlScene)
    self.curveSelector.setToolTip("Select curve that defines the edit region")
    self.parametersFormLayout.addRow("Curve: ", self.curveSelector)

    self.viewSelector = slicer.qMRMLNodeComboBox()
    self.viewSelector.nodeTypes = ["vtkMRMLViewNode"]
    self.viewSelector.setMRMLScene(slicer.mrmlScene)
    self.viewSelector.setToolTip("Select view that defines the edit region")
    self.parametersFormLayout.addRow("View: ", self.viewSelector)

    self.editButton = qt.QPushButton("Edit")
    #self.editButton.enabled = False
    self.parametersFormLayout.addRow("", self.editButton)

    # Add vertical spacer
    self.layout.addStretch(1)

    self.logic = MarkupEditorLogic()

    self.editButton.connect("clicked()", self.onEditMarkups)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()


  def onEditMarkups(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:
      viewNode = self.viewSelector.currentNode()
      layoutManager = slicer.app.layoutManager()
      self.logic.editMarkups(self.fiducialsSelector.currentNode(),
                             self.curveSelector.currentNode(),
                             self.viewSelector.currentNode())
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()


#
# MarkupEditorLogic
#

class MarkupEditorLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    self.observerTags = {}

  def editMarkups(self, fiducialsNode, curveNode, viewNode):

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.viewWidget(viewNode)
    aspectRatio = threeDWidget.width / threeDWidget.height

    cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
    camera = cameraNode.GetCamera()
    raswToXYZW = vtk.vtkMatrix4x4()
    modelView = camera.GetModelViewTransformMatrix()
    projection = camera.GetProjectionTransformMatrix(aspectRatio, 1, 100) # near/far are arbitrary
    raswToXYZW.Multiply4x4(projection, modelView, raswToXYZW)

    def rasToColumnRow(ras):
      rasw = *ras,1
      xyzw = raswToXYZW.MultiplyPoint(rasw)
      x,y = [xyzw[0] / xyzw[3], xyzw[1] / xyzw[3]]
      column = (x + 1)/2  * threeDWidget.width
      row = (1 - (y + 1)/2) * threeDWidget.height
      return column, row

    curveNode.ResampleCurveWorld(5)

    selectionPolygon = qt.QPolygonF()
    for index in range(curveNode.GetNumberOfControlPoints()):
      ras = [0]*3
      curveNode.GetNthControlPointPositionWorld(index, ras)
      column, row = rasToColumnRow(ras)
      point = qt.QPointF(column, row)
      selectionPolygon.push_back(point)

    pickImage = qt.QImage(threeDWidget.width, threeDWidget.height, qt.QImage().Format_ARGB32)
    backgroundColor = qt.QColor("#ffffffff")
    pickImage.fill(backgroundColor)

    painter = qt.QPainter()
    painter.begin(pickImage)
    painterPath = qt.QPainterPath()
    painterPath.addPolygon(selectionPolygon)
    brush = qt.QBrush(qt.Qt.SolidPattern)
    painter.setBrush(brush)
    painter.drawPath(painterPath)
    painter.end()

    debugging = False
    if debugging:
        pixmap = qt.QPixmap().fromImage(pickImage)
        slicer.modules.label = qt.QLabel()
        slicer.modules.label.setPixmap(pixmap)
        slicer.modules.label.show()

    for index in range(fiducialsNode.GetNumberOfControlPoints()):
      ras = [0]*3
      fiducialsNode.GetNthControlPointPositionWorld(index, ras)
      column, row = rasToColumnRow(ras)
      pickColor = pickImage.pixelColor(column, row)
      fiducialsNode.SetNthControlPointSelected(index, pickColor != backgroundColor)


#
# MarkupEditorTest
#

class MarkupEditorTest(ScriptedLoadableModuleTest):
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
    self.test_MarkupEditor1()

  def test_MarkupEditor1(self):
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

    slicer.util.selectModule("MarkupEditor")

    # Get/create input data

    import SampleData
    url = 'https://raw.githubusercontent.com/SlicerMorph/SampleData/master/4074_S_lm1.fcsv'
    filePath = SampleData.SampleDataLogic().downloadFileIntoCache(url, "4074_S_lm1.fcsv")

    self.delayDisplay("reading")
    markups = slicer.util.loadMarkupsFiducialList(filePath)

    slicer.vtkSlicerMarkupsLogic().SetAllMarkupsSelected(markups, False)

    slicer.app.layoutManager().threeDWidget(0).threeDView().resetCamera()

    self.delayDisplay('Finished with download and loading')

    # Test the module logic

    logic = MarkupEditorLogic()

    # Test algorithm with non-inverted threshold
    self.delayDisplay("editing")
    logic.editMarkups(markups, curve, view)

    self.assertEqual(markups, markups)

    self.delayDisplay('Test passed')
