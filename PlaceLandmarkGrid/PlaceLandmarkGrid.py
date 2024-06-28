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
        # set sample rate value
        #
        self.sampleRate = ctk.ctkDoubleSpinBox()
        self.sampleRate.singleStep = 1
        self.sampleRate.minimum = 1
        self.sampleRate.maximum = 100
        self.sampleRate.setDecimals(0)
        self.sampleRate.value = 4
        self.sampleRate.setToolTip("Select grid resolution")
        parametersFormLayout.addRow("Resolution for landmark grid:", self.sampleRate)

        #
        # check box to trigger taking screen shots for later use in tutorials
        #
        self.flipNormalsCheckBox = qt.QCheckBox()
        self.flipNormalsCheckBox.checked = 1
        self.flipNormalsCheckBox.setToolTip("If checked, flip grid surface direction.")
        parametersFormLayout.addRow("Flip grid orientation", self.flipNormalsCheckBox)

        #
        # Outline Button
        #
        self.outlineButton = qt.QPushButton("Place grid outline")
        self.outlineButton.toolTip = "Initiate placement of grid outline"
        self.outlineButton.enabled = False
        parametersFormLayout.addRow(self.outlineButton)
        
        #
        # Grid Button
        #
        self.sampleGridButton = qt.QPushButton("Sample grid")
        self.sampleGridButton.toolTip = "Initiate sampling of grid"
        self.sampleGridButton.enabled = False
        parametersFormLayout.addRow(self.sampleGridButton)
        
        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = PlaceLandmarkGridLogic()

        # Connections
        self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.outlineButton.connect('clicked(bool)', self.onOutlineButton)
        self.sampleGridButton.connect('clicked(bool)', self.onSampleGridButton)

    @vtk.calldata_type(vtk.VTK_INT)

    def onSelect(self):
        self.outlineButton.enabled = bool(self.modelSelector.currentNode())

    def onOutlineButton(self):
        modelNode = self.modelSelector.currentNode()
        self.outlineCurve = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsClosedCurveNode", "gridOutline")
        self.outlineCurve.AddNControlPoints(4, "outline", (0,0,0) )
        self.outlineCurve.UnsetAllControlPoints()
        self.outlineCurve.SetFixedNumberOfControlPoints(True)
        self.outlineCurve.SetCurveTypeToLinear()
        self.outlineCurve.SetAndObserveSurfaceConstraintNode(modelNode)
        self.outlineCurve.SetSurfaceConstraintMaximumSearchRadiusTolerance(.75)
        self.outlineCurve.GetDisplayNode().SetSelectedColor(0,1,0)
        self.outlineCurve.GetDisplayNode().SetGlyphScale(3.2)
        slicer.modules.markups.toolBar().onPlacePointShortcut()
        self.sampleGridButton.enabled  = True

    def onSampleGridButton(self):
      if self.outlineCurve.GetNumberOfControlPoints() != 4:
        print("Please finish placing grid outline with 4 points")
        return
      gridResolution = int(self.sampleRate.value)
      self.modelNode = self.modelSelector.currentNode()
      flipNormalsFlag = self.flipNormalsCheckBox.checked
      # set up grid
      self.gridNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsGridSurfaceNode","grid")
      self.gridNode.SetGridResolution(gridResolution,gridResolution)
      self.gridModel=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode","gridModel")
      self.logic.placeGrid(gridResolution, self.outlineCurve, self.gridNode)
      self.gridNode.SetOutputSurfaceModelNodeID(self.gridModel.GetID())
      # flip model normals
      if flipNormalsFlag:
        self.logic.flipSurfacePatchOrientation(self.gridModel)
      else:
        print("no flip")
      self.logic.projectPatch(self.modelNode, self.gridNode, self.gridModel)
      self.logic.relaxGrid(self.gridNode, self.modelNode, gridResolution)

      # update view
      self.gridModel.SetDisplayVisibility(False)
      self.gridNode.GetDisplayNode().SetGlyphSize(2.8)
      self.gridNode.LockedOn()

      # curve event handling
      observerTag = self.outlineCurve.AddObserver(slicer.vtkMRMLMarkupsClosedCurveNode.PointEndInteractionEvent, self.refreshGrid)

    def refreshGrid(self, caller, eventId):
      self.gridNode.LockedOff()
      gridResolution = int(self.sampleRate.value)
      self.gridNode.RemoveAllControlPoints()
      self.gridNode.SetGridResolution(gridResolution,gridResolution)
      self.gridModel = self.gridNode.GetOutputSurfaceModelNode()
      self.logic.placeGrid(gridResolution, self.outlineCurve, self.gridNode)
      self.gridNode.SetOutputSurfaceModelNodeID(self.gridModel.GetID())
      self.logic.projectPatch(self.modelNode, self.gridNode, self.gridModel)
      self.logic.relaxGrid(self.gridNode, self.modelNode, gridResolution)
      self.gridNode.LockedOn()
      
# PlaceLandmarkGridLogic
#

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
    def placeGrid(self, gridResolution, curveNode, gridNode):
        error = 0.00003
        gridPointNumber = gridResolution*gridResolution

        # set up transform between base lms and current lms
        sourcePoints = vtk.vtkPoints()
        targetPoints = vtk.vtkPoints()

        for i in range(3):
          point = curveNode.GetNthControlPointPosition(i)
          sourcePoints.InsertNextPoint(point)
          gridNode.AddControlPoint(point)

        #get source points from grid corners
        gridCorners = [gridNode.GetNthControlPointPosition(0), gridNode.GetNthControlPointPosition(gridResolution-1), gridNode.GetNthControlPointPosition(gridPointNumber-gridResolution), gridNode.GetNthControlPointPosition(gridPointNumber-1)]
        curveCorners=[]
        #get target points from placed curve
        for i in range(4):
          point = curveNode.GetNthControlPointPosition(i)
          targetPoints.InsertNextPoint(point)
          curveCorners.append(point)

        for corner in gridCorners:
          if not np.isclose(curveCorners, corner, error).any():
            sourcePoints.InsertNextPoint(corner)

        if sourcePoints.GetNumberOfPoints() != targetPoints.GetNumberOfPoints():
          print("Grid corners already at curve corners")
          return 

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
      print("flipping patch...")
      reverse = vtk.vtkReverseSense()
      reverse.SetInputData(gridModelNode.GetPolyData())
      reverse.Update()
      gridModelNode.SetAndObservePolyData(reverse.GetOutput())
      normals = vtk.vtkPolyDataNormals()
      normals.SetInputData(gridModelNode.GetPolyData())
      normals.Update()
      gridModelNode.SetAndObservePolyData(normals.GetOutput())

    def projectPatch(self, model, markupNode, markupModel):
      points = self.markup2VtkPoints(markupNode)
      maxProjection = (model.GetPolyData().GetLength()) * 0.3
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
      print('Original points:', originalPoints.GetNumberOfPoints() )
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
      print('Projected points:', originalPoints.GetNumberOfPoints() )
      return projectedPointData

    def relaxGrid(self, gridNode, modelNode, gridResolution):  
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
      smoothPolyDataFilter.SetBoundarySmoothing(1)
      smoothPolyDataFilter.SetRelaxationFactor(.8)
      smoothPolyDataFilter.SetNumberOfIterations(300)
      smoothPolyDataFilter.Update()

      pdNew=smoothPolyDataFilter.GetOutput()
      pdNewPoints = pdNew.GetPoints()
      for i in range(pdNewPoints.GetNumberOfPoints()):
        p = pdNewPoints.GetPoint(i)
        gridNode.SetNthControlPointPosition(i,p)
