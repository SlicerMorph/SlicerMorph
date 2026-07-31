import logging
import os

import vtk

import slicer
# Explicit imports to avoid linter/star import issues
from slicer.ScriptedLoadableModule import (
  ScriptedLoadableModule,
  ScriptedLoadableModuleWidget,
  ScriptedLoadableModuleLogic,
)
from slicer.util import VTKObservationMixin

import numpy as np
import scipy.linalg as sp

# Layout IDs for QuickAlign custom layouts
LAYOUT_ID_QUICKALIGN_2VIEW = 701
LAYOUT_ID_QUICKALIGN_4VIEW = 702

#
# QuickAlign
#

class QuickAlign(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "QuickAlign"
        self.parent.categories = ["SlicerMorph.Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Sara Rolfe (SCRI), Murat Maga (SCRI, UW)"]
        self.parent.helpText = """
        This module temporarily fixes the alignment of two nodes in linked 3D views. If the nodes are point lists, joint editing can be enabled.
        """
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
        This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. Development of SlicerMorph is supported by NSF grants 1759883 and 2301405 to Murat Maga.
        """

#
# QuickAlignWidget
#

class QuickAlignWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
        # zoom sync bookkeeping
        self._zoomSyncActive = False
        self._zoomObserverTags = []
        self._zoomSourceToTarget = {}
        # display state captured before the module took the scene over, so that
        # Unlink can put the scene back the way the user left it
        self._savedDisplayState = {}
        # joint point list editing: the nodes the observers are actually attached
        # to, so teardown never depends on what the selectors currently say
        self.jointEditNodes = None
        self.observerList = []
        self._updatingJointEditing = False

        # Define custom layouts for module in slicer global namespace
        slicer.customLayoutQuickAlign = """
          <layout type=\"vertical\" split=\"true\" >
           <item splitSize=\"500\">
             <layout type=\"horizontal\">
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"1\">
                 <property name=\"viewlabel\" action=\"default\">1</property>
                </view>
               </item>
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">
                 <property name=\"viewlabel\" action=\"default\">2</property>
                </view>
              </item>
             </layout>
           </item>
          </layout>
        """

        # Define 2x2 layout with four 3D viewers
        slicer.customLayoutQuickAlignLayout = """
          <layout type=\"vertical\" split=\"true\">
           <item splitSize=\"500\">
             <layout type=\"horizontal\">
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"1\">
                 <property name=\"viewlabel\" action=\"default\">1</property>
                </view>
               </item>
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">
                 <property name=\"viewlabel\" action=\"default\">2</property>
                </view>
              </item>
             </layout>
           </item>
           <item splitSize=\"500\">
             <layout type=\"horizontal\">
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"3\" type=\"secondary\">
                 <property name=\"viewlabel\" action=\"default\">3</property>
                </view>
               </item>
               <item>
                <view class=\"vtkMRMLViewNode\" singletontag=\"4\" type=\"secondary\">
                 <property name=\"viewlabel\" action=\"default\">4</property>
                </view>
              </item>
             </layout>
           </item>
          </layout>
        """

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/QuickAlign.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)
        self.ui.inputSelector1.setMRMLScene(slicer.mrmlScene)
        self.ui.inputSelector2.setMRMLScene(slicer.mrmlScene)
        self.ui.landmarksSelector1.setMRMLScene(slicer.mrmlScene)
        self.ui.landmarksSelector2.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = QuickAlignLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        #self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        #self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.inputSelector1.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.ui.inputSelector2.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.ui.landmarksSelector1.connect('currentNodeChanged(vtkMRMLNode*)', self.onLandmarkChanged)
        self.ui.landmarksSelector2.connect('currentNodeChanged(vtkMRMLNode*)', self.onLandmarkChanged)
        self.ui.jointEditCheckBox.connect('toggled(bool)', self.onJointEditToggled)
        self.ui.initializeViewButton.connect('clicked(bool)', self.onInitializeViewButton)
        self.ui.linkButton.connect('clicked(bool)', self.onLinkButton)
        self.ui.unlinkButton.connect('clicked(bool)', self.onUnlinkButton)

        # Custom Layout button
        self.addLayoutButton(LAYOUT_ID_QUICKALIGN_2VIEW, 'QuickAlign View', 'Custom layout for QuickAlign module', 'LayoutSlicerMorphView.png', slicer.customLayoutQuickAlign)
        self.addLayoutButton(LAYOUT_ID_QUICKALIGN_4VIEW, 'QuickAlignLayout', 'QuickAlign 2x2 layout with four 3D viewers', 'LayoutSlicerMorphView.png', slicer.customLayoutQuickAlignLayout)

        # Initially disable landmark selectors until sync starts
        self.ui.landmarksSelector1.enabled = False
        self.ui.landmarksSelector2.enabled = False

    def onLandmarkChanged(self):
        """Called when landmark selection changes - update visibility and transforms immediately"""
        # Only process if we're in synced state (the link button is disabled while synced)
        if not hasattr(self, 'viewNode1') or self.ui.linkButton.enabled:
            return

        # Validate that selected landmarks are not the same as objects
        if hasattr(self, 'excludedLandmarkIDs'):
            for selector in [self.ui.landmarksSelector1, self.ui.landmarksSelector2]:
                currentNode = selector.currentNode()
                if currentNode and currentNode.GetID() in self.excludedLandmarkIDs:
                    selector.setCurrentNode(None)
                    slicer.util.warningDisplay(f"Cannot use {currentNode.GetName()} as a landmark - it is already selected as Object 1 or Object 2")

        self.updateLandmarkDisplay()
        self.updateJointEditingAvailability()
        # Landmarks can only be picked once the sync has started, so this is where
        # joint editing on a landmark pair actually gets wired up.
        self.updateJointEditing()

    def onJointEditToggled(self, checked):
        """Start or stop joint editing when the user toggles the check box."""
        self.updateJointEditing()

    def jointEditingNodes(self):
        """The pair of point lists joint editing should operate on, or (None, None).

        The aligned objects are preferred when they are themselves point lists;
        otherwise their landmark sets are used.
        """
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        landmarks1 = self.ui.landmarksSelector1.currentNode()
        landmarks2 = self.ui.landmarksSelector2.currentNode()
        editNode1 = node1 if self.isFiducialNode(node1) else landmarks1
        editNode2 = node2 if self.isFiducialNode(node2) else landmarks2
        if self.isFiducialNode(editNode1) and self.isFiducialNode(editNode2):
            return editNode1, editNode2
        return None, None

    def updateJointEditing(self):
        """Make the joint editing observers match the current selection.

        Called whenever anything that feeds jointEditingNodes() changes, so that
        picking landmarks after Link -- the only time they can be picked -- starts
        joint editing, and swapping a selection re-targets it instead of leaving
        observers on the old node.
        """
        if self._updatingJointEditing:
            return
        self._updatingJointEditing = True
        try:
            editNode1, editNode2 = self.jointEditingNodes()
            wanted = bool(self.ui.jointEditCheckBox.enabled
                          and self.ui.jointEditCheckBox.checked
                          and editNode1 and editNode2)

            # Tear down first if joint editing is running on the wrong pair
            if self.jointEditNodes and (not wanted or self.jointEditNodes != (editNode1, editNode2)):
                self.stopJointEditing()

            if wanted and not self.jointEditNodes:
                observerList = self.logic.startJointMarkupEditing(editNode1, editNode2)
                if observerList:
                    self.jointEditNodes = (editNode1, editNode2)
                    self.observerList = observerList
                else:
                    self.ui.jointEditCheckBox.checked = False
                    slicer.util.errorDisplay(
                        "Joint editing was not enabled: the two point lists must have "
                        "the same number of points.")
        finally:
            self._updatingJointEditing = False

    def stopJointEditing(self):
        """Detach joint editing from whichever nodes it was actually started on."""
        if not self.jointEditNodes:
            return
        self.logic.endJointMarkupEditing(self.jointEditNodes[0], self.jointEditNodes[1], self.observerList)
        self.jointEditNodes = None
        self.observerList = []

    def filterLandmarkSelectors(self):
        """Hide Object 1 and Object 2 from the landmark selectors if they are markups.

        Filtering is done by node ID through the combo box's sort/filter proxy model.
        Note that qMRMLNodeComboBox.baseName is *not* a filter -- it only supplies the
        default name for nodes created from the combo box -- so it cannot be used here.

        hiddenNodeIDs must be assigned as a property: setHiddenNodeIDs() is a plain
        public C++ method, neither a slot nor Q_INVOKABLE, so it is not callable
        from Python.
        """
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()

        # Get IDs to exclude
        excludeIDs = set()
        if node1 and node1.IsA('vtkMRMLMarkupsNode'):
            excludeIDs.add(node1.GetID())
        if node2 and node2.IsA('vtkMRMLMarkupsNode'):
            excludeIDs.add(node2.GetID())

        # Store excluded IDs so onLandmarkChanged can validate a selection that
        # was already in place before the filter was applied
        self.excludedLandmarkIDs = excludeIDs

        for selector in [self.ui.landmarksSelector1, self.ui.landmarksSelector2]:
            proxyModel = selector.sortFilterProxyModel()
            if proxyModel:
                proxyModel.hiddenNodeIDs = sorted(excludeIDs)

    def updateLandmarkDisplay(self):
        """Apply transforms and view restrictions to currently selected landmarks"""
        if not (hasattr(self, 'centerNode1Transform') and hasattr(self, 'centerNode2Transform')):
            return

        landmarks1 = self.ui.landmarksSelector1.currentNode()
        landmarks2 = self.ui.landmarksSelector2.currentNode()

        # Update landmarks 1
        if landmarks1:
            landmarks1.SetAndObserveTransformNodeID(self.centerNode1Transform.GetID())
            dn = landmarks1.GetDisplayNode()
            self.setDisplayViewNodeIDs(dn, [self.viewNode1.GetID()])
            self.setDisplayVisibility(dn, True)

        # Update landmarks 2
        if landmarks2:
            landmarks2.SetAndObserveTransformNodeID(self.centerNode2Transform.GetID())
            dn = landmarks2.GetDisplayNode()
            self.setDisplayViewNodeIDs(dn, [self.viewNode2.GetID()])
            self.setDisplayVisibility(dn, True)

    def clearLandmarkSelectorFilter(self):
        """Stop hiding nodes in the landmark selectors."""
        self.excludedLandmarkIDs = set()
        for selector in [self.ui.landmarksSelector1, self.ui.landmarksSelector2]:
            proxyModel = selector.sortFilterProxyModel()
            if proxyModel:
                proxyModel.hiddenNodeIDs = []

    def hasFourViewNodes(self):
        """True when all four QuickAlign view nodes have been resolved."""
        return all(getattr(self, name, None) for name in
                   ['viewNode1', 'viewNode2', 'viewNode3', 'viewNode4'])

    @staticmethod
    def isFiducialNode(node):
        """True when node is a markups fiducial (point list) node."""
        return node is not None and node.GetNodeTagName() == "MarkupsFiducial"

    def updateJointEditingAvailability(self):
        """Enable joint editing if either objects or landmarks are both fiducial markups"""
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        landmarks1 = self.ui.landmarksSelector1.currentNode()
        landmarks2 = self.ui.landmarksSelector2.currentNode()

        # Check if objects themselves are fiducials
        objectsAreFiducials = self.isFiducialNode(node1) and self.isFiducialNode(node2)

        # Check if landmarks are fiducials
        landmarksAreFiducials = self.isFiducialNode(landmarks1) and self.isFiducialNode(landmarks2)

        # Enable if either condition is true
        available = objectsAreFiducials or landmarksAreFiducials
        self.ui.jointEditCheckBox.enabled = available

        # Auto-check if enabled and objects are fiducials (original behavior).
        # Clear it when joint editing is not available at all, so a stale checked
        # state cannot outlive the selection that justified it.
        if objectsAreFiducials:
            self.ui.jointEditCheckBox.checked = True
        elif not available:
            self.ui.jointEditCheckBox.checked = False

    def onSelect(self):
        self.ui.initializeViewButton.enabled = bool(self.ui.inputSelector1.currentNode() and self.ui.inputSelector2.currentNode())

        # Update joint editing availability during selection phase
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        if node1 and node2:
            self.updateJointEditingAvailability()
        # The object selectors stay live during a sync, so re-target (or drop)
        # joint editing rather than leaving observers on the previous node.
        self.updateJointEditing()


    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        # Release the point lists before going away, otherwise they stay locked
        # at a fixed control point count.
        self.stopJointEditing()
        # The zoom sync observers are added directly on the camera nodes, so
        # VTKObservationMixin.removeObservers() does not know about them.
        self.removeZoomSyncObservers()
        self.removeObservers()

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
    def exit(self):
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
        #self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    def onSceneStartClose(self, caller, event):
        """
        Called just before the scene is closed.
        """

    def onSceneEndClose(self, caller, event):
        """
        Called just after the scene is closed.
        """

    def update3DViews(self):
        #update cameras
        layoutManager = slicer.app.layoutManager()
        for threeDViewIndex in range(layoutManager.threeDViewCount) :
          view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
          view.resetFocalPoint()

    def onLinkButton(self):
        """
        Run processing when user clicks "Link" button.
        Links views 1 and 2 (superior views) while keeping side views 3 and 4 independent.
        """
        if not self.hasFourViewNodes():
          slicer.util.errorDisplay("Can not find 4 3D views to link. Please reinitialize views.")
          return

        # Get all cameras
        camera1 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode1)
        camera2 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode2)

        # Calculate alignment between cameras 1 and 2 (the two superior views)
        camera2ZoomFactor = camera1.GetParallelScale()/camera2.GetParallelScale()
        scalingTransform=vtk.vtkTransform()
        scalingTransform.Scale(camera2ZoomFactor,camera2ZoomFactor,camera2ZoomFactor)
        self.scalingTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "scale transform")
        self.scalingTransformNode.SetMatrixTransformToParent(scalingTransform.GetMatrix())

        # Get alignment transform between the two objects (cameras 1 and 2)
        self.alignmentTransform = self.logic.getCameraAlignmentTransform(camera1, camera2)

        # Apply alignment to object 2 (shared transform used by both its view display nodes)
        if hasattr(self, 'centerNode2Transform'):
          self.centerNode2Transform.SetAndObserveTransformNodeID(self.alignmentTransform.GetID())
        self.alignmentTransform.SetAndObserveTransformNodeID(self.scalingTransformNode.GetID())

        # Link views properly: SetLinkedControl must be True on the PRIMARY view
        # All views start unlinked
        self.viewNode1.SetLinkedControl(False)
        self.viewNode2.SetLinkedControl(False)
        self.viewNode3.SetLinkedControl(False)
        self.viewNode4.SetLinkedControl(False)

        # Now enable linking on view 1 - this will link ALL views together
        self.viewNode1.SetLinkedControl(True)

        # Switch to two-view layout (horizontal 1 & 2) per requirement
        try:
          layoutManager = slicer.app.layoutManager()
          layoutManager.setLayout(LAYOUT_ID_QUICKALIGN_2VIEW)  # custom two-view layout id defined earlier
        except Exception as e:
          logging.error(f"Failed to switch to two-view layout: {e}")

        # Restrict display nodes to just their primary views (remove side views during sync)
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()

        if node1:
            self.setDisplayViewNodeIDs(node1.GetDisplayNode(), [self.viewNode1.GetID()])
        if node2:
            self.setDisplayViewNodeIDs(node2.GetDisplayNode(), [self.viewNode2.GetID()])

        # The scene has now been changed, so Unlink must be reachable from here on.
        # Enable it before the optional landmark / joint editing work below, so that
        # a failure there still leaves the user a way back to the original scene.
        self.ui.unlinkButton.enabled = True
        self.ui.linkButton.enabled = False
        self.ui.initializeViewButton.enabled = False

        # Enable landmark selectors now that sync has started
        self.ui.landmarksSelector1.enabled = True
        self.ui.landmarksSelector2.enabled = True

        # Filter landmark selectors to exclude Object 1 and Object 2
        self.filterLandmarkSelectors()

        # Apply landmarks if already selected
        self.updateLandmarkDisplay()

        self.update3DViews()

        # Update joint editing availability after landmarks are applied, then start
        # it if it applies. The check box stays live during the sync: landmarks can
        # only be picked from here on, so joint editing on a landmark pair has to be
        # able to start after Link (see updateJointEditing).
        self.updateJointEditingAvailability()
        self.updateJointEditing()

    def onUnlinkButton(self):
        """
        Run processing when user clicks "Unlink" button.
        """
        self.cleanUpTransformNodes()
        self.ui.unlinkButton.enabled = False
        self.ui.linkButton.enabled = False

        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()

        # End joint editing, on whichever nodes it was actually started on
        self.stopJointEditing()

        # Disable landmark selectors when not synced, and stop filtering them
        self.ui.landmarksSelector1.enabled = False
        self.ui.landmarksSelector2.enabled = False
        self.clearLandmarkSelectorFilter()

        # Give every display node we touched its original visibility and views back
        self.restoreDisplayState()

        # unlink all the views
        for viewNodeAttr in ['viewNode1', 'viewNode2', 'viewNode3', 'viewNode4']:
            viewNode = getattr(self, viewNodeAttr, None)
            if viewNode:
                viewNode.SetLinkedControl(False)

        self.update3DViews()
        self.ui.initializeViewButton.enabled = bool(node1 and node2)
        self.updateJointEditingAvailability()

    def addLayoutButton(self, layoutID, buttonAction, toolTip, imageFileName, layoutDiscription):
        layoutManager = slicer.app.layoutManager()
        layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(layoutID, layoutDiscription)

        viewToolBar = slicer.util.mainWindow().findChild('QToolBar', 'ViewToolBar')
        layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
        layoutSwitchActionParent = layoutMenu
        # use `layoutMenu` to add inside layout list, use `viewToolBar` to add next the standard layout list
        layoutSwitchAction = layoutSwitchActionParent.addAction(buttonAction) # add inside layout list

        moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
        #iconPath = os.path.join(moduleDir, 'Resources/Icons', imageFileName)
        #layoutSwitchAction.setIcon(qt.QIcon(iconPath))
        layoutSwitchAction.setToolTip(toolTip)
        layoutSwitchAction.connect('triggered()', lambda layoutId = layoutID: slicer.app.layoutManager().setLayout(layoutId))
        layoutSwitchAction.setData(layoutID)

    def centerNodes(self, node1, node2):
      """Translate both nodes so their geometric (RAS bounds) centers align to origin.
      Use shared transform per node so rotation stays in place across multiple views."""
      def nodeCenter(n):
        bounds = [0,0,0,0,0,0]
        # Prefer RAS bounds if available
        try:
          n.GetRASBounds(bounds)
        except Exception:
          # fallback to display node bounds
          dn = n.GetDisplayNode()
          if dn:
            dn.GetBounds(bounds)
        cx = (bounds[0]+bounds[1])/2.0
        cy = (bounds[2]+bounds[3])/2.0
        cz = (bounds[4]+bounds[5])/2.0
        return np.array([cx,cy,cz])

      c1 = nodeCenter(node1)
      c2 = nodeCenter(node2)

      t1 = vtk.vtkTransform()
      t1.Translate(-c1)
      t2 = vtk.vtkTransform()
      t2.Translate(-c2)

      self.centerNode1Transform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "center node 1")
      self.centerNode1Transform.SetMatrixTransformToParent(t1.GetMatrix())
      self.centerNode2Transform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "center node 2")
      self.centerNode2Transform.SetMatrixTransformToParent(t2.GetMatrix())

      node1.SetAndObserveTransformNodeID(self.centerNode1Transform.GetID())
      node2.SetAndObserveTransformNodeID(self.centerNode2Transform.GetID())

      # Make sure all cameras look at origin now
      for v in [self.viewNode1, self.viewNode2, self.viewNode3, self.viewNode4]:
        camNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(v)
        if camNode:
          camNode.GetCamera().SetFocalPoint(0,0,0)
      self.update3DViews()

    def cleanUpTransformNodes(self):
        # remove alignment transforms from previous runs
        if hasattr(self, 'centerNode1Transform'):
          # First detach the transform before removal
          if self.centerNode1Transform:
            self.centerNode1Transform.GetTransformToParent().Identity()
            self.centerNode1Transform.SetAndObserveTransformNodeID(None)
          slicer.mrmlScene.RemoveNode(self.centerNode1Transform)
        if hasattr(self, 'centerNode2Transform'):
          # First detach the transform before removal
          if self.centerNode2Transform:
            self.centerNode2Transform.GetTransformToParent().Identity()
            self.centerNode2Transform.SetAndObserveTransformNodeID(None)
          slicer.mrmlScene.RemoveNode(self.centerNode2Transform)
        if hasattr(self, 'alignmentTransform'):
          # First detach the transform before removal
          if self.alignmentTransform:
            self.alignmentTransform.GetTransformToParent().Identity()
            self.alignmentTransform.SetAndObserveTransformNodeID(None)
          slicer.mrmlScene.RemoveNode(self.alignmentTransform)
        if hasattr(self, 'scalingTransformNode'):
          # First detach the transform before removal
          if self.scalingTransformNode:
            self.scalingTransformNode.GetTransformToParent().Identity()
            self.scalingTransformNode.SetAndObserveTransformNodeID(None)
          slicer.mrmlScene.RemoveNode(self.scalingTransformNode)
        self.removeZoomSyncObservers()

    def removeZoomSyncObservers(self):
        if self._zoomObserverTags:
            for camNode, tag in self._zoomObserverTags:
                try:
                    camNode.RemoveObserver(tag)
                except Exception:
                    pass
        self._zoomObserverTags = []
        self._zoomSourceToTarget = {}
        self._zoomSyncActive = False

    def saveDisplayState(self, displayNode):
        """Remember a display node's visibility and view restriction before we change it.

        The first saved value wins, so repeated calls within one session do not
        overwrite the user's original state with our own.
        """
        if not displayNode:
            return
        nodeID = displayNode.GetID()
        if nodeID in self._savedDisplayState:
            return
        self._savedDisplayState[nodeID] = (
            displayNode.GetVisibility(),
            list(displayNode.GetViewNodeIDs() or []),
        )

    def restoreDisplayState(self):
        """Put every display node this module touched back the way we found it."""
        for nodeID, (visibility, viewNodeIDs) in self._savedDisplayState.items():
            displayNode = slicer.mrmlScene.GetNodeByID(nodeID)
            if not displayNode:
                continue
            displayNode.SetViewNodeIDs(viewNodeIDs)
            displayNode.SetVisibility(visibility)
        self._savedDisplayState = {}

    def setDisplayViewNodeIDs(self, displayNode, viewNodeIDs):
        """Restrict a display node to the given views, remembering its prior state."""
        if not displayNode:
            return
        self.saveDisplayState(displayNode)
        displayNode.SetViewNodeIDs(viewNodeIDs)

    def setDisplayVisibility(self, displayNode, visible):
        """Set a display node's visibility, remembering its prior state."""
        if not displayNode:
            return
        self.saveDisplayState(displayNode)
        displayNode.SetVisibility(visible)

    def hideAllObjectsExcept(self, keepNodes):
        """Hide all models, volumes, and markups except the specified nodes.

        Prior visibility is recorded so that Unlink can restore it.
        """
        keepNodeIDs = {n.GetID() for n in keepNodes if n}

        # Hide all models
        models = slicer.util.getNodesByClass('vtkMRMLModelNode')
        for model in models:
            if model.GetID() not in keepNodeIDs:
                self.setDisplayVisibility(model.GetDisplayNode(), False)

        # Hide all volumes (scalar and volume rendering)
        volumes = slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')
        for vol in volumes:
            if vol.GetID() not in keepNodeIDs:
                for i in range(vol.GetNumberOfDisplayNodes()):
                    self.setDisplayVisibility(vol.GetNthDisplayNode(i), False)

        # Hide all markups
        markups = slicer.util.getNodesByClass('vtkMRMLMarkupsNode')
        for markup in markups:
            if markup.GetID() not in keepNodeIDs:
                self.setDisplayVisibility(markup.GetDisplayNode(), False)

    def onInitializeViewButton(self):
        self.cleanUpTransformNodes()
        # Undo any display changes left over from an earlier initialization, so
        # that re-initializing does not bake our own state in as the "original".
        self.restoreDisplayState()

        # Get selected objects
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        if not (node1 and node2):
            slicer.util.errorDisplay("Please select both Object 1 and Object 2.")
            return

        customLayoutId1=LAYOUT_ID_QUICKALIGN_4VIEW  # Use the 2x2 QuickAlignLayout
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(customLayoutId1)

        #set up 4 3D views
        self.viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        self.viewNode2 = slicer.mrmlScene.GetFirstNodeByName("View2")
        self.viewNode3 = slicer.mrmlScene.GetFirstNodeByName("View3")
        self.viewNode4 = slicer.mrmlScene.GetFirstNodeByName("View4")

        if not self.hasFourViewNodes():
            slicer.util.errorDisplay(
                "Could not create the four 3D views required by QuickAlign. "
                "Please switch to the 'QuickAlignLayout' layout and try again.")
            return

        # Hide all other objects in the scene. Done only once the views are known
        # to exist, so a failure above leaves the scene untouched.
        self.hideAllObjectsExcept([node1, node2])

        # Configure all views
        for viewNode in [self.viewNode1, self.viewNode2, self.viewNode3, self.viewNode4]:
            viewNode.SetAxisLabelsVisible(False)
            viewNode.SetBoxVisible(False)

        # Desired view assignments:
        #   node1 -> View1 & View3
        #   node2 -> View2 & View4
        node1Views = [self.viewNode1.GetID(), self.viewNode3.GetID()]
        node2Views = [self.viewNode2.GetID(), self.viewNode4.GetID()]
        volRenLogic = slicer.modules.volumerendering.logic()

        def prepareVolumeRenderingDisplay(n):
          # Ensure a volume rendering display node exists and return it
          vrDisplayNode = None
          for i in range(n.GetNumberOfDisplayNodes()):
            dn = n.GetNthDisplayNode(i)
            if dn.IsA("vtkMRMLVolumeRenderingDisplayNode"):
              vrDisplayNode = dn
          if vrDisplayNode is None:
            vrDisplayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(n)
            # Use a neutral preset if available
            preset = volRenLogic.GetPresetByName("MR-Default") or volRenLogic.GetPresetByName("CT-AAA") or volRenLogic.GetPresetByName("US-Fetal")
            if preset:
              vrDisplayNode.GetVolumePropertyNode().Copy(preset)
          return vrDisplayNode

        def assignViews(n, desiredViews):
          if n is None:
            return
          if n.GetNodeTagName() == "Volume":
            vrDisplayNode = prepareVolumeRenderingDisplay(n)
            # Hide scalar volume display nodes (to avoid duplicate rendering) and restrict VR display
            for i in range(n.GetNumberOfDisplayNodes()):
              dn = n.GetNthDisplayNode(i)
              if dn == vrDisplayNode:
                self.setDisplayViewNodeIDs(dn, desiredViews)
                self.setDisplayVisibility(dn, True)
              else:
                # Hide other display nodes (slice or scalar) in 3D views; they will still be available in slice viewers if needed
                self.setDisplayVisibility(dn, False)
          else:
            dn = n.GetDisplayNode()
            self.setDisplayViewNodeIDs(dn, desiredViews)
            self.setDisplayVisibility(dn, True)

        assignViews(node1, node1Views)
        assignViews(node2, node2Views)

        # Unlink all views initially
        self.viewNode1.SetLinkedControl(False)
        self.viewNode2.SetLinkedControl(False)
        self.viewNode3.SetLinkedControl(False)
        self.viewNode4.SetLinkedControl(False)

        #update views
        self.update3DViews()

        # Set camera orientations
        # View 1: Superior view (looking down from top)
        # View 3: Side/Lateral view (90 degree rotation)
        # View 2: Superior view
        # View 4: Side/Lateral view
        self.setCameraOrientation(self.viewNode1, viewUp=[0, 1, 0], position=[0, 0, 1])
        self.setCameraOrientation(self.viewNode3, viewUp=[0, 0, 1], position=[1, 0, 0])
        self.setCameraOrientation(self.viewNode2, viewUp=[0, 1, 0], position=[0, 0, 1])
        self.setCameraOrientation(self.viewNode4, viewUp=[0, 0, 1], position=[1, 0, 0])

        # Setup zoom synchronization (1 <-> 3) and (2 <-> 4) for initialization
        self.setupZoomSyncPairs()

        self.ui.linkButton.enabled = True
        self.ui.unlinkButton.enabled = False

        #translate all nodes to origin
        self.centerNodes(node1, node2)

    def setCameraOrientation(self, viewNode, viewUp, position):
        """Set camera orientation for a specific view"""
        camera = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)
        if camera:
            # Get the camera
            cam = camera.GetCamera()
            # Reset the camera to default
            cam.SetPosition(position[0] * 500, position[1] * 500, position[2] * 500)
            cam.SetFocalPoint(0, 0, 0)
            cam.SetViewUp(viewUp[0], viewUp[1], viewUp[2])
            cam.OrthogonalizeViewUp()
            # Reset the clipping range. threeDWidget() takes a widget index or a
            # widget name -- passing the view node returns None, silently skipping
            # the reset -- and the widget name matches the view node name.
            layoutManager = slicer.app.layoutManager()
            threeDWidget = layoutManager.threeDWidget(viewNode.GetName())
            if threeDWidget:
                threeDView = threeDWidget.threeDView()
                threeDView.resetFocalPoint()

    # ---- Zoom synchronization helpers ----
    def setupZoomSyncPairs(self):
      """Keep each specimen's superior and lateral view at the same zoom level.

      Sync runs both ways within a pair; the _zoomSyncActive guard in
      onZoomSourceModified stops the two observers from echoing each other.
      """
      self.removeZoomSyncObservers()
      pairs = [
        (self.viewNode1, self.viewNode3),  # object 1 superior & side
        (self.viewNode2, self.viewNode4),  # object 2 superior & side
      ]
      for superiorViewNode, lateralViewNode in pairs:
        superiorCamNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(superiorViewNode)
        lateralCamNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(lateralViewNode)
        if not superiorCamNode or not lateralCamNode:
          continue
        # Initial sync of zoom level, taking the superior view as the reference
        self.copyZoom(superiorCamNode, lateralCamNode)
        for sourceCamNode, targetCamNode in [(superiorCamNode, lateralCamNode),
                                             (lateralCamNode, superiorCamNode)]:
          self._zoomSourceToTarget[sourceCamNode.GetID()] = targetCamNode
          tag = sourceCamNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onZoomSourceModified)
          self._zoomObserverTags.append((sourceCamNode, tag))

    def copyZoom(self, sourceCamNode, targetCamNode):
      srcCam = sourceCamNode.GetCamera()
      tgtCam = targetCamNode.GetCamera()
      if srcCam.GetParallelProjection():
        tgtCam.SetParallelScale(srcCam.GetParallelScale())
      else:
        # Perspective: match distance while keeping target orientation
        focal = np.array(tgtCam.GetFocalPoint())
        pos = np.array(tgtCam.GetPosition())
        direction = pos - focal
        norm = np.linalg.norm(direction)
        newDist = srcCam.GetDistance()
        if norm > 1e-6:
          newPos = focal + direction / norm * newDist
          tgtCam.SetPosition(*newPos)
        else:
          # Degenerate case: camera position equals focal point
          logging.warning("QuickAlign: Camera position equals focal point, skipping zoom sync")
      targetCamNode.Modified()

    def onZoomSourceModified(self, caller, event):
      if self._zoomSyncActive:
        return
      camNode = caller  # vtkMRMLCameraNode
      target = self._zoomSourceToTarget.get(camNode.GetID())
      if not target:
        return
      self._zoomSyncActive = True
      try:
        self.copyZoom(camNode, target)
      finally:
        self._zoomSyncActive = False

