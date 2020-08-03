import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

import SemiLandmark
import re
import csv
#
# SphericalSampling
#

class SphericalSampling(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SphericalSampling" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module samples projects semi-landmark points from a spherical surface to a model.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
      3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

#
# SphericalSamplingWidget
#

class SphericalSamplingWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.getPointNumberButton.enabled = bool ( self.modelSelector.currentNode() )
          
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    
    # Instantiate and connect widgets ...
    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Input Parameters"
    self.layout.addWidget(parametersCollapsibleButton)
    
    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)
  
    #
    # Select base mesh
    #
    self.modelSelector = slicer.qMRMLNodeComboBox()
    self.modelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.modelSelector.selectNodeUponCreation = False
    self.modelSelector.addEnabled = False
    self.modelSelector.removeEnabled = False
    self.modelSelector.noneEnabled = True
    self.modelSelector.showHidden = False
    self.modelSelector.setMRMLScene( slicer.mrmlScene )
    parametersFormLayout.addRow("Base mesh: ", self.modelSelector)
    
    #
    # Set spacing tolerance
    #
    self.spacingTolerance = ctk.ctkSliderWidget()
    self.spacingTolerance.singleStep = .1
    self.spacingTolerance.minimum = 0
    self.spacingTolerance.maximum = 10
    self.spacingTolerance.value = 4
    self.spacingTolerance.setToolTip("Set tolerance of spacing as a percentage of the image diagonal")
    parametersFormLayout.addRow("Spacing tolerance: ", self.spacingTolerance)
    
    #
    # Parameters Area
    #
    templateCollapsibleButton = ctk.ctkCollapsibleButton()
    templateCollapsibleButton.text = "Template Geometry"
    self.layout.addWidget(templateCollapsibleButton)
    
    # Layout within the dummy collapsible button
    templateFormLayout = qt.QFormLayout(templateCollapsibleButton)
    
    #
    # Select geometry of template
    #
    self.OriginalType=qt.QRadioButton()
    self.OriginalType.setChecked(True)
    self.EllipseType=qt.QRadioButton()
    self.SphereType=qt.QRadioButton()   
    templateFormLayout.addRow("Original Geometry", self.OriginalType)
    templateFormLayout.addRow("Ellipse", self.EllipseType)
    templateFormLayout.addRow("Sphere", self.SphereType)
    
    #
    # Set template scale factor
    #
    self.scaleFactor = ctk.ctkSliderWidget()
    self.scaleFactor.enabled = False
    self.scaleFactor.singleStep = 1
    self.scaleFactor.minimum = 75
    self.scaleFactor.maximum = 150
    self.scaleFactor.value = 110
    self.scaleFactor.setToolTip("Set  template scale factor as a percentage of the image diagonal")
    templateFormLayout.addRow("Template scale factor : ", self.scaleFactor)
    
    #
    # Run Area
    #
    samplingCollapsibleButton = ctk.ctkCollapsibleButton()
    samplingCollapsibleButton.text = "Run Sampling"
    self.layout.addWidget(samplingCollapsibleButton)
    
    # Layout within the dummy collapsible button
    samplingFormLayout = qt.QFormLayout(samplingCollapsibleButton)
    #
    # Get Subsample Rate Button
    #
    self.getPointNumberButton = qt.QPushButton("Get subsample number")
    self.getPointNumberButton.toolTip = "Output the number of points sampled on the template shape."
    self.getPointNumberButton.enabled = False
    samplingFormLayout.addRow(self.getPointNumberButton)
    
    #
    # Subsample Information
    #
    self.subsampleInfo = qt.QPlainTextEdit()
    self.subsampleInfo.setPlaceholderText("Subsampling information")
    self.subsampleInfo.setReadOnly(True)
    samplingFormLayout.addRow(self.subsampleInfo)
    
    #
    # Apply sphere button
    #
    self.applySphereButton = qt.QPushButton("Generate template")
    self.applySphereButton.toolTip = "Generate sampled template shape."
    self.applySphereButton.enabled = False
    samplingFormLayout.addRow(self.applySphereButton)
    
    #
    # Project Points button
    #
    self.projectPointsButton = qt.QPushButton("Project points to surface")
    self.projectPointsButton.toolTip = "Project the points from the sampled template to the model surface."
    self.projectPointsButton.enabled = False
    samplingFormLayout.addRow(self.projectPointsButton)
    
    #
    # Clean Points button
    #
    self.cleanButton = qt.QPushButton("Enforce spatial sampling rate")
    self.cleanButton.toolTip = "Remove points spaced closer than the user-specified tolerance."
    self.cleanButton.enabled = False
    samplingFormLayout.addRow(self.cleanButton)
    
    
    
    # connections
    self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.OriginalType.connect('toggled(bool)', self.onToggleModel)
    self.getPointNumberButton.connect('clicked(bool)', self.onGetPointNumberButton)
    self.applySphereButton.connect('clicked(bool)', self.onApplySphereButton)
    self.projectPointsButton.connect('clicked(bool)', self.onProjectPointsButton)
    self.cleanButton.connect('clicked(bool)', self.onCleanButton)
    
    # Add vertical spacer
    self.layout.addStretch(1)
  
  def cleanup(self):
    pass
  
  def onToggleModel(self):
    self.scaleFactor.enabled = bool(self.OriginalType.isChecked()) is False
      
  def onGetPointNumberButton(self):
    logic = SphericalSamplingLogic()
    spacingPercentage = self.spacingTolerance.value/100
    scaleFactor = self.scaleFactor.value/100
    if self.EllipseType.isChecked():
      self.templatePolyData = logic.generateEllipseTemplate(self.modelSelector.currentNode(), spacingPercentage, scaleFactor)
    elif self.SphereType.isChecked():
      self.templatePolyData = logic.generateSphereTemplate(self.modelSelector.currentNode(), spacingPercentage, scaleFactor)
    else: 
      self.templatePolyData = logic.generateOriginalGeometryTemplate(self.modelSelector.currentNode(), spacingPercentage)
      
    self.subsampleInfo.insertPlainText(f'The subsampled template has a total of {self.templatePolyData.GetNumberOfPoints()} points. \n')
    
    # enable next step
    self.applySphereButton.enabled = True
  
  def onApplySphereButton(self):
    logic = SphericalSamplingLogic()
    # set up MRML node for sphere polyData and visualize
    self.templateNode = logic.addTemplateToScene(self.templatePolyData)
    #self.templateLMNode = logic.getTemplateLandmarks(self.templatePolyData)
    
    # update visualization
    #self.templateLMNode.GetDisplayNode().SetPointLabelsVisibility(False)
   # blue=[0,0,1]
    #self.templateLMNode.GetDisplayNode().SetSelectedColor(blue)
    # enable next step
    self.projectPointsButton.enabled = True
      
  def onProjectPointsButton(self):
    logic = SphericalSamplingLogic()
    isOriginalGeometry = self.OriginalType.isChecked()
    if isOriginalGeometry:
      self.projectedLM = logic.runPointProjection(self.modelSelector.currentNode(), self.modelSelector.currentNode(), self.templateNode.GetPolyData().GetPoints(), isOriginalGeometry)
    else:    
      self.projectedLM = logic.runPointProjection(self.templateNode, self.modelSelector.currentNode(), self.templateNode.GetPolyData().GetPoints(), isOriginalGeometry)
    
    if self.projectedLM.GetNumberOfFiducials() == self.templateNode.GetPolyData().GetNumberOfPoints():
      # update visualization
      #self.templateLMNode.SetDisplayVisibility(False)
      self.templateNode.SetDisplayVisibility(False)
      self.projectedLM.GetDisplayNode().SetPointLabelsVisibility(False)
      red=[1,0,0]
      self.projectedLM.GetDisplayNode().SetSelectedColor(red) 
    
      # enable next step
      self.cleanButton.enabled = True
    else:
      print("Error: projected point number does not match template point number")
      self.cleanButton.enabled = False
    
  def onCleanButton(self):
    logic = SphericalSamplingLogic()
    spacingPercentage = self.spacingTolerance.value/100
    self.sphericalSemiLandmarks = logic.runCleaning(self.projectedLM, self.templateNode, spacingPercentage)
    
    # update visualization
    self.projectedLM.SetDisplayVisibility(False)
    self.sphericalSemiLandmarks.GetDisplayNode().SetPointLabelsVisibility(False)
    green=[0,1,0]
    self.sphericalSemiLandmarks.GetDisplayNode().SetSelectedColor(green)
  
    #confirm number of cleaned points is in the expected range
    self.subsampleInfo.insertPlainText(f'After filtering there are {self.sphericalSemiLandmarks.GetNumberOfFiducials()} semi-landmark points. \n')
