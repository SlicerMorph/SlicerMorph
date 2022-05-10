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
# CreateSemiLMPatches
#

class CreateSemiLMPatches(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "CreateSemiLMPatches" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Geometric Morphometrics"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module interactively places patches of semi-landmarks between user-specified anatomical landmarks.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/CreateSemiLMPatches">online documentation.</a>.</p>
      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe, and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  # It is always recommended to provide sample data for users to make it easy to try the module,
  # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  # To ensure that the source code repository remains small (can be downloaded and installed quickly)
  # it is recommended to store data sets that are larger than a few MB in a Github release.

  # TemplateKey1
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey1',
    # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
    # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey1.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
    fileNames='TemplateKey1.nrrd',
    # Checksum to ensure file integrity. Can be computed by this command:
    #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
    checksums = 'SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey1'
  )

  # TemplateKey2
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey2',
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey2.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
    fileNames='TemplateKey2.nrrd',
    checksums = 'SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey2'
  )


#
# CreateSemiLMPatchesWidget
#

class CreateSemiLMPatchesWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onMeshSelect(self):
    self.applyButton.enabled = bool (self.meshSelect.currentNode() and self.LMSelect.currentNode())
    nodes=self.fiducialView.selectedIndexes()
    self.mergeButton.enabled = bool (nodes and self.LMSelect.currentNode() and self.meshSelect.currentNode())

  def onLMSelect(self):
    self.applyButton.enabled = bool (self.meshSelect.currentNode() and self.LMSelect.currentNode())
    nodes=self.fiducialView.selectedIndexes()
    self.mergeButton.enabled = bool (nodes and self.LMSelect.currentNode() and self.meshSelect.currentNode())

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

    # 3D view set up tab
    self.meshSelect = slicer.qMRMLNodeComboBox()
    self.meshSelect.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.meshSelect.selectNodeUponCreation = False
    self.meshSelect.addEnabled = False
    self.meshSelect.removeEnabled = False
    self.meshSelect.noneEnabled = True
    self.meshSelect.showHidden = False
    self.meshSelect.setMRMLScene( slicer.mrmlScene )
    self.meshSelect.connect("currentNodeChanged(vtkMRMLNode*)", self.onMeshSelect)
    parametersFormLayout.addRow("Model: ", self.meshSelect)
    self.meshSelect.setToolTip( "Select model node for semilandmarking" )

    self.LMSelect = slicer.qMRMLNodeComboBox()
    self.LMSelect.nodeTypes = ( ('vtkMRMLMarkupsFiducialNode'), "" )
    self.LMSelect.selectNodeUponCreation = False
    self.LMSelect.addEnabled = False
    self.LMSelect.removeEnabled = False
    self.LMSelect.noneEnabled = True
    self.LMSelect.showHidden = False
    self.LMSelect.showChildNodeTypes = False
    self.LMSelect.setMRMLScene( slicer.mrmlScene )
    self.LMSelect.connect("currentNodeChanged(vtkMRMLNode*)", self.onLMSelect)
    parametersFormLayout.addRow("Landmark set: ", self.LMSelect)
    self.LMSelect.setToolTip( "Select the landmark set that corresponds to the model" )

    #
    # input landmark numbers for grid
    #
    gridPointsLayout= qt.QGridLayout()
    self.landmarkGridPoint1 = ctk.ctkDoubleSpinBox()
    self.landmarkGridPoint1.minimum = 0
    self.landmarkGridPoint1.singleStep = 1
    self.landmarkGridPoint1.setDecimals(0)
    self.landmarkGridPoint1.setToolTip("Input the landmark numbers to create grid")

    self.landmarkGridPoint2 = ctk.ctkDoubleSpinBox()
    self.landmarkGridPoint2.minimum = 0
    self.landmarkGridPoint2.singleStep = 1
    self.landmarkGridPoint2.setDecimals(0)
    self.landmarkGridPoint2.setToolTip("Input the landmark numbers to create grid")

    self.landmarkGridPoint3 = ctk.ctkDoubleSpinBox()
    self.landmarkGridPoint3.minimum = 0
    self.landmarkGridPoint3.singleStep = 1
    self.landmarkGridPoint3.setDecimals(0)
    self.landmarkGridPoint3.setToolTip("Input the landmark numbers to create grid")

    gridPointsLayout.addWidget(self.landmarkGridPoint1,1,2)
    gridPointsLayout.addWidget(self.landmarkGridPoint2,1,3)
    gridPointsLayout.addWidget(self.landmarkGridPoint3,1,4)

    parametersFormLayout.addRow("Semi-landmark grid points:", gridPointsLayout)

    #
    # set number of sample points in each triangle
    #
    self.gridSamplingRate = ctk.ctkDoubleSpinBox()
    self.gridSamplingRate.minimum = 3
    self.gridSamplingRate.maximum = 50
    self.gridSamplingRate.singleStep = 1
    self.gridSamplingRate.setDecimals(0)
    self.gridSamplingRate.value = 10
    self.gridSamplingRate.setToolTip("Input the landmark numbers to create grid")
    parametersFormLayout.addRow("Select number of rows/columns in resampled grid:", self.gridSamplingRate)

    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)

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
    # Maximum projection slider
    #
    self.projectionDistanceSlider = ctk.ctkSliderWidget()
    self.projectionDistanceSlider.singleStep = 1
    self.projectionDistanceSlider.minimum = 0
    self.projectionDistanceSlider.maximum = 100
    self.projectionDistanceSlider.value = 25
    self.projectionDistanceSlider.setToolTip("Set maximum projection distance as a percentage of image size")
    advancedFormLayout.addRow("Set maximum projection distance: ", self.projectionDistanceSlider)

    #
    # Normal smoothing slider
    #
    self.smoothingSlider = ctk.ctkSliderWidget()
    self.smoothingSlider.singleStep = 1
    self.smoothingSlider.minimum = 0
    self.smoothingSlider.maximum = 100
    self.smoothingSlider.value = 0
    self.smoothingSlider.setToolTip("Set smothing of normal vectors for projection")
    advancedFormLayout.addRow("Set smoothing of projection vectors: ", self.smoothingSlider)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Generate semilandmarks."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    #
    # Fiducials view
    #
    self.fiducialView = slicer.qMRMLSubjectHierarchyTreeView()
    self.fiducialView.setMRMLScene(slicer.mrmlScene)
    self.fiducialView.setMultiSelection(True)
    self.fiducialView.setAlternatingRowColors(True)
    self.fiducialView.setDragDropMode(True)
    self.fiducialView.setColumnHidden(self.fiducialView.model().transformColumn, True);
    self.fiducialView.sortFilterProxyModel().setNodeTypes(["vtkMRMLMarkupsFiducialNode"])
    parametersFormLayout.addRow(self.fiducialView)

    #
    # Apply Button
    #
    self.mergeButton = qt.QPushButton("Merge highlighted nodes")
    self.mergeButton.toolTip = "Generate a single merged landmark file from the selected nodes"
    self.mergeButton.enabled = False
    parametersFormLayout.addRow(self.mergeButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.mergeButton.connect('clicked(bool)', self.onMergeButton)
    self.fiducialView.connect('currentItemChanged(vtkIdType)', self.updateMergeButton)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def onApplyButton(self):
    logic = CreateSemiLMPatchesLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    gridLandmarks = [int(self.landmarkGridPoint1.value), int(self.landmarkGridPoint2.value), int(self.landmarkGridPoint3.value)]
    smoothingIterations =  int(self.smoothingSlider.value)
    projectionRayTolerance = self.projectionDistanceSlider.value/100
    logic.run(self.meshSelect.currentNode(), self.LMSelect.currentNode(), gridLandmarks, int(self.gridSamplingRate.value)+1, smoothingIterations, projectionRayTolerance)

  def onMergeButton(self):
    logic = CreateSemiLMPatchesLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    logic.mergeTree(self.fiducialView, self.LMSelect.currentNode(), self.meshSelect.currentNode(),int(self.gridSamplingRate.value))

  def updateMergeButton(self):
    nodes=self.fiducialView.selectedIndexes()
    self.mergeButton.enabled = bool (nodes and self.LMSelect.currentNode() and self.meshSelect.currentNode())

#
# CreateSemiLMPatchesLogic
#

class CreateSemiLMPatchesLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, meshNode, LMNode, gridLandmarks, sampleRate, smoothingIterations, maximumProjectionDistance=.25):
    if(smoothingIterations == 0):
      surfacePolydata = meshNode.GetPolyData()
      normalArray = surfacePolydata.GetPointData().GetArray("Normals")
      if(not normalArray):
        normalFilter=vtk.vtkPolyDataNormals()
        normalFilter.ComputePointNormalsOn()
        normalFilter.SetInputData(surfacePolydata)
        normalFilter.Update()
        normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
        if(not normalArray):
          print("Error: no normal array")
    else:
      print('smoothing normals')
      normalArray = self.getSmoothNormals(meshNode,smoothingIterations)
    semiLandmarks = self.applyPatch(meshNode, LMNode, gridLandmarks, sampleRate, normalArray, maximumProjectionDistance)


    return True

  def applyPatch(self, meshNode, LMNode, gridLandmarks, sampleRate, polydataNormalArray, maximumProjectionDistance=.25):
    surfacePolydata = meshNode.GetPolyData()

    gridPoints = vtk.vtkPoints()

    gridPoints.InsertNextPoint(0,0,0)
    gridPoints.InsertNextPoint(0,sampleRate-1,0)
    gridPoints.InsertNextPoint(sampleRate-1,0,0)
    for row in range(1,sampleRate-1):
      for col in range(1,sampleRate-1):
        if (row+col)<(sampleRate-1):
          gridPoints.InsertNextPoint(row,col,0)

    gridPolydata=vtk.vtkPolyData()
    gridPolydata.SetPoints(gridPoints)

    sourcePoints = vtk.vtkPoints()
    targetPoints = vtk.vtkPoints()

    sourcePoints.InsertNextPoint(gridPoints.GetPoint(0))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(1))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(2))

    point=[0,0,0]
    for gridVertex in gridLandmarks:
      LMNode.GetMarkupPoint(0,int(gridVertex-1),point)
      targetPoints.InsertNextPoint(point)

    #transform grid to triangle
    transform = vtk.vtkThinPlateSplineTransform()
    transform.SetSourceLandmarks( sourcePoints )
    transform.SetTargetLandmarks( targetPoints )
    transform.SetBasisToR()

    transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
    transformNode.SetAndObserveTransformToParent(transform)

    model=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "mesh_resampled")
    model.SetAndObservePolyData(gridPolydata)
    model.SetAndObserveTransformNodeID(transformNode.GetID())
    slicer.vtkSlicerTransformLogic().hardenTransform(model)

    resampledPolydata = model.GetPolyData()

    pointLocator = vtk.vtkPointLocator()
    pointLocator.SetDataSet(surfacePolydata)
    pointLocator.BuildLocator()

    #get surface normal from each landmark point
    rayDirection=[0,0,0]

    for gridVertex in gridLandmarks:
      LMNode.GetMarkupPoint(0,int(gridVertex-1),point)
      closestPointId = pointLocator.FindClosestPoint(point)
      tempNormal = polydataNormalArray.GetTuple(closestPointId)
      rayDirection[0] += tempNormal[0]
      rayDirection[1] += tempNormal[1]
      rayDirection[2] += tempNormal[2]

    #normalize
    vtk.vtkMath().Normalize(rayDirection)

    # # get normal at each grid point
    # gridNormals = np.zeros((3,3))
    # gridIndex=0
    # for gridVertex in gridLandmarks:
      # print(gridVertex)
      # LMNode.GetMarkupPoint(0,int(gridVertex-1),point)
      # closestPointId = pointLocator.FindClosestPoint(point)
      # tempNormal = polydataNormalArray.GetTuple(closestPointId)
      # print(tempNormal)
      # gridNormals[gridIndex] = tempNormal
      # gridIndex+=1
    # print(gridNormals)

    #set up locater for intersection with normal vector rays
    obbTree = vtk.vtkOBBTree()
    obbTree.SetDataSet(surfacePolydata)
    obbTree.BuildLocator()

    #define new landmark sets
    semilandmarkNodeName = "semiLM_" + str(gridLandmarks[0]) + "_" + str(gridLandmarks[1]) + "_" + str(gridLandmarks[2])
    semilandmarkPoints=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", semilandmarkNodeName)

    #get a sample distance for quality control
    m1 = model.GetPolyData().GetPoint(0)
    m2 = model.GetPolyData().GetPoint(1)
    m3 = model.GetPolyData().GetPoint(2)
    d1 = math.sqrt(vtk.vtkMath().Distance2BetweenPoints(m1, m2))
    d2 = math.sqrt(vtk.vtkMath().Distance2BetweenPoints(m2, m3))
    d3 = math.sqrt(vtk.vtkMath().Distance2BetweenPoints(m1, m3))
    sampleDistance = (d1 + d2 + d3)

    # set initial three grid points
    for index in range(0,3):
      origLMPoint=resampledPolydata.GetPoint(index)
      #landmarkLabel = LMNode.GetNthFiducialLabel(gridLandmarks[index]-1)
      landmarkLabel = str(gridLandmarks[index])
      semilandmarkPoints.AddFiducialFromArray(origLMPoint, landmarkLabel)

    # calculate maximum projection distance
    projectionTolerance = maximumProjectionDistance/.25
    #boundingBox = vtk.vtkBoundingBox()
    #boundingBox.AddBounds(surfacePolydata.GetBounds())
    #diagonalDistance = boundingBox.GetDiagonalLength()
    #rayLength = math.sqrt(diagonalDistance) * projectionTolerance
    rayLength = sampleDistance * projectionTolerance

    # get normal projection intersections for remaining semi-landmarks
    for index in range(3,resampledPolydata.GetNumberOfPoints()):
      modelPoint=resampledPolydata.GetPoint(index)

      # ## get estimated normal vector
      # rayDirection = [0,0,0]
      # distance1=math.sqrt(vtk.vtkMath().Distance2BetweenPoints(modelPoint,resampledPolydata.GetPoint(0)))
      # distance2=math.sqrt(vtk.vtkMath().Distance2BetweenPoints(modelPoint,resampledPolydata.GetPoint(1)))
      # distance3=math.sqrt(vtk.vtkMath().Distance2BetweenPoints(modelPoint,resampledPolydata.GetPoint(2)))
      # distanceTotal = distance1 + distance2 + distance3
      # weights=[(distance3+distance2)/distanceTotal, (distance1+distance3)/distanceTotal,(distance1+distance2)/distanceTotal]

      # for gridIndex in range(0,3):
        # rayDirection+=(weights[gridIndex]*gridNormals[gridIndex])
      # vtk.vtkMath().Normalize(rayDirection)
      # ##

      rayEndPoint=[0,0,0]
      for dim in range(len(rayEndPoint)):
        rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* rayLength
      intersectionIds=vtk.vtkIdList()
      intersectionPoints=vtk.vtkPoints()
      obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
      #if there are intersections, update the point to most external one.
      if intersectionPoints.GetNumberOfPoints()>0:
        exteriorPoint = intersectionPoints.GetPoint(intersectionPoints.GetNumberOfPoints()-1)
        semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
      #if there are no intersections, reverse the normal vector
      else:
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* -rayLength
        obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(0)
          semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
        else:
          print("No intersection, using closest point")
          closestPointId = pointLocator.FindClosestPoint(modelPoint)
          rayOrigin = surfacePolydata.GetPoint(closestPointId)
          semilandmarkPoints.AddFiducialFromArray(rayOrigin)

    # update lock status and color
    semilandmarkPoints.SetLocked(True)
    semilandmarkPoints.GetDisplayNode().SetColor(random.random(), random.random(), random.random())
    semilandmarkPoints.GetDisplayNode().SetSelectedColor(random.random(), random.random(), random.random())
    semilandmarkPoints.GetDisplayNode().PointLabelsVisibilityOff()
    #clean up
    slicer.mrmlScene.RemoveNode(transformNode)
    slicer.mrmlScene.RemoveNode(model)
    print("Total points:", semilandmarkPoints.GetNumberOfFiducials() )
    return semilandmarkPoints

  def getSmoothNormals(self, surfaceNode,iterations):
    smoothFilter = vtk.vtkSmoothPolyDataFilter()
    smoothFilter.SetInputData(surfaceNode.GetPolyData())
    smoothFilter.FeatureEdgeSmoothingOff()
    smoothFilter.BoundarySmoothingOn()
    smoothFilter.SetNumberOfIterations(iterations)
    smoothFilter.SetRelaxationFactor(1)
    smoothFilter.Update()
    normalGenerator = vtk.vtkPolyDataNormals()
    normalGenerator.ComputePointNormalsOn()
    normalGenerator.SetInputData(smoothFilter.GetOutput())
    normalGenerator.Update()
    normalArray = normalGenerator.GetOutput().GetPointData().GetArray("Normals")
    return normalArray

  def getLandmarks(self, landmarkDirectory):
    files_to_open=[]
    for path, dir, files in os.walk(landmarkDirectory):
      for filename in files:
        if fnmatch.fnmatch(filename,"*.fcsv"):
          files_to_open.append(filename)

    tmp = self.readLandmarkFile(os.path.join(landmarkDirectory, files_to_open[0]))    #check size of landmark data array

    [i,j]=tmp.shape
    landmarkArray=np.zeros(shape=(i,j,len(files_to_open)))  # initialize landmark array

    for i in range(len(files_to_open)):
      tmp = self.readLandmarkFile(os.path.join(landmarkDirectory, files_to_open[i]))
      landmarkArray[:,:,i]=tmp
    return landmarkArray

  def readLandmarkFile(self, landmarkFilename):
    datafile=open(landmarkFilename)
    data=[]
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):  #if not a commented line
        data.append(row.strip().split(','))
    dataArray=np.zeros(shape=(len(data),3))
    j=0
    sorter=[]
    for i in data:
      tmp=np.array(i)[1:4]
      dataArray[j,0:3]=tmp
      x=np.array(i).shape
      j=j+1
    slicer.app.processEvents()
    return dataArray

  def getGridPoints(self, landmarkArray, gridLandmarkNumbers):
    gridArray=[]
    return gridArray

  def setAllLandmarksType(self,landmarkNode, setToSemiType):
    landmarkDescription = "Semi"
    if setToSemiType is False:
      landmarkDescription = "Fixed"
    for controlPointIndex in range(landmarkNode.GetNumberOfControlPoints()):
      landmarkNode.SetNthControlPointDescription(controlPointIndex, landmarkDescription)

  def mergeTree(self, treeWidget, landmarkNode, modelNode,rowColNumber):
    nodeIDs=treeWidget.selectedIndexes()
    nodeList = vtk.vtkCollection()
    for id in nodeIDs:
      if id.column() == 0:
        currentNode = slicer.util.getNode(id.data())
        nodeList.AddItem(currentNode)
    mergedNodeName = landmarkNode.GetName() + "_mergedNode"
    mergedNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', mergedNodeName)
    self.mergeList(nodeList, landmarkNode, modelNode,rowColNumber,mergedNode)
    return True

  def mergeList(self, nodeList, landmarkNode, modelNode,rowColNumber,mergedNode):
    pt=[0,0,0]
    triangleList=[]
    lineSegmentList=[]
    pointList=[]

    # Add semi-landmark points within triangle patches
    for currentNode in nodeList:
      if currentNode != landmarkNode:
        for index in range(3,currentNode.GetNumberOfFiducials()):
          currentNode.GetNthFiducialPosition(index,pt)
          fiducialLabel = currentNode.GetNthFiducialLabel(index)
          mergedNode.AddFiducialFromArray(pt,fiducialLabel)
        p1=currentNode.GetNthFiducialLabel(0)
        p2=currentNode.GetNthFiducialLabel(1)
        p3=currentNode.GetNthFiducialLabel(2)
        landmarkVector = [p1,p2,p3]
        triangleList.append(landmarkVector)
        lineSegmentList.append(sorted([p1,p2]))
        lineSegmentList.append(sorted([p2,p3]))
        lineSegmentList.append(sorted([p3,p1]))
        pointList.append(p1)
        pointList.append(p2)
        pointList.append(p3)

    # Add semilandmark points on curves between landmark points
    seenVertices=set()
    lineSegmentList_edit=[]
    # Remove duplicate line segments
    for segment in lineSegmentList:
      segmentTuple = tuple(segment)
      if segmentTuple not in seenVertices:
        lineSegmentList_edit.append(segment)
        seenVertices.add(segmentTuple)

    seenPoints=set()
    pointList_edit=[]
    # Remove duplicate points
    for originalLandmarkPoint in pointList:
      lmTuple = tuple(originalLandmarkPoint)
      if lmTuple not in seenPoints:
        pointList_edit.append(originalLandmarkPoint)
        seenPoints.add(lmTuple)

    # add line segments between triangles
    controlPoint=vtk.vtkVector3d()
    edgePoints=vtk.vtkPoints()
    tempCurve = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsCurveNode', 'temporaryCurve')
    for segment in lineSegmentList_edit:
      landmarkIndex = int(segment[0])
      landmarkNode.GetMarkupPoint(0,int(landmarkIndex-1),controlPoint)
      tempCurve.AddControlPoint(controlPoint)
      landmarkIndex = int(segment[1])
      landmarkNode.GetMarkupPoint(0,int(landmarkIndex-1),controlPoint)
      tempCurve.AddControlPoint(controlPoint)
      sampleDist = tempCurve.GetCurveLengthWorld() / (rowColNumber - 1);
      tempCurve.ResampleCurveSurface(sampleDist, modelNode, .99)
      tempCurve.GetControlPointPositionsWorld(edgePoints)
      for i in range(1,edgePoints.GetNumberOfPoints()-1):
        mergedNode.AddFiducialFromArray(edgePoints.GetPoint(i))
      tempCurve.RemoveAllControlPoints()

    # ------ removing manual points from SL set, leaving this as a placeholder while testing
    # add original landmark points
    #for originalLandmarkPoint in pointList_edit:
    #  landmarkIndex = int(originalLandmarkPoint)
    #  landmarkNode.GetMarkupPoint(0,int(landmarkIndex-1),controlPoint)
    #  mergedNode.AddFiducialFromArray(controlPoint)

    # update lock status and color of merged node
    mergedNode.SetLocked(True)
    mergedNode.GetDisplayNode().SetColor(random.random(), random.random(), random.random())
    mergedNode.GetDisplayNode().SetSelectedColor(random.random(), random.random(), random.random())
    mergedNode.GetDisplayNode().PointLabelsVisibilityOff()
    landmarkTypeSemi=True
    self.setAllLandmarksType(mergedNode, landmarkTypeSemi)

    # clean up
    slicer.mrmlScene.RemoveNode(tempCurve)

    # write selected triangles to table
    tableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Semi-landmark Grid')
    col1=tableNode.AddColumn()
    col1.SetName('Vertice 1')
    col2=tableNode.AddColumn()
    col2.SetName('Vertice 2')
    col3=tableNode.AddColumn()
    col3.SetName('Vertice 3')
    tableNode.SetColumnType('Vertice 1',vtk.VTK_STRING)
    tableNode.SetColumnType('Vertice 2',vtk.VTK_STRING)
    tableNode.SetColumnType('Vertice 3',vtk.VTK_STRING)

    for i in range(len(triangleList)):
      tableNode.AddEmptyRow()
      triangle=triangleList[i]
      tableNode.SetCellText(i,0,str(triangle[0]))
      tableNode.SetCellText(i,1,str(triangle[1]))
      tableNode.SetCellText(i,2,str(triangle[2]))

    return True

  def projectPoints(self, sourceMesh, targetMesh, originalPoints, projectedPoints, rayLength):
    sourcePolydata = sourceMesh.GetPolyData()
    targetPolydata = targetMesh.GetPolyData()

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
      normalFilter=vtk.vtkPolyDataNormals()
      normalFilter.ComputePointNormalsOn()
      normalFilter.SetInputData(sourcePolydata)
      normalFilter.Update()
      normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
      if(not normalArray):
        print("Error: no normal array")

    for index in range(originalPoints.GetNumberOfMarkups()):
      originalPoint=[0,0,0]
      originalPoints.GetMarkupPoint(0,index,originalPoint)
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
        projectedPoints.AddFiducialFromArray(exteriorPoint)
      #if there are no intersections, reverse the normal vector
      else:
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* -rayLength
        obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(0)
          projectedPoints.AddFiducialFromArray(exteriorPoint)
        #if none in reverse direction, use closest mesh point
        else:
          closestPointId = targetPointLocator.FindClosestPoint(originalPoint)
          rayOrigin = targetPolydata.GetPoint(closestPointId)
          projectedPoints.AddFiducialFromArray(rayOrigin)
    return True

  def projectPointsOut(self, sourcePolydata, targetPolydata, originalPoints, projectedPoints, rayLength):
    #sourcePolydata = sourceMesh.GetPolyData()
    #targetPolydata = targetMesh.GetPolyData()

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
      normalFilter=vtk.vtkPolyDataNormals()
      normalFilter.ComputePointNormalsOn()
      normalFilter.SetInputData(sourcePolydata)
      normalFilter.Update()
      normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
      if(not normalArray):
        print("Error: no normal array")

    for index in range(originalPoints.GetNumberOfMarkups()):
      originalPoint=[0,0,0]
      originalPoints.GetMarkupPoint(0,index,originalPoint)
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
        projectedPoints.AddFiducialFromArray(exteriorPoint)
    return True

  def projectPointsOutIn(self, sourcePolydata, targetPolydata, originalPoints, projectedPoints, rayLength):
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
      normalFilter=vtk.vtkPolyDataNormals()
      normalFilter.ComputePointNormalsOn()
      normalFilter.SetInputData(sourcePolydata)
      normalFilter.Update()
      normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
      if(not normalArray):
        print("Error: no normal array")

    for index in range(originalPoints.GetNumberOfMarkups()):
      originalPoint=[0,0,0]
      originalPoints.GetMarkupPoint(0,index,originalPoint)
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
        projectedPoints.AddFiducialFromArray(exteriorPoint)
      #if there are no intersections, reverse the normal vector
      else:
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = originalPoint[dim] + rayDirection[dim]* -rayLength
        obbTree.IntersectWithLine(originalPoint,rayEndPoint,intersectionPoints,intersectionIds)
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(0)
          projectedPoints.AddFiducialFromArray(exteriorPoint)
    return True

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def process(self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """

    if not inputVolume or not outputVolume:
      raise ValueError("Input or output volume is invalid")

    import time
    startTime = time.time()
    logging.info('Processing started')

    # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
    cliParams = {
      'InputVolume': inputVolume.GetID(),
      'OutputVolume': outputVolume.GetID(),
      'ThresholdValue' : imageThreshold,
      'ThresholdType' : 'Above' if invert else 'Below'
      }
    cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
    # We don't need the CLI module node anymore, remove it to not clutter the scene with it
    slicer.mrmlScene.RemoveNode(cliNode)

    stopTime = time.time()
    logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')


class CreateSemiLMPatchesTest(ScriptedLoadableModuleTest):
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
    self.test_CreateSemiLMPatches1()

  def test_CreateSemiLMPatches1(self):
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
    registerSampleData()
    inputVolume = SampleData.downloadSample('TemplateKey1')
    self.delayDisplay('Loaded test data set')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 695)

    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    threshold = 100

    # Test the module logic

    logic = CreateSemiLMPatchesLogic()

    # Test algorithm with non-inverted threshold
    logic.process(inputVolume, outputVolume, threshold, True)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], threshold)

    # Test algorithm with inverted threshold
    logic.process(inputVolume, outputVolume, threshold, False)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')
