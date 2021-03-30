import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# SegmentEndocranium
#

class SegmentEndocranium(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Segment Endocranium"
    self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Andras Lasso (PerkLab)"]
    self.parent.helpText = """
Automatic segmentation of endocranium from dry bone CT images.
"""  # TODO: update with short description of the module
    self.parent.acknowledgementText = """
This file was originally developed by Andras Lasso, PerkLab.
"""  # TODO: replace with organization, grant and thanks.

#
# SegmentEndocraniumWidget
#

class SegmentEndocraniumWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/SegmentEndocranium.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create a new parameterNode
    # This parameterNode stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.logic = SegmentEndocraniumLogic()
    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Connections
    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.smoothingKernelSizeSliderWidget.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    self.ui.splitCavitiesDiameterSliderWidget.connect("valueChanged(double)", self.updateParameterNodeFromGUI)

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

    # Set parameter node in the parameter node selector widget
    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

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

    # Disable all sections if no parameter node is selected
    self.ui.basicCollapsibleButton.enabled = self._parameterNode is not None
    if self._parameterNode is None:
      return

    # Update each widget from parameter node
    # Need to temporarily block signals to prevent infinite recursion (MRML node update triggers
    # GUI update, which triggers MRML node update, which triggers GUI update, ...)

    wasBlocked = self.ui.inputSelector.blockSignals(True)
    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
    self.ui.inputSelector.blockSignals(wasBlocked)

    wasBlocked = self.ui.outputSelector.blockSignals(True)
    self.ui.outputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputSegmentation"))
    self.ui.outputSelector.blockSignals(wasBlocked)

    wasBlocked = self.ui.smoothingKernelSizeSliderWidget.blockSignals(True)
    if self._parameterNode.GetParameter("SmoothingKernelSize"):
      self.ui.smoothingKernelSizeSliderWidget.value = float(self._parameterNode.GetParameter("SmoothingKernelSize"))
    self.ui.smoothingKernelSizeSliderWidget.blockSignals(wasBlocked)

    wasBlocked = self.ui.splitCavitiesDiameterSliderWidget.blockSignals(True)
    if self._parameterNode.GetParameter("SplitCavitiesDiameter"):
      self.ui.splitCavitiesDiameterSliderWidget.value = float(self._parameterNode.GetParameter("SplitCavitiesDiameter"))
    self.ui.splitCavitiesDiameterSliderWidget.blockSignals(wasBlocked)

    # Update buttons states and tooltips
    if self._parameterNode.GetNodeReference("InputVolume") and self._parameterNode.GetNodeReference("OutputSegmentation"):
      self.ui.applyButton.toolTip = "Compute output segmentation"
      self.ui.applyButton.enabled = True
    else:
      self.ui.applyButton.toolTip = "Select input and output segmentation nodes"
      self.ui.applyButton.enabled = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
      return

    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    self._parameterNode.SetNodeReferenceID("OutputSegmentation", self.ui.outputSelector.currentNodeID)
    self._parameterNode.SetParameter("SmoothingKernelSize", str(self.ui.smoothingKernelSizeSliderWidget.value))
    self._parameterNode.SetParameter("SplitCavitiesDiameter", str(self.ui.splitCavitiesDiameterSliderWidget.value))

  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """

    try:
      qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
      self.logic.run(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
        self.ui.smoothingKernelSizeSliderWidget.value, self.ui.splitCavitiesDiameterSliderWidget.value)
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()
    finally:
      qt.QApplication.restoreOverrideCursor()


#
# SegmentEndocraniumLogic
#

class SegmentEndocraniumLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("SmoothingKernelSize"):
      parameterNode.SetParameter("SmoothingKernelSize", "3.0")

  def run(self, inputVolume, outputSegmentation, smoothingKernelSize=3.0, splitCavitiesDiameter=15.0):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be segmented
    :param outputSegmentation: segmentation to sore the result in
    :param smoothingKernelSize: this is used for closing small holes in the segmentation
    :param splitCavitiesDiameter: plugs in holes smaller than splitCavitiesDiamater.
    """

    if not inputVolume or not outputSegmentation:
      raise ValueError("Input volume or output segmentation is invalid")

    logging.info('Processing started')

    # Compute bone threshold value automatically
    import vtkITK
    thresholdCalculator = vtkITK.vtkITKImageThresholdCalculator()
    thresholdCalculator.SetInputData(inputVolume.GetImageData())
    # thresholdCalculator.SetMethodToOtsu()  - this does not always work (see for example CTHead example data set)
    thresholdCalculator.SetMethodToMaximumEntropy()
    thresholdCalculator.Update()
    boneThresholdValue = thresholdCalculator.GetThreshold()
    volumeScalarRange = inputVolume.GetImageData().GetScalarRange()
    logging.debug("Volume minimum = {0}, maximum = {1}, bone threshold = {2}".format(volumeScalarRange[0], volumeScalarRange[1], boneThresholdValue))

    # Set up segmentation
    outputSegmentation.CreateDefaultDisplayNodes()
    outputSegmentation.SetReferenceImageGeometryParameterFromVolumeNode(inputVolume)

    # Create segment editor to get access to effects
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    # To show segment editor widget (useful for debugging): segmentEditorWidget.show()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    if not segmentEditorWidget.effectByName("Wrap Solidify"):
      raise NotImplementedError("SurfaceWrapSolidify extension is required")

    segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
    slicer.mrmlScene.AddNode(segmentEditorNode)
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(outputSegmentation)
    segmentEditorWidget.setMasterVolumeNode(inputVolume)

    # Create bone segment by thresholding
    boneSegmentID = outputSegmentation.GetSegmentation().AddEmptySegment("bone")
    segmentEditorNode.SetSelectedSegmentID(boneSegmentID)
    segmentEditorWidget.setActiveEffectByName("Threshold")
    effect = segmentEditorWidget.activeEffect()
    effect.setParameter("MinimumThreshold",str(boneThresholdValue))
    effect.setParameter("MaximumThreshold",str(volumeScalarRange[1]))
    effect.self().onApply()

    # Smooth bone segment (just to reduce solidification computation time)
    segmentEditorWidget.setActiveEffectByName("Smoothing")
    effect = segmentEditorWidget.activeEffect()
    effect.setParameter("SmoothingMethod", "MORPHOLOGICAL_CLOSING")
    effect.setParameter("KernelSizeMm", str(smoothingKernelSize))
    effect.self().onApply()

    # Solidify bone
    segmentEditorWidget.setActiveEffectByName("Wrap Solidify")
    effect = segmentEditorWidget.activeEffect()
    effect.setParameter("region", "largestCavity")
    effect.setParameter("splitCavities", "True" if splitCavitiesDiameter > 0 else "False")
    effect.setParameter("splitCavitiesDiameter", str(splitCavitiesDiameter))  # in mm
    effect.setParameter("outputType", "newSegment")  # in mm
    effect.self().onApply()

    # Clean up
    #slicer.mrmlScene.RemoveNode(segmentEditorNode)
    #outputSegmentation.RemoveSegment(boneSegmentID)
    #segmentEditorWidget = None

    logging.info('Processing completed')

#
# SegmentEndocraniumTest
#

class SegmentEndocraniumTest(ScriptedLoadableModuleTest):
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
    self.test_SegmentEndocranium1()

  def test_SegmentEndocranium1(self):
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

    # Get/create input data

    import SampleData
    inputVolume = SampleData.downloadFromURL(
      nodeNames='MRHead',
      fileNames='MR-Head.nrrd',
      uris='https://github.com/Slicer/SlicerTestingData/releases/download/MD5/39b01631b7b38232a220007230624c8e',
      checksums='MD5:39b01631b7b38232a220007230624c8e')[0]
    self.delayDisplay('Finished with download and loading')

    outputSegmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    logic = SegmentEndocraniumLogic()

    # TODO: implement test - it should be reasonable quick (no more than 1-2 minutes) and use an openly available data set
    #logic.run(inputVolume, outputSegmentation)
    #outputScalarRange = outputSegmentation.GetImageData().GetScalarRange()
    #self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    #self.assertEqual(outputScalarRange[1], threshold)

    self.delayDisplay('Test passed')
