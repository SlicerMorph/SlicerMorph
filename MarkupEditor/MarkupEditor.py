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
    self.parametersFormLayout.addRow("Curve: ", self.viewSelector)

    self.editButton = qt.QPushButton("Edit")
    #self.editButton.enabled = False
    self.parametersFormLayout.addRow("", self.editButton)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Create a new parameterNode
    # This parameterNode stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.logic = MarkupEditorLogic()
    self.setParameterNode(self.logic.getParameterNode())

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    #self.markupSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.editButton.connect("clicked()", self.onEditMarkups)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def setParameterNode(self, inputParameterNode):
    """
    Adds observers to the selected parameter node. Observation is needed because when the
    parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previusly selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if inputParameterNode is not None:
      self.addObserver(inputParameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    if self._parameterNode is None:
      return

    TODO = """
    wasBlocked = self.markupSelector.blockSignals(True)
    self.markupSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolumeInverse"))
    self.markupSelector.blockSignals(wasBlocked)

    # Update buttons states and tooltips
    if self._parameterNode.GetNodeReference("Markups"):
      self.editButton.toolTip = "Use scissors to select fiducials"
      self.editButton.enabled = True
    else:
      self.editButton.toolTip = "Select a markup list"
      self.editButton.enabled = False
    """

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
      return

    TODO = """
    self._parameterNode.SetNodeReferenceID("OutputVolumeInverse", self.markupSelector.currentNodeID)
    """

  def onEditMarkups(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:
      viewNode = self.viewSelector.currentNode()
      layoutManager = slicer.app.layoutManager()
      aspectRatio = 1
      for index in range(layoutManager.threeDViewCount):
        threeDWidget = layoutManager.threeDWidget(index)
        if threeDWidget.mrmlViewNode().GetID() == viewNode.GetID():
          aspectRatio = threeDWidget.width / threeDWidget.height
          break
      self.logic.editMarkups(self.fiducialsSelector.currentNode(), self.curveSelector.currentNode(), self.viewSelector.currentNode(), aspectRatio)
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


  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("Threshold"):
      parameterNode.SetParameter("Threshold", "50.0")
    if not parameterNode.GetParameter("Invert"):
      parameterNode.SetParameter("Invert", "false")

  def editMarkups(self, fiducialsNode, curveNode, viewNode, aspectRatio):

    cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
    camera = cameraNode.GetCamera()
    raswToXYZW = vtk.vtkMatrix4x4()
    modelView = camera.GetModelViewTransformMatrix()
    projection = camera.GetProjectionTransformMatrix(aspectRatio, 1, 100) # near/far are arbitrary
    raswToXYZW.Multiply4x4(projection, modelView, raswToXYZW)
    print(raswToXYZW)

    for index in range(fiducialsNode.GetNumberOfControlPoints()):
      ras = [0]*3
      fiducialsNode.GetNthControlPointPositionWorld(index, ras)
      rasw = *ras,1
      xyzw = raswToXYZW.MultiplyPoint(rasw)
      xy = [xyzw[0] / xyzw[3], xyzw[1] / xyzw[3]]
      print(f"{index}: {ras}")
      print(f"{xy}")


  def editMarkupsSEG(self, markups, segmentEditorWidget):
    """
    Edit markups
    Can be used without GUI widget.
    :param markups: markups fiducial node to be edited
    """

    if not markups:
      raise ValueError("markups invalid")

    logging.info('Processing started')

    pointArray = slicer.util.arrayFromMarkupsControlPoints(markups)

    bounds = [0]*6
    markups.GetRASBounds(bounds)
    bounds[0] -= 10; bounds[2] -= 10; bounds[4] -= 10;
    bounds[1] += 10; bounds[3] += 10; bounds[5] += 10;

    print(f'entering n^2 loop on {len(pointArray)} points')
    minDistance = bounds[1]-bounds[0];
    for p in pointArray:
        for pp in pointArray:
            distance = numpy.linalg.norm(p - pp)
            if distance != 0:
                minDistance = min(minDistance, distance)


    print("minDistance", minDistance)
    print("bounds", bounds)

    spacing = min(1,minDistance)

    origin = [bounds[0], bounds[2], bounds[4]]
    farCorner = [bounds[1], bounds[3], bounds[5]]
    shape = [ math.ceil((farCorner[0] - origin[0]) / spacing),
              math.ceil((farCorner[1] - origin[1]) / spacing),
              math.ceil((farCorner[2] - origin[2]) / spacing) ]
    shape.reverse()
    segentationArray = numpy.zeros(shape)
    segentationIJKToRAS = vtk.vtkMatrix4x4()
    segentationIJKToRAS.SetElement(0,0, spacing)
    segentationIJKToRAS.SetElement(1,1, spacing)
    segentationIJKToRAS.SetElement(2,2, spacing)
    segentationIJKToRAS.SetElement(0,3, origin[0])
    segentationIJKToRAS.SetElement(1,3, origin[1])
    segentationIJKToRAS.SetElement(2,3, origin[2])

    print("adding volume")
    masterVolumeNode = slicer.util.addVolumeFromArray(segentationArray, segentationIJKToRAS, "markupVolume")

    # Create segmentation
    segmentationNode = slicer.vtkMRMLSegmentationNode()
    slicer.mrmlScene.AddNode(segmentationNode)
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)

    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

    selectionSegment = slicer.vtkSegment()
    selectionSegment.SetName("selection")
    selectionSegment.SetColor([1.0,0.0,0.0])
    segmentationNode.GetSegmentation().AddSegment(selectionSegment,"selection")
    segmentEditorWidget.setCurrentSegmentID("selection")

    # Run segmentation
    segmentEditorWidget.setActiveEffectByName("Scissors")
    scissors = segmentEditorWidget.activeEffect()
    # You can change parameters by calling: effect.setParameter("MyParameterName", someValue)
    scissors.setParameter("Operation", "FillInside")

    def onRepresentationModified(caller, event):
      selectionArray = slicer.util.arrayFromSegmentInternalBinaryLabelmap(segmentationNode, "selection")
      print("selectionArray.shape", selectionArray.shape)
      orientedImage = slicer.vtkOrientedImageData()
      segmentationNode.GetBinaryLabelmapRepresentation("selection", orientedImage)
      worldToImageMatrix = vtk.vtkMatrix4x4()
      orientedImage.GetImageToWorldMatrix(worldToImageMatrix)
      print(worldToImageMatrix)
      worldToImageMatrix.Invert()
      print(worldToImageMatrix)
      wasModified = markups.StartModify()
      for pointIndex in range(len(pointArray)):
        point = pointArray[pointIndex]
        print("ras point", point)
        ijkFloat = list(worldToImageMatrix.MultiplyPoint([*point, 1])[:3])
        ijkFloat.reverse()
        ijk = [int(round(e)) for e in ijkFloat]
        print("segment ijk", ijk)
        try:
          print(selectionArray[ijk[0], ijk[1], ijk[2]])
          markups.SetNthControlPointSelected(pointIndex, selectionArray[ijk[0], ijk[1], ijk[2]])

        except IndexError:
          print("out of range")
          markups.SetNthControlPointSelected(pointIndex, 0)
      markups.EndModify(wasModified)
      segmentEditorWidget.setActiveEffectByName("None")

    def onSegmentModified(caller, event):
      if not "scalars" in self.observerTags:
        outputOrientedImageData = slicer.vtkOrientedImageData()
        slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentBinaryLabelmapRepresentation(
                                    segmentationNode, "selection", outputOrientedImageData)
        scalars = outputOrientedImageData.GetPointData().GetScalars()
        tag = scalars.AddObserver(vtk.vtkCommand.ModifiedEvent, onScalarsModified)
        self.observerTags['scalars'] = tag
        onScalarsModified(None, None)

    print("ready for scissors")
    #self.observerTags['segment'] = selectionSegment.AddObserver(vtk.vtkCommand.ModifiedEvent, onSegmentModified)
    self.observerTags['segmentation'] = segmentationNode.GetSegmentation().AddObserver(
                slicer.vtkSegmentation.RepresentationModified, onRepresentationModified)

    slicer.modules.sew = segmentEditorWidget
    slicer.modules.scissors = scissors



    TODO = """
    # Clean up and show results
    ################################################
    # Clean up
    slicer.mrmlScene.RemoveNode(segmentEditorNode)

    # Make segmentation results nicely visible in 3D
    segmentationDisplayNode = segmentationNode.GetDisplayNode()
    segmentationDisplayNode.SetSegmentVisibility(backgroundSegmentId, False)
    """


    logging.info('Processing completed')


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

    segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentEditorNode')
    slicer.modules.MarkupEditorWidget.segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)

    # Get/create input data

    import SampleData
    url = 'https://raw.githubusercontent.com/SlicerMorph/SampleData/master/4074_S_lm1.fcsv'
    filePath = SampleData.SampleDataLogic().downloadFileIntoCache(url, "4074_S_lm1.fcsv")

    # filePath = "/Volumes/SSD2T/data/SlicerMorph/markup-performance/USNM174715-Cranium.vtk_SL_warped.fcsv"

    self.delayDisplay("reading")
    markups = slicer.util.loadMarkupsFiducialList(filePath)


    slicer.vtkSlicerMarkupsLogic().SetAllMarkupsSelected(markups, False)

    slicer.app.layoutManager().threeDWidget(0).threeDView().resetCamera()

    self.delayDisplay('Finished with download and loading')

    # Test the module logic

    logic = MarkupEditorLogic()

    # Test algorithm with non-inverted threshold
    self.delayDisplay("editing")
    logic.editMarkups(markups, slicer.modules.MarkupEditorWidget.segmentEditorWidget)

    self.assertEqual(markups, markups)

    self.delayDisplay('Test passed')
