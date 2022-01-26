import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np

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
    self.parent.categories = ["SlicerMorph"]
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
    # input landmark directory selector
    #
    self.inputLandmarkDirectory = ctk.ctkDirectoryButton()
    self.inputLandmarkDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Landmark Directory:", self.inputLandmarkDirectory)
    self.inputLandmarkDirectory.setToolTip( "Select directory containing landmark files" )

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

    self.landmarkGridPoint4 = ctk.ctkDoubleSpinBox()
    self.landmarkGridPoint4.minimum = 0
    self.landmarkGridPoint4.singleStep = 1
    self.landmarkGridPoint4.setDecimals(0)
    self.landmarkGridPoint4.setToolTip("Input the landmark numbers to create grid")

    gridPointsLayout.addWidget(self.landmarkGridPoint1,1,2)
    gridPointsLayout.addWidget(self.landmarkGridPoint2,1,3)
    gridPointsLayout.addWidget(self.landmarkGridPoint3,1,4)
    gridPointsLayout.addWidget(self.landmarkGridPoint4,1,5)

    parametersFormLayout.addRow("Semi-landmark grid points:", gridPointsLayout)

    #
    # input mesh directory selector
    #
    self.inputMeshDirectory = ctk.ctkDirectoryButton()
    self.inputMeshDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Mesh Directory:", self.inputMeshDirectory)
    self.inputMeshDirectory.setToolTip( "Select directory containing mesh files" )

    #
    # output directory selector
    #
    self.outputDirectory = ctk.ctkDirectoryButton()
    self.outputDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Output Directory:", self.outputDirectory)
    self.inputMeshDirectory.setToolTip( "Select directory for output semi-landmark files" )

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
    self.applyButton.toolTip = "Run the conversion."
    self.applyButton.enabled = True
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass


  def onApplyButton(self):
    logic = SemiLandmarkLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    gridLandmarks = [self.landmarkGridPoint1.value, self.landmarkGridPoint2.value, self.landmarkGridPoint3.value, self.landmarkGridPoint4.value]
    logic.run(self.inputLandmarkDirectory.directory, self.inputMeshDirectory.directory, gridLandmarks, self.outputDirectory.directory)

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
  def run(self, landmarkDirectory, meshDirectory, gridLandmarks, outputDirectory):
    #read all landmarks
    #landmarks = self.getLandmarks(landmarkDirectory)
    #print("landmark file shape: ", landmarks.shape)
    #[landmarkNumber,dim,subjectNumber] = landmarks.shape
    #get grid points
    #newGridPoints = self.getGridPoints(landmarks, gridLandmarks)
    #reflect gridPoints onto each surface
    #meshList = self.getAllSubjectMeshes(meshDirectory)
    #for i in range(subjectNumber):
      #mesh = self.readMesh(meshList(i))
      #stickToSurface(newGridPoints(:,:,i), mesh)
    # save semi-landmarks
    #self.saveSemiLandmarks(newGridPoints, outputDirectory)

    #Read data
    S=slicer.util.getNode("gor_skull")
    L=slicer.util.getNode("Gorilla_template_LM1")
    surfacePolydata = S.GetPolyData()

    # Set up point locator for later
    pointLocator = vtk.vtkPointLocator()
    pointLocator.SetDataSet(surfacePolydata)
    pointLocator.BuildLocator()
    #set up locater for intersection with normal vector rays
    obbTree = vtk.vtkOBBTree()
    obbTree.SetDataSet(surfacePolydata)
    obbTree.BuildLocator()

    #Set up fiducial grid
    print("Set up grid")
    fiducialPoints=vtk.vtkPoints()
    point=[0,0,0]
    for pt in range(L.GetNumberOfControlPoints()):
      L.GetMarkupPoint(pt,0,point)
      fiducialPoints.InsertNextPoint(point)

    fiducialPolydata = vtk.vtkPolyData()
    fiducialPolydata.SetPoints(fiducialPoints)
    delaunayFilter = vtk.vtkDelaunay2D()
    delaunayFilter.SetInputData(fiducialPolydata)
    delaunayFilter.Update()
    fiducialMesh=delaunayFilter.GetOutput()
    fiducialMeshModel=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode","fiducialMesh")
    fiducialMeshModel.SetAndObservePolyData(fiducialMesh)

    #Set up triangle grid for projection
    gridPoints = vtk.vtkPoints()
    sampleRate=3

    for row in range(sampleRate):
      for col in range(sampleRate):
        if (row+col)<sampleRate:
          gridPoints.InsertNextPoint(row,col,0)

    gridPolydata=vtk.vtkPolyData()
    gridPolydata.SetPoints(gridPoints)

    #Set up source and target for triangle transform
    sourcePoints = vtk.vtkPoints()
    targetPoints = vtk.vtkPoints()

    sourcePoints.InsertNextPoint(gridPoints.GetPoint(0))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(sampleRate-1))
    sourcePoints.InsertNextPoint(gridPoints.GetPoint(gridPoints.GetNumberOfPoints()-1))

    #set up transform
    transform = vtk.vtkThinPlateSplineTransform()
    transform.SetSourceLandmarks( sourcePoints )
    transform.SetBasisToR()
    transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
    transformNode.SetAndObserveTransformToParent(transform)

    #Iterate through each triangle in fiducial mesh and project sampled triangle
    idList=vtk.vtkIdList()
    triangleArray = fiducialMesh.GetPolys()
    triangleArray.InitTraversal()

    #define new landmark sets
    semilandmarkPoints=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "semiLM")
    gridPoints=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "grid")

    print("Iterate through cells")
    #iterate through each triangle cell in the landmark mesh
    for triangle in range(4): #(triangleArray.GetNumberOfCells()):
      print("Semilandmark n: ", semilandmarkPoints.GetNumberOfFiducials())
      print("Triangle: ", triangle)
      triangleArray.GetNextCell(idList)
      print(idList)
      targetPoints.Reset()
      for verticeIndex in range(3):
        verticeID=idList.GetId(verticeIndex)
        verticeLocation=fiducialMesh.GetPoint(verticeID)
        targetPoints.InsertNextPoint(verticeLocation)
        print("Adding target point: ", verticeLocation)

      transform.SetTargetLandmarks( targetPoints )
      model=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "mesh_resampled")
      model.SetAndObservePolyData(gridPolydata)
      model.SetAndObserveTransformNodeID(transformNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(model)
      transformedPolydata = model.GetPolyData()

      # #get surface normal from each landmark point
      rayDirection=[0,0,0]
      normalArray = surfacePolydata.GetPointData().GetArray("Normals")

      # #calculate average normal from cell landmarks
      for verticeIndex in range(3):
        verticeLocation = targetPoints.GetPoint(verticeIndex)
        closestPointId = pointLocator.FindClosestPoint(verticeLocation)
        tempNormal = normalArray.GetTuple(closestPointId)
        print("Normal: ", tempNormal)
        rayDirection[0] += tempNormal[0]
        rayDirection[1] += tempNormal[1]
        rayDirection[2] += tempNormal[2]

      for dim in range(len(rayDirection)):
        rayDirection[dim]=rayDirection[dim]/3

      #get a sample distance for quality control
      m1 = model.GetPolyData().GetPoint(0)
      m2 = model.GetPolyData().GetPoint(1)
      #sampleDistance = 3*abs( (m1[0] - m2[0])+(m1[1] - m2[1])+ (m1[2] - m2[2]))
      sampleDistance = fiducialMesh.GetLength()/10
      print("Sample distance: ", sampleDistance)

      # iterate through each point in the resampled triangle
      for index in range(model.GetPolyData().GetNumberOfPoints()):
        print("Point: ", index)
        modelPoint=model.GetPolyData().GetPoint(index)
        gridPoints.AddFiducialFromArray(modelPoint)
        rayEndPoint=[0,0,0]
        for dim in range(len(rayEndPoint)):
          rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* 1000
        intersectionIds=vtk.vtkIdList()
        intersectionPoints=vtk.vtkPoints()
        obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
        #print("Intersections: ", intersectionIds.GetNumberOfIds())
        #if there are intersections, update the point to most external one.
        if intersectionPoints.GetNumberOfPoints()>0:
          exteriorPoint = intersectionPoints.GetPoint(intersectionPoints.GetNumberOfPoints()-1)
          projectionDistance=abs( (exteriorPoint[0] - modelPoint[0])+(exteriorPoint[1] - modelPoint[1])+ (exteriorPoint[2] - modelPoint[2]))
          semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
        #if there are no intersections, reverse the normal vector
        else:
          for dim in range(len(rayEndPoint)):
            rayEndPoint[dim] = modelPoint[dim] + rayDirection[dim]* -1000
          obbTree.IntersectWithLine(modelPoint,rayEndPoint,intersectionPoints,intersectionIds)
          if intersectionPoints.GetNumberOfPoints()>0:
            exteriorPoint = intersectionPoints.GetPoint(0)
            projectionDistance=abs( (exteriorPoint[0] - modelPoint[0])+(exteriorPoint[1] - modelPoint[1])+ (exteriorPoint[2] - modelPoint[2]))
            if projectionDistance < sampleDistance:
              semilandmarkPoints.AddFiducialFromArray(exteriorPoint)
            else:
              print("projectionDistance distance: ", projectionDistance)
              closestPointId = pointLocator.FindClosestPoint(modelPoint)
              rayOrigin = surfacePolydata.GetPoint(closestPointId)
              semilandmarkPoints.AddFiducialFromArray(rayOrigin)

          #if none in reverse direction, use closest mesh point
          else:
            closestPointId = pointLocator.FindClosestPoint(modelPoint)
            rayOrigin = surfacePolydata.GetPoint(closestPointId)
            semilandmarkPoints.AddFiducialFromArray(rayOrigin)
      #remove temporary model node
      #slicer.mrmlScene.RemoveNode(model)

    slicer.mrmlScene.RemoveNode(transformNode)
    return True

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
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767',
      checksums='SHA256:12d17fba4f2e1f1a843f0757366f28c3f3e1a8bb38836f0de2a32bb1cd476560')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = SemiLandmarkLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
