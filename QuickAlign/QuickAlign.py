import logging
import os

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import math
import numpy as np

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

    def dotproduct(self, v1, v2):
      return sum((a*b) for a, b in zip(v1, v2))

    def length(self, v):
      return math.sqrt(self.dotproduct(v, v))

    def angle(self, v1, v2):
       dotProductResult = self.dotproduct(v1, v2)
       v1Length = self.length(v1)
       v2Length = self.length(v2)
       return math.acos(dotProductResult / ( v1Length * v2Length))

    def onLinkButton(self):
        """
        Run processing when user clicks "Link" button.
        """
        fixedModel = self.ui.inputSelector1.currentNode()
        movingModel = self.ui.inputSelector2.currentNode()
        self.alignmentTransform = self.tieCameras(movingModel, fixedModel)
        self.ui.unlinkButton.enabled = True
        self.ui.linkButton.enabled = False

    def tieCameras(self, movingModel, templateModel):
      #set layout manager to dual 3d view
      layoutManager = slicer.app.layoutManager()
      layoutManager.setLayout(701)
      if layoutManager.threeDViewCount != 2:
        print("Error: Can not find 2 3d views to link.")
        return

      v1 = layoutManager.threeDWidget(0).threeDView().mrmlViewNode()
      v2 = layoutManager.threeDWidget(1).threeDView().mrmlViewNode()
      c1 = slicer.modules.cameras.logic().GetViewActiveCameraNode(v1)
      c2 = slicer.modules.cameras.logic().GetViewActiveCameraNode(v2)

      #set up the views
      movingModel.GetDisplayNode().SetVisibility(True)
      movingModel.GetDisplayNode().SetViewNodeIDs([v1.GetID()])
      templateModel.GetDisplayNode().SetVisibility(True)
      templateModel.GetDisplayNode().SetViewNodeIDs([v2.GetID()])

      c1Pos = np.array(c1.GetPosition())
      c1View = np.array(c1.GetViewUp())
      c1FocalPoint = np.array(c1.GetFocalPoint())
      c1Angle = np.array(c1.GetViewAngle())

      c2Pos = np.array(c2.GetPosition())
      c2View = np.array(c2.GetViewUp())
      c2FocalPoint = np.array(c2.GetFocalPoint())
      c2Angle = np.array(c2.GetViewAngle())

      # link the views
      v2.SetLinkedControl(True)

      c2Pos2 = np.array(c2.GetPosition())
      c2View2 = np.array(c2.GetViewUp())
      c2FocalPoint2 = np.array(c2.GetFocalPoint())
      c2Angle2 = np.array(c2.GetViewAngle())

      upAngle = self.angle(c1View, c2View) #column 2 (PA)
      v_1 = c1Pos-c1FocalPoint
      v_1=v_1/np.linalg.norm(v_1)
      v_2 = c2Pos-c2FocalPoint
      v_2=v_2/np.linalg.norm(v_2)
      forwardAngle = self.angle(v_1, v_2) #column3 (IS)

      #Apply rotation transform
      transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "alignment transform")
      align=vtk.vtkTransform()
      align.RotateZ(vtk.vtkMath().DegreesFromRadians(forwardAngle))
      align.RotateY(vtk.vtkMath().DegreesFromRadians(upAngle))
      transformNode.SetMatrixTransformToParent(align.GetMatrix())
      movingModel.SetAndObserveTransformNodeID(transformNode.GetID())


      #update camera, get new focal point, create translation transform from original to new focal point
      for threeDViewIndex in range(layoutManager.threeDViewCount) :
        view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
        view.resetFocalPoint()

      #update focal points
      c1FocalPoint = np.array(c1.GetFocalPoint())
      c2FocalPoint = np.array(c2.GetFocalPoint())

      translation = c1FocalPoint - c2FocalPoint
      align.Translate(translation)
      transformNode.SetMatrixTransformToParent(align.GetMatrix())

      #update camera, get new focal point, create translation transform from original to new focal point
      for threeDViewIndex in range(layoutManager.threeDViewCount) :
        view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
        view.resetFocalPoint()

      return transformNode

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

        #link whatever is in the 3D views
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        viewNode2 = slicer.mrmlScene.GetFirstNodeByName("View2")
        viewNode1.SetAxisLabelsVisible(False)
        viewNode2.SetAxisLabelsVisible(False)
        viewNode1.SetBoxVisible(False)
        viewNode2.SetBoxVisible(False)
        viewNode1.SetLinkedControl(True)
        viewNode2.SetLinkedControl(True)

        node1 = self.ui.inputSelector1.currentNode()
        node2 = self.ui.inputSelector2.currentNode()
        volRenLogic = slicer.modules.volumerendering.logic()
        displayNode1 = volRenLogic.CreateDefaultVolumeRenderingNodes(node1)
        displayNode2 = volRenLogic.CreateDefaultVolumeRenderingNodes(node2)
        displayNode1.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName("US-Fetal"))
        displayNode2.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName("US-Fetal"))
        displayNode1.SetVisibility(True)
        displayNode2.SetVisibility(True)
        displayNode1.SetViewNodeIDs([viewNode1.GetID()])
        displayNode2.SetViewNodeIDs([viewNode2.GetID()])
        viewNode1.SetLinkedControl(False)
        viewNode2.SetLinkedControl(False)
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

    def linkNodes(self, inputNode1, inputNode2):
        logging.info('Linking nodes')
        if inputNode1.GetNumberOfControlPoints() != inputNode2.GetNumberOfControlPoints():
          print("Error: point lists must have same number of points to link.")
          return
        self.node1 = inputNode1
        self.node2 = inputNode2
        self.updatingNodesActive = False
        self.node1.SetFixedNumberOfControlPoints(True)
        self.node2.SetFixedNumberOfControlPoints(True)
        observerTag1 = inputNode1.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.updateSelectPoints1)
        observerTag2 = inputNode2.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.updateSelectPoints2)

        return[observerTag1, observerTag2]

    def unLinkNodes(self, inputNode1, inputNode2, observerTags):
        logging.info('Unlinking nodes')
        try:
          inputNode1.RemoveObserver(observerTags[0])
        except:
          print(f"No tag found for {inputNode1.GetName()}")
        try:
          inputNode2.RemoveObserver(observerTags[1])
        except:
          print(f"No tag found for {inputNode2.GetName()}")

