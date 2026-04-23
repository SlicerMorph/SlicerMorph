import json
import logging
import math
import os
import unittest
import uuid
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# action classes
#
class AnimatorAction:
  """Superclass for actions to be animated."""
  def __init__(self):
    self.uuid = uuid.uuid4()

  def cleanup(self, action):
    """Called when the action is deleted"""
    pass

  def act(self, action, scriptTime):
    pass

  def gui(self, action, layout):
    pass

  def allowMultiple(self):
    return True

  def wantsNonModalEditor(self):
    """Return True if the action's editor should open as a non-modal
    side panel (so the user can keep interacting with the 3D view)
    instead of a blocking modal dialog. Persistence then happens after
    every change via the onChanged callback that the editor receives.
    """
    return False

class CameraRotationAction(AnimatorAction):
  """Defines an animation of a transform"""
  def __init__(self):
    super().__init__()
    self.name = "Camera Rotation"
    self.animationMethods = ['azimuth', 'elevation', 'roll']

  def allowMultiple(self):
    return False

  def defaultAction(self):
    layoutManager = slicer.app.layoutManager()
    threeDView = layoutManager.threeDWidget(0).threeDView()
    animatedCamera = threeDView.cameraNode()
    referenceCamera = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLCameraNode')
    referenceCamera.SetName('referenceCamera')
    referenceCamera.GetCamera().DeepCopy(animatedCamera.GetCamera())
    cameraRotationAction = {
      'name': 'CameraRotation',
      'class': 'CameraRotationAction',
      'id': 'cameraRotation-'+str(self.uuid),
      'startTime': 0,
      'endTime': -1,
      'interpolation': 'linear',
      'referenceCameraID': referenceCamera.GetID(),
      'animatedCameraID': animatedCamera.GetID(),
      'degreesPerSecond': 90,
      'animationMethod': 'azimuth',
    }
    return(cameraRotationAction)

  def act(self, action, scriptTime):
    referenceCamera = slicer.mrmlScene.GetNodeByID(action['referenceCameraID'])
    animatedCamera = slicer.mrmlScene.GetNodeByID(action['animatedCameraID'])

    animatedCamera.GetCamera().DeepCopy(referenceCamera.GetCamera())
    if scriptTime <= action['startTime']:
      return
    else:
      actionTime = scriptTime - action['startTime']
      if actionTime > action['endTime']:
        actionTime = action['endTime'] # clamp to rotation at end
      angle = actionTime * action['degreesPerSecond']
      cameraObject = animatedCamera.GetCamera()
      methodMapping = {'azimuth': cameraObject.Azimuth,
                       'elevation': cameraObject.Elevation,
                       'roll': cameraObject.Roll,}
      methodMapping[action['animationMethod']](angle)
      animatedCamera.GetCamera().OrthogonalizeViewUp()
      # TODO: this->Renderer->UpdateLightsGeometryToFollowCamera()

  def gui(self, action, layout):
    super().gui(action, layout)

    self.referenceSelector = slicer.qMRMLNodeComboBox()
    self.referenceSelector.nodeTypes = ["vtkMRMLCameraNode"]
    self.referenceSelector.addEnabled = True
    self.referenceSelector.renameEnabled = True
    self.referenceSelector.removeEnabled = False
    self.referenceSelector.noneEnabled = False
    self.referenceSelector.selectNodeUponCreation = True
    self.referenceSelector.showHidden = True
    self.referenceSelector.showChildNodeTypes = True
    self.referenceSelector.setMRMLScene( slicer.mrmlScene )
    self.referenceSelector.setToolTip( "Pick the reference camera" )
    self.referenceSelector.currentNodeID = action['referenceCameraID']
    layout.addRow("Reference camera", self.referenceSelector)

    self.animatedSelector = slicer.qMRMLNodeComboBox()
    self.animatedSelector.nodeTypes = ["vtkMRMLCameraNode"]
    self.animatedSelector.addEnabled = True
    self.animatedSelector.renameEnabled = True
    self.animatedSelector.removeEnabled = False
    self.animatedSelector.noneEnabled = False
    self.animatedSelector.selectNodeUponCreation = True
    self.animatedSelector.showHidden = True
    self.animatedSelector.showChildNodeTypes = True
    self.animatedSelector.setMRMLScene( slicer.mrmlScene )
    self.animatedSelector.setToolTip( "Pick the animated camera" )
    self.animatedSelector.currentNodeID = action['animatedCameraID']
    layout.addRow("Animated camera", self.animatedSelector)

    self.rate = ctk.ctkDoubleSpinBox()
    self.rate.suffix = " degreesPerSecond"
    self.rate.decimals = 2
    self.rate.minimum = 0
    self.rate.maximum = 1000
    self.rate.value = action['degreesPerSecond']
    layout.addRow("Rotation rate", self.rate)

    self.method = qt.QComboBox()
    for method in self.animationMethods:
      self.method.addItem(method)
    self.method.currentText = action['animationMethod']
    layout.addRow("Animation method", self.method)

  def updateFromGUI(self, action):
    action['referenceCameraID'] = self.referenceSelector.currentNodeID
    action['animatedCameraID'] = self.animatedSelector.currentNodeID
    action['degreesPerSecond'] = self.rate.value
    action['animationMethod'] = self.method.currentText

class ROIAction(AnimatorAction):
  """Defines an animation of an roi (e.g. for volume cropping)"""
  def __init__(self):
    super().__init__()
    self.name = "ROI"

  def allowMultiple(self):
    return False

  def defaultAction(self):
    volumeRenderingNode = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    if not volumeRenderingNode:
      msg = "Need to set up volume rendering before using this action"
      logging.error(msg)
      raise RuntimeError
      return None
    slicer.modules.volumeRenderingNode = volumeRenderingNode
    animatedROI = volumeRenderingNode.GetMarkupsROINode()
    if not animatedROI:
      msg = "Need to set up volume rendering cropping ROI before using this action"
      logging.error(msg)
      raise RuntimeError
      return None
    volumeRenderingNode.SetCroppingEnabled(True)
    startROIID = None
    endROIID = None
    if False:
      # don't create start-and-end ROIs, but instead rely on
      # user to create them so they can have more than
      startROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
      startROI.SetName('Start ROI')
      endROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
      endROI.SetName('End ROI')
      for roi in [startROI, endROI]:
        for index in range(roi.GetNumberOfDisplayNodes()):
          roi.GetNthDisplayNode(index).SetVisibility(False)
      startROIID = startROI.GetID()
      endROIID = endROI.GetID()

      start = [0.,]*3
      animatedROI.GetXYZ(start)
      startROI.SetXYZ(start)
      endROI.SetXYZ(start)
      animatedROI.GetRadiusXYZ(start)
      startROI.SetRadiusXYZ(start)
      end = [0.,]*3
      for i in range(3):
        end[i] = start[i] / 2.
      endROI.SetRadiusXYZ(end)

    roiAction = {
      'name': 'ROI',
      'class': 'ROIAction',
      'id': 'roi-'+str(self.uuid),
      'startTime': 0,
      'endTime': -1,
      'interpolation': 'linear',
      'startROIID': startROIID,
      'endROIID': endROIID,
      'animatedROIID': animatedROI.GetID(),
    }
    return(roiAction)

  def act(self, action, scriptTime):
    if action['startROIID'] is None or action['startROIID'] is None:
      return
    startROI = slicer.mrmlScene.GetNodeByID(action['startROIID'])
    endROI = slicer.mrmlScene.GetNodeByID(action['endROIID'])
    animatedROI = slicer.mrmlScene.GetNodeByID(action['animatedROIID'])
    start = [0.,]*3
    end = [0.,]*3
    animated = [0,]*3
    if scriptTime <= action['startTime']:
      startROI.GetXYZ(start)
      animatedROI.SetXYZ(start)
      startROI.GetRadiusXYZ(start)
      animatedROI.SetRadiusXYZ(start)
    elif scriptTime >= action['endTime']:
      endROI.GetXYZ(end)
      animatedROI.SetXYZ(end)
      endROI.GetRadiusXYZ(end)
      animatedROI.SetRadiusXYZ(end)
    else:
      actionTime = scriptTime - action['startTime']
      duration = action['endTime'] - action['startTime']
      fraction = actionTime / duration
      startROI.GetXYZ(start)
      endROI.GetXYZ(end)
      for i in range(3):
        animated[i] = start[i] + fraction * (end[i]-start[i])
      animatedROI.SetXYZ(animated)
      startROI.GetRadiusXYZ(start)
      endROI.GetRadiusXYZ(end)
      for i in range(3):
        animated[i] = start[i] + fraction * (end[i]-start[i])
      animatedROI.SetRadiusXYZ(animated)

  def gui(self, action, layout):
    super().gui(action, layout)

    self.startSelector = slicer.qMRMLNodeComboBox()
    self.startSelector.nodeTypes = ["vtkMRMLMarkupsROINode", "vtkMRMLAnnotationROINode"]
    self.startSelector.addEnabled = True
    self.startSelector.renameEnabled = True
    self.startSelector.removeEnabled = True
    self.startSelector.noneEnabled = False
    self.startSelector.selectNodeUponCreation = True
    self.startSelector.showHidden = True
    self.startSelector.showChildNodeTypes = True
    self.startSelector.setMRMLScene( slicer.mrmlScene )
    self.startSelector.setToolTip( "Pick the start ROI" )
    self.startSelector.currentNodeID = action['startROIID']
    layout.addRow("Start ROI", self.startSelector)

    self.endSelector = slicer.qMRMLNodeComboBox()
    self.endSelector.nodeTypes = ["vtkMRMLMarkupsROINode", "vtkMRMLAnnotationROINode"]
    self.endSelector.addEnabled = True
    self.endSelector.renameEnabled = True
    self.endSelector.removeEnabled = True
    self.endSelector.noneEnabled = False
    self.endSelector.selectNodeUponCreation = True
    self.endSelector.showHidden = True
    self.endSelector.showChildNodeTypes = True
    self.endSelector.setMRMLScene( slicer.mrmlScene )
    self.endSelector.setToolTip( "Pick the end ROI" )
    self.endSelector.currentNodeID = action['endROIID']
    layout.addRow("End ROI", self.endSelector)

    self.animatedSelector = slicer.qMRMLNodeComboBox()
    self.animatedSelector.nodeTypes = ["vtkMRMLMarkupsROINode", "vtkMRMLAnnotationROINode"]
    self.animatedSelector.addEnabled = True
    self.animatedSelector.renameEnabled = True
    self.animatedSelector.removeEnabled = True
    self.animatedSelector.noneEnabled = False
    self.animatedSelector.selectNodeUponCreation = True
    self.animatedSelector.showHidden = True
    self.animatedSelector.showChildNodeTypes = True
    self.animatedSelector.setMRMLScene( slicer.mrmlScene )
    self.animatedSelector.setToolTip( "Pick the animated ROI" )
    self.animatedSelector.currentNodeID = action['animatedROIID']
    layout.addRow("Animated ROI", self.animatedSelector)

  def updateFromGUI(self, action):
    action['startROIID'] = self.startSelector.currentNodeID
    action['endROIID'] = self.endSelector.currentNodeID
    action['animatedROIID'] = self.animatedSelector.currentNodeID

