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

import math
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
        self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Sara Rolfe (SCRI), Murat Maga (SCRI, UW)"]
        self.parent.helpText = """
        This module temporarily fixes the alignment of two nodes in linked 3D views. If the nodes are point lists, joint editing can be enabled.
        """
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
        This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
        awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
        https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
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
                <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">"
                 <property name=\"viewlabel\" action=\"default\">2</property>"
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
        # Only process if we're in synced state
        if not hasattr(self, 'viewNode1') or not self.ui.linkButton.enabled == False:
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
    
    def filterLandmarkSelectors(self):
        """Filter landmark selectors to exclude Object 1 and Object 2 if they are markups"""
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        
        # Get names to exclude
        excludeNames = []
        excludeIDs = set()
        if node1 and node1.IsA('vtkMRMLMarkupsNode'):
            excludeNames.append(node1.GetName())
            excludeIDs.add(node1.GetID())
        if node2 and node2.IsA('vtkMRMLMarkupsNode'):
            excludeNames.append(node2.GetName())
            excludeIDs.add(node2.GetID())
        
        # Store excluded IDs for validation
        self.excludedLandmarkIDs = excludeIDs
        
        # Try to filter using baseName with negative lookahead regex
        if excludeNames:
            # Create a regex pattern that matches anything EXCEPT the excluded names
            # Escape special regex characters in names
            import re
            escaped_names = [re.escape(name) for name in excludeNames]
            # Pattern: match anything that is NOT exactly one of the excluded names
            # Using negative lookahead: ^(?!exact_match1$|exact_match2$).*
            pattern = "^(?!" + "|".join([f"{name}$" for name in escaped_names]) + ").*"
            
            for selector in [self.ui.landmarksSelector1, self.ui.landmarksSelector2]:
                try:
                    selector.baseName = pattern
                except:
                    # If baseName doesn't work, we'll rely on validation in onLandmarkChanged
                    pass
    
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
            if dn:
                dn.SetViewNodeIDs([self.viewNode1.GetID()])
                dn.SetVisibility(True)
        
        # Update landmarks 2
        if landmarks2:
            landmarks2.SetAndObserveTransformNodeID(self.centerNode2Transform.GetID())
            dn = landmarks2.GetDisplayNode()
            if dn:
                dn.SetViewNodeIDs([self.viewNode2.GetID()])
                dn.SetVisibility(True)
    
    def updateJointEditingAvailability(self):
        """Enable joint editing if either objects or landmarks are both fiducial markups"""
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        landmarks1 = self.ui.landmarksSelector1.currentNode()
        landmarks2 = self.ui.landmarksSelector2.currentNode()
        
        # Check if objects themselves are fiducials
        objectsAreFiducials = (node1 and node2 and 
                               node1.GetNodeTagName() == "MarkupsFiducial" and 
                               node2.GetNodeTagName() == "MarkupsFiducial")
        
        # Check if landmarks are fiducials
        landmarksAreFiducials = (landmarks1 and landmarks2 and 
                                 landmarks1.GetNodeTagName() == "MarkupsFiducial" and 
                                 landmarks2.GetNodeTagName() == "MarkupsFiducial")
        
        # Enable if either condition is true
        self.ui.jointEditCheckBox.enabled = objectsAreFiducials or landmarksAreFiducials
        
        # Auto-check if enabled and objects are fiducials (original behavior)
        if objectsAreFiducials:
            self.ui.jointEditCheckBox.checked = True

    def onSelect(self):
        self.ui.initializeViewButton.enabled = bool(self.ui.inputSelector1.currentNode() and self.ui.inputSelector2.currentNode())
        
        # Update joint editing availability during selection phase
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        if node1 and node2:
            self.updateJointEditingAvailability()


    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
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
        if not (hasattr(self, 'viewNode1') and hasattr(self, 'viewNode2') and 
                hasattr(self, 'viewNode3') and hasattr(self, 'viewNode4')):
          print("Error: Can not find 4 3d views to link. Please reinitialize views.")
          return
        
        # Get all cameras
        camera1 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode1)
        camera2 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode2)

        logic = QuickAlignLogic()
        
        # Calculate alignment between cameras 1 and 2 (the two superior views)
        camera2ZoomFactor = camera1.GetParallelScale()/camera2.GetParallelScale()
        scalingTransform=vtk.vtkTransform()
        scalingTransform.Scale(camera2ZoomFactor,camera2ZoomFactor,camera2ZoomFactor)
        self.scalingTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "scale transform")
        self.scalingTransformNode.SetMatrixTransformToParent(scalingTransform.GetMatrix())

        # Get alignment transform between the two objects (cameras 1 and 2)
        self.alignmentTransform = logic.getCameraAlignmentTransform(camera1, camera2)
        
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
            dn1 = node1.GetDisplayNode()
            if dn1:
                dn1.SetViewNodeIDs([self.viewNode1.GetID()])
        if node2:
            dn2 = node2.GetDisplayNode()
            if dn2:
                dn2.SetViewNodeIDs([self.viewNode2.GetID()])
        
        # Enable landmark selectors now that sync has started
        self.ui.landmarksSelector1.enabled = True
        self.ui.landmarksSelector2.enabled = True
        
        # Filter landmark selectors to exclude Object 1 and Object 2
        self.filterLandmarkSelectors()
        
        # Apply landmarks if already selected
        self.updateLandmarkDisplay()
        
        layoutManager = slicer.app.layoutManager()
        self.update3DViews()

        # Update joint editing availability after landmarks are applied
        self.updateJointEditingAvailability()
        
        # If joint editing checkbox is enabled and checked, start joint editing
        if self.ui.jointEditCheckBox.enabled and self.ui.jointEditCheckBox.checked:
            node1 = self.ui.inputSelector1.currentNode()
            node2 = self.ui.inputSelector2.currentNode()
            landmarks1 = self.ui.landmarksSelector1.currentNode()
            landmarks2 = self.ui.landmarksSelector2.currentNode()
            
            # Prefer objects if they're fiducials, otherwise use landmarks
            editNode1 = node1 if (node1 and node1.GetNodeTagName() == "MarkupsFiducial") else landmarks1
            editNode2 = node2 if (node2 and node2.GetNodeTagName() == "MarkupsFiducial") else landmarks2
            
            if editNode1 and editNode2:
                self.observerList = logic.startJointMarkupEditing(editNode1, editNode2)
                if self.observerList == []:
                    self.ui.jointEditCheckBox.checked = False

        #set up for unlink action
        self.ui.unlinkButton.enabled = True
        self.ui.linkButton.enabled = False
        self.ui.initializeViewButton.enabled = False
        self.ui.jointEditCheckBox.enabled = False

    def onUnlinkButton(self):
        """
        Run processing when user clicks "Unlink" button.
        """
        self.cleanUpTransformNodes()
        self.ui.unlinkButton.enabled = False
        self.ui.linkButton.enabled = False
        # Disable landmark selectors when not synced
        self.ui.landmarksSelector1.enabled = False
        self.ui.landmarksSelector2.enabled = False
        
        # End joint editing if it was initiated
        if self.ui.jointEditCheckBox.checked and hasattr(self, 'observerList'):
            node1 = self.ui.inputSelector1.currentNode()
            node2 = self.ui.inputSelector2.currentNode()
            landmarks1 = self.ui.landmarksSelector1.currentNode()
            landmarks2 = self.ui.landmarksSelector2.currentNode()
            
            # Determine which nodes were being edited
            editNode1 = node1 if (node1 and node1.GetNodeTagName() == "MarkupsFiducial") else landmarks1
            editNode2 = node2 if (node2 and node2.GetNodeTagName() == "MarkupsFiducial") else landmarks2
            
            if editNode1 and editNode2:
                self.logic.endJointMarkupEditing(editNode1, editNode2, self.observerList)
        
        # unlink all the views
        if hasattr(self, 'viewNode1'):
            self.viewNode1.SetLinkedControl(False)
        if hasattr(self, 'viewNode2'):
            self.viewNode2.SetLinkedControl(False)
        if hasattr(self, 'viewNode3'):
            self.viewNode3.SetLinkedControl(False)
        if hasattr(self, 'viewNode4'):
            self.viewNode4.SetLinkedControl(False)
        
        self.update3DViews()
        self.ui.initializeViewButton.enabled = True
        markupsTypeNodes = bool(node1.GetNodeTagName() == "MarkupsFiducial" and node2.GetNodeTagName() == "MarkupsFiducial")
        self.ui.jointEditCheckBox.enabled = markupsTypeNodes

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
          slicer.mrmlScene.RemoveNode(self.centerNode1Transform)
        if hasattr(self, 'centerNode2Transform'):
          slicer.mrmlScene.RemoveNode(self.centerNode2Transform)
        if hasattr(self, 'alignmentTransform'):
          slicer.mrmlScene.RemoveNode(self.alignmentTransform)
        if hasattr(self, 'scalingTransformNode'):
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

    def hideAllObjectsExcept(self, keepNodes):
        """Hide all models, volumes, and markups except the specified nodes"""
        keepNodeIDs = set([n.GetID() for n in keepNodes if n])
        
        # Hide all models
        models = slicer.util.getNodesByClass('vtkMRMLModelNode')
        for model in models:
            if model.GetID() not in keepNodeIDs:
                dn = model.GetDisplayNode()
                if dn:
                    dn.SetVisibility(False)
        
        # Hide all volumes (scalar and volume rendering)
        volumes = slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')
        for vol in volumes:
            if vol.GetID() not in keepNodeIDs:
                for i in range(vol.GetNumberOfDisplayNodes()):
                    dn = vol.GetNthDisplayNode(i)
                    if dn:
                        dn.SetVisibility(False)
        
        # Hide all markups
        markups = slicer.util.getNodesByClass('vtkMRMLMarkupsNode')
        for markup in markups:
            if markup.GetID() not in keepNodeIDs:
                dn = markup.GetDisplayNode()
                if dn:
                    dn.SetVisibility(False)
    
    def onInitializeViewButton(self):
        self.cleanUpTransformNodes()
        
        # Get selected objects
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        
        # Hide all other objects in the scene
        self.hideAllObjectsExcept([node1, node2])
        
        customLayoutId1=LAYOUT_ID_QUICKALIGN_4VIEW  # Use the 2x2 QuickAlignLayout
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(customLayoutId1)

        #set up 4 3D views
        self.viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        self.viewNode2 = slicer.mrmlScene.GetFirstNodeByName("View2")
        self.viewNode3 = slicer.mrmlScene.GetFirstNodeByName("View3")
        self.viewNode4 = slicer.mrmlScene.GetFirstNodeByName("View4")
        
        # Configure all views
        for viewNode in [self.viewNode1, self.viewNode2, self.viewNode3, self.viewNode4]:
            viewNode.SetAxisLabelsVisible(False)
            viewNode.SetBoxVisible(False)

        #set up selected nodes in views
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
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
                dn.SetViewNodeIDs(desiredViews)
                dn.SetVisibility(True)
              else:
                # Hide other display nodes (slice or scalar) in 3D views; they will still be available in slice viewers if needed
                dn.SetVisibility(False)
          else:
            dn = n.GetDisplayNode()
            if dn:
              dn.SetViewNodeIDs(desiredViews)
              dn.SetVisibility(True)

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
            # Reset the clipping range
            layoutManager = slicer.app.layoutManager()
            threeDWidget = layoutManager.threeDWidget(viewNode)
            if threeDWidget:
                threeDView = threeDWidget.threeDView()
                threeDView.resetFocalPoint()

    # ---- Zoom synchronization helpers ----
    def setupZoomSyncPairs(self):
      self.removeZoomSyncObservers()
      pairs = [
        (self.viewNode1, self.viewNode3),  # object 1 superior & side
        (self.viewNode2, self.viewNode4),  # object 2 superior & side
      ]
      for sourceViewNode, targetViewNode in pairs:
        sourceCamNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(sourceViewNode)
        targetCamNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(targetViewNode)
        if not sourceCamNode or not targetCamNode:
          continue
        # Initial sync of zoom level
        self.copyZoom(sourceCamNode, targetCamNode)
        # Record mapping and add observer
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
    @vtk.calldata_type(vtk.VTK_INT)

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
        if inputNode1.GetNumberOfControlPoints() != inputNode2.GetNumberOfControlPoints():
          print("Error: point lists must have same number of points to enable joint editing.")
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
        try:
          inputNode1.RemoveObserver(observerTags[0])
        except:
          print(f"No tag found for {inputNode1.GetName()}")
        try:
          inputNode2.RemoveObserver(observerTags[1])
        except:
          print(f"No tag found for {inputNode2.GetName()}")

