import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch
import  numpy as np
import random
import math

import re
import csv
#
# PseudoLMGenerator
#

class PseudoLMGenerator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "PseudoLMGenerator" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Geometric Morphometrics"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module densely samples pseudo-landmarks on the surface of a model.
      <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PseudoLMGenerator">online documentation.</a>.</p>
      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
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
# PseudoLMGeneratorWidget
#

class PseudoLMGeneratorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def onSelect(self):
    self.getPointNumberButton.enabled = bool ( self.modelSelector.currentNode() )
    self.projectionFactor.enabled = True

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
    # Select base model
    #
    self.modelSelector = slicer.qMRMLNodeComboBox()
    self.modelSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    self.modelSelector.selectNodeUponCreation = False
    self.modelSelector.addEnabled = False
    self.modelSelector.removeEnabled = False
    self.modelSelector.noneEnabled = True
    self.modelSelector.showHidden = False
    self.modelSelector.setMRMLScene( slicer.mrmlScene )
    parametersFormLayout.addRow("Base model: ", self.modelSelector)

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
    # Specify plane of symmetry
    #
    self.planeSelector = slicer.qMRMLNodeComboBox()
    self.planeSelector.nodeTypes = ( ("vtkMRMLMarkupsPlaneNode"), "" )
    self.planeSelector.enabled = True
    self.planeSelector.selectNodeUponCreation = False
    self.planeSelector.addEnabled = False
    self.planeSelector.removeEnabled = False
    self.planeSelector.noneEnabled = True
    self.planeSelector.showHidden = False
    self.planeSelector.setMRMLScene( slicer.mrmlScene )
    templateFormLayout.addRow("Symmetry plane: ", self.planeSelector)

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
    # Set max projection factor
    #
    self.projectionFactor = ctk.ctkSliderWidget()
    self.projectionFactor.enabled = False
    self.projectionFactor.singleStep = 1
    self.projectionFactor.minimum = 1
    self.projectionFactor.maximum = 200
    self.projectionFactor.value = 200
    self.projectionFactor.setToolTip("Set maximum projection as a percentage of the image diagonal")
    templateFormLayout.addRow("Maximum projection factor : ", self.projectionFactor)

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
    logic = PseudoLMGeneratorLogic()
    spacingPercentage = self.spacingTolerance.value/100
    scaleFactor = self.scaleFactor.value/100
    if self.EllipseType.isChecked():
      template = logic.generateEllipseTemplate(self.modelSelector.currentNode(), spacingPercentage, scaleFactor)
    elif self.SphereType.isChecked():
      template = logic.generateSphereTemplate(self.modelSelector.currentNode(), spacingPercentage, scaleFactor)
    else:
      template = logic.generateOriginalGeometryTemplate(self.modelSelector.currentNode(), spacingPercentage)

    #if (self.planeSelector.currentNode() is not None):
      #self.templatePolyData = logic.cropWithPlane(template, self.planeSelector.currentNode())
    #else:

    self.templatePolyData = template

    self.subsampleInfo.insertPlainText(f'The subsampled template has a total of {self.templatePolyData.GetNumberOfPoints()} points. \n')

    # enable next step
    self.applySphereButton.enabled = True

  def onApplySphereButton(self):
    logic = PseudoLMGeneratorLogic()
    # set up MRML node for sphere polyData and visualize
    self.templateNode = logic.addTemplateToScene(self.templatePolyData)

    # enable next step
    self.projectPointsButton.enabled = True

  def onProjectPointsButton(self):
    logic = PseudoLMGeneratorLogic()
    isOriginalGeometry = self.OriginalType.isChecked()
    maxProjection = self.projectionFactor.value/100
    projectionModel = self.modelSelector.currentNode().GetPolyData()
    if isOriginalGeometry:
      projectionTemplate = projectionModel
    else:
      projectionTemplate = self.templateNode.GetPolyData()

    self.projectedLM = logic.runPointProjection(projectionTemplate, projectionModel, self.templateNode.GetPolyData().GetPoints(), maxProjection, isOriginalGeometry, self.planeSelector.currentNode())

    # update visualization
    self.templateNode.SetDisplayVisibility(False)
    self.projectedLM.SetDisplayVisibility(True)
    self.projectedLM.GetDisplayNode().SetPointLabelsVisibility(False)
    red=[1,0,0]
    self.projectedLM.GetDisplayNode().SetSelectedColor(red)

    # enable next step
    self.cleanButton.enabled = True

  def onCleanButton(self):
    logic = PseudoLMGeneratorLogic()
    spacingPercentage = self.spacingTolerance.value/100
    self.sphericalSemiLandmarks = logic.runCleaningFast(self.projectedLM, self.templateNode, spacingPercentage)

    # update visualization
    for i in range(self.sphericalSemiLandmarks.GetNumberOfFiducials()):
      self.sphericalSemiLandmarks.SetNthFiducialLocked(i,True)

    self.sphericalSemiLandmarks.GetDisplayNode().SetPointLabelsVisibility(False)
    green=[0,1,0]
    purple=[1,0,1]
    self.sphericalSemiLandmarks.GetDisplayNode().SetSelectedColor(green)
    self.sphericalSemiLandmarks.GetDisplayNode().SetColor(purple)
    self.projectedLM.SetDisplayVisibility(False)

    #confirm number of cleaned points is in the expected range
    self.subsampleInfo.insertPlainText(f'After filtering there are {self.sphericalSemiLandmarks.GetNumberOfFiducials()} semi-landmark points. \n')

    if self.planeSelector.currentNode() is not None:
      print("Symmetrizing points")
      logic.symmetrizeLandmarks(self.modelSelector.currentNode(), self.sphericalSemiLandmarks, self.planeSelector.currentNode(), spacingPercentage)
      self.sphericalSemiLandmarks.SetDisplayVisibility(False)
