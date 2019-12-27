
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
# SemiLandmark
#

class SemiLandmark(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SemiLandmark" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module takes a data set of landmark files and subject meshes and places semi-landmarks.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
      3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

#
# SemiLandmarkWidget
#

class SemiLandmarkWidget(ScriptedLoadableModuleWidget):
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
    logic = SemiLandmarkLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    gridLandmarks = [int(self.landmarkGridPoint1.value), int(self.landmarkGridPoint2.value), int(self.landmarkGridPoint3.value)]
    logic.run(self.meshSelect.currentNode(), self.LMSelect.currentNode(), gridLandmarks, int(self.gridSamplingRate.value)+1)
  
  def onMergeButton(self):
    logic = SemiLandmarkLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    logic.mergeTree(self.fiducialView, self.LMSelect.currentNode(), self.meshSelect.currentNode(),int(self.gridSamplingRate.value))
    
  def updateMergeButton(self):
    nodes=self.fiducialView.selectedIndexes()
    self.mergeButton.enabled = bool (nodes and self.LMSelect.currentNode() and self.meshSelect.currentNode())

      
      

      
  

#
# SemiLandmarkLogic
#

class SemiLandmarkLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def run(self, meshNode, LMNode, gridLandmarks, sampleRate):
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

    #sourcePoints.InsertNextPoint(gridPoints.GetPoint(0))
    #sourcePoints.InsertNextPoint(gridPoints.GetPoint(sampleRate-1))
    #sourcePoints.InsertNextPoint(gridPoints.GetPoint(gridPoints.GetNumberOfPoints()-1))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(0))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(1))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(2))

    point=[0,0,0]
    for gridVertex in gridLandmarks:
      LMNode.GetMarkupPoint(int(gridVertex-1),0,point)
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
    normalArray = surfacePolydata.GetPointData().GetArray("Normals")
    if(not normalArray):
      normalFilter=vtk.vtkPolyDataNormals()
      normalFilter.ComputePointNormalsOn()
      normalFilter.SetInputData(surfacePolydata)
      normalFilter.Update()
      normalArray = normalFilter.GetOutput().GetPointData().GetArray("Normals")
      if(not normalArray):
        print("Error: no normal array")
      
    for gridVertex in gridLandmarks:
      LMNode.GetMarkupPoint(int(gridVertex-1),0,point)
      closestPointId = pointLocator.FindClosestPoint(point)
      tempNormal = normalArray.GetTuple(closestPointId)
      rayDirection[0] += tempNormal[0]
      rayDirection[1] += tempNormal[1]
      rayDirection[2] += tempNormal[2]

    #calculate average
    for dim in range(len(rayDirection)):
      rayDirection[dim]=rayDirection[dim]/4

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
    m3 = model.GetPolyData().GetPoint(1)
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
    projectionTolerance = 2
    boundingBox = vtk.vtkBoundingBox() 
    boundingBox.AddBounds(surfacePolydata.GetBounds())
    diagonalDistance = boundingBox.GetDiagonalLength()
    #rayLength = math.sqrt(diagonalDistance) * projectionTolerance
    rayLength = sampleDistance

    # get normal projection intersections for remaining semi-landmarks
    print("Target number of points: ", resampledPolydata.GetNumberOfPoints())
    for index in range(3,resampledPolydata.GetNumberOfPoints()):
      modelPoint=resampledPolydata.GetPoint(index)
      rayEndPoint=[0,0,0]
      for dim in range(len(rayEndPoint)):
        rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* rayLength
      intersectionIds=vtk.vtkIdList()
      intersectionPoints=vtk.vtkPoints()
      obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
      #if there are intersections, update the point to most external one.
      if intersectionPoints.GetNumberOfPoints()>0:
        exteriorPoint = intersectionPoints.GetPoint(intersectionPoints.GetNumberOfPoints()-1)
        #projectionDistance=math.sqrt(vtk.vtkMath().Distance2BetweenPoints(exteriorPoint, modelPoint))
        semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
      #if there are no intersections, reverse the normal vector
      else: 
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* -rayLength
        obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(0)
          semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
          #projectionDistance=math.sqrt(vtk.vtkMath().Distance2BetweenPoints(exteriorPoint, modelPoint))
          #if projectionDistance < sampleDistance:
          #  semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
          #else:
          #  closestPointId = pointLocator.FindClosestPoint(modelPoint)
          #  rayOrigin = surfacePolydata.GetPoint(closestPointId)
          #  semilandmarkPoints.AddFiducialFromArray(rayOrigin)
  
        #if none in reverse direction, use closest mesh point
        else:
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
    datafile=open(landmarkFilename,'r')
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
    
    # Add semilandmark points on curves betweeen landmark points
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
      landmarkNode.GetMarkupPoint(int(landmarkIndex-1),0, controlPoint)
      tempCurve.AddControlPoint(controlPoint)
      landmarkIndex = int(segment[1])
      landmarkNode.GetMarkupPoint(int(landmarkIndex-1),0, controlPoint)
      tempCurve.AddControlPoint(controlPoint)
      sampleDist = tempCurve.GetCurveLengthWorld() / (rowColNumber - 1);
      tempCurve.ResampleCurveSurface(sampleDist, modelNode, .99)
      tempCurve.GetControlPointPositionsWorld(edgePoints)
      for i in range(1,edgePoints.GetNumberOfPoints()-1):
        mergedNode.AddFiducialFromArray(edgePoints.GetPoint(i)) 
      tempCurve.RemoveAllControlPoints()
    
    # add original landmark points
    for originalLandmarkPoint in pointList_edit:
      landmarkIndex = int(originalLandmarkPoint)
      landmarkNode.GetMarkupPoint(int(landmarkIndex-1),0, controlPoint)
      mergedNode.AddFiducialFromArray(controlPoint)
     
    # update lock status and color of merged node    
    mergedNode.SetLocked(True)
    mergedNode.GetDisplayNode().SetColor(random.random(), random.random(), random.random())
    mergedNode.GetDisplayNode().SetSelectedColor(random.random(), random.random(), random.random())
    mergedNode.GetDisplayNode().PointLabelsVisibilityOff()     

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


class SemiLandmarkTest(ScriptedLoadableModuleTest):
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
    self.test_SemiLandmark1()
  
  def test_SemiLandmark1(self):
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
    logic = SemiLandmarkLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')