class VolumePropertyAction(AnimatorAction):
  """Animate a volume rendering's color/opacity transfer functions
  through an ordered list of keyframes.

  Each keyframe is ``{'time': float in [0,1], 'volumePropertyID': str}``.
  ``time`` is the fractional position within the action's
  [startTime, endTime] window. The first keyframe is always at 0.0 and
  the last at 1.0; intermediate keyframes are user-added.

  Adjacent keyframe pairs are linearly interpolated. Their VolumeProperty
  nodes do NOT need to share the same number of control points -- the
  transfer functions are resampled onto the union of their x positions.
  """
  def __init__(self):
    super().__init__()
    self.name = "Volume Property"

  def _snapshotVP(self, sourceVP, actionId, fraction, label=None):
    from AnimatorLib.VolumePropertyKeyframes import (
      snapshot_volume_property, keyframe_node_name)
    return snapshot_volume_property(
      sourceVP, keyframe_node_name(actionId, fraction, label))

  def defaultAction(self):
    volumeRenderingNode = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    if volumeRenderingNode is None:
      logging.error("Can't add VolumePropertyAction, no volume rendering node in the scene")
      return None
    animatedVolumeProperty = volumeRenderingNode.GetVolumePropertyNode()

    actionId = 'volumeProperty1-' + str(self.uuid)
    startVP = self._snapshotVP(animatedVolumeProperty, actionId, 0.0, 'start')
    endVP = self._snapshotVP(animatedVolumeProperty, actionId, 1.0, 'end')

    volumePropertyAction = {
      'name': 'Volume Property',
      'class': 'VolumePropertyAction',
      'id': actionId,
      'startTime': 0,
      'endTime': -1,
      'interpolation': 'linear',
      'animatedVolumePropertyID': animatedVolumeProperty.GetID(),
      'keyframes': [
        {'time': 0.0, 'volumePropertyID': startVP.GetID()},
        {'time': 1.0, 'volumePropertyID': endVP.GetID()},
      ],
    }
    return(volumePropertyAction)

  def act(self, action, scriptTime):
    from AnimatorLib.VolumePropertyKeyframes import (
      migrate_legacy_action, find_bracket, interpolate_volume_properties)

    migrate_legacy_action(action)
    keyframes = action.get('keyframes', [])
    if len(keyframes) < 1:
      return

    animatedVolumeProperty = slicer.mrmlScene.GetNodeByID(action['animatedVolumePropertyID'])
    if animatedVolumeProperty is None:
      return

    duration = action['endTime'] - action['startTime']
    if duration <= 0:
      fraction = 0.0
    elif scriptTime <= action['startTime']:
      fraction = 0.0
    elif scriptTime >= action['endTime']:
      fraction = 1.0
    else:
      fraction = (scriptTime - action['startTime']) / duration

    kf_a, kf_b, local = find_bracket(keyframes, fraction)
    if kf_a is None:
      return
    vp_a = slicer.mrmlScene.GetNodeByID(kf_a['volumePropertyID'])
    vp_b = slicer.mrmlScene.GetNodeByID(kf_b['volumePropertyID'])
    if vp_a is None or vp_b is None:
      return
    interpolate_volume_properties(vp_a, vp_b, local, animatedVolumeProperty)

  def gui(self, action, layout):
    from AnimatorLib.VolumePropertyKeyframes import migrate_legacy_action
    super().gui(action, layout)

    migrate_legacy_action(action)
    self._editAction = action

    # Animated VolumeProperty (advanced, but kept visible)
    self.animatedSelector = slicer.qMRMLNodeComboBox()
    self.animatedSelector.nodeTypes = ["vtkMRMLVolumePropertyNode"]
    self.animatedSelector.addEnabled = True
    self.animatedSelector.renameEnabled = True
    self.animatedSelector.editEnabled = False
    self.animatedSelector.removeEnabled = False
    self.animatedSelector.noneEnabled = False
    self.animatedSelector.selectNodeUponCreation = True
    self.animatedSelector.showHidden = True
    self.animatedSelector.showChildNodeTypes = True
    self.animatedSelector.setMRMLScene(slicer.mrmlScene)
    self.animatedSelector.setToolTip(
      "Volume Property node that the animation drives. "
      "Usually the one currently used by Volume Rendering.")
    self.animatedSelector.currentNodeID = action['animatedVolumePropertyID']
    layout.addRow("Animated VolumeProperty", self.animatedSelector)

    # Helper text
    info = qt.QLabel(
      "Keyframes define what the volume looks like at moments along "
      "the action's timeline (0% = start, 100% = end). The animation "
      "smoothly interpolates between consecutive keyframes. Edit a "
      "keyframe's transfer functions with the pencil button next to "
      "its node selector.")
    info.setWordWrap(True)
    layout.addRow(info)

    # Keyframe table
    self.keyframeTable = qt.QTableWidget()
    self.keyframeTable.setColumnCount(3)
    self.keyframeTable.setHorizontalHeaderLabels(["Time (%)", "VolumeProperty", ""])
    self.keyframeTable.horizontalHeader().setStretchLastSection(False)
    self.keyframeTable.horizontalHeader().setSectionResizeMode(1, qt.QHeaderView.Stretch)
    self.keyframeTable.verticalHeader().visible = False
    self.keyframeTable.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
    self.keyframeTable.setSelectionMode(qt.QAbstractItemView.SingleSelection)
    self.keyframeTable.minimumHeight = 160
    self._populateKeyframeTable()
    layout.addRow(self.keyframeTable)

    # Add / replace controls
    addRow = qt.QHBoxLayout()
    self.newKeyframeTimeSpin = ctk.ctkDoubleSpinBox()
    self.newKeyframeTimeSpin.suffix = " %"
    self.newKeyframeTimeSpin.minimum = 0.1
    self.newKeyframeTimeSpin.maximum = 99.9
    self.newKeyframeTimeSpin.singleStep = 5.0
    self.newKeyframeTimeSpin.value = 50.0
    self.newKeyframeTimeSpin.decimals = 1
    addRow.addWidget(qt.QLabel("at"))
    addRow.addWidget(self.newKeyframeTimeSpin)

    self.addKeyframeButton = qt.QPushButton("Add keyframe (snapshot of animated VP)")
    self.addKeyframeButton.setToolTip(
      "Insert a new keyframe at the chosen time, snapshotting the current "
      "state of the Animated VolumeProperty.")
    self.addKeyframeButton.connect('clicked()', self._onAddKeyframeClicked)
    addRow.addWidget(self.addKeyframeButton)
    addRow.addStretch(1)
    layout.addRow(addRow)

    replaceRow = qt.QHBoxLayout()
    self.replaceKeyframeButton = qt.QPushButton("Replace selected from animated VP")
    self.replaceKeyframeButton.setToolTip(
      "Overwrite the selected keyframe's VolumeProperty with the current "
      "state of the Animated VolumeProperty. Use this after tweaking the "
      "animated VP in the Volume Rendering module.")
    self.replaceKeyframeButton.connect('clicked()', self._onReplaceSelectedClicked)
    replaceRow.addWidget(self.replaceKeyframeButton)

    self.deleteKeyframeButton = qt.QPushButton("Delete selected")
    self.deleteKeyframeButton.setToolTip(
      "Delete the selected keyframe (the 0% and 100% endpoints cannot be deleted).")
    self.deleteKeyframeButton.connect('clicked()', self._onDeleteSelectedClicked)
    replaceRow.addWidget(self.deleteKeyframeButton)
    replaceRow.addStretch(1)
    layout.addRow(replaceRow)

  def _populateKeyframeTable(self):
    keyframes = sorted(self._editAction.get('keyframes', []), key=lambda k: k['time'])
    self._editAction['keyframes'] = keyframes
    self.keyframeTable.setRowCount(len(keyframes))
    for row, kf in enumerate(keyframes):
      # Time column
      timeItem = qt.QTableWidgetItem(f"{kf['time'] * 100:.1f}")
      timeItem.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable)
      self.keyframeTable.setItem(row, 0, timeItem)
      # Volume property selector (lets user pick a different VP node and edit it)
      vpSelector = slicer.qMRMLNodeComboBox()
      vpSelector.nodeTypes = ["vtkMRMLVolumePropertyNode"]
      vpSelector.addEnabled = False
      vpSelector.renameEnabled = True
      vpSelector.editEnabled = True
      vpSelector.removeEnabled = False
      vpSelector.noneEnabled = False
      vpSelector.showHidden = True
      vpSelector.showChildNodeTypes = True
      vpSelector.setMRMLScene(slicer.mrmlScene)
      vpSelector.currentNodeID = kf['volumePropertyID']
      vpSelector.connect(
        'currentNodeChanged(vtkMRMLNode*)',
        lambda node, r=row: self._onKeyframeVPChanged(r, node))
      self.keyframeTable.setCellWidget(row, 1, vpSelector)
      # Tag column to indicate endpoints
      tag = ""
      if abs(kf['time']) < 1e-6:
        tag = "start"
      elif abs(kf['time'] - 1.0) < 1e-6:
        tag = "end"
      tagItem = qt.QTableWidgetItem(tag)
      tagItem.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable)
      self.keyframeTable.setItem(row, 2, tagItem)
    self.keyframeTable.resizeColumnsToContents()
    self.keyframeTable.horizontalHeader().setSectionResizeMode(1, qt.QHeaderView.Stretch)

  def _onKeyframeVPChanged(self, row, node):
    keyframes = self._editAction['keyframes']
    if 0 <= row < len(keyframes) and node is not None:
      keyframes[row]['volumePropertyID'] = node.GetID()

  def _onAddKeyframeClicked(self):
    fraction = self.newKeyframeTimeSpin.value / 100.0
    keyframes = self._editAction['keyframes']
    # Collision check
    for kf in keyframes:
      if abs(kf['time'] - fraction) < 0.005:
        slicer.util.messageBox(
          f"A keyframe already exists at {fraction * 100:.1f}%. "
          "Pick a different time.")
        return
    animatedVPID = (self.animatedSelector.currentNodeID
                    or self._editAction.get('animatedVolumePropertyID'))
    animatedVP = slicer.mrmlScene.GetNodeByID(animatedVPID) if animatedVPID else None
    if animatedVP is None:
      slicer.util.messageBox("No Animated VolumeProperty selected to snapshot.")
      return
    newVP = self._snapshotVP(animatedVP, self._editAction['id'], fraction)
    keyframes.append({'time': fraction, 'volumePropertyID': newVP.GetID()})
    self._populateKeyframeTable()

  def _onReplaceSelectedClicked(self):
    row = self.keyframeTable.currentRow
    keyframes = self._editAction['keyframes']
    if not (0 <= row < len(keyframes)):
      slicer.util.messageBox("Select a keyframe row first.")
      return
    animatedVPID = (self.animatedSelector.currentNodeID
                    or self._editAction.get('animatedVolumePropertyID'))
    animatedVP = slicer.mrmlScene.GetNodeByID(animatedVPID) if animatedVPID else None
    if animatedVP is None:
      slicer.util.messageBox("No Animated VolumeProperty selected to snapshot.")
      return
    kfVP = slicer.mrmlScene.GetNodeByID(keyframes[row]['volumePropertyID'])
    if kfVP is None:
      slicer.util.messageBox("Keyframe's VolumeProperty node is missing.")
      return
    kfVP.CopyParameterSet(animatedVP)

  def _onDeleteSelectedClicked(self):
    row = self.keyframeTable.currentRow
    keyframes = self._editAction['keyframes']
    if not (0 <= row < len(keyframes)):
      slicer.util.messageBox("Select a keyframe row first.")
      return
    t = keyframes[row]['time']
    if abs(t) < 1e-6 or abs(t - 1.0) < 1e-6:
      slicer.util.messageBox("The 0% and 100% endpoint keyframes cannot be deleted.")
      return
    del keyframes[row]
    self._populateKeyframeTable()

  def updateFromGUI(self, action):
    action['animatedVolumePropertyID'] = self.animatedSelector.currentNodeID
    action['keyframes'] = sorted(self._editAction['keyframes'], key=lambda k: k['time'])
    # Drop the legacy fields if anything still has them.
    for legacy in ('startVolumePropertyID', 'endVolumePropertyID',
                   'clampAtStart', 'clampAtEnd'):
      action.pop(legacy, None)