#
# PseudoLMGeneratorLogic
#

class PseudoLMGeneratorLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def setAllLandmarksType(self,landmarkNode, setToSemiType):
    landmarkDescription = "Semi"
    if setToSemiType is False:
      landmarkDescription = "Fixed"
    for controlPointIndex in range(landmarkNode.GetNumberOfControlPoints()):
      landmarkNode.SetNthControlPointDescription(controlPointIndex, landmarkDescription)

  def runCleaningPointCloud(self, projectedLM, sphere, spacingPercentage):
    # Convert projected surface points to a VTK array for transform
    p=[0,0,0]
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfFiducials()):
      projectedLM.GetMarkupPoint(0,i,p)
      targetPoints.InsertNextPoint(p)
      print("inserting vtk point: ", p)

    pointPD=vtk.vtkPolyData()
    pointPD.SetPoints(targetPoints)

    glyphFilter=vtk.vtkGlyph3D()
    glyphFilter.SetInputData(pointPD)
    glyphFilter.Update()
    glyphPD = glyphFilter.GetOutput()

    cleanFilter=vtk.vtkCleanPolyData()
    cleanFilter.SetTolerance(spacingPercentage)
    cleanFilter.SetInputData(glyphPD)
    cleanFilter.Update()
    outputPoints = cleanFilter.GetOutput()

    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"PseudoLandmarks")
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(outputPoints.GetNumberOfPoints()):
      point = outputPoints.GetPoint(i)
      sphereSampleLMNode.AddFiducialFromArray(point)
      print("inserting fiducial point: ", p)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
    return sphereSampleLMNode

  def runCleaningFast(self, projectedLM, sphere, spacingPercentage):
    # Convert projected surface points to a VTK array for transform
    p=[0,0,0]
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfFiducials()):
      projectedLM.GetMarkupPoint(0,i,p)
      targetPoints.InsertNextPoint(p)

    templateData = sphere.GetPolyData()
    templateData.SetPoints(targetPoints)

    # Clean up semi-landmarks within radius
    filter=vtk.vtkCleanPolyData()
    filter.SetToleranceIsAbsolute(False)
    filter.SetTolerance(spacingPercentage/2)
    filter.SetInputData(templateData)
    filter.Update()
    cleanPolyData=filter.GetOutput()

    # Create a landmark node from the cleaned polyData
    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"PseudoLandmarks")
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(cleanPolyData.GetNumberOfPoints()):
      point = cleanPolyData.GetPoint(i)
      sphereSampleLMNode.AddFiducialFromArray(point)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
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
    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"PseudoLandmarks")
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(cleanPolyData.GetNumberOfPoints()):
      point = cleanPolyData.GetPoint(i)
      sphereSampleLMNode.AddFiducialFromArray(point)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
    return sphereSampleLMNode

  def runPointProjection(self, sphere, model, spherePoints, maxProjectionFactor, isOriginalGeometry, symmetryPlane=None):
    maxProjection = (model.GetLength()) * maxProjectionFactor
    print('max projection: ', maxProjection)
    # project landmarks from template to model
    projectedPoints = self.projectPointsPolydata(sphere, model, spherePoints, maxProjection)
    projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"projectedLM")
    projectedLMNode.CreateDefaultDisplayNodes()
    if(isOriginalGeometry):
      for i in range(projectedPoints.GetNumberOfPoints()):
        point = projectedPoints.GetPoint(i)
        projectedLMNode.AddFiducialFromArray(point)
      return projectedLMNode
    else:
      #project landmarks from model to model external surface
      projectedPointsExternal = self.projectPointsPolydata(model, model, projectedPoints, maxProjection)
      for i in range(projectedPointsExternal.GetNumberOfPoints()):
        point = projectedPointsExternal.GetPoint(i)
        projectedLMNode.AddFiducialFromArray(point)
      return projectedLMNode

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
        #if none in reverse direction, use closest model point
        else:
          closestPointId = targetPointLocator.FindClosestPoint(originalPoint)
          rayOrigin = targetPolydata.GetPoint(closestPointId)
          projectedPoints.InsertNextPoint(rayOrigin)
    print('Projected points:', originalPoints.GetNumberOfPoints() )
    return projectedPointData

  def getTemplateLandmarks(self, spherePolyData):
    semiLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"templatePoints")
    semiLMNode.CreateDefaultDisplayNodes()
    for i in range(spherePolyData.GetNumberOfPoints()):
      point = spherePolyData.GetPoint(i)
      semiLMNode.AddFiducialFromArray(point)

    return semiLMNode

  def addTemplateToScene(self, spherePolyData):
    sphereNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode',"templateModel")
    sphereNode.CreateDefaultDisplayNodes()
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

  def cropWithPlane(self, inputData, plane, insideOutOption=False):
    normal=[0,0,0]
    origin=[0,0,0]
    plane.GetNormalWorld(normal)
    plane.GetOriginWorld(origin)

    vtkPlane = vtk.vtkPlane()
    vtkPlane.SetOrigin(origin)
    vtkPlane.SetNormal(normal)
    clipper = vtk.vtkClipPolyData()
    clipper.SetClipFunction(vtkPlane)
    clipper.SetInputData(inputData)
    clipper.SetInsideOut(insideOutOption)
    clipper.Update()
    return clipper.GetOutput()

  def createSymmetry(self, inputData, plane):
    normal=[0,0,0]
    origin=[0,0,0]
    plane.GetNormalWorld(normal)
    plane.GetOriginWorld(origin)

    vtkPlane = vtk.vtkPlane()
    vtkPlane.SetOrigin(origin)
    vtkPlane.SetNormal(normal)
    clipper = vtk.vtkClipPolyData()
    clipper.SetClipFunction(vtkPlane)
    clipper.SetInputData(inputData)
    clipper.Update()
    return cleanFilter.GetOutput()

    mirrorMatrix = vtk.vtkMatrix4x4()
    mirrorMatrix.SetElement(0, 0, 1 - 2 * normal[0] * normal[0])
    mirrorMatrix.SetElement(0, 1, - 2 * normal[0] * normal[1])
    mirrorMatrix.SetElement(0, 2, - 2 * normal[0] * normal[2])
    mirrorMatrix.SetElement(1, 0, - 2 * normal[0] * normal[1])
    mirrorMatrix.SetElement(1, 1, 1 - 2 * normal[1] * normal[1])
    mirrorMatrix.SetElement(1, 2, - 2 * normal[1] * normal[2])
    mirrorMatrix.SetElement(2, 0, - 2 * normal[0] * normal[2])
    mirrorMatrix.SetElement(2, 1, - 2 * normal[1] * normal[2])
    mirrorMatrix.SetElement(2, 2, 1 - 2 * normal[2] * normal[2])

    translateWorldToPlane = [0,0,0]
    vtk.vtkMath.Add(translateWorldToPlane, origin, translateWorldToPlane)
    translatePlaneOToWorld = [0,0,0]
    vtk.vtkMath.Add(translatePlaneOToWorld, origin, translatePlaneOToWorld)
    vtk.vtkMath.MultiplyScalar(translatePlaneOToWorld ,-1)

    mirrorTransform = vtk.vtkTransform()
    mirrorTransform.SetMatrix(mirrorMatrix)
    mirrorTransform.PostMultiply()
    mirrorTransform.Identity()
    mirrorTransform.Translate(translatePlaneOToWorld)
    mirrorTransform.Concatenate(mirrorMatrix)
    mirrorTransform.Translate(translateWorldToPlane)
    mirrorFilter = vtk.vtkTransformFilter()
    mirrorFilter.SetTransform(mirrorTransform)
    mirrorFilter.SetInputConnection(clipper.GetOutputPort())

    reverseNormalFilter = vtk.vtkReverseSense()
    reverseNormalFilter.SetInputConnection(mirrorFilter.GetOutputPort())
    reverseNormalFilter.Update()

    appendFilter = vtk.vtkAppendPolyData()
    appendFilter.AddInputData(clipper.GetOutput())
    appendFilter.AddInputData(reverseNormalFilter.GetOutput())

    cleanFilter = vtk.vtkCleanPolyData()
    cleanFilter.SetInputConnection(appendFilter.GetOutputPort())
    cleanFilter.Update()
    return cleanFilter.GetOutput()

  def clipAndMirrorWithPlane(self, inputData, plane):
    normal=[0,0,0]
    origin=[0,0,0]
    plane.GetNormalWorld(normal)
    plane.GetOriginWorld(origin)

    vtkPlane = vtk.vtkPlane()
    vtkPlane.SetOrigin(origin)
    vtkPlane.SetNormal(normal)
    clipper = vtk.vtkClipPolyData()
    clipper.SetClipFunction(vtkPlane)
    clipper.SetInputData(inputData)
    clipper.Update()

    mirrorMatrix = vtk.vtkMatrix4x4()
    mirrorMatrix.SetElement(0, 0, 1 - 2 * normal[0] * normal[0])
    mirrorMatrix.SetElement(0, 1, - 2 * normal[0] * normal[1])
    mirrorMatrix.SetElement(0, 2, - 2 * normal[0] * normal[2])
    mirrorMatrix.SetElement(1, 0, - 2 * normal[0] * normal[1])
    mirrorMatrix.SetElement(1, 1, 1 - 2 * normal[1] * normal[1])
    mirrorMatrix.SetElement(1, 2, - 2 * normal[1] * normal[2])
    mirrorMatrix.SetElement(2, 0, - 2 * normal[0] * normal[2])
    mirrorMatrix.SetElement(2, 1, - 2 * normal[1] * normal[2])
    mirrorMatrix.SetElement(2, 2, 1 - 2 * normal[2] * normal[2])

    translateWorldToPlane = [0,0,0]
    vtk.vtkMath.Add(translateWorldToPlane, origin, translateWorldToPlane)
    translatePlaneOToWorld = [0,0,0]
    vtk.vtkMath.Add(translatePlaneOToWorld, origin, translatePlaneOToWorld)
    vtk.vtkMath.MultiplyScalar(translatePlaneOToWorld ,-1)

    mirrorTransform = vtk.vtkTransform()
    mirrorTransform.SetMatrix(mirrorMatrix)
    mirrorTransform.PostMultiply()
    mirrorTransform.Identity()
    mirrorTransform.Translate(translatePlaneOToWorld)
    mirrorTransform.Concatenate(mirrorMatrix)
    mirrorTransform.Translate(translateWorldToPlane)
    mirrorFilter = vtk.vtkTransformFilter()
    mirrorFilter.SetTransform(mirrorTransform)
    mirrorFilter.SetInputConnection(clipper.GetOutputPort())

    reverseNormalFilter = vtk.vtkReverseSense()
    reverseNormalFilter.SetInputConnection(mirrorFilter.GetOutputPort())
    reverseNormalFilter.Update()

    return reverseNormalFilter.GetOutput()

  def symmetrizeLandmarks(self, modelNode, landmarkNode, plane, samplingPercentage):
    # clip and mirror model and points
    pointsVTK = vtk.vtkPoints()
    pointPolyData = vtk.vtkPolyData()
    pointPolyData.SetPoints(pointsVTK)
    model = modelNode.GetPolyData()
    for i in range(landmarkNode.GetNumberOfFiducials()):
      pointsVTK.InsertNextPoint(landmarkNode.GetNthControlPointPositionVector(i))
    geometryFilter = vtk.vtkVertexGlyphFilter()
    geometryFilter.SetInputData(pointPolyData)
    geometryFilter.Update()
    vertPolyData = geometryFilter.GetOutput()
    mirrorPoints = self.clipAndMirrorWithPlane(vertPolyData, plane)
    mirrorMesh = self.clipAndMirrorWithPlane(model, plane)
    # get clipped point set
    clippedPoints = self.cropWithPlane(vertPolyData, plane)
    insideOutOption = True
    clippedMesh = self.cropWithPlane(model, plane, insideOutOption)

    # project mirrored points onto model
    maxProjection = model.GetLength()*.3
    projectedPoints = self.projectPointsPolydata(mirrorMesh, clippedMesh, mirrorPoints, maxProjection)

    # convert symmetric points to landmark node
    clippedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"LM_normal")
    clippedLMNode.CreateDefaultDisplayNodes()
    clippedLMNode.SetDisplayVisibility(False)
    clippedLMNode.GetDisplayNode().SetPointLabelsVisibility(False)
    pink=[1,0,1]
    clippedLMNode.GetDisplayNode().SetSelectedColor(pink)

    projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"LM_inverse")
    projectedLMNode.CreateDefaultDisplayNodes()
    projectedLMNode.SetDisplayVisibility(False)
    projectedLMNode.GetDisplayNode().SetPointLabelsVisibility(False)
    teal=[0,1,1]
    projectedLMNode.GetDisplayNode().SetSelectedColor(teal)

    midlineLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"LM_merged")
    midlineLMNode.CreateDefaultDisplayNodes()
    midlineLMNode.SetDisplayVisibility(False)
    midlineLMNode.GetDisplayNode().SetPointLabelsVisibility(False)
    orange=[1,.5,0]
    midlineLMNode.GetDisplayNode().SetSelectedColor(orange)

    totalLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',"SymmetricPseudoLandmarks")
    totalLMNode.CreateDefaultDisplayNodes()
    totalLMNode.GetDisplayNode().SetPointLabelsVisibility(False)
    green=[0,1,0]
    purple=[1,0,1]
    totalLMNode.GetDisplayNode().SetSelectedColor(green)
    totalLMNode.GetDisplayNode().SetColor(purple)

    samplingDistance = model.GetLength()*samplingPercentage
    spatialConstraint = samplingDistance*samplingDistance
    mergedPoint = [0,0,0]
    for i in range(projectedPoints.GetNumberOfPoints()):
      clippedPoint = clippedPoints.GetPoint(i)
      projectedPoint = projectedPoints.GetPoint(i)
      distance = vtk.vtkMath().Distance2BetweenPoints(clippedPoint, projectedPoint)
      if distance > spatialConstraint:
        clippedLMNode.AddFiducialFromArray(clippedPoint, 'n_'+str(i))
        projectedLMNode.AddFiducialFromArray(projectedPoint, 'i_'+str(i))
        totalLMNode.AddFiducialFromArray(clippedPoint, 'n_'+str(i))
        totalLMNode.AddFiducialFromArray(projectedPoint, 'i_'+str(i))
      else:
        mergedPoint[0] = (clippedPoint[0]+projectedPoint[0])/2
        mergedPoint[1] = (clippedPoint[1]+projectedPoint[1])/2
        mergedPoint[2] = (clippedPoint[2]+projectedPoint[2])/2
        totalLMNode.AddFiducialFromArray(mergedPoint, 'm_'+str(i))
        midlineLMNode.AddFiducialFromArray(mergedPoint, 'm_'+str(i))

    # set pseudo landmarks created to type II
    landmarkTypeSemi=True
    self.setAllLandmarksType(totalLMNode, landmarkTypeSemi)
    self.setAllLandmarksType(midlineLMNode, landmarkTypeSemi)
    self.setAllLandmarksType(projectedLMNode, landmarkTypeSemi)
    self.setAllLandmarksType(clippedLMNode, landmarkTypeSemi)

    return projectedLMNode

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


class PseudoLMGeneratorTest(ScriptedLoadableModuleTest):
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
    self.test_PseudoLMGenerator1()

  def test_PseudoLMGenerator1(self):
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

    logic = PseudoLMGeneratorLogic()

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
