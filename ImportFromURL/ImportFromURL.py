import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import fnmatch

import re
import csv
import SampleData
#
# ImportFromURL
#

class ImportFromURL(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ImportFromURL" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
      This module imports data from a URL into the scene. This module requires the URL to reference a single file and the filename to be contained in the URL.

      """
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """ # replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#


#
# ImportFromURLWidget
#

class ImportFromURLWidget(ScriptedLoadableModuleWidget):
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
    parametersCollapsibleButton.text = "Input Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Input URL
    #
    self.InputURLText = qt.QLineEdit()
    self.InputURLText.setToolTip("Copy and paste the URL in this box")
    parametersFormLayout.addRow("URL: ", self.InputURLText)

    #
    # File Names
    #
    self.FileNameText = qt.QLineEdit()
    self.FileNameText.setToolTip("Enter the file name")
    parametersFormLayout.addRow("File name: ", self.FileNameText)

    #
    # Node Names
    #
    self.NodeNameText = qt.QLineEdit()
    self.NodeNameText.setToolTip("Enter the node names")
    parametersFormLayout.addRow("Node name: ", self.NodeNameText)

    #
    # Import button
    #
    self.ImportButton = qt.QPushButton("Import data")
    self.ImportButton.toolTip = "Import data from URL"
    self.ImportButton.enabled = False
    parametersFormLayout.addRow(self.ImportButton)

    # Connections
    self.InputURLText.connect('textChanged(const QString &)', self.onEnterURL)
    self.ImportButton.connect('clicked(bool)', self.onImport)

  def onEnterURL(self):
    url = self.InputURLText.text
    self.ImportButton.enabled = bool(url)
    base = os.path.basename(url)
    fileName = base.split('?')[0]
    nodeName = fileName.split('.')[0]
    self.FileNameText.text = fileName
    self.NodeNameText.text = nodeName


  def onImport(self):
    logic = ImportFromURLLogic()
    try:
      logic.runImport(self.InputURLText.text, self.FileNameText.text, self.NodeNameText.text)
    except:
      logging.debug('Could not import data. Please confirm that the URL and file name is valid.')


class ImportFromURLLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """
  def runImport(self, url, fileNames, nodeNames):
    loadFileProperties={}
    filename, extension = os.path.splitext(fileNames)
    if(extension in ['.zip']):
      fileTypes = 'ZipFile'
    elif(extension in ['.mrb'] ):
      fileTypes = 'SceneFile'
    elif(extension in ['.dcm', '.nrrd', '.nii', '.mhd', '.mha', '.hdr', '.img', '.bmp', '.jpg', '.jpeg', '.png', '.tif', '.tiff']):
      if '.seg' in filename:
        fileTypes = 'SegmentationFile'
      else:
        fileTypes = 'VolumeFile'
        if '-label' in filename:
          loadFileProperties["labelmap"] = True
    elif(extension == '.gz'):
      subfilename, subextension = os.path.splitext(filename)
      if subextension == '.nii':
        if '.seg' in filename:
          fileTypes = 'SegmentationFile'
        else:
          fileTypes = 'VolumeFile'
          if '-label' in filename:
            loadFileProperties["labelmap"] = True
        fileTypes = 'VolumeFile'
      else:
        logging.debug('Could not download data. Not a supported file type.')
    elif(extension in ['.vtk', '.vtp', '.obj', '.ply', '.stl'] ):
      fileTypes = 'ModelFile'
    elif(extension in ['.fcsv', '.json'] ):
      fileTypes = 'MarkupsFile'
    else:
      logging.debug('Could not download data. Not a supported file type.')

    sampleDataLogic = SampleData.SampleDataLogic()
    url=self.processUrl(url)
    loadedNodes = sampleDataLogic.downloadFromURL(
    nodeNames= nodeNames,
    fileNames= fileNames,
    loadFileTypes=fileTypes,
    loadFiles = True,
    loadFileProperties = loadFileProperties,
    uris= url)

    # Check if download from URL returned a node collection. If not, then file was downloaded but not imported.
    if isinstance(loadedNodes[0], str):
      logging.debug('Could not import data into the scene. Downloaded to: ' + loadedNodes[0])
    elif fileTypes == 'VolumeFile':
      self.autoRenderVolume(loadedNodes[0])

  def processUrl(self, url):
    # Apply DropBox and GitHub specific URL fixes if needed
    if "www.dropbox.com" in url:
      url=url.replace("www.dropbox.com", "dl.dropbox.com")
      url=url.split('?')[0]
    if "github.com" in url:
      url=url.replace("github.com", "raw.githubusercontent.com")
      url=url.replace("/blob", "")
      url=url.split('?')[0]
    return url

  def autoRenderVolume(self, volumeNode):
    print("Auto-render node: "+volumeNode.GetName())
    volRenLogic = slicer.modules.volumerendering.logic()
    displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
    displayNode.SetVisibility(True)
    scalarRange = volumeNode.GetImageData().GetScalarRange()
    if scalarRange[1]-scalarRange[0] < 1500:
      # small dynamic range, probably MRI
      displayNode.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName('MR-Default'))
    else:
      # larger dynamic range, probably CT
      displayNode.GetVolumePropertyNode().Copy(volRenLogic.GetPresetByName('CT-Chest-Contrast-Enhanced'))

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


class ImportFromURLTest(ScriptedLoadableModuleTest):
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
    self.test_ImportFromURL1()

  def test_ImportFromURL1(self):
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

    logic = ImportFromURLLogic()

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