class ExplodeModelsAction(AnimatorAction):
  """Explodes a model hierarchy in a selected subject hierarchy tree branch"""

  # Cache stores information that needs to be extracted from the scene once
  # (list of nodes, positions, etc.)
  # The cache stores information for all the actions, identified by
  # the action's id.
  cache = {}

  def __init__(self):
    super().__init__()
    self.name = "Explode models"

  def cleanup(self, action):
    if action['id'] in ExplodeModelsAction.cache:
      del(ExplodeModelsAction.cache[action['id']])

    if ExplodeModelsAction.cache:
      # there are still explode model actions, no more cleanup is needed
      return

    # No more explode models action are in the scene - remove all automatically added transforms.
    # We only remove transforms when all the ExplodeModel actions are deleted because the transforms
    # may be shared between multiple actions.

    # Collect all transforms and transformed nodes first. Changing the parent transforms would change the list
    # of references, so first we collect all information then make all the changes.
    numberOfNodeReferences = slicer.mrmlScene.GetNumberOfNodeReferences()
    transformNodesToRemove = set()
    transformsToSet = []  # list of pairs of transformed nodes and the new transform to observe
    for nodeReferenceIndex in range(numberOfNodeReferences):
      transformNode = slicer.mrmlScene.GetNodeByID(slicer.mrmlScene.GetNthReferencedID(nodeReferenceIndex))
      if transformNode and transformNode.GetAttribute("Animator.ExplodeModels.AutoCreated"):
        transformNodesToRemove.add(transformNode)
        transformsToSet.append([slicer.mrmlScene.GetNthReferencingNode(nodeReferenceIndex), transformNode.GetParentTransformNode()])

    # restore original parent transforms
    for transformedNode, transformNode in transformsToSet:
      transformedNode.SetAndObserveTransformNodeID(transformNode.GetID() if transformNode else None)

    # remove unused transforms
    for transformNode in transformNodesToRemove:
      slicer.mrmlScene.RemoveNode(transformNode)

  def allowMultiple(self):
    return True

  def defaultAction(self):
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    action = {
      'name': 'ExplodeModels',
      'class': 'ExplodeModelsAction',
      'id': 'explodeModels-'+str(self.uuid),
      'startTime': 0,
      'endTime': -1,
      'subjectHierarchyFolderID': shNode.GetSceneItemID(),
      'explosionCenterFiducialNodeID': '',
      'explosionScaleFactor': 2.0,
      'explodedViewDurationPercent': 10,
      }
    return action

  def act(self, action, scriptTime):

    if action['endTime'] <= action['startTime']:
      return

    if action['id'] not in ExplodeModelsAction.cache:
      self.updateCache(action)
    cache = ExplodeModelsAction.cache[action['id']]

    normalizedActionTime = (scriptTime - action['startTime'])/(action['endTime']-action['startTime'])
    if normalizedActionTime < 0.0 or normalizedActionTime > 1.0:
      return

    explodedViewDurationPercent = action['explodedViewDurationPercent']
    explosionDistanceScale = action['explosionScaleFactor']
    modelsCenterOfGravity = cache['modelsCenterOfGravity']
    modelNodes = cache['modelNodes']
    transformNodes = cache['transformNodes']
    modelPositions = cache['modelPositions']

    centerFiducialNode = slicer.mrmlScene.GetNodeByID(action['explosionCenterFiducialNodeID'])
    if centerFiducialNode and centerFiducialNode.GetNumberOfDefinedControlPoints()>0:
      explosionCenter = [0,0,0]
      centerFiducialNode.GetNthControlPointPositionWorld(0, explosionCenter)
    else:
      explosionCenter = cache['modelsCenterOfGravity']

    animationDuration = (1.0-explodedViewDurationPercent/100.0)/2.0
    if normalizedActionTime < animationDuration:
      # expansion animation
      scaleFactor = cache['expandScaleFactors'](normalizedActionTime/animationDuration)
    elif normalizedActionTime > 1.0-animationDuration:
      # contraction animation
      scaleFactor = cache['contractScaleFactors']((normalizedActionTime-1.0+animationDuration)/animationDuration)
    else:
      # in the middle, hold exploded view
      scaleFactor = 1.0

    for modelNode, transformNode, modelPosition in zip(modelNodes, transformNodes, modelPositions):
        offset = explosionDistanceScale * scaleFactor * (modelPosition-explosionCenter)
        transformMatrix = vtk.vtkMatrix4x4()
        for i in range(3):
            transformMatrix.SetElement(i, 3, offset[i])
        transformNode.SetMatrixTransformToParent(transformMatrix)

  def gui(self, action, layout):
    super().gui(action, layout)

    self.shFolderSelector = slicer.qMRMLSubjectHierarchyComboBox()
    self.shFolderSelector.setMRMLScene( slicer.mrmlScene )
    self.shFolderSelector.setToolTip("Pick the folder that contains all the model nodes")
    self.shFolderSelector.setCurrentItem(action['subjectHierarchyFolderID'])
    self.shFolderSelector.minimumWidth=200
    layout.addRow("Models folder", self.shFolderSelector)

    self.explosionScaleFactor = ctk.ctkDoubleSpinBox()
    self.explosionScaleFactor.suffix = "x"
    self.explosionScaleFactor.decimals = 1
    self.explosionScaleFactor.minimum = 1
    self.explosionScaleFactor.maximum = 10
    self.explosionScaleFactor.value = action['explosionScaleFactor']
    layout.addRow("Explosion scale factor", self.explosionScaleFactor)

    self.explodedViewDurationPercent = ctk.ctkDoubleSpinBox()
    self.explodedViewDurationPercent.suffix = "%"
    self.explodedViewDurationPercent.decimals = 0
    self.explodedViewDurationPercent.minimum = 0
    self.explodedViewDurationPercent.maximum = 100
    self.explodedViewDurationPercent.value = action['explodedViewDurationPercent']
    layout.addRow("Exploded view duration", self.explodedViewDurationPercent)

    self.centerFiducialSelector = slicer.qMRMLNodeComboBox()
    self.centerFiducialSelector.nodeTypes = ["vtkMRMLMarkupsFiducialNode"]
    self.centerFiducialSelector.addEnabled = False
    self.centerFiducialSelector.renameEnabled = False
    self.centerFiducialSelector.removeEnabled = False
    self.centerFiducialSelector.noneEnabled = True
    self.centerFiducialSelector.noneDisplay = "auto"
    self.centerFiducialSelector.selectNodeUponCreation = True
    self.centerFiducialSelector.setMRMLScene( slicer.mrmlScene )
    self.centerFiducialSelector.setToolTip( "Models will be moved away from this position." )
    self.centerFiducialSelector.currentNodeID = action['explosionCenterFiducialNodeID']
    layout.addRow("Epicenter of explosion", self.centerFiducialSelector)

  def updateFromGUI(self, action):
    action['subjectHierarchyFolderID'] = self.shFolderSelector.currentItem()
    action['explosionScaleFactor'] = self.explosionScaleFactor.value
    action['explodedViewDurationPercent'] = self.explodedViewDurationPercent.value
    action['explosionCenterFiducialNodeID'] = self.centerFiducialSelector.currentNodeID
    self.updateCache(action)

  def updateCache(self, action):
    try:
      import easing_functions
    except ModuleNotFoundError as e:
      if slicer.util.confirmOkCancelDisplay(
              "This module requires 'easing-functions' Python package. Click OK to install it now."):
        slicer.util.pip_install("easing-functions")
        import easing_functions
      else:
        return

    # Insert transform node above the model so that we can move it
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    modelNodesCollection = vtk.vtkCollection()
    shNode.GetDataNodesInBranch(action['subjectHierarchyFolderID'], modelNodesCollection, "vtkMRMLModelNode")
    modelNodes = []
    transformNodes = []
    for i in range(modelNodesCollection.GetNumberOfItems()):
      modelNode = modelNodesCollection.GetItemAsObject(i)
      modelNodes.append(modelNode)
      transformNode = modelNode.GetParentTransformNode()
      if not transformNode or not transformNode.GetAttribute("Animator.ExplodeModels.AutoCreated"):
        transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode")
        transformNode.SetAttribute("Animator.ExplodeModels.AutoCreated", "1")
        oldParentTransformNode = modelNode.GetParentTransformNode()
        modelNode.SetAndObserveTransformNodeID(transformNode.GetID())
        if oldParentTransformNode:
          transformNode.SetAndObserveTransformNodeID(oldParentTransformNode.GetID())
      transformNodes.append(transformNode)
      transformNode.SetAndObserveMatrixTransformToParent(vtk.vtkMatrix4x4())

    import numpy as np
    modelPositions = []
    for modelNode in modelNodes:
        bounds = np.zeros(6)
        modelNode.GetRASBounds(bounds)
        modelPositions.append(np.array([(bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0]))

    modelsCenterOfGravity = np.mean(np.array(modelPositions), axis=0)

    import easing_functions
    expandScaleFactors = easing_functions.CircularEaseInOut(start=0, end=1, duration=1.0)
    contractScaleFactors = easing_functions.CircularEaseInOut(start=1, end=0, duration=1.0)

    cache = {
      'modelNodes': modelNodes,
      'transformNodes': transformNodes,
      'modelPositions': modelPositions,
      'modelsCenterOfGravity': modelsCenterOfGravity,
      'expandScaleFactors': expandScaleFactors,
      'contractScaleFactors': contractScaleFactors,
      }

    ExplodeModelsAction.cache[action['id']] = cache


class SceneSnapshotAction(AnimatorAction):
  """Snapshot-based animation: capture the current camera (and optionally
  Volume Property) state at moments along the timeline; the action
  interpolates linearly between consecutive snapshots.

  Each keyframe stores absolute master-time seconds (not a fraction),
  so the action's startTime/endTime are derived from min/max keyframe
  time. Per-segment behavior is selectable: ``interpolate`` (default)
  or ``hold``.
  """
  def __init__(self):
    super().__init__()
    self.name = "Scene Snapshot"

  def defaultAction(self):
    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0) if layoutManager else None
    threeDView = threeDWidget.threeDView() if threeDWidget else None
    cameraNode = threeDView.cameraNode() if threeDView else None
    if cameraNode is None:
      logging.error("SceneSnapshotAction: no 3D view / camera available")
      return None

    # Optional VP target if there's a volume rendering in the scene.
    animatedVolumePropertyID = None
    volumeRenderingNode = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    if volumeRenderingNode is not None:
      vp = volumeRenderingNode.GetVolumePropertyNode()
      if vp is not None:
        animatedVolumePropertyID = vp.GetID()

    actionId = 'sceneSnapshot-' + str(self.uuid)

    from AnimatorLib.SceneSnapshot import (
      capture_current_scene, capture_thumbnail)
    first_kf = capture_current_scene(
      animated_camera_id=cameraNode.GetID(),
      animated_vp_id=animatedVolumePropertyID,
      action_id=actionId,
      time_seconds=0.0,
      label="Snapshot 1",
    )
    first_kf['thumbnailPath'] = capture_thumbnail(threeDView, first_kf['id'])

    return {
      'name': 'Scene Snapshot',
      'class': 'SceneSnapshotAction',
      'id': actionId,
      'startTime': 0,
      'endTime': 0,
      'interpolation': 'linear',
      'animatedCameraID': cameraNode.GetID(),
      'animatedVolumePropertyID': animatedVolumePropertyID,
      'keyframes': [first_kf],
    }

  def act(self, action, scriptTime):
    from AnimatorLib.SceneSnapshot import evaluate_at, apply_camera_state
    cam_state = evaluate_at(action, float(scriptTime))
    if cam_state is None:
      return
    cam_id = action.get('animatedCameraID')
    if not cam_id:
      return
    cam_node = slicer.mrmlScene.GetNodeByID(cam_id)
    if cam_node is None:
      return
    apply_camera_state(cam_node, cam_state)

  def cleanup(self, action):
    """Remove the snapshot VP nodes we created so the scene doesn't leak."""
    for kf in action.get('keyframes', []):
      vp_id = kf.get('volumePropertyID')
      if vp_id:
        node = slicer.mrmlScene.GetNodeByID(vp_id)
        if node is not None:
          slicer.mrmlScene.RemoveNode(node)

  def wantsNonModalEditor(self):
    # Snapshot timeline is built around capturing the current 3D view,
    # so the editor must not block interaction with the 3D view.
    return True

  def gui(self, action, layout):
    super().gui(action, layout)

    # Camera + VP selectors (advanced; usually defaults are fine)
    self.cameraSelector = slicer.qMRMLNodeComboBox()
    self.cameraSelector.nodeTypes = ["vtkMRMLCameraNode"]
    self.cameraSelector.addEnabled = False
    self.cameraSelector.removeEnabled = False
    self.cameraSelector.noneEnabled = False
    self.cameraSelector.showHidden = True
    self.cameraSelector.showChildNodeTypes = True
    self.cameraSelector.setMRMLScene(slicer.mrmlScene)
    self.cameraSelector.currentNodeID = action.get('animatedCameraID', '')
    self.cameraSelector.setToolTip(
      "Camera that the snapshot timeline drives.")
    layout.addRow("Animated camera", self.cameraSelector)

    self.vpSelector = slicer.qMRMLNodeComboBox()
    self.vpSelector.nodeTypes = ["vtkMRMLVolumePropertyNode"]
    self.vpSelector.addEnabled = False
    self.vpSelector.removeEnabled = False
    self.vpSelector.noneEnabled = True
    self.vpSelector.showHidden = True
    self.vpSelector.showChildNodeTypes = True
    self.vpSelector.setMRMLScene(slicer.mrmlScene)
    self.vpSelector.currentNodeID = action.get('animatedVolumePropertyID') or ''
    self.vpSelector.setToolTip(
      "Optional: Volume Property node that the snapshot also tweens. "
      "Leave empty for camera-only animation.")
    layout.addRow("Animated VolumeProperty", self.vpSelector)

    info = qt.QLabel(
      "<b>How to use:</b>"
      "<ol style='margin-left:-20px;'>"
      "<li>Adjust the 3D view (rotate / zoom / change colors) until it "
      "looks like the moment you want.</li>"
      "<li>Click <i>Capture current state</i> &rarr; a tile is added "
      "1&nbsp;second after the previous one.</li>"
      "<li>Repeat for as many key moments as you want.</li>"
      "<li>Click <i>Play preview</i> below to see the animation, or drag "
      "the time slider to scrub. Use <i>Restore live</i> to put the 3D "
      "view back where it was before scrubbing.</li>"
      "</ol>"
      "When you close this window, the animation timeline at the top of "
      "the Animator panel will cover the full snapshot range and you "
      "can export to video.")
    info.setWordWrap(True)
    info.setTextFormat(qt.Qt.RichText)
    layout.addRow(info)

    # The actual timeline editor
    layoutManager = slicer.app.layoutManager()
    threeDView = layoutManager.threeDWidget(0).threeDView() if layoutManager else None
    from AnimatorLib.SnapshotTimelineWidget import SnapshotTimelineWidget
    # When the editor is opened non-modal, AnimatorActionsGUI will set
    # self.onChanged to a callback that persists the action to the
    # animation node after every edit.
    persistCallback = getattr(self, 'onChanged', lambda: None)
    self._timelineWidget = SnapshotTimelineWidget(
      action=action,
      threeDView=threeDView,
      onChanged=persistCallback,
    )
    layout.addRow(self._timelineWidget)

  def updateFromGUI(self, action):
    if hasattr(self, 'cameraSelector') and self.cameraSelector.currentNodeID:
      action['animatedCameraID'] = self.cameraSelector.currentNodeID
    if hasattr(self, 'vpSelector'):
      action['animatedVolumePropertyID'] = self.vpSelector.currentNodeID or None
    # Sync action time range to keyframe span
    kfs = action.get('keyframes', [])
    if kfs:
      times = [kf['time'] for kf in kfs]
      action['startTime'] = min(times)
      action['endTime'] = max(times)