#
# SphericalSamplingLogic
#

class SphericalSamplingLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def runCleaningOriginalGeometry(self, projectedLM, sphere, spacingPercentage): 
    # Convert projected surface points to a VTK array for transform
    p=[0,0,0]
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfFiducials()):
      projectedLM.GetMarkupPoint(0,i,p)
      targetPoints.InsertNextPoint(p)
      
    pointPD=vtk.vtkPolyData()
    pointPD.SetPoints(targetPoints)

    glyphFilter=vtk.vtkGlyph3D()
    glyphFilter.SetInputData(pointPD)
    glyphFilter.Update()
    glyphPD = glyph.GetOutput()

    cleanFilter=vtk.vtkCleanPolyData()
    cleanFilter.SetTolerance(spacingPercentage)
    cleanFilter.SetInputData(glyphPD)
    cleanFilter.Update()
    outputPoints = cleanFilter.GetOutput()

    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"sphericalSampledLandmarks")
    for i in range(outputPoints.GetNumberOfPoints()):
      point = outputPoints.GetPoint(i)
      sphereSampleLMNode.AddFiducialFromArray(point)
    
    return sphereSampleLMNode
      
  def runCleaning(self, projectedLM, sphere, spacingPercentage):    
    # Convert projected surface points to a VTK array for transform
    p=[0,0,0]
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfFiducials()):
      projectedLM.GetMarkupPoint(0,i,p)
      targetPoints.InsertNextPoint(p)
      
    # Set up a transform between the sphere and the points projected to the surface
    transform = vtk.vtkThinPlateSplineTransform()
    transform.SetSourceLandmarks( sphere.GetPolyData().GetPoints() )
    transform.SetTargetLandmarks( targetPoints )
    transform.SetBasisToR()

    # Apply the transform to the sphere to create a model with spherical topology
    transformNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode","TPS")
    transformNode.SetAndObserveTransformToParent(transform)
    sphere.SetAndObserveTransformNodeID(transformNode.GetID())  
    slicer.vtkSlicerTransformLogic().hardenTransform(sphere)
    sphere.SetDisplayVisibility(False)
    
    # Clean up semi-landmarks within radius
    filter=vtk.vtkCleanPolyData()
    filter.SetToleranceIsAbsolute(False)
    filter.SetTolerance(spacingPercentage/2)
    filter.SetInputData(sphere.GetPolyData())
    filter.Update()
    cleanPolyData=filter.GetOutput()
    
    # Create a landmark node from the cleaned polyData
    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"sphericalSampledLandmarks")
    for i in range(cleanPolyData.GetNumberOfPoints()):
      point = cleanPolyData.GetPoint(i)
      sphereSampleLMNode.AddFiducialFromArray(point)
    
    return sphereSampleLMNode
    
  def runPointProjection(self, sphere, model, spherePoints, isOriginalGeometry):
    print("template points", spherePoints.GetNumberOfPoints())
    # project landmarks from template to model
    projectedPoints = self.projectPointsPolydata(sphere.GetPolyData(), model.GetPolyData(), spherePoints, 1000)
    print("Points found 1st:", projectedPoints.GetNumberOfPoints())
    projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"projectedLM")
    if(isOriginalGeometry):
      for i in range(projectedPoints.GetNumberOfPoints()):
        point = projectedPoints.GetPoint(i)
        projectedLMNode.AddFiducialFromArray(point)
      return projectedLMNode
    else:    
      #project landmarks from model to model external surface
      projectedPointsExternal = self.projectPointsPolydata(model.GetPolyData(), model.GetPolyData(), projectedPoints, 1000)
      print("Points found 2nd:", projectedPointsExternal.GetNumberOfPoints())
      for i in range(projectedPointsExternal.GetNumberOfPoints()):
        point = projectedPointsExternal.GetPoint(i)
        projectedLMNode.AddFiducialFromArray(point)
      return projectedLMNode
  
  def projectPointsPolydata(self, sourcePolydata, targetPolydata, originalPoints, rayLength):
    print("original points: ", originalPoints.GetNumberOfPoints())
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
       
  def getTemplateLandmarks(self, spherePolyData):
    semiLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"templatePoints")
    for i in range(spherePolyData.GetNumberOfPoints()):
      point = spherePolyData.GetPoint(i)
      semiLMNode.AddFiducialFromArray(point)
    
    return semiLMNode
  
  def addTemplateToScene(self, spherePolyData):
    sphereNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode',"templateModel")
    sphereNode.SetAndObservePolyData(spherePolyData)
    sphereNode.CreateDefaultDisplayNodes()
    sphereNode.GetDisplayNode().SetRepresentation(1)
    sphereNode.GetDisplayNode().SetColor(0,0,1)
    return sphereNode
  
  def generateOriginalGeometryTemplate(self, model, spacingPercentage):
    points=model.GetPolyData()
    cleanFilter=vtk.vtkCleanPolyData()
    cleanFilter.SetToleranceIsAbsolute(False)
    cleanFilter.SetTolerance(spacingPercentage)
    cleanFilter.SetInputData(points)
    cleanFilter.Update()
    return cleanFilter.GetOutput()   
      
  def generateEllipseTemplate(self, model, spacingPercentage, scaleFactor):
    [x1,x2,y1,y2,z1,z2] = model.GetPolyData().GetBounds()
    lengthX = abs(x2-x1)
    lengthY = abs(y2-y1)
    lengthZ = abs(z2-z1)
    totalLength = lengthX +lengthY + lengthZ
    sphereSamplingRate = int(math.pi/spacingPercentage)
    ellipseCenter = [((x2-x1)/2)+x1, ((y2-y1)/2)+y1 ,((z2-z1)/2)+z1]
    
    # Generate an ellipse equation
    ellipse = vtk.vtkParametricEllipsoid()
    ellipse.SetXRadius(scaleFactor*(lengthX/2))
    ellipse.SetYRadius(scaleFactor*(lengthY/2))
    ellipse.SetZRadius(scaleFactor*(lengthZ/2))
    ellipseSource = vtk.vtkParametricFunctionSource()
    ellipseSource.SetParametricFunction(ellipse)
    ellipseSource.SetUResolution(sphereSamplingRate)
    ellipseSource.SetVResolution(sphereSamplingRate)
    ellipseSource.Update()
    
    #translate to origin
    transform = vtk.vtkTransform()
    transform.Translate(ellipseCenter)
    translateEllipse=vtk.vtkTransformFilter()
    translateEllipse.SetTransform(transform)
    translateEllipse.SetInputData(ellipseSource.GetOutput())
    translateEllipse.Update()
    
    # Clean up semi-landmarks within tolerance    
    cleanFilter=vtk.vtkCleanPolyData()
    cleanFilter.SetToleranceIsAbsolute(False)
    cleanFilter.SetTolerance(spacingPercentage)
    cleanFilter.SetInputData(translateEllipse.GetOutput())
    cleanFilter.Update()   

    return cleanFilter.GetOutput()   

  def generateSphereTemplate(self, model, spacingPercentage, scaleFactor):
    [x1,x2,y1,y2,z1,z2] = model.GetPolyData().GetBounds()
    lengthX = abs(x2-x1)
    lengthY = abs(y2-y1)
    lengthZ = abs(z2-z1)
    totalLength = lengthX +lengthY + lengthZ
    sphereSamplingRate = int(math.pi/spacingPercentage)
    sphereCenter = [((x2-x1)/2)+x1, ((y2-y1)/2)+y1 ,((z2-z1)/2)+z1]
    
    # Generate an ellipse equation
    sphere = vtk.vtkSphereSource()
    sphere.SetRadius(scaleFactor*totalLength/6)
    sphere.SetCenter(sphereCenter)
    sphere.SetThetaResolution(sphereSamplingRate)
    sphere.SetPhiResolution(sphereSamplingRate)
    sphere.Update()
    
    # Clean up semi-landmarks within tolerance    
    cleanFilter=vtk.vtkCleanPolyData()
    cleanFilter.SetToleranceIsAbsolute(False)
    cleanFilter.SetTolerance(spacingPercentage)
    cleanFilter.SetInputData(sphere.GetOutput())
    cleanFilter.Update() 
    
    return cleanFilter.GetOutput() 
        
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


class SphericalSamplingTest(ScriptedLoadableModuleTest):
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
    self.test_SphericalSampling1()
  
  def test_SphericalSampling1(self):
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
    logic = SphericalSamplingLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')



