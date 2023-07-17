import logging
import os

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import math
import numpy as np
import scipy.linalg as sp

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
        self.parent.categories = ["Testing.TestCases"]
        self.parent.dependencies = []
        self.parent.contributors = ["Sara Rolfe (SCRI), Murat Maga (SCRI, UW)"]
        self.parent.helpText = """
        This is test module to link two markup nodes for joint editing.
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
        self.ui.initializeViewButton.connect('clicked(bool)', self.onInitializeViewButton)
        self.ui.linkButton.connect('clicked(bool)', self.onLinkButton)
        self.ui.unlinkButton.connect('clicked(bool)', self.onUnlinkButton)

        # Custom Layout button
        self.addLayoutButton(701, 'QuickAlign View', 'Custom layout for QuickAlign module', 'LayoutSlicerMorphView.png', slicer.customLayoutQuickAlign)

    def onSelect(self):
        self.ui.initializeViewButton.enabled = bool(self.ui.inputSelector1.currentNode() and self.ui.inputSelector2.currentNode())

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

    def onLinkButton(self):
        """
        Run processing when user clicks "Link" button.
        """
        if not (hasattr(self, 'viewNode1') and hasattr(self, 'viewNode2')):
          print("Error: Can not find 2 3d views to link. Please reinitialize views.")
          return
        camera1 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode1)
        camera2 = slicer.modules.cameras.logic().GetViewActiveCameraNode(self.viewNode2)

        #get alignment transform between cameras
        logic = QuickAlignLogic()
        self.alignmentTransform = logic.getCameraAlignmentTransform(camera1, camera2)

        #apply to moving node
        movingModel = self.ui.inputSelector2.currentNode()
        movingModel.SetAndObserveTransformNodeID(self.alignmentTransform.GetID())

        #link and update views
        self.viewNode2.SetLinkedControl(True)
        layoutManager = slicer.app.layoutManager()
        for threeDViewIndex in range(layoutManager.threeDViewCount) :
          view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
          view.resetFocalPoint()

        #set up for unlink action
        self.ui.unlinkButton.enabled = True
        self.ui.linkButton.enabled = False

    def onUnlinkButton(self):
        """
        Run processing when user clicks "Unlink" button.
        """
        slicer.mrmlScene.RemoveNode(self.alignmentTransform)
        self.ui.unlinkButton.enabled = False
        self.ui.linkButton.enabled = bool(self.ui.inputSelector1.currentNode and self.ui.inputSelector2.currentNode)
        # unlink the views
        layoutManager = slicer.app.layoutManager()
        v1 = layoutManager.threeDWidget(0).threeDView().mrmlViewNode()
        v1.SetLinkedControl(False)

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

    def onInitializeViewButton(self):
        customLayoutId1=701
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(customLayoutId1)

        #set up 2 unlinked 3D views
        self.viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        self.viewNode2 = slicer.mrmlScene.GetFirstNodeByName("View2")
        self.viewNode1.SetAxisLabelsVisible(False)
        self.viewNode2.SetAxisLabelsVisible(False)
        self.viewNode1.SetBoxVisible(False)
        self.viewNode2.SetBoxVisible(False)

        #set up selected nodes in views
        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        volRenLogic = slicer.modules.volumerendering.logic()
        displayNode1 = volRenLogic.CreateDefaultVolumeRenderingNodes(node1)
        displayNode2 = volRenLogic.CreateDefaultVolumeRenderingNodes(node2)
        displayNode1.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName("US-Fetal"))
        displayNode2.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName("US-Fetal"))
        displayNode1.SetVisibility(True)
        displayNode2.SetVisibility(True)
        displayNode1.SetViewNodeIDs([self.viewNode1.GetID()])
        displayNode2.SetViewNodeIDs([self.viewNode2.GetID()])
        self.viewNode1.SetLinkedControl(False)
        self.viewNode2.SetLinkedControl(False)
        self.ui.linkButton.enabled = True

        #update camera
        for threeDViewIndex in range(layoutManager.threeDViewCount) :
          view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
          view.resetFocalPoint()

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