#
# QuickAlignLogic
#

class QuickAlignLogic(ScriptedLoadableModuleLogic):
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
        self.node1 = None
        self.node2 = None
        self.updatingNodesActive = False

    def getCameraAlignmentTransform(self, camera1, camera2):
      #get transform matrices from cameras
      transformMatrix1_vtk = camera1.GetCamera().GetViewTransformMatrix()
      transformMatrix2_vtk = camera2.GetCamera().GetViewTransformMatrix()
      transformMatrix1 = slicer.util.arrayFromVTKMatrix(transformMatrix1_vtk)
      transformMatrix2 = slicer.util.arrayFromVTKMatrix(transformMatrix2_vtk)

      #approximate mapping between transforms
      u,s,v=sp.svd(np.dot(np.transpose(transformMatrix2),transformMatrix1), full_matrices=True)
      alignmentMatrix=np.dot(np.transpose(v), np.transpose(u))
      alignmentMatrix_vtk = slicer.util.vtkMatrixFromArray(alignmentMatrix)

      #apply to moving node
      transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "alignment transform")
      transformNode.SetMatrixTransformToParent(alignmentMatrix_vtk)
      return transformNode

    def updateSelectPoints1(self, caller, eventId):
      if not self.updatingNodesActive:
        self.updatingNodesActive = True
        for i in range(self.node1.GetNumberOfControlPoints()):
          self.node2.SetNthControlPointSelected(i,self.node1.GetNthControlPointSelected(i))
        self.updatingNodesActive = False

    def updateSelectPoints2(self, caller, eventId):
      if not self.updatingNodesActive:
        self.updatingNodesActive = True
        for i in range(self.node2.GetNumberOfControlPoints()):
          self.node1.SetNthControlPointSelected(i,self.node2.GetNthControlPointSelected(i))
        self.updatingNodesActive = False

    def startJointMarkupEditing(self, inputNode1, inputNode2):
        logging.info('Enabling joint editing of point list nodes')
        # The logic class stays GUI-free; the widget reports the failure to the user.
        if inputNode1.GetNumberOfControlPoints() != inputNode2.GetNumberOfControlPoints():
          logging.error("QuickAlign: point lists must have the same number of points to enable joint editing.")
          return []
        self.node1 = inputNode1
        self.node2 = inputNode2
        self.updatingNodesActive = False
        self.node1.SetFixedNumberOfControlPoints(True)
        self.node2.SetFixedNumberOfControlPoints(True)
        observerTag1 = inputNode1.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.updateSelectPoints1)
        observerTag2 = inputNode2.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.updateSelectPoints2)

        return[observerTag1, observerTag2]

    def endJointMarkupEditing(self, inputNode1, inputNode2, observerTags):
        logging.info('Ending joint editing of point lists')
        for inputNode, observerTag in zip([inputNode1, inputNode2], observerTags):
          try:
            inputNode.RemoveObserver(observerTag)
          except Exception:
            logging.warning(f"QuickAlign: no observer tag found for {inputNode.GetName()}")
          # Release the lock that startJointMarkupEditing put on the point list,
          # otherwise the user cannot add or remove points after unlinking.
          inputNode.SetFixedNumberOfControlPoints(False)
        self.node1 = None
        self.node2 = None
        self.updatingNodesActive = False

