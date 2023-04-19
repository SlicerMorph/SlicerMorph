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
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#MarkupLink">module documentation</a>.
"""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

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

    # MarkupLink1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='MarkupLink',
        sampleName='MarkupLink1',
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, 'MarkupLink1.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames='MarkupLink1.nrrd',
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums='SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
        # This node name will be used when the data set is loaded
        nodeNames='MarkupLink1'
    )

    # MarkupLink2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='MarkupLink',
        sampleName='MarkupLink2',
        thumbnailFileName=os.path.join(iconsPath, 'MarkupLink2.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames='MarkupLink2.nrrd',
        checksums='SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
        # This node name will be used when the data set is loaded
        nodeNames='MarkupLink2'
    )


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
        #observerTag1 = inputNode1.AddObserver(slicer.vtkMRMLMarkupsNode.PointRemovedEvent, self.updateinputNode2)
        #observerTag2 = inputNode2.AddObserver(slicer.vtkMRMLMarkupsNode.PointRemovedEvent, self.updateinputNode1)
        
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


#
# MarkupLinkTest
#

class MarkupLinkTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_MarkupLink1()

    def test_MarkupLink1(self):
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
        inputVolume = SampleData.downloadSample('MarkupLink1')
        self.delayDisplay('Loaded test data set')

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = MarkupLinkLogic()

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
