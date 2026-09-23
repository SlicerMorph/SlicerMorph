import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# IDAVLMConverter
#

class IDAVLMConverter(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "IDAVLMConverter" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Murat Maga (UW), Sara Rolfe (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module converts raw landmark coordinates (.pts format) exported from the IDAV Landmark Editor into fcsv format.
It does not accept the Landmark Editor's project files (.land format).
<p>For more information about usage and potential issues, please see <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/IDAVLMConverter">online documentation.</A>
"""
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

#
# IDAVLMConverterWidget
#

class IDAVLMConverterWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Select landmark file to import
    #
    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.filters  = ctk.ctkPathLineEdit().Files
    self.inputFileSelector.setToolTip( "Select landmark file for import" )
    parametersFormLayout.addRow("Select file containing landmark names and coordinates to load:", self.inputFileSelector)

    #
    # output directory selector
    #
    self.outputDirectory = ctk.ctkDirectoryButton()
    self.outputDirectory.directory = slicer.mrmlScene.GetCacheManager().GetRemoteCacheDirectory()
    parametersFormLayout.addRow("Output Directory:", self.outputDirectory)

    #
    # Get header length
    #
    self.headerLengthWidget = ctk.ctkDoubleSpinBox()
    self.headerLengthWidget.value = 2
    self.headerLengthWidget.minimum = 0
    self.headerLengthWidget.singleStep = 1
    self.headerLengthWidget.setToolTip("Input the number of lines in header")
    parametersFormLayout.addRow("Header length:", self.headerLengthWidget)

    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.loadLandmarkNode = qt.QCheckBox()
    self.loadLandmarkNode.checked = 0
    self.loadLandmarkNode.setToolTip("After conversion, load landmarks into the scene.")
    parametersFormLayout.addRow("Load landmarks into scene", self.loadLandmarkNode)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputFileSelector.connect('validInputChanged(bool)', self.onSelect)


    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = bool(self.inputFileSelector.currentPath)

  def onApplyButton(self):
    logic = IDAVLMConverterLogic()
    loadFileOption = self.loadLandmarkNode.checked
    logic.run(self.inputFileSelector.currentPath, self.outputDirectory.directory, self.headerLengthWidget.value, loadFileOption)

#
# IDAVLMConverterLogic
#

class IDAVLMConverterLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def run(self, landmarkFilePath, outputDirectory, headerSize, loadFileOption):
    """
    Run the actual algorithm
    """
    # set landmark filename and length of header
    headerSize = 2  #number of lines in the header
    landmarkFileName = os.path.basename(landmarkFilePath)
    (landmarkFileBase, ext) = os.path.splitext(landmarkFileName)


    # Create a markups node for imported points
    fiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
    slicer.mrmlScene.AddNode(fiducialNode)
    fiducialNode.CreateDefaultDisplayNodes()
    fiducialNode.SetName(landmarkFileBase)

    # read landmarks
    landmarkFile = open(landmarkFilePath)
    lines = landmarkFile.readlines()
    landmarkFile.close()

    #iterate through list of and place in markups node
    for i in range(headerSize,len(lines)-1):
      # in this file format, lines contain [name, x-coordinate, y-coordinate, z-coordinate]
      # by default, split command splits by whitespace
      lineData = lines[i].split()
      if len(lineData) == 4:
        coordinates = [float(lineData[1]), float(lineData[2]), float(lineData[3])]
        name = lineData[0]
        fiducialNode.AddFiducialFromArray(coordinates, name)
      else:
        logging.debug("Error: not a supported landmark file format")

    outputPath = os.path.join(outputDirectory, landmarkFileBase + '.fcsv')
    slicer.util.saveNode(fiducialNode, outputPath)
    if not loadFileOption:
      slicer.mrmlScene.RemoveNode(fiducialNode)  #remove node from scene

    logging.info('Processing completed')

    return True

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


class IDAVLMConverterTest(ScriptedLoadableModuleTest):
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
    self.test_IDAVLMConverter1()

  def test_IDAVLMConverter1(self):
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

    logic = IDAVLMConverterLogic()

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
