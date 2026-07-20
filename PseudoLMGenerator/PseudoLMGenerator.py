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
      This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. Development of SlicerMorph is supported by NSF grants 1759883 and 2301405 to Murat Maga.
      """ # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#


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
    # Symmetrize the template
    #
    self.symmetrizeCheckBox = qt.QCheckBox()
    self.symmetrizeCheckBox.checked = False
    self.symmetrizeCheckBox.setToolTip("If checked, the mid-sagittal plane is estimated automatically from the model and the template is made bilaterally symmetric, output as matched normal / inverse / midline landmark sets. Leave unchecked for structures that are not bilaterally symmetric.")
    templateFormLayout.addRow("Symmetrize the template", self.symmetrizeCheckBox)

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
    self.projectionFactor.value = 10
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

    self.projectedLM = logic.runPointProjection(projectionTemplate, projectionModel, self.templateNode.GetPolyData().GetPoints(), maxProjection, isOriginalGeometry)

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
    for i in range(self.sphericalSemiLandmarks.GetNumberOfControlPoints()):
      self.sphericalSemiLandmarks.SetNthControlPointLocked(i,True)

    self.sphericalSemiLandmarks.GetDisplayNode().SetPointLabelsVisibility(False)
    green=[0,1,0]
    purple=[1,0,1]
    self.sphericalSemiLandmarks.GetDisplayNode().SetSelectedColor(green)
    self.sphericalSemiLandmarks.GetDisplayNode().SetColor(purple)
    self.projectedLM.SetDisplayVisibility(False)

    #confirm number of cleaned points is in the expected range
    self.subsampleInfo.insertPlainText(f'After filtering there are {self.sphericalSemiLandmarks.GetNumberOfControlPoints()} semi-landmark points. \n')

    if self.symmetrizeCheckBox.checked:
      planeNode = logic.detectSymmetryPlane(self.modelSelector.currentNode())
      normalNode, inverseNode, midlineNode, symmetricNode = logic.symmetrizeTemplate(self.modelSelector.currentNode(), self.sphericalSemiLandmarks, planeNode, spacingPercentage)
      self.sphericalSemiLandmarks.SetDisplayVisibility(False)
      # group the matched sides + midline in a folder named after the joint landmark set
      folderName = symmetricNode.GetName().replace("SymmetricPseudoLandmarks", "SymmetricPseudoLMs")
      self.nestNodesInFolder([normalNode, inverseNode, midlineNode], folderName)
      # show only the combined symmetric landmark set by default; hide the rest
      for node in [self.templateNode, normalNode, inverseNode, midlineNode]:
        node.SetDisplayVisibility(False)
      symmetricNode.SetDisplayVisibility(True)
      slicer.mrmlScene.RemoveNode(planeNode)  # transient: only used to define the reflection
      self.subsampleInfo.insertPlainText(f'Symmetrized about the auto-detected plane: {normalNode.GetNumberOfControlPoints()} normal + {inverseNode.GetNumberOfControlPoints()} inverse (matched pairs) + {midlineNode.GetNumberOfControlPoints()} midline points. \n')

  def nestNodesInFolder(self, nodes, folderName):
    # Group the given nodes under a new subject-hierarchy folder. folderName is
    # expected to be unique (the combined node's name), so repeated runs get
    # their own distinct folder. Per-node visibility is set by the caller; the
    # folder's own visibility is left on so the shown node stays visible.
    shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    folderItemID = shNode.CreateFolderItem(shNode.GetSceneItemID(), folderName)
    for node in nodes:
      shNode.SetItemParent(shNode.GetItemByDataNode(node), folderItemID)
    return folderItemID
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

  def _pointsToPolyData(self, points):
    # Wrap an Nx3 numpy array as a vtkPolyData vertex cloud (for ICP / locators).
    from vtk.util import numpy_support
    polyData = vtk.vtkPolyData()
    vtkPoints = vtk.vtkPoints()
    vtkPoints.SetData(numpy_support.numpy_to_vtk(np.ascontiguousarray(points, dtype=np.float64)))
    polyData.SetPoints(vtkPoints)
    vertexFilter = vtk.vtkVertexGlyphFilter()
    vertexFilter.SetInputData(polyData)
    vertexFilter.Update()
    return vertexFilter.GetOutput()

  def detectSymmetryPlane(self, modelNode, sampleSize=40000):
    # Estimate the bilateral (mid-sagittal) symmetry plane automatically, with no
    # manually drawn plane and no assumption about surface orientation. The model
    # is reflected across an initial guess plane and the reflection is rigidly
    # registered back onto the original (reflective ICP); the composed improper
    # transform is the mirror operator, whose eigenvector for eigenvalue -1 is the
    # plane normal. Returns a vtkMRMLMarkupsPlaneNode.
    points = slicer.util.arrayFromModelPoints(modelNode).astype(float)
    points = points[np.isfinite(points).all(axis=1)]
    center = points.mean(axis=0)
    if len(points) > sampleSize:
      generator = np.random.default_rng(0)
      points = points[generator.choice(len(points), sampleSize, replace=False)]

    # Initial guess: reflect across the plane normal to the shortest bounding-box axis.
    extent = points.max(axis=0) - points.min(axis=0)
    guessNormal = np.zeros(3)
    guessNormal[int(np.argmin(extent))] = 1.0
    reflectionMatrix = np.eye(4)
    reflectionMatrix[:3, :3] = np.eye(3) - 2.0 * np.outer(guessNormal, guessNormal)
    reflectionMatrix[:3, 3] = 2.0 * float(center @ guessNormal) * guessNormal
    reflected = (reflectionMatrix[:3, :3] @ points.T).T + reflectionMatrix[:3, 3]

    # Rigid ICP: reflected cloud -> original cloud.
    icp = vtk.vtkIterativeClosestPointTransform()
    icp.SetSource(self._pointsToPolyData(reflected))
    icp.SetTarget(self._pointsToPolyData(points))
    icp.GetLandmarkTransform().SetModeToRigidBody()
    icp.SetMaximumNumberOfIterations(60)
    icp.Update()
    icpMatrix = np.array([[icp.GetMatrix().GetElement(i, j) for j in range(4)] for i in range(4)])

    mirror = icpMatrix @ reflectionMatrix
    eigenvalues, eigenvectors = np.linalg.eig(mirror[:3, :3])
    normal = np.real(eigenvectors[:, int(np.argmin(eigenvalues.real))])
    normal = normal / np.linalg.norm(normal)
    offset = float(normal @ mirror[:3, 3]) / 2.0
    origin = center - (float(center @ normal) - offset) * normal

    tilt = np.degrees(np.arccos(min(1.0, abs(float(normal @ guessNormal)))))
    logging.info("PseudoLMGenerator: auto symmetry plane tilt %.2f deg from initial axis" % tilt)

    planeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsPlaneNode', slicer.mrmlScene.GenerateUniqueName('SymmetryPlane'))
    planeNode.SetNormalWorld(normal.tolist())
    planeNode.SetOriginWorld(origin.tolist())
    return planeNode

  def symmetrizeTemplate(self, modelNode, landmarkNode, plane, samplingPercentage):
    # Build a bilaterally symmetric template from the generated landmarks and
    # return it as distinct, index-matched markups nodes: the kept ("normal")
    # side, its exact mirror ("inverse", in the same order so index i is the
    # left/right partner across the two nodes), the midline (snapped onto the
    # plane), and a combined node. One side is kept and reflected so the two
    # sides correspond exactly, which is what makes the pairs usable for
    # asymmetry analysis.
    normal = [0.0, 0.0, 0.0]
    origin = [0.0, 0.0, 0.0]
    plane.GetNormalWorld(normal)
    plane.GetOriginWorld(origin)
    normal = np.array(normal, dtype=float)
    normal = normal / np.linalg.norm(normal)
    offset = float(np.array(origin, dtype=float) @ normal)

    points = slicer.util.arrayFromMarkupsControlPoints(landmarkNode, world=True).astype(float)
    signed = points @ normal - offset

    def reflectAcrossPlane(pointArray):
      return pointArray - 2.0 * (pointArray @ normal - offset)[:, None] * normal[None]

    midlineTolerance = 0.5 * samplingPercentage * modelNode.GetPolyData().GetLength()
    isMidline = np.abs(signed) < midlineTolerance

    # Keep whichever side of the plane carries more points as the reference side.
    positiveSide = signed >= midlineTolerance
    negativeSide = signed <= -midlineTolerance
    normalMask = positiveSide if int(np.count_nonzero(positiveSide)) >= int(np.count_nonzero(negativeSide)) else negativeSide

    normalPoints = points[normalMask]
    # inverse is the exact analytic mirror of the kept side and is intentionally
    # NOT re-projected onto the model surface: exact left/right correspondence is
    # required for a symmetric template, and re-projecting would reintroduce
    # asymmetry. On a near-symmetric reference the mirror lands essentially on the
    # surface anyway; on a strongly asymmetric one it may sit slightly off it.
    inversePoints = reflectAcrossPlane(normalPoints)
    midlinePoints = points[isMidline] - signed[isMidline][:, None] * normal[None]
    midlinePoints = self._mergeClosePoints(midlinePoints, midlineTolerance)

    blocks = [normalPoints, inversePoints]
    if len(midlinePoints):
      blocks.append(midlinePoints)
    combinedPoints = np.vstack(blocks)

    normalNode = self._makeLandmarkNode(normalPoints, 'PseudoLandmarks_normal', [0.0, 0.6, 1.0], 'n')
    inverseNode = self._makeLandmarkNode(inversePoints, 'PseudoLandmarks_inverse', [1.0, 0.4, 0.0], 'i')
    midlineNode = self._makeLandmarkNode(midlinePoints, 'PseudoLandmarks_midline', [0.0, 1.0, 0.0], 'm')
    combinedNode = self._makeLandmarkNode(combinedPoints, 'SymmetricPseudoLandmarks', [1.0, 0.0, 1.0], None)
    return normalNode, inverseNode, midlineNode, combinedNode

  def _makeLandmarkNode(self, pointsArray, name, color, labelPrefix):
    # Create a semi-landmark markups node from an Nx3 world-coordinate array.
    node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', slicer.mrmlScene.GenerateUniqueName(name))
    node.CreateDefaultDisplayNodes()
    if len(pointsArray):
      slicer.util.updateMarkupsControlPointsFromArray(node, np.ascontiguousarray(pointsArray, dtype=np.float64), world=True)
    self.setAllLandmarksType(node, True)
    if labelPrefix is not None:
      for controlPointIndex in range(node.GetNumberOfControlPoints()):
        node.SetNthControlPointLabel(controlPointIndex, "%s_%d" % (labelPrefix, controlPointIndex))
    node.GetDisplayNode().SetPointLabelsVisibility(False)
    node.GetDisplayNode().SetSelectedColor(color)
    return node

  def _mergeClosePoints(self, pointsArray, tolerance):
    # Merge points closer than tolerance, used to collapse near-duplicate midline
    # points that straddle the plane. Returns the deduplicated Nx3 array.
    if len(pointsArray) == 0:
      return pointsArray
    from vtk.util import numpy_support
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(self._pointsToPolyData(pointsArray))
    cleaner.SetToleranceIsAbsolute(True)
    cleaner.SetAbsoluteTolerance(tolerance)
    cleaner.Update()
    mergedPoints = cleaner.GetOutput().GetPoints()
    if mergedPoints is None or mergedPoints.GetNumberOfPoints() == 0:
      return pointsArray
    return numpy_support.vtk_to_numpy(mergedPoints.GetData()).astype(float)

  def runCleaningPointCloud(self, projectedLM, sphere, spacingPercentage):
    # Convert projected surface points to a VTK array for transform
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfControlPoints()):
      p = projectedLM.GetNthControlPointPosition(i)
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

    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',slicer.mrmlScene.GenerateUniqueName("PseudoLandmarks"))
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(outputPoints.GetNumberOfPoints()):
      point = outputPoints.GetPoint(i)
      sphereSampleLMNode.AddControlPoint(point)
      print("inserting fiducial point: ", p)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
    return sphereSampleLMNode

  def runCleaningFast(self, projectedLM, sphere, spacingPercentage):
    # Convert projected surface points to a VTK array for transform
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfControlPoints()):
      p = projectedLM.GetNthControlPointPosition(i)
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
    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',slicer.mrmlScene.GenerateUniqueName("PseudoLandmarks"))
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(cleanPolyData.GetNumberOfPoints()):
      point = cleanPolyData.GetPoint(i)
      sphereSampleLMNode.AddControlPoint(point)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
    return sphereSampleLMNode

  def runCleaning(self, projectedLM, sphere, spacingPercentage):
    # Convert projected surface points to a VTK array for transform
    targetPoints = vtk.vtkPoints()
    for i in range(projectedLM.GetNumberOfControlPoints()):
      p = projectedLM.GetNthControlPointPosition(i)
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
    sphereSampleLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',slicer.mrmlScene.GenerateUniqueName("PseudoLandmarks"))
    sphereSampleLMNode.CreateDefaultDisplayNodes()
    for i in range(cleanPolyData.GetNumberOfPoints()):
      point = cleanPolyData.GetPoint(i)
      sphereSampleLMNode.AddControlPoint(point)

    landmarkTypeSemi=True
    self.setAllLandmarksType(sphereSampleLMNode, landmarkTypeSemi)
    return sphereSampleLMNode

  def runPointProjection(self, sphere, model, spherePoints, maxProjectionFactor, isOriginalGeometry):
    maxProjection = (model.GetLength()) * maxProjectionFactor
    print('max projection: ', maxProjection)
    # project landmarks from template to model
    projectedPoints = self.projectPointsPolydata(sphere, model, spherePoints, maxProjection)
    projectedLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',slicer.mrmlScene.GenerateUniqueName("projectedLM"))
    projectedLMNode.CreateDefaultDisplayNodes()
    if(isOriginalGeometry):
      for i in range(projectedPoints.GetNumberOfPoints()):
        point = projectedPoints.GetPoint(i)
        projectedLMNode.AddControlPoint(point)
      return projectedLMNode
    else:
      #project landmarks from model to model external surface
      projectedPointsExternal = self.projectPointsPolydata(model, model, projectedPoints, maxProjection)
      for i in range(projectedPointsExternal.GetNumberOfPoints()):
        point = projectedPointsExternal.GetPoint(i)
        projectedLMNode.AddControlPoint(point)
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
    semiLMNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',slicer.mrmlScene.GenerateUniqueName("templatePoints"))
    semiLMNode.CreateDefaultDisplayNodes()
    for i in range(spherePolyData.GetNumberOfPoints()):
      point = spherePolyData.GetPoint(i)
      semiLMNode.AddControlPoint(point)

    return semiLMNode

  def addTemplateToScene(self, spherePolyData):
    sphereNode= slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode',slicer.mrmlScene.GenerateUniqueName("templateModel"))
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
