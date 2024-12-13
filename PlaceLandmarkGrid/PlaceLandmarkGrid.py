import logging
import os
import qt
import vtk
import ctk
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import math
import numpy as np
import scipy.linalg as sp

#
# PlaceLandmarkGrid
#

class PlaceLandmarkGrid(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "PlaceLandmarkGrid"
        self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Sara Rolfe (SCRI), Murat Maga (SCRI, UW)"]
        self.parent.helpText = """
        This module places a grid of semi-landmark points that are snapped to a model.
        """
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
        This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
        awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
        https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
        """

#
# PlaceLandmarkGridWidget
#

class PlaceLandmarkGridWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        extensionName = 'SurfaceMarkup'
        em = slicer.app.extensionsManagerModel()
        if not em.isExtensionInstalled(extensionName):
          if slicer.util.confirmOkCancelDisplay("PlaceLandmarkGrid requires installation of the SurfaceMarkup extension.\nClick OK to install and restart the application."):
            em.interactive = False  # prevent display of popups
            em.updateExtensionsMetadataFromServer(True, True)  # update extension metadata from server
            if not em.downloadAndInstallExtensionByName(extensionName, True, True):
              raise ValueError(f"Failed to install {extensionName} extension")
            else:
              slicer.util.restart()

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)
        #
        # Parameters Area
        #
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Parameters"
        self.layout.addWidget(parametersCollapsibleButton)

        # Layout within the dummy collapsible button
        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        #
        # Select model
        #
        self.modelSelector = slicer.qMRMLNodeComboBox()
        self.modelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
        self.modelSelector.selectNodeUponCreation = False
        self.modelSelector.addEnabled = False
        self.modelSelector.removeEnabled = False
        self.modelSelector.noneEnabled = True
        self.modelSelector.showHidden = False
        self.modelSelector.setMRMLScene( slicer.mrmlScene )
        parametersFormLayout.addRow("Model: ", self.modelSelector)

        #
        # Select active patch
        #
        self.gridSelector = qt.QComboBox()
        self.gridSelector.addItem('None')
        parametersFormLayout.addRow("Active patch: ", self.gridSelector)

        #
        # set sample rate value
        #
        self.sampleRate = ctk.ctkDoubleSpinBox()
        self.sampleRate.singleStep = 2
        self.sampleRate.minimum = 3
        self.sampleRate.maximum = 100
        self.sampleRate.setDecimals(0)
        self.sampleRate.value = 5
        self.sampleRate.setToolTip("Select grid resolution")
        parametersFormLayout.addRow("Resolution for landmark grid:", self.sampleRate)

        #
        # flip normals checkbox
        #
        self.flipNormalsCheckBox = qt.QCheckBox()
        self.flipNormalsCheckBox.checked = False
        self.flipNormalsCheckBox.setToolTip("If checked, flip grid surface direction.")
        parametersFormLayout.addRow("Flip grid orientation", self.flipNormalsCheckBox)

        #
        # Advanced menu
        #
        advancedCollapsibleButton = ctk.ctkCollapsibleButton()
        advancedCollapsibleButton.text = "Advanced"
        advancedCollapsibleButton.collapsed = True
        parametersFormLayout.addRow(advancedCollapsibleButton)
        # Layout within the dummy collapsible button
        advancedFormLayout = qt.QFormLayout(advancedCollapsibleButton)

        #
        # Spatial filtering slider
        #
        self.projectionDistanceSlider = ctk.ctkSliderWidget()
        self.projectionDistanceSlider.singleStep = 0.01
        self.projectionDistanceSlider.minimum = 0
        self.projectionDistanceSlider.maximum = 1
        self.projectionDistanceSlider.value = 0.2
        self.projectionDistanceSlider.setToolTip("Set the projection factor as a percentage of image")
        advancedFormLayout.addRow("Set projection factor: ", self.projectionDistanceSlider)

        self.relaxationSlider = ctk.ctkSliderWidget()
        self.relaxationSlider.singleStep = 0.1
        self.relaxationSlider.minimum = 0
        self.relaxationSlider.maximum = 1
        self.relaxationSlider.value = 0.8
        self.relaxationSlider.setToolTip("Set the grid relaxation factor")
        advancedFormLayout.addRow("Set relaxation factor: ", self.relaxationSlider)

        self.iterationsSlider = ctk.ctkSliderWidget()
        self.iterationsSlider.singleStep = 10
        self.iterationsSlider.minimum = 0
        self.iterationsSlider.maximum = 500
        self.iterationsSlider.value = 100
        self.iterationsSlider.setToolTip("Set number of smoothing iterations for grid relaxation")
        advancedFormLayout.addRow("Set grid smoothing iterations: ", self.iterationsSlider)

        #
        # Create Grid Button
        #
        self.createGridButton = qt.QPushButton("Create a new grid patch")
        self.createGridButton.toolTip = "Initiate placement of a new grid markup"
        self.createGridButton.enabled = False
        parametersFormLayout.addRow(self.createGridButton)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = PlaceLandmarkGridLogic()

        # Connections
        self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.gridSelector.connect('currentIndexChanged(int)', self.onSelectGrid)
        self.flipNormalsCheckBox.connect('stateChanged(int)', self.onResampleGrid)
        self.createGridButton.connect('clicked(bool)', self.onCreateGridButton)
        self.sampleRate.connect('valueChanged(double )', self.onSampleRateChanged)
        self.projectionDistanceSlider.connect('valueChanged(double )', self.onResampleGrid)

        # Track number of patches generated for naming
        self.patchCounter = -1
        self.patchList = []
        self.updatingGUI = False
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        self.observerTagDeleteGrid = shNode.AddObserver(shNode.SubjectHierarchyItemAboutToBeRemovedEvent, self.deleteObservers)

    @vtk.calldata_type(vtk.VTK_INT)
    def onSampleRateChanged(self):
        if self.sampleRate.value <= 1:
          self.sampleRate.value = 3
          qt.QMessageBox.critical(slicer.util.mainWindow(),
            'Warning', 'The minimum landmark grid resolution is 3x3')
        if self.sampleRate.value % 2 == 0:
          self.sampleRate.value += 1
          qt.QMessageBox.critical(slicer.util.mainWindow(),
            'Warning', 'The landmark grid resolution must be odd')
        self.onResampleGrid()

    def onSelect(self):
        self.createGridButton.enabled = bool(self.modelSelector.currentNode())

    def onSelectGrid(self):
        if self.gridSelector.currentText == "None":
          return
        if not self.updatingGUI:
          try:
            newPatch = self.patchList[self.gridSelector.currentIndex - 1]
            self.updateCurrentPatch(newPatch)
            print("New patch: ", self.patchList[self.gridSelector.currentIndex - 1].name)
          except:
            qt.QMessageBox.critical(slicer.util.mainWindow(),
            'Error', 'The selected landmark grid patch is not valid.')
            self.gridSelector.setCurrentIndex(0)

    def onCreateGridButton(self):
        self.patchCounter += 1
        constraintNode = self.modelSelector.currentNode()
        self.outlineCurve = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsClosedCurveNode", f"gridOutline_{self.patchCounter}")
        self.outlineCurve.AddNControlPoints(4, "outline", (0,0,0) )
        self.outlineCurve.UnsetAllControlPoints()
        self.outlineCurve.SetFixedNumberOfControlPoints(True)
        self.outlineCurve.SetCurveTypeToLinear()
        self.outlineCurve.SetAndObserveSurfaceConstraintNode(constraintNode)
        self.outlineCurve.SetSurfaceConstraintMaximumSearchRadiusTolerance(.75)
        self.outlineCurve.GetDisplayNode().SetSelectedColor(0,1,0)
        self.outlineCurve.GetDisplayNode().SetGlyphScale(3.2)
        slicer.modules.markups.toolBar().onPlacePointShortcut()

        # hide support nodes and update GUI
        observerTagPointAdded = self.outlineCurve.AddObserver(slicer.vtkMRMLMarkupsClosedCurveNode.PointPositionDefinedEvent, self.initializeInteractivePatch)

    def onResampleGrid(self):
      if self.outlineCurve.GetNumberOfControlPoints() != 4:
        print("Please finish placing grid outline with 4 points")
        return
      gridResolution = int(self.sampleRate.value)
      flipNormalsFlag = self.flipNormalsCheckBox.checked
      #if not self.patch.hasGrid:
      self.patch.initializeGrid(gridResolution)
      self.logic.placeGrid(gridResolution, self.patch)
      self.logic.relaxGrid(self.patch.gridNode, self.patch.constraintNode, gridResolution, self.relaxationSlider.value, int(self.iterationsSlider.value))
      self.logic.projectPatch(self.patch.constraintNode, self.patch.gridNode, self.patch.gridModel, self.projectionDistanceSlider.value, flipNormalsFlag)

    def onSampleGrid(self):
      if self.outlineCurve.GetNumberOfControlPoints() != 4:
        print("Please finish placing grid outline with 4 points")
        return
      gridResolution = int(self.sampleRate.value)
      flipNormalsFlag = self.flipNormalsCheckBox.checked
      #if not self.patch.hasGrid:
      self.patch.initializeGrid(gridResolution)
      self.logic.placeGrid(gridResolution, self.patch)
      self.logic.relaxGrid(self.patch.gridNode, self.patch.constraintNode, gridResolution, self.relaxationSlider.value, int(self.iterationsSlider.value))
      self.logic.projectPatch(self.patch.constraintNode, self.patch.gridNode, self.patch.gridModel, self.projectionDistanceSlider.value, flipNormalsFlag)

      # curve event handling
      observerTagGridCorner0 = self.patch.cornerPoint0.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridCorner1 = self.patch.cornerPoint1.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridCorner2 = self.patch.cornerPoint2.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridCorner3 = self.patch.cornerPoint3.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)

      observerTagGridMid0 = self.patch.midPoint0.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridMid1 = self.patch.midPoint1.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridMid2 = self.patch.midPoint2.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)
      observerTagGridMid3 = self.patch.midPoint3.AddObserver(slicer.vtkMRMLMarkupsCurveNode.PointEndInteractionEvent, self.refreshGrid)

    def refreshGrid(self, caller, eventId):
      self.patch.gridNode.LockedOff()
      gridResolution = int(self.patch.resolution)
      flipNormalsFlag = self.flipNormalsCheckBox.checked
      self.patch.gridNode.RemoveAllControlPoints()
      self.patch.gridNode.SetGridResolution(gridResolution,gridResolution)
      self.patch.gridModel = self.patch.gridNode.GetOutputSurfaceModelNode()
      self.logic.placeGrid(gridResolution, self.patch)
      self.patch.gridNode.SetOutputSurfaceModelNodeID(self.patch.gridModel.GetID())
      self.logic.relaxGrid(self.patch.gridNode, self.patch.constraintNode, gridResolution, self.relaxationSlider.value, int(self.iterationsSlider.value))
      self.logic.projectPatch(self.patch.constraintNode, self.patch.gridNode, self.patch.gridModel, self.projectionDistanceSlider.value, flipNormalsFlag)
      self.patch.gridModel.SetDisplayVisibility(False)
      self.patch.gridNode.LockedOn()

    def initializeInteractivePatch(self, caller, eventId):
      if self.outlineCurve.GetNumberOfDefinedControlPoints() != 4:
        return
      self.updatingGUI = True
      self.logic = PlaceLandmarkGridLogic()
      gridName = "gridPatch_" + str(self.patchCounter)
      constraintNode = self.modelSelector.currentNode()
      self.patch = InteractivePatch(self.outlineCurve, constraintNode, str(self.patchCounter))
      self.updatingNodesActive = False
      if self.gridSelector.currentIndex>0:
        lastPatch = self.patchList[self.gridSelector.currentIndex-1]
        lastPatch.setLockPatch(True)
      self.patchList.append(self.patch)
      self.gridSelector.addItem(self.patch.name)
      self.gridSelector.setCurrentText(self.patch.name)
      self.outlineCurve.SetDisplayVisibility(False)
      self.outlineCurve.HideFromEditorsOn()
      self.updatingGUI = False
      self.onSampleGrid()

    def updateCurrentPatch(self, newPatch):
      self.patch.setLockPatch(True)
      self.patch = newPatch
      self.patch.setLockPatch(False)
      self.sampleRate.value = self.patch.resolution

    @vtk.calldata_type(vtk.VTK_INT)
    def deleteObservers(self, caller, event, removedItem):
      shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
      removedNode = shNode.GetItemDataNode(removedItem) if removedItem else None
      if removedNode is not None and removedNode.IsA('vtkMRMLNode'):
        removedNode.RemoveAllObservers()
        removedNodeGridName = shNode.GetItemName(removedItem)
        removedNodeName = removedNodeGridName.replace("grid", "gridPatch")
        allGrids = [self.gridSelector.itemText(i) for i in range(self.gridSelector.count)]
        if removedNodeName in allGrids:
          index = allGrids.index(removedNodeName)
          self.gridSelector.removeItem(index)
          self.patchList.pop(index-1)

# PlaceLandmarkGridLogic
#
class InteractivePatch:
  def __init__(self, closedCurve, surfaceConstraintNode, gridID):
    self.name = "gridPatch_" + gridID
    self.gridID = gridID
    self.constraintNode = surfaceConstraintNode
    self.hasGrid = False
    self.resolution = 5
    self.colorValue=[0,0,0]
    colorNode=slicer.util.getNode("MediumChartColors")
    colorNode.GetLookupTable().GetColor(int(gridID),self.colorValue)

    self.cornerPoint0 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "cornerPoint0")
    self.cornerPoint0.AddControlPoint(closedCurve.GetNthControlPointPosition(0))
    self.cornerPoint0.GetDisplayNode().SetSelectedColor(0,1,0)
    self.cornerPoint0.GetDisplayNode().SetTextScale(0)
    self.tagC0 = self.cornerPoint0.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateCornerPoint)
    self.cornerPoint1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "cornerPoint1")
    self.cornerPoint1.AddControlPoint(closedCurve.GetNthControlPointPosition(1))
    self.cornerPoint1.GetDisplayNode().SetSelectedColor(0,1,0)
    self.cornerPoint1.GetDisplayNode().SetTextScale(0)
    self.tagC1 = self.cornerPoint1.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateCornerPoint)
    self.cornerPoint2 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "cornerPoint2")
    self.cornerPoint2.AddControlPoint(closedCurve.GetNthControlPointPosition(2))
    self.cornerPoint2.GetDisplayNode().SetSelectedColor(0,1,0)
    self.cornerPoint2.GetDisplayNode().SetTextScale(0)
    self.tagC2 = self.cornerPoint2.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateCornerPoint)
    self.cornerPoint3 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "cornerPoint3")
    self.cornerPoint3.AddControlPoint(closedCurve.GetNthControlPointPosition(3))
    self.cornerPoint3.GetDisplayNode().SetSelectedColor(0,1,0)
    self.cornerPoint3.GetDisplayNode().SetTextScale(0)
    self.tagC3 = self.cornerPoint3.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateCornerPoint)

    self.gridLine0 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode", "gridLine0")
    self.gridLine0.AddControlPoint(closedCurve.GetNthControlPointPosition(0))
    self.gridLine0.AddControlPoint(closedCurve.GetNthControlPointPosition(1))
    self.gridLine0.SetAndObserveSurfaceConstraintNode(surfaceConstraintNode)
    self.gridLine0.ResampleCurveWorld(self.gridLine0.GetCurveLengthWorld()/2)
    self.gridLine0.SetFixedNumberOfControlPoints(True)
    self.gridLine0.GetDisplayNode().SetGlyphScale(2.5)
    self.gridLine0.GetDisplayNode().SetTextScale(0)
    self.gridLine0.GetDisplayNode().SetSelectedColor(0,1,0)
    self.gridLine0.LockedOn()

    self.gridLine1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode", "gridLine1")
    self.gridLine1.AddControlPoint(closedCurve.GetNthControlPointPosition(1))
    self.gridLine1.AddControlPoint(closedCurve.GetNthControlPointPosition(2))
    self.gridLine1.SetAndObserveSurfaceConstraintNode(surfaceConstraintNode)
    self.gridLine1.ResampleCurveWorld(self.gridLine1.GetCurveLengthWorld()/2)
    self.gridLine1.SetFixedNumberOfControlPoints(True)
    self.gridLine1.GetDisplayNode().SetGlyphScale(2.5)
    self.gridLine1.GetDisplayNode().SetTextScale(0)
    self.gridLine1.GetDisplayNode().SetSelectedColor(0,1,0)
    self.gridLine1.LockedOn()

    self.gridLine2 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode", "gridLine2")
    self.gridLine2.AddControlPoint(closedCurve.GetNthControlPointPosition(2))
    self.gridLine2.AddControlPoint(closedCurve.GetNthControlPointPosition(3))
    self.gridLine2.SetAndObserveSurfaceConstraintNode(surfaceConstraintNode)
    self.gridLine2.ResampleCurveWorld(self.gridLine2.GetCurveLengthWorld()/2)
    self.gridLine2.SetFixedNumberOfControlPoints(True)
    self.gridLine2.GetDisplayNode().SetGlyphScale(2.5)
    self.gridLine2.GetDisplayNode().SetTextScale(0)
    self.gridLine2.GetDisplayNode().SetSelectedColor(0,1,0)
    self.gridLine2.LockedOn()

    self.gridLine3 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode", "gridLine3")
    self.gridLine3.AddControlPoint(closedCurve.GetNthControlPointPosition(3))
    self.gridLine3.AddControlPoint(closedCurve.GetNthControlPointPosition(0))
    self.gridLine3.SetAndObserveSurfaceConstraintNode(surfaceConstraintNode)
    self.gridLine3.ResampleCurveWorld(self.gridLine3.GetCurveLengthWorld()/2)
    self.gridLine3.SetFixedNumberOfControlPoints(True)
    self.gridLine3.GetDisplayNode().SetGlyphScale(2.5)
    self.gridLine3.GetDisplayNode().SetTextScale(0)
    self.gridLine3.GetDisplayNode().SetSelectedColor(0,1,0)
    self.gridLine3.LockedOn()

    self.midPoint0 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "midPoint0")
    self.midPoint0.AddControlPoint(self.gridLine0.GetNthControlPointPosition(1))
    self.midPoint0.GetDisplayNode().SetSelectedColor(0,0,1)
    self.midPoint0.GetDisplayNode().SetTextScale(0)
    self.midPoint0.GetDisplayNode().SetGlyphScale(3.2)
    self.tag_M0 = self.midPoint0.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateMidPoint)
    self.midPoint1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "midPoint1")
    self.midPoint1.AddControlPoint(self.gridLine1.GetNthControlPointPosition(1))
    self.midPoint1.GetDisplayNode().SetSelectedColor(0,0,1)
    self.midPoint1.GetDisplayNode().SetTextScale(0)
    self.midPoint1.GetDisplayNode().SetGlyphScale(3.2)
    self.tag_M1 = self.midPoint1.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateMidPoint)
    self.midPoint2 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "midPoint2")
    self.midPoint2.AddControlPoint(self.gridLine2.GetNthControlPointPosition(1))
    self.midPoint2.GetDisplayNode().SetSelectedColor(0,0,1)
    self.midPoint2.GetDisplayNode().SetTextScale(0)
    self.midPoint2.GetDisplayNode().SetGlyphScale(3.2)
    self.tag_M2 = self.midPoint2.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateMidPoint)
    self.midPoint3 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "midPoint3")
    self.midPoint3.AddControlPoint(self.gridLine3.GetNthControlPointPosition(1))
    self.midPoint3.GetDisplayNode().SetSelectedColor(0,0,1)
    self.midPoint3.GetDisplayNode().SetTextScale(0)
    self.midPoint3.GetDisplayNode().SetGlyphScale(3.2)
    self.tag_M3 = self.midPoint3.AddObserver(slicer.vtkMRMLMarkupsFiducialNode().PointModifiedEvent, self.updateMidPoint)

    shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    sceneItemID = shNode.GetSceneItemID()
    self.folder = shNode.CreateFolderItem(sceneItemID, self.name)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.cornerPoint0), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.cornerPoint1), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.cornerPoint2), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.cornerPoint3), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.midPoint0), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.midPoint1), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.midPoint2), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.midPoint3), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridLine0), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridLine1), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridLine2), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridLine3), self.folder)

    self.updatingNodesActive = False

  def initializeGrid(self, gridResolution):
    # set up grid and supporting nodes
    if not self.hasGrid:
      self.gridNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsGridSurfaceNode",f"grid_{self.gridID}")
      self.gridModel=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode",f"gridModel_{self.gridID}")
    self.gridNode.SetOutputSurfaceModelNodeID(self.gridModel.GetID())
    self.gridNode.SetGridResolution(gridResolution,gridResolution)
    self.gridNode.RemoveAllControlPoints()
    self.hasGrid = True
    # update view
    self.gridModel.SetDisplayVisibility(False)
    self.gridModel.HideFromEditorsOn()
    self.gridNode.GetDisplayNode().SetGlyphScale(2.5)
    self.gridNode.LockedOn()
    self.gridNode.GetDisplayNode().SetSelectedColor(self.colorValue)
    self.resolution = gridResolution

    shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridModel), self.folder)
    shNode.SetItemParent(shNode.GetItemByDataNode(self.gridNode), self.folder)

  def unsetGridLine(self, gridLine):
    gridLine.LockedOff()
    gridLine.SetFixedNumberOfControlPoints(False)
    gridLine.RemoveNthControlPoint(1)

  def resetGridLine(self, gridLine):
    gridLine.ResampleCurveWorld(gridLine.GetCurveLengthWorld()/2)
    gridLine.SetFixedNumberOfControlPoints(True)
    gridLine.LockedOn()

  def updateCornerPoint(self, caller, eventId):
    if not self.updatingNodesActive:
      self.updatingNodesActive = True
      if caller.GetName() == "cornerPoint0":
        self.unsetGridLine(self.gridLine0)
        self.unsetGridLine(self.gridLine3)
        self.gridLine0.SetNthControlPointPosition(0, caller.GetNthControlPointPosition(0))
        self.gridLine3.SetNthControlPointPosition(1, caller.GetNthControlPointPosition(0))
        self.resetGridLine(self.gridLine0)
        self.resetGridLine(self.gridLine3)
        self.midPoint0.SetNthControlPointPosition(0,self.gridLine0.GetNthControlPointPosition(1))
        self.midPoint3.SetNthControlPointPosition(0,self.gridLine3.GetNthControlPointPosition(1))
      elif caller.GetName() == "cornerPoint1":
        self.unsetGridLine(self.gridLine0)
        self.unsetGridLine(self.gridLine1)
        self.gridLine0.SetNthControlPointPosition(1, caller.GetNthControlPointPosition(0))
        self.gridLine1.SetNthControlPointPosition(0, caller.GetNthControlPointPosition(0))
        self.resetGridLine(self.gridLine0)
        self.resetGridLine(self.gridLine1)
        self.midPoint0.SetNthControlPointPosition(0,self.gridLine0.GetNthControlPointPosition(1))
        self.midPoint1.SetNthControlPointPosition(0,self.gridLine1.GetNthControlPointPosition(1))
      elif caller.GetName() == "cornerPoint2":
        self.unsetGridLine(self.gridLine1)
        self.unsetGridLine(self.gridLine2)
        self.gridLine1.SetNthControlPointPosition(1, caller.GetNthControlPointPosition(0))
        self.gridLine2.SetNthControlPointPosition(0, caller.GetNthControlPointPosition(0))
        self.resetGridLine(self.gridLine1)
        self.resetGridLine(self.gridLine2)
        self.midPoint1.SetNthControlPointPosition(0,self.gridLine1.GetNthControlPointPosition(1))
        self.midPoint2.SetNthControlPointPosition(0,self.gridLine2.GetNthControlPointPosition(1))
      elif caller.GetName() == "cornerPoint3":
        self.unsetGridLine(self.gridLine2)
        self.unsetGridLine(self.gridLine3)
        self.gridLine2.SetNthControlPointPosition(1, caller.GetNthControlPointPosition(0))
        self.gridLine3.SetNthControlPointPosition(0, caller.GetNthControlPointPosition(0))
        self.resetGridLine(self.gridLine2)
        self.resetGridLine(self.gridLine3)
        self.midPoint2.SetNthControlPointPosition(0,self.gridLine2.GetNthControlPointPosition(1))
        self.midPoint3.SetNthControlPointPosition(0,self.gridLine3.GetNthControlPointPosition(1))
      self.updatingNodesActive = False

  def updateMidPoint(self, caller, eventId):
    if not self.updatingNodesActive:
      self.updatingNodesActive = True
      self.gridLine0.SetNthControlPointPosition(1,self.midPoint0.GetNthControlPointPosition(0))
      self.gridLine1.SetNthControlPointPosition(1,self.midPoint1.GetNthControlPointPosition(0))
      self.gridLine2.SetNthControlPointPosition(1,self.midPoint2.GetNthControlPointPosition(0))
      self.gridLine3.SetNthControlPointPosition(1,self.midPoint3.GetNthControlPointPosition(0))
      self.updatingNodesActive = False

  def setLockPatch(self, setLocked):
    #self.gridNode.SetLocked(setLocked)
    self.cornerPoint0.SetLocked(setLocked)
    self.cornerPoint1.SetLocked(setLocked)
    self.cornerPoint2.SetLocked(setLocked)
    self.cornerPoint3.SetLocked(setLocked)
    self.midPoint0.SetLocked(setLocked)
    self.midPoint1.SetLocked(setLocked)
    self.midPoint2.SetLocked(setLocked)
    self.midPoint3.SetLocked(setLocked)


class PlaceLandmarkGridLogic(ScriptedLoadableModuleLogic):
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

    def placeGrid(self, gridResolution, patch):
        error = 0.0003
        gridPointNumber = gridResolution*gridResolution
        gridNode = patch.gridNode
        # set up transform between base lms and current lms
        sourcePoints = vtk.vtkPoints()
        targetPoints = vtk.vtkPoints()
        sourcePoints.InsertNextPoint(patch.cornerPoint0.GetNthControlPointPosition(0))
        sourcePoints.InsertNextPoint(patch.cornerPoint1.GetNthControlPointPosition(0))
        sourcePoints.InsertNextPoint(patch.cornerPoint2.GetNthControlPointPosition(0))

        for i in range(3):
          point = sourcePoints.GetPoint(i)
          gridNode.AddControlPoint(point)
        gridNumber = gridNode.GetNumberOfControlPoints()
        gridResMid = int((gridResolution-1)/2)
        #get source points from grid corners and midpoints
        gridCorners = [gridNode.GetNthControlPointPosition(0), gridNode.GetNthControlPointPosition(gridResolution-1), gridNode.GetNthControlPointPosition(gridPointNumber-gridResolution), gridNode.GetNthControlPointPosition(gridPointNumber-1)]
        gridMidPoints = [gridNode.GetNthControlPointPosition(gridResMid), gridNode.GetNthControlPointPosition(int(((gridNumber-1)/2)-gridResMid)), gridNode.GetNthControlPointPosition(int(((gridNumber-1)/2)+gridResMid)), gridNode.GetNthControlPointPosition(gridPointNumber-gridResMid-1)]
        curveCorners=[]
        #get target points from placed curve
        targetPoints.InsertNextPoint(patch.cornerPoint0.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.cornerPoint1.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.cornerPoint2.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.cornerPoint3.GetNthControlPointPosition(0))
        for i in range(4):
          point = targetPoints.GetPoint(i)
          curveCorners.append(point)

        for corner in gridCorners:
          if not np.isclose(curveCorners, corner, error).any():
            sourcePoints.InsertNextPoint(corner)

        if sourcePoints.GetNumberOfPoints() != targetPoints.GetNumberOfPoints():
          print("Grid corners already at curve corners")
          sourcePoints = targetPoints

        # add midpoints
        for gridMidPoint in gridMidPoints:
            sourcePoints.InsertNextPoint(gridMidPoint)
        targetPoints.InsertNextPoint(patch.midPoint0.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.midPoint3.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.midPoint1.GetNthControlPointPosition(0))
        targetPoints.InsertNextPoint(patch.midPoint2.GetNthControlPointPosition(0))

        transform = vtk.vtkThinPlateSplineTransform()
        transform.SetSourceLandmarks( sourcePoints )
        transform.SetTargetLandmarks( targetPoints )
        transform.SetBasisToR()  # for 3D transform

        transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
        transformNode.SetAndObserveTransformToParent(transform)
        gridNode.SetAndObserveTransformNodeID(transformNode.GetID())
        gridNode.HardenTransform()
        slicer.mrmlScene.RemoveNode(transformNode)

    def flipSurfacePatchOrientation(self, gridModelNode):
      reverse = vtk.vtkReverseSense()
      reverse.SetInputData(gridModelNode.GetPolyData())
      reverse.Update()
      gridModelNode.SetAndObservePolyData(reverse.GetOutput())
      normals = vtk.vtkPolyDataNormals()
      normals.SetInputData(gridModelNode.GetPolyData())
      normals.Update()
      gridModelNode.SetAndObservePolyData(normals.GetOutput())

    def projectPatch(self, model, markupNode, markupModel, projectionFactor, flipNormalsFlag):
      points = self.markup2VtkPoints(markupNode)
      maxProjection = (model.GetPolyData().GetLength()) * projectionFactor
      if flipNormalsFlag:
        gridModelFlip=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode","gridModelTemp")
        gridModelFlip.SetAndObservePolyData(markupModel.GetPolyData())
        self.flipSurfacePatchOrientation(gridModelFlip)
        projectedPoints = self.projectPointsPolydata(gridModelFlip.GetPolyData(), model.GetPolyData(), points, maxProjection)
        slicer.mrmlScene.RemoveNode(gridModelFlip)
      else:
        projectedPoints = self.projectPointsPolydata(markupModel.GetPolyData(), model.GetPolyData(), points, maxProjection)
      self.updateGridPoints(markupNode, projectedPoints)

    def updateGridPoints(self, grid, pointsVtk):
      for i in range(pointsVtk.GetNumberOfPoints()):
        p = pointsVtk.GetPoint(i)
        grid.SetNthControlPointPosition(i,p)

    def markup2VtkPoints(self, markupNode):
      # Convert markup points to VTK points
      pointsVtk = vtk.vtkPoints()
      for i in range(markupNode.GetNumberOfControlPoints()):
        p=markupNode.GetNthControlPointPosition(i)
        pointsVtk.InsertNextPoint(p)
      return pointsVtk

    def vtkPoints2Markup(self, pointsVtk):
      # Convert markup points to VTK points
      markupNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"projected landmarks")
      markupNode.CreateDefaultDisplayNodes()
      for i in range(pointsVtk.GetNumberOfPoints()):
        p = pointsVtk.GetPoint(i)
        markupNode.AddControlPoint(p)
      markupNode.GetDisplayNode().SetTextScale(0)
      return markupNode

    def projectPointsPolydata(self, sourcePolydata, targetPolydata, originalPoints, rayLength):
      #set up polydata for projected points to return
      projectedPointData = vtk.vtkPolyData()
      projectedPoints = vtk.vtkPoints()
      projectedPointData.SetPoints(projectedPoints)

      #set up locater for intersection with normal vector rays
      obbTree = vtk.vtkOBBTree()
      obbTree.SetDataSet(targetPolydata)
      obbTree.BuildLocator()

      #set up point locator for finding surface normals and closest point
      pointLocator = vtk.vtkPointLocator()
      pointLocator.SetDataSet(sourcePolydata)
      pointLocator.BuildLocator()

      targetPointLocator = vtk.vtkPointLocator()
      targetPointLocator.SetDataSet(targetPolydata)
      targetPointLocator.BuildLocator()

      #get surface normal from each landmark point
      rayDirection=[0,0,0]
      normalArray = sourcePolydata.GetPointData().GetArray("Normals")
      if(not normalArray):
        print("no normal array, calculating....")
        normalFilter=vtk.vtkPolyDataNormals()
        normalFilter.ComputePointNormalsOn()
        normalFilter.SetInputData(sourcePolydata)
        normalFilter.Update()
        normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
        if(not normalArray):
          print("Error: no normal array")
          return projectedPointData
      for index in range(originalPoints.GetNumberOfPoints()):
        originalPoint= originalPoints.GetPoint(index)
        # get ray direction from closest normal
        closestPointId = pointLocator.FindClosestPoint(originalPoint)
        rayDirection = normalArray.GetTuple(closestPointId)
        rayEndPoint=[0,0,0]
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* rayLength
        intersectionIds=vtk.vtkIdList()
        intersectionPoints=vtk.vtkPoints()
        obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
        #if there are intersections, update the point to most external one.
        if intersectionPoints.GetNumberOfPoints() > 0:
          exteriorPoint = intersectionPoints.GetPoint(intersectionPoints.GetNumberOfPoints()-1)
          projectedPoints.InsertNextPoint(exteriorPoint)
        #if there are no intersections, reverse the normal vector
        else:
          for dim in range(len(rayEndPoint)):
            rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* -rayLength
          obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
          if intersectionPoints.GetNumberOfPoints()>0:
            exteriorPoint = intersectionPoints.GetPoint(0)
            projectedPoints.InsertNextPoint(exteriorPoint)
          #if none in reverse direction, use closest mesh point
          else:
            closestPointId = targetPointLocator.FindClosestPoint(originalPoint)
            rayOrigin = targetPolydata.GetPoint(closestPointId)
            projectedPoints.InsertNextPoint(rayOrigin)
      return projectedPointData

    def relaxGrid(self, gridNode, modelNode, gridResolution, relaxation, iterations):
      gridResolutionU = gridResolution
      gridResolutionV = gridResolution
      gridPointsPolyData = vtk.vtkPolyData()
      gridPoints = vtk.vtkPoints()
      gridPoints.SetNumberOfPoints(gridResolutionU * gridResolutionV)
      for pointIndex in range(gridResolutionV * gridResolutionU):
        gridPoints.SetPoint(pointIndex, gridNode.GetNthControlPointPosition(pointIndex))
      gridPointsPolyData.SetPoints(gridPoints)

      # Create poly data from array for smoothing
      polygons = vtk.vtkCellArray()
      for y in range(gridResolutionV-1):
        for x in range(gridResolutionU-1):
          polygon = vtk.vtkPolygon()
          polygonPointIds = polygon.GetPointIds()
          polygonPointIds.SetNumberOfIds(4)
          polygonPointIds.SetId(0, y * gridResolutionU + x)
          polygonPointIds.SetId(1, y * gridResolutionU + x + 1)
          polygonPointIds.SetId(2, (y + 1) * gridResolutionU + x + 1)
          polygonPointIds.SetId(3, (y + 1) * gridResolutionU + x)
          polygons.InsertNextCell(polygon)
      gridPointsPolyData.SetPolys(polygons)

      # Perform poly data smoothing
      smoothPolyDataFilter = vtk.vtkSmoothPolyDataFilter()
      smoothPolyDataFilter.SetInputDataObject(gridPointsPolyData)
      smoothPolyDataFilter.SetSourceData(modelNode.GetPolyData())
      smoothPolyDataFilter.SetBoundarySmoothing(0)
      smoothPolyDataFilter.SetRelaxationFactor(relaxation)
      smoothPolyDataFilter.SetNumberOfIterations(iterations)
      smoothPolyDataFilter.Update()

      pdNew=smoothPolyDataFilter.GetOutput()
      pdNewPoints = pdNew.GetPoints()
      for i in range(pdNewPoints.GetNumberOfPoints()):
        p = pdNewPoints.GetPoint(i)
        gridNode.SetNthControlPointPosition(i,p)
