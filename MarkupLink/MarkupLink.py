import logging
import os

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# MarkupLink
#

class MarkupLink(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "MarkupLink"
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
# MarkupLinkWidget
#

class MarkupLinkWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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

        # Define custom layouts for GPA modules in slicer global namespace
        slicer.customLayoutMarkupLink = """
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
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/MarkupLink.ui'))
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
        self.logic = MarkupLinkLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        #self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        #self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.inputSelector1.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.ui.inputSelector2.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
        self.ui.linkButton.connect('clicked(bool)', self.onLinkButton)
        self.ui.unlinkButton.connect('clicked(bool)', self.onUnlinkButton)

        # Custom Layout button
        self.addLayoutButton(700, 'MarkupLink View', 'Custom layout for MarkupLink module', 'LayoutSlicerMorphView.png', slicer.customLayoutMarkupLink)

    def onSelect(self):
        self.ui.linkButton.enabled = bool(self.ui.inputSelector1.currentNode and self.ui.inputSelector2.currentNode)

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
        self.observerList = self.logic.linkNodes(self.ui.inputSelector1.currentNode(), self.ui.inputSelector2.currentNode())
        self.assignLayoutDescription(self.ui.inputSelector1.currentNode(), self.ui.inputSelector2.currentNode())
        self.ui.unlinkButton.enabled = True
        self.ui.linkButton.enabled = False

    def onUnlinkButton(self):
        """
        Run processing when user clicks "Unlink" button.
        """
        self.logic.unLinkNodes(self.ui.inputSelector1.currentNode(), self.ui.inputSelector1.currentNode(), self.observerList)
        self.ui.unlinkButton.enabled = False
        self.ui.linkButton.enabled = bool(self.ui.inputSelector1.currentNode and self.ui.inputSelector2.currentNode)

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

    def assignLayoutDescription(self, node1, node2):
        customLayoutId1=700
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

        node1.GetDisplayNode().SetViewNodeIDs([viewNode1.GetID()])
        node2.GetDisplayNode().SetViewNodeIDs([viewNode2.GetID()])

#
# MarkupLinkLogic
#

class MarkupLinkLogic(ScriptedLoadableModuleLogic):
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
    def updateinputNode2(self, caller, eventId, callData):
        if not self.updatingNodesActive:
          print(f"PointRemovedEvent: {callData}")
          self.updatingNodesActive = True
          self.node2.RemoveNthControlPoint(callData)
        else:
          self.updatingNodesActive = False

    @vtk.calldata_type(vtk.VTK_INT)
    def updateinputNode1(self, caller, eventId, callData):
        if not self.updatingNodesActive:
          print(f"PointRemovedEvent: {callData}")
          self.updatingNodesActive = True
          self.node1.RemoveNthControlPoint(callData)
        else:
          self.updatingNodesActive = False

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

