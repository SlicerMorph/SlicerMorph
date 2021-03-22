
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math


#
# MergeCurves
#

class MergeCurves(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "MergeCurves" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module interactively merges markups nodes.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MergeCurves">online documentation.</a>.</p> 
      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe, and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections" 
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839). 
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

#
# MergeCurvesWidget
#

class MergeCurvesWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    
    # Instantiate and connect widgets ...
    
    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)
    
    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)
    
    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.continuousCurvesCheckBox = qt.QCheckBox()
    self.continuousCurvesCheckBox.checked = 0
    self.continuousCurvesCheckBox.setToolTip("If checked, redundant points will be removed on merging.")
    parametersFormLayout.addRow("Contiuous curves", self.continuousCurvesCheckBox)
    
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate semilandmarks."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)
    
    #
    # markups view
    #
    self.markupsView = slicer.qMRMLSubjectHierarchyTreeView()
    self.markupsView.setMRMLScene(slicer.mrmlScene)
    self.markupsView.setMultiSelection(True)
    self.markupsView.setAlternatingRowColors(True)
    self.markupsView.setDragDropMode(qt.QAbstractItemView().DragDrop)
    self.markupsView.setColumnHidden(self.markupsView.model().transformColumn, True)
    self.markupsView.sortFilterProxyModel().setNodeTypes(["vtkMRMLMarkupsCurveNode"])
    parametersFormLayout.addRow(self.markupsView)
    
    #
    # Merge Button
    #
    self.mergeButton = qt.QPushButton("Merge highlighted nodes")
    self.mergeButton.toolTip = "Generate a single merged markup file from the selected nodes"
    self.mergeButton.enabled = False
    parametersFormLayout.addRow(self.mergeButton)
    
    # connections
    self.mergeButton.connect('clicked(bool)', self.onMergeButton)
    self.markupsView.connect('currentItemChanged(vtkIdType)', self.updateMergeButton)
    
    # Add vertical spacer
    self.layout.addStretch(1)
  
  def cleanup(self):
    pass
  
  def onMergeButton(self):
    logic = MergeCurvesLogic()
    logic.run(self.markupsView, self.continuousCurvesCheckBox.checked)
    
  def updateMergeButton(self):
    nodes=self.markupsView.selectedIndexes()
    self.mergeButton.enabled = bool(nodes)

#
# MergeCurvesLogic
#

class MergeCurvesLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, markupsTreeView, continuousCurveOption):
    nodeIDs=markupsTreeView.selectedIndexes()
    nodeList = vtk.vtkCollection()
    for id in nodeIDs:
      if id.column() == 0:
        currentNode = slicer.util.getNode(id.data())
        nodeList.AddItem(currentNode)
    mergedNodeName = "mergedMarkupsNode"
    mergedNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsCurveNode', mergedNodeName)
    purple=[1,0,1]
    mergedNode.GetDisplayNode().SetSelectedColor(purple)
    self.mergeList(nodeList, mergedNode, continuousCurveOption)
    return True
  
  def mergeList(self, nodeList,mergedNode, continuousCurveOption):
    pointList=[]          
    connectingNode=False
    # Add semi-landmark points within triangle patches
    for currentNode in nodeList:
      for index in range(currentNode.GetNumberOfControlPoints()):
        if not(index==0 and continuousCurveOption and connectingNode):
          pt = currentNode.GetNthControlPointPositionVector(index)
          pt_array = [pt.GetX(), pt.GetY(), pt.GetZ()]
          if pt_array not in pointList:
            pointList.append(pt_array)
            fiducialLabel = currentNode.GetNthControlPointLabel(index)
            fiducialDescription = currentNode.GetNthControlPointDescription(index)
            fiducialMeasurement = currentNode.GetNthMeasurement(index)
            mergedNode.AddControlPoint(pt,fiducialLabel)
            mergedIndex = mergedNode.GetNumberOfControlPoints()-1
            mergedNode.SetNthControlPointDescription(mergedIndex,fiducialDescription)
            mergedNode.SetNthMeasurement(mergedIndex, fiducialMeasurement)
      connectingNode=True  
    return True
  
class MergeCurvesTest(ScriptedLoadableModuleTest):
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
    self.test_MergeCurves1()
  
  def test_MergeCurves1(self):
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
    #
    # first, get some data
    #
    import urllib
    downloads = (
                 ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
                 )
    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')
    
    volumeNode = slicer.util.getNode(pattern="FA")
    logic = MergeCurvesLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