# add an module-specific dict for any module other to add animator plugins.
# these must be subclasses (or duck types) of the
# AnimatorAction class below.  Dict keys are action types
# and values are classes
try:
  slicer.modules.animatorActionPlugins
except AttributeError:
  slicer.modules.animatorActionPlugins = {}
slicer.modules.animatorActionPlugins['CameraRotationAction'] = CameraRotationAction
slicer.modules.animatorActionPlugins['ROIAction'] = ROIAction
slicer.modules.animatorActionPlugins['VolumePropertyAction'] = VolumePropertyAction
slicer.modules.animatorActionPlugins['ExplodeModelsAction'] = ExplodeModelsAction
slicer.modules.animatorActionPlugins['SceneSnapshotAction'] = SceneSnapshotAction


#
# Animator
#

class Animator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Animator"
    self.parent.categories = ["SlicerMorph.Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"]
    self.parent.helpText = """
A high-level animation interface that operates on top of the Sequences and Screen Capture interfaces.
    <p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/Animator">online documentation</a>.</p>

"""
    self.parent.acknowledgementText = """
This module was developed by Steve Pieper for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.


#
# AnimatorWidget
#

class AnimatorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    super().__init__(parent)
    self.defaultFileFormat = "mp4 (H264)"

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # tracks the modified event observer on the currently
    # selected sequence browser node
    self.sequenceBrowserObserverRecord = None

    self.animatorActionsGUI = None

    self.logic = AnimatorLogic()

    # Try to import the shared viewer-size controller from HiResScreenCapture.
    # Animator's export pipeline depends on this helper to undock the 3D
    # viewer and snap to a codec-friendly size before recording.
    try:
      from HiResScreenCaptureLib.SlicerMorphViewerSize import ViewerSizeController, snap_to_codec_size
      self._ViewerSizeController = ViewerSizeController
      self._snap_to_codec_size = snap_to_codec_size
    except ImportError as e:
      logging.error(
        "Animator: failed to import HiResScreenCaptureLib.SlicerMorphViewerSize from HiResScreenCapture: %s. "
        "Make sure the HiResScreenCapture module is installed and enabled.", e)
      self._ViewerSizeController = None
      self._snap_to_codec_size = None

    # Instantiate and connect widgets ...

    #
    # Output Viewer Setup (must happen BEFORE the user composes the animation
    # so that the on-screen 3D viewer matches the final MP4 dimensions)
    #
    viewerSetupCollapsibleButton = ctk.ctkCollapsibleButton()
    viewerSetupCollapsibleButton.text = "Output Viewer Setup"
    self.layout.addWidget(viewerSetupCollapsibleButton)
    viewerSetupFormLayout = qt.QFormLayout(viewerSetupCollapsibleButton)

    instructionsLabel = qt.QLabel(
      "<i>Step 1:</i> Undock the 3D viewer and arrange your scene at the desired "
      "aspect ratio.<br>"
      "<i>Step 2:</i> Click <b>Snap to codec-safe size</b> to lock the viewer to "
      "dimensions that H.264 can encode without padding.<br>"
      "<i>Step 3:</i> Build your animation below; what you see is what gets "
      "recorded.")
    instructionsLabel.setWordWrap(True)
    viewerSetupFormLayout.addRow(instructionsLabel)

    if self._ViewerSizeController is not None:
      self.viewerSizeController = self._ViewerSizeController()
      viewerSetupFormLayout.addRow(self.viewerSizeController)
      self.viewerSizeController.sizeChanged.connect(self._onViewerSizeChanged)
      self.viewerSizeController.lockChanged.connect(self._onViewerLockChanged)
      self.viewerSizeController.undockChanged.connect(self._onViewerUndockChanged)
    else:
      self.viewerSizeController = None
      viewerSetupFormLayout.addRow(qt.QLabel(
        "<b>Error:</b> HiResScreenCapture module is required for viewer size control."))

    self.snapButton = qt.QPushButton("Snap to codec-safe size")
    self.snapButton.toolTip = (
      "Round the current viewer width and height to the nearest multiple of 16 "
      "(preserving aspect ratio) and lock the viewer to that size. H.264 encodes "
      "best at multiples of 16; otherwise ffmpeg will pad or duplicate columns.")
    self.snapButton.enabled = False
    self.snapButton.clicked.connect(self.onSnapToCodecSize)
    viewerSetupFormLayout.addRow("", self.snapButton)

    self.lockedSizeLabel = qt.QLabel("Output size: <i>not locked</i>")
    viewerSetupFormLayout.addRow(self.lockedSizeLabel)

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Animation Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    self.durationBox = ctk.ctkDoubleSpinBox()
    self.durationBox.suffix = " seconds"
    self.durationBox.decimals = 1
    self.durationBox.minimum = 1
    self.durationBox.value = 5
    self.durationBox.toolTip = "Duration cannot be changed after animation created"
    parametersFormLayout.addRow("New animation duration", self.durationBox)

    #
    # animation selector
    #
    self.animationSelector = slicer.qMRMLNodeComboBox()
    self.animationSelector.nodeTypes = ["vtkMRMLScriptedModuleNode"]
    self.animationSelector.setNodeTypeLabel("Animation", "vtkMRMLScriptedModuleNode")
    self.animationSelector.selectNodeUponCreation = True
    self.animationSelector.addEnabled = True
    self.animationSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", "Animation")
    self.animationSelector.baseName = "Animation"
    self.animationSelector.removeEnabled = True
    self.animationSelector.noneEnabled = True
    self.animationSelector.showHidden = True
    self.animationSelector.showChildNodeTypes = False
    self.animationSelector.setMRMLScene( slicer.mrmlScene )
    self.animationSelector.setToolTip( "Pick the animation description." )
    parametersFormLayout.addRow("Animation Node: ", self.animationSelector)

    self.sequencePlay = slicer.qMRMLSequenceBrowserPlayWidget()
    self.sequencePlay.setMRMLScene(slicer.mrmlScene)
    self.sequenceSeek = slicer.qMRMLSequenceBrowserSeekWidget()
    self.sequenceSeek.setMRMLScene(slicer.mrmlScene)

    parametersFormLayout.addRow(self.sequencePlay)
    parametersFormLayout.addRow(self.sequenceSeek)

    self.actionsMenuButton = qt.QPushButton("Add Action")
    self.actionsMenuButton.enabled = False
    self.actionsMenu = qt.QMenu()
    self.actionsMenuButton.setMenu(self.actionsMenu)
    for actionName in slicer.modules.animatorActionPlugins.keys():
      qAction = qt.QAction(actionName, self.actionsMenu)
      qAction.connect('triggered()', lambda actionName=actionName: self.onAddAction(actionName))
      self.actionsMenu.addAction(qAction)
    parametersFormLayout.addWidget(self.actionsMenuButton)

    #
    # Actions Area
    #
    self.actionsCollapsibleButton = ctk.ctkCollapsibleButton()
    self.actionsCollapsibleButton.text = "Actions"
    self.layout.addWidget(self.actionsCollapsibleButton)

    # Layout within the dummy collapsible button
    self.actionsFormLayout = qt.QFormLayout(self.actionsCollapsibleButton)

    #
    # Export Area
    #
    self.exportCollapsibleButton = ctk.ctkCollapsibleButton()
    self.exportCollapsibleButton.text = "Export"
    self.layout.addWidget(self.exportCollapsibleButton)
    self.exportCollapsibleButton.enabled = False
    self.exportFormLayout = qt.QFormLayout(self.exportCollapsibleButton)

    self.exportSizeLabel = qt.QLabel("Animation size: <i>lock viewer above first</i>")
    self.exportFormLayout.addRow(self.exportSizeLabel)

    from ScreenCapture import ScreenCaptureLogic
    logic = ScreenCaptureLogic()
    self.videoFormatWidget = qt.QComboBox()
    self.videoFormatWidget.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Preferred)
    for videoFormatPreset in logic.videoFormatPresets:
      self.videoFormatWidget.addItem(videoFormatPreset["name"])
    self.exportFormLayout.addRow("Video format:", self.videoFormatWidget)

    self.outputFileButton = qt.QPushButton("Select a file...")
    self.exportFormLayout.addRow("Output file", self.outputFileButton)

    self.exportButton = qt.QPushButton("Export")
    self.exportButton.enabled = False
    self.exportFormLayout.addRow("", self.exportButton)

    # connections
    self.animationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.outputFileButton.connect("clicked()", self.selectExportFile)
    self.exportButton.connect("clicked()", self.onExport)

    # Add vertical spacer
    self.layout.addStretch(1)

  def removeSequenceBrowserObserver(self):
    if self.sequenceBrowserObserverRecord:
      object,tag = self.sequenceBrowserObserverRecord
      object.RemoveObserver(tag)
    self.sequenceBrowserObserverRecord = None

  def cleanup(self):
    self.removeSequenceBrowserObserver()
    if getattr(self, "viewerSizeController", None) is not None:
      self.viewerSizeController.cleanup()

  def onSelect(self):
    sequenceBrowserNode = None
    sequenceNode = None

    if self.animatorActionsGUI:
      self.animatorActionsGUI.destroyGUI()
    layout = self.actionsFormLayout
    for item in range(layout.count()):
      layout.takeAt(0)

    animationNode = self.animationSelector.currentNode()
    if animationNode:
      sequenceBrowserNodeID = animationNode.GetAttribute('Animator.sequenceBrowserNodeID')
      if sequenceBrowserNodeID is None:
        self.logic.initializeAnimationNode(animationNode, self.durationBox.value)
        sequenceBrowserNodeID = animationNode.GetAttribute('Animator.sequenceBrowserNodeID')
      sequenceBrowserNode = slicer.mrmlScene.GetNodeByID(sequenceBrowserNodeID)
      sequenceNodeID = animationNode.GetAttribute('Animator.sequenceNodeID')
      sequenceNode = slicer.mrmlScene.GetNodeByID(sequenceNodeID)
      self.removeSequenceBrowserObserver()

      def onBrowserModified(caller, event):
        index = sequenceBrowserNode.GetSelectedItemNumber()
        scriptTime = float(sequenceNode.GetNthIndexValue(index))
        self.logic.act(animationNode, scriptTime)
      tag = sequenceBrowserNode.AddObserver(vtk.vtkCommand.ModifiedEvent, onBrowserModified)
      self.sequenceBrowserObserverRecord = (sequenceBrowserNode, tag)

      self.animatorActionsGUI = AnimatorActionsGUI(animationNode, deleteCallback=self.onSelect)
      self.actionsFormLayout.addRow(self.animatorActionsGUI.buildGUI())

    self.actionsMenuButton.enabled = animationNode != None
    self.exportCollapsibleButton.enabled = animationNode != None
    self.sequencePlay.setMRMLSequenceBrowserNode(sequenceBrowserNode)
    self.sequenceSeek.setMRMLSequenceBrowserNode(sequenceBrowserNode)

  def onAddAction(self, actionName):
    animationNode = self.animationSelector.currentNode()
    if animationNode:
      script = self.logic.getScript(animationNode)
      actionInstance = slicer.modules.animatorActionPlugins[actionName]()
      action = actionInstance.defaultAction()
      if action:
        if not actionInstance.allowMultiple() and "actions" in script:
          for actionKey in script['actions'].keys():
            if script['actions'][actionKey]['class'] == action['class']:
              slicer.util.messageBox(f"Sorry, only {action['class']} per animation is supported")
              return

        actionsByClass = self.logic.getActionsByClass(animationNode)
        if action['class'] in actionsByClass.keys():
          classActions = actionsByClass[action['class']]
          lastAction = classActions[0]
          latestEndTime = lastAction['endTime']
          for classAction in classActions:
            if classAction['endTime'] > latestEndTime:
              lastAction = classAction
              latestEndTime = lastAction['endTime']
          midTime = lastAction['startTime'] + 0.5 * (lastAction['endTime'] - lastAction['startTime'])
          action['startTime'] = midTime
          action['endTime'] = lastAction['endTime']
          script['actions'][lastAction['id']]['endTime'] = midTime
          self.logic.setScript(animationNode, script)
        else:
          action['startTime'] = 0
          action['endTime'] = script['duration']
        self.logic.addAction(animationNode, action)
        self.onSelect()
      else:
        slicer.util.messageBox("Could not add action. See error log.")

  def selectExportFile(self):
    self.outputFileButton.text = qt.QFileDialog.getSaveFileName(
            slicer.util.mainWindow(),
            "Animation file",
            "Animation",
            "")
    self._refreshExportButtonState()

  def _refreshExportButtonState(self):
    """Enable Export only when an output file is set AND the viewer is locked."""
    locked = (self.viewerSizeController is not None
              and self.viewerSizeController.lockedSize() is not None)
    has_path = bool(self.outputFileButton.text) and self.outputFileButton.text != "Select a file..."
    self.exportButton.enabled = locked and has_path

  def _onViewerSizeChanged(self, width, height):
    """Enable the Snap button whenever we know a valid current size and the
    viewer is undocked but not yet locked."""
    if self.viewerSizeController is None:
      return
    self.snapButton.enabled = (
      self.viewerSizeController.isUndocked()
      and not self.viewerSizeController.isLocked()
      and width > 0 and height > 0)

  def _onViewerUndockChanged(self, undocked):
    if self.viewerSizeController is None:
      return
    if not undocked:
      # Re-docking releases the lock and disables export.
      self.snapButton.enabled = False
      self.lockedSizeLabel.text = "Output size: <i>not locked</i>"
      self.exportSizeLabel.text = "Animation size: <i>lock viewer above first</i>"
      self._refreshExportButtonState()
    else:
      w, h = self.viewerSizeController.currentSize()
      self.snapButton.enabled = (w > 0 and h > 0
                                 and not self.viewerSizeController.isLocked())

  def _onViewerLockChanged(self, locked, width, height):
    if locked:
      self.snapButton.enabled = False
      self.lockedSizeLabel.text = (
        f"Output size: <b>{width} \u00d7 {height}</b> (locked)")
      self.exportSizeLabel.text = (
        f"Animation size: <b>{width} \u00d7 {height}</b>")
    else:
      self.snapButton.enabled = (
        self.viewerSizeController is not None
        and self.viewerSizeController.isUndocked())
      self.lockedSizeLabel.text = "Output size: <i>not locked</i>"
      self.exportSizeLabel.text = "Animation size: <i>lock viewer above first</i>"
    self._refreshExportButtonState()

  def onSnapToCodecSize(self):
    """Compute the codec-friendly size, ask the user to confirm, then lock."""
    if self.viewerSizeController is None or self._snap_to_codec_size is None:
      return
    if not self.viewerSizeController.isUndocked():
      slicer.util.messageBox("Please undock the 3D viewer first.")
      return
    cur_w, cur_h = self.viewerSizeController.currentSize()
    if not cur_w or not cur_h:
      slicer.util.messageBox("Could not read the current viewer size.")
      return
    snap_w, snap_h, drift = self._snap_to_codec_size(cur_w, cur_h, multiple=16)
    cur_aspect = cur_w / float(cur_h)
    snap_aspect = snap_w / float(snap_h)
    msg = (
      f"Current viewer:  {cur_w} \u00d7 {cur_h}  (aspect {cur_aspect:.3f})\n"
      f"Codec-safe size: {snap_w} \u00d7 {snap_h}  (aspect {snap_aspect:.3f})\n"
      f"Aspect drift:    {drift:.2f}%\n\n"
      f"Lock the viewer to {snap_w} \u00d7 {snap_h}?")
    result = qt.QMessageBox.question(
      slicer.util.mainWindow(),
      "Snap to codec-safe size",
      msg,
      qt.QMessageBox.Yes | qt.QMessageBox.No)
    if result == qt.QMessageBox.Yes:
      self.viewerSizeController.pinSize(snap_w, snap_h)

  def onExport(self):
    if self.viewerSizeController is None:
      slicer.util.errorDisplay(
        "HiResScreenCapture module is required for Animator export.")
      return
    locked = self.viewerSizeController.lockedSize()
    if not locked:
      slicer.util.messageBox(
        "Please lock the 3D viewer to a codec-safe size before exporting.")
      return
    threeDWidget = self.viewerSizeController.threeDWidget()
    if threeDWidget is None:
      slicer.util.messageBox(
        "The 3D viewer is no longer undocked. Please undock and lock again.")
      return

    # Pre-flight: ffmpeg must be installed and configured. Otherwise the
    # whole frame-capture pass runs for nothing and createVideo dies.
    from ScreenCapture import ScreenCaptureLogic
    logic = ScreenCaptureLogic()
    if not logic.isFfmpegPathValid():
      configured_path = logic.getFfmpegPath() or "<not set>"
      slicer.util.errorDisplay(
        "Animator export requires ffmpeg, which is not installed or not "
        "configured in Slicer.\n\n"
        f"Slicer is currently looking for ffmpeg at:\n    {configured_path}\n\n"
        "Please install ffmpeg and set its path in the Screen Capture "
        "module (then click outside the field or press Tab to make sure the "
        "value is saved). See:\n"
        "https://slicer.readthedocs.io/en/latest/user_guide/modules/"
        "screencapture.html#setting-up-ffmpeg\n\n"
        "Then re-run Animator export.")
      # Jump to the Screen Capture module so the user can set the path.
      try:
        slicer.util.selectModule('ScreenCapture')
      except Exception:
        pass
      return

    # Hide the 3D controller bar so it doesn't appear in the recording, and
    # confirm the widget is at the locked dimensions.
    width, height = locked
    threeDWidget.threeDController().visible = False
    threeDWidget.resize(qt.QSize(width, height))
    slicer.app.processEvents()

    try:
      # set up the animation nodes
      viewNode = threeDWidget.threeDView().mrmlViewNode()
      animationNode = self.animationSelector.currentNode()
      sequenceBrowserNode = slicer.util.getNode(animationNode.GetAttribute('Animator.sequenceBrowserNodeID'))
      sequenceNodes = vtk.vtkCollection()
      sequenceBrowserNode.GetSynchronizedSequenceNodes(sequenceNodes, True) # include master
      sequenceNode = sequenceNodes.GetItemAsObject(0)
      frameCount = sequenceNode.GetNumberOfDataNodes()
      tempDir = qt.QTemporaryDir()

      # perform the screen capture and video creation
      videoFormatIndex = self.videoFormatWidget.currentIndex
      videoFormat = logic.videoFormatPresets[videoFormatIndex]
      logic.captureSequence(
              viewNode,
              sequenceBrowserNode,
              0, frameCount-1, frameCount,
              tempDir.path(),
              "Slicer-%04d.png")
      logic.createVideo(
              60,
              videoFormat['extraVideoOptions'],
              tempDir.path(),
              "Slicer-%04d.png",
              self.outputFileButton.text+"."+videoFormat['fileExtension'])
    finally:
      # Always restore the 3D controller bar so the viewer is usable again.
      threeDWidget.threeDController().visible = True


class AnimatorActionsGUI:
  """Manage the UI elements for animation script
     Gets the script from the animationNode and
     returns a QWidget.
     Updates animation node script based on events from UI.

     TODO: this is hard coded for now, but can be generalized
     based on experience.
  """
  def __init__(self, animationNode, deleteCallback=lambda : None):
    self.animationNode = animationNode
    self.logic = AnimatorLogic()
    self.script = self.logic.getScript(self.animationNode)
    self.deleteCallback = deleteCallback

  def buildGUI(self):
    self.scrollArea = qt.QScrollArea()
    self.widget = qt.QWidget()
    self.scrollArea.widgetResizable = True
    self.scrollArea.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAsNeeded)
    self.layout = qt.QFormLayout()
    self.widget.setLayout(self.layout)
    self.scrollArea.setWidget(self.widget)
    actions = self.logic.getActions(self.animationNode)
    for action in actions.values():
      actionRowLayout = qt.QHBoxLayout()
      actionLabel = qt.QLabel(action['name'])
      actionRowLayout.addWidget(actionLabel)
      editButton = qt.QPushButton('Edit')
      editButton.connect('clicked()', lambda action=action : self.onEdit(action))
      actionRowLayout.addWidget(editButton)
      deleteButton = qt.QPushButton('Delete')
      deleteButton.connect('clicked()', lambda action=action : self.onDelete(action))
      actionRowLayout.addWidget(deleteButton)
      self.layout.addRow(actionRowLayout)
      durationSlider = ctk.ctkDoubleRangeSlider()
      durationSlider.maximum = self.script['duration']
      durationSlider.minimumValue = action['startTime']
      durationSlider.maximumValue = action['endTime']
      durationSlider.singleStep = 0.001
      durationSlider.orientation = qt.Qt.Horizontal
      self.layout.addRow(durationSlider)
      def updateDuration(start, end, action):
        action['startTime'] = start
        action['endTime'] = end
        self.logic.setAction(self.animationNode, action)
      durationSlider.connect('valuesChanged(double,double)', lambda start, end, action=action: updateDuration(start, end, action))
    return self.scrollArea

  def destroyGUI(self):
    self.scrollArea.takeWidget()

  def onEdit(self, action):
    actionInstance = slicer.modules.animatorActionPlugins[action['class']]()

    if actionInstance.wantsNonModalEditor():
      self._openNonModalEditor(action, actionInstance)
      return

    dialog = qt.QDialog(slicer.util.mainWindow())
    layout = qt.QFormLayout(dialog)

    label = qt.QLabel(action['name'])
    layout.addRow("Edit properties of:",  label )

    self.actionInstance = actionInstance
    self.actionInstance.gui(action, layout)

    buttonBox = qt.QDialogButtonBox()
    buttonBox.setStandardButtons(qt.QDialogButtonBox.Ok |
                                      qt.QDialogButtonBox.Cancel)
    layout.addRow(buttonBox)
    buttonBox.button(qt.QDialogButtonBox.Ok).setToolTip("Use currently selected color node.")
    buttonBox.button(qt.QDialogButtonBox.Cancel).setToolTip("Cancel current operation.")
    buttonBox.connect("accepted()", lambda action=action : self.accept(dialog, action))
    buttonBox.connect("rejected()", dialog, "reject()")

    dialog.exec_()

  def _openNonModalEditor(self, action, actionInstance):
    """Open a non-modal, always-on-top side editor whose changes are
    persisted live (no OK/Cancel). If an editor for this action is
    already open, just raise it."""
    if not hasattr(self, '_openEditors'):
      self._openEditors = {}
    existing = self._openEditors.get(action['id'])
    if existing is not None:
      try:
        existing.raise_()
        existing.activateWindow()
        return
      except Exception:
        # stale handle
        self._openEditors.pop(action['id'], None)

    dialog = qt.QDialog(slicer.util.mainWindow())
    # Qt.Tool keeps it floating above the main window without grabbing
    # the modal flag, so the 3D view stays fully interactive.
    dialog.setWindowFlags(qt.Qt.Tool)
    dialog.setWindowTitle(f"Edit \u2014 {action['name']}")
    dialog.setModal(False)
    layout = qt.QFormLayout(dialog)

    layout.addRow("Edit properties of:", qt.QLabel(action['name']))

    # Persistence callback: copy the live edits back to the animation node.
    def persist():
      try:
        actionInstance.updateFromGUI(action)
        self.logic.setAction(self.animationNode, action)
      except Exception as exc:
        logging.warning(f"Animator: failed to persist live edit: {exc}")
    actionInstance.onChanged = persist

    actionInstance.gui(action, layout)

    closeButton = qt.QPushButton("Close")
    closeButton.connect('clicked()', dialog.close)
    layout.addRow(closeButton)

    def onClosed():
      # Final persist on close, then drop the handle and rebind the
      # outer UI so the sequence-browser widgets pick up any new
      # duration/timing.
      try:
        # If the action's editor exposed a stop hook (e.g. preview
        # playback timer), trigger it before tearing things down.
        timeline = getattr(actionInstance, '_timelineWidget', None)
        if timeline is not None and hasattr(timeline, 'stopPlayback'):
          try:
            timeline.stopPlayback()
          except Exception:
            pass
        persist()
      finally:
        self._openEditors.pop(action['id'], None)
        try:
          self.deleteCallback()
        except Exception:
          pass
    dialog.connect('finished(int)', lambda _result: onClosed())

    self._openEditors[action['id']] = dialog
    dialog.show()
    dialog.raise_()

  def accept(self, dialog, action):
    self.actionInstance.updateFromGUI(action)
    self.logic.setAction(self.animationNode, action)
    dialog.accept()

  def onDelete(self, action):
    self.logic.removeAction(self.animationNode, action)
    self.deleteCallback()

#
# AnimatorLogic
#

class AnimatorLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def initializeAnimationNode(self,animationNode,duration=5):
    animationNode.SetAttribute('ModuleName', 'Animation')
    script = {}
    script['title'] = "Slicer Animation"
    script['duration'] = duration # in seconds
    script['framesPerSecond'] = 60
    self.setScript(animationNode, script)
    self.generateSequence(animationNode)

  def generateSequence(self,animationNode):
    sequenceBrowserNode = self.compileScript(animationNode)
    sequenceNodes = vtk.vtkCollection()
    sequenceBrowserNode.GetSynchronizedSequenceNodes(sequenceNodes, True) # include master
    sequenceNode = sequenceNodes.GetItemAsObject(0)
    animationNode.SetAttribute('Animator.sequenceBrowserNodeID', sequenceBrowserNode.GetID())
    animationNode.SetAttribute('Animator.sequenceNodeID', sequenceNode.GetID())

  def getScript(self, animationNode):
    scriptJSON = animationNode.GetAttribute("Animation.script") or "{}"
    script = json.loads(scriptJSON)
    return(script)

  def setScript(self, animationNode, script):
    scriptJSON = json.dumps(script)
    animationNode.SetAttribute("Animation.script", scriptJSON)

  def getActions(self, animationNode):
    script = self.getScript(animationNode)
    actions = script['actions'] if "actions" in script else {}
    return(actions)

  def getActionsByClass(self, animationNode):
    actions = self.getActions(animationNode)
    actionsByClass = {}
    for actionIndex in range(len(actions.keys())):
      action = actions[list(actions.keys())[actionIndex]]
      if not action['class'] in actionsByClass.keys():
        actionsByClass[action['class']] = []
      actionsByClass[action['class']].append(action)
    return(actionsByClass)

  def addAction(self, animationNode, action):
    """Add an action to the script """
    script = self.getScript(animationNode)
    actions = self.getActions(animationNode)
    actions[action['id']] = action
    script['actions'] = actions
    self.setScript(animationNode, script)

  def removeAction(self, animationNode, action):
    """Remove an action from the script """
    script = self.getScript(animationNode)
    actions = self.getActions(animationNode)

    # Notify the action that it will be deleted (gives a chance to clean up internal caches and scene modifications)
    action = actions[action['id']]
    actionInstance = slicer.modules.animatorActionPlugins[action['class']]()
    actionInstance.cleanup(action)

    del(actions[action['id']])
    script['actions'] = actions
    self.setScript(animationNode, script)

  def setAction(self, animationNode, action):
    script = self.getScript(animationNode)
    script['actions'][action['id']] = action
    self.setScript(animationNode, script)
    self._refreshSequenceForActions(animationNode)

  def _refreshSequenceForActions(self, animationNode):
    """If any action's endTime exceeds the script duration, expand the
    duration and append new frames to the existing playback sequence so
    the play/seek widgets keep working without needing to rebind."""
    script = self.getScript(animationNode)
    actions = script.get('actions', {})
    if not actions:
      return
    needed = max((a.get('endTime', 0) or 0) for a in actions.values())
    current = script.get('duration', 0) or 0
    if needed <= current:
      return

    sequenceNodeID = animationNode.GetAttribute('Animator.sequenceNodeID')
    sequenceNode = slicer.mrmlScene.GetNodeByID(sequenceNodeID) if sequenceNodeID else None
    if sequenceNode is None:
      # No sequence yet, regenerate from scratch.
      script['duration'] = float(needed)
      self.setScript(animationNode, script)
      self.generateSequence(animationNode)
      return

    fps = script.get('framesPerSecond', 60)
    secondsPerFrame = 1.0 / fps
    # Append new frames covering (current, needed].
    start_frame = math.ceil(current * fps)
    end_frame = math.ceil(needed * fps)
    for frame in range(start_frame, end_frame + 1):
      scriptTime = frame * secondsPerFrame
      if scriptTime <= current:
        continue
      timePointDataNode = slicer.vtkMRMLScriptedModuleNode()
      sequenceNode.SetDataNodeAtValue(timePointDataNode, str(scriptTime))
    script['duration'] = float(needed)
    self.setScript(animationNode, script)

  def compileScript(self, animationNode):
    """Convert the node's script into sequences and a sequence browser node.
       Returns the sequenceBrowserNode.
    """
    sequenceBrowserNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceBrowserNode')
    sequenceBrowserNode.SetName(animationNode.GetName() + "-Browser")

    # TODO: use this when exporting
    # sequenceBrowserNode.SetPlaybackItemSkippingEnabled(False)

    sequenceNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceNode')
    sequenceNode.SetIndexType(sequenceNode.NumericIndex)
    sequenceNode.SetName(animationNode.GetName() + "-TimingSequence")
    sequenceBrowserNode.AddSynchronizedSequenceNode(sequenceNode)

    # create one data node per frame of the script.
    # these are used to synchronize the animation
    # but don't hold any other data
    script = self.getScript(animationNode)
    frames = script['framesPerSecond'] * script['duration']
    secondsPerFrame = 1. / script['framesPerSecond']
    for frame in range(math.ceil(frames)):
      scriptTime = frame * secondsPerFrame
      timePointDataNode = slicer.vtkMRMLScriptedModuleNode()
      sequenceNode.SetDataNodeAtValue(timePointDataNode, str(scriptTime))

    return(sequenceBrowserNode)

  def act(self, animationNode, scriptTime):
    """Give each action in the script a chance to act at the current script time"""
    # Pause render while updating the scene to make sure that all changes appear at once
    # and no time is spent with unnecessary intermediate rendering step.
    slicer.app.pauseRender()
    try:
      actions = self.getActions(animationNode)
      for action in actions.values():
        actionInstance = slicer.modules.animatorActionPlugins[action['class']]()
        actionInstance.act(action, scriptTime)
    finally:
      slicer.app.resumeRender()


class AnimatorTest(ScriptedLoadableModuleTest):
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
    self.test_Animator1()

  def test_Animator1(self):
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

    self.delayDisplay("Starting the test", 10)
    #
    # first, get some data and make it visible
    #
    import SampleData
    mrHead = SampleData.downloadSample('MRHead')
    slicer.util.delayDisplay("Head downloaded...",10)

    slicer.util.mainWindow().moduleSelector().selectModule('VolumeRendering')
    volumeRenderingWidgetRep = slicer.modules.volumerendering.widgetRepresentation()
    volumeRenderingWidgetRep.setMRMLVolumeNode(mrHead)

    volumeRenderingNode = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    volumeRenderingNode.SetVisibility(1)
    volumeRenderingNode.SetShading(False)
    volumeRenderingLogic = slicer.modules.volumerendering.logic()
    animatedROI = volumeRenderingLogic.CreateROINode(volumeRenderingNode)
    slicer.util.mainWindow().moduleSelector().selectModule('Animator')

    self.delayDisplay('Volume rendering on')

    #
    # set up an animation
    #
    animationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScriptedModuleNode')
    animationNode.SetName('SelfTest Animation')

    logic = AnimatorLogic()
    logic.initializeAnimationNode(animationNode)

    #
    # set up a camera rotation action
    #
    actionInstance = slicer.modules.animatorActionPlugins["CameraRotationAction"]()
    cameraRotationAction = actionInstance.defaultAction()
    cameraRotationAction['endTime'] = 5
    logic.addAction(animationNode, cameraRotationAction)

    #
    # set up an ROI action
    #
    actionInstance = slicer.modules.animatorActionPlugins["ROIAction"]()
    roiAction = actionInstance.defaultAction()
    startROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
    startROI.SetName('Start ROI')
    endROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
    endROI.SetName('End ROI')
    for roi in [startROI, endROI]:
      for index in range(roi.GetNumberOfDisplayNodes()):
        roi.GetNthDisplayNode(index).SetVisibility(False)
    startROIID = startROI.GetID()
    endROIID = endROI.GetID()

    start = [0.,]*3
    animatedROI.GetXYZ(start)
    startROI.SetXYZ(start)
    endROI.SetXYZ(start)
    animatedROI.GetRadiusXYZ(start)
    startROI.SetRadiusXYZ(start)
    end = [0.,]*3
    for i in range(3):
      end[i] = start[i] / 2.
      endROI.SetRadiusXYZ(end)

    roiAction['endTime'] = 4
    roiAction['startROIID'] = startROIID
    roiAction['endROIID'] = endROIID
    roiAction['awimatedROIID'] =  animatedROI.GetID(),
    logic.addAction(animationNode, roiAction)

    #
    # set up a volume property action
    #
    actionInstance = slicer.modules.animatorActionPlugins["VolumePropertyAction"]()
    volumePropertyAction = actionInstance.defaultAction()
    logic.addAction(animationNode, volumePropertyAction)

    #
    # set up the animation and turn it on
    #
    sequenceBrowserNode = logic.compileScript(animationNode)

    sequenceNodes = vtk.vtkCollection()
    sequenceBrowserNode.GetSynchronizedSequenceNodes(sequenceNodes, True) # include master
    sequenceNode = sequenceNodes.GetItemAsObject(0)

    animationNode.SetAttribute('Animator.sequenceBrowserNodeID', sequenceBrowserNode.GetID())
    animationNode.SetAttribute('Animator.sequenceNodeID', sequenceNode.GetID())

    slicer.modules.AnimatorWidget.animationSelector.setCurrentNode(animationNode)

    sequenceBrowserNode.SetPlaybackActive(True)

    self.delayDisplay('Test passed!', 10)
