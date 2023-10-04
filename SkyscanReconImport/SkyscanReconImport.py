import SimpleITK as sitk
import sitkUtils
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
import string
#
# SkyscanReconImport
#

class SkyscanReconImport(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SkyscanReconImport" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Input and Output"]
    self.parent.dependencies = []
    self.parent.contributors = ["Murat Maga (UW), Sara Rolfe (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module imports an image sequence from Bruker Skyscan microCT's into Slicer as a scalar 3D volume with correct image spacing. Accepted formats are TIF, PNG, JPG and BMP.
User needs to be point out to the *_Rec.log file found in the reconstruction folder.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.

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

  # TemplateKey1
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey1',
    # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
    # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey1.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
    fileNames='TemplateKey1.nrrd',
    # Checksum to ensure file integrity. Can be computed by this command:
    #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
    checksums = 'SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey1'
  )

  # TemplateKey2
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='TemplateKey',
    sampleName='TemplateKey2',
    thumbnailFileName=os.path.join(iconsPath, 'TemplateKey2.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
    fileNames='TemplateKey2.nrrd',
    checksums = 'SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
    # This node name will be used when the data set is loaded
    nodeNames='TemplateKey2'
  )


#
# SkyscanReconImportWidget
#

class SkyscanReconImportWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    # Set up tabs to split workflow
    tabsWidget = qt.QTabWidget()
    singleTab = qt.QWidget()
    singleTabLayout = qt.QFormLayout(singleTab)
    batchTab = qt.QWidget()
    batchTabLayout = qt.QFormLayout(batchTab)

    tabsWidget.addTab(singleTab, "Single Image Import")
    tabsWidget.addTab(batchTab, "Batch Import")
    self.layout.addWidget(tabsWidget)
    
    # Single Image Import Tab

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    #self.layout.addWidget(parametersCollapsibleButton)
    singleTabLayout.addRow(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input selector
    #
    # File dialog to select a file template for series
    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.filters  = ctk.ctkPathLineEdit().Files
    self.inputFileSelector.setToolTip( "Select log file from a directory of images." )
    parametersFormLayout.addRow("Select log file from image series:", self.inputFileSelector)

    #
    # Encoding Selector
    #
    self.defaultCodingButton = qt.QRadioButton("Default")
    self.defaultCodingButton.checked = True
    self.utf8CodingButton = qt.QRadioButton("Utf-8")
    self.latin1CodingButton = qt.QRadioButton("Latin-1")
    self.encodingSelector = qt.QVBoxLayout()
    self.encodingSelector.addWidget(self.defaultCodingButton)
    self.encodingSelector.addWidget(self.utf8CodingButton)
    self.encodingSelector.addWidget(self.latin1CodingButton)
    parametersFormLayout.addRow("Select log file encoding type: ", self.encodingSelector)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    #self.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.inputFileSelector.connect("currentPathChanged(const QString &)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

    # Batch Import Tab

    #
    # Parameters Area
    #
    parametersBatchCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersBatchCollapsibleButton.text = "Parameters"
    batchTabLayout.addRow(parametersBatchCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersBatchFormLayout = qt.QFormLayout(parametersBatchCollapsibleButton)

    #
    # File path box
    #
    self.filepathBox = qt.QTextEdit()
    parametersBatchFormLayout.addRow("Enter paths to log files: ", self.filepathBox)
    
    #
    # Output selector
    #
    # File dialog to select output directory for images
    self.outputFileSelector = ctk.ctkPathLineEdit()
    self.outputFileSelector.filters  = ctk.ctkPathLineEdit().Dirs
    self.outputFileSelector.setToolTip( "Select directory where images will be exported." )
    parametersBatchFormLayout.addRow("Select output directory:", self.outputFileSelector)
    #
    # Encoding Selector
    #    
    self.defaultCodingBatchButton = qt.QRadioButton("Default")
    self.defaultCodingBatchButton.checked = True
    self.utf8CodingBatchButton = qt.QRadioButton("Utf-8")
    self.latin1CodingBatchButton = qt.QRadioButton("Latin-1")
    self.encodingBatchSelector = qt.QVBoxLayout()
    self.encodingBatchSelector.addWidget(self.defaultCodingBatchButton)
    self.encodingBatchSelector.addWidget(self.utf8CodingBatchButton)
    self.encodingBatchSelector.addWidget(self.latin1CodingBatchButton)
    parametersBatchFormLayout.addRow("Select log file encoding type: ", self.encodingBatchSelector)
    
    #
    # Apply Button
    #
    self.applyBatchButton = qt.QPushButton("Apply")
    self.applyBatchButton.toolTip = "Run the algorithm."
    self.applyBatchButton.enabled = False
    parametersBatchFormLayout.addRow(self.applyBatchButton)

    

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = bool(self.inputFileSelector.currentPath)


  def onApplyButton(self):
    logic = SkyscanReconImportLogic()
    if self.defaultCodingButton.checked:
      encodingType = ""
    elif self.utf8CodingButton.checked:
      encodingType = "utf8"
    else:
      encodingType = "ISO-8859-1"
    logic.run(self.inputFileSelector.currentPath, encodingType)


class LogDataObject:
  """This class i
     """
  def __init__(self):
    self.FileType = "NULL"
    self.X  = "NULL"
    self.Y = "NULL"
    self.Z = "NULL"
    self.Resolution = "NULL"
    self.Prefix = "NULL"
    self.IndexLength = "NULL"
    self.SequenceStart = "NULL"
    self.SequenceEnd = "NULL"

  def ImportFromFile(self, LogFilename, encodingType):
    lines = []       #Declare an empty list to read file into
    with open (LogFilename, encoding= encodingType) as in_file:
      for line in in_file:
        lines.append(line.strip("\n"))     # add that line list, get rid of line endings
      for element in lines:  # For each element in list
        if(element.find("Result File Type=")>=0):
          self.FileType = element.split('=', 1)[1].lower()  #get standard lowercase
          print(self.FileType)
          print(element.split('=', 1)[1])
        if(element.find("Result Image Width (pixels)=")>=0):
          self.X = int(element.split('=', 1)[1])
        if(element.find("Result Image Height (pixels)=")>=0):
          self.Y = int(element.split('=', 1)[1])
        if(element.find("Sections Count=")>=0):
          self.Z = int(element.split('=', 1)[1])
        if(element.find("Pixel Size (um)=")>=0):
          self.Resolution = float(element.split('=', 1)[1])/1000 #convert from um to mm
        if(element.find("Filename Prefix=")>=0):
          self.Prefix = element.split('=', 1)[1]
        if(element.find("Filename Index Length=")>=0):
          self.IndexLength = element.split('=', 1)[1]
        if(element.find("First Section=")>=0):
          self.SequenceStart = element.split('=', 1)[1]
        if(element.find("Last Section=")>=0):
          self.SequenceEnd = element.split('=', 1)[1]
    self.SequenceStart=self.SequenceStart.zfill(int(self.IndexLength)) #pad with zeros to index length
    self.SequenceEnd=self.SequenceEnd.zfill(int(self.IndexLength)) #pad with zeros to index length

  def VerifyParameters(self):
    for attr, value in self.__dict__.items():
        if(str(value) == "NULL"):
          logging.debug("Read Failed: Please check log format")
          logging.debug(attr,value)
          return False
    return True

#
# SkyscanReconImportLogic
#
class SkyscanReconImportLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def isValidImageFileType(self, extension):
    """Checks for extensions from valid image types
    """
    if not extension in ('tif', 'bmp', 'jpg', 'png', 'tiff', 'jpeg'):
      logging.debug('isValidImageFileType failed: not a supported image type')
      return False
    return True

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def applySkyscanTransform(self, volumeNode):
    #set up transform node
    transformNode = slicer.vtkMRMLTransformNode()
    slicer.mrmlScene.AddNode(transformNode)
    volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

    #set up Skyscan transform
    transformMatrixNp  = np.array([[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]])
    transformMatrixVTK = vtk.vtkMatrix4x4()
    for row in range(4):
      for col in range(4):
        transformMatrixVTK.SetElement(row, col, transformMatrixNp[row,col])

    transformNode.SetMatrixTransformToParent(transformMatrixVTK)

    #harden and clean up
    slicer.vtkSlicerTransformLogic().hardenTransform(volumeNode)
    slicer.mrmlScene.RemoveNode(transformNode)

  def run(self, inputFile, encodingType):
    """
    Run the actual algorithm
    """
    #parse logfile
    logging.info('Processing started')
    imageLogFile = LogDataObject()   #initialize log object
    imageLogFile.ImportFromFile(inputFile, encodingType)  #import image parameters of log object

    if not(imageLogFile.VerifyParameters()): #check that all parameters were set
      logging.info('Failed: Log file parameters not set')
      return False
    if not(self.isValidImageFileType(imageLogFile.FileType)): #check for valid file type
      logging.info('Failed: Invalid image type')
      logging.info(imageLogFile.FileType)
      return False

    # read image
    (inputDirectory,logPath) = os.path.split(inputFile)
    imageFileTemplate = os.path.join(inputDirectory, imageLogFile.Prefix + imageLogFile.SequenceStart + "." + imageLogFile.FileType)
    readVolumeNode = slicer.util.loadVolume(imageFileTemplate)
    #calculate image spacing
    spacing = [imageLogFile.Resolution, imageLogFile.Resolution, imageLogFile.Resolution]

    # if vector image, convert to scalar using luminance (0.30*R + 0.59*G + 0.11*B + 0.0*A)
    #check if loaded volume is vector type, if so convert to scalar
    if readVolumeNode.GetClassName() =='vtkMRMLVectorVolumeNode':
      scalarVolumeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode', imageLogFile.Prefix)
      ijkToRAS = vtk.vtkMatrix4x4()
      readVolumeNode.GetIJKToRASMatrix(ijkToRAS)
      scalarVolumeNode.SetIJKToRASMatrix(ijkToRAS)

      scalarVolumeNode.SetSpacing(spacing)
      extractVTK = vtk.vtkImageExtractComponents()
      extractVTK.SetInputConnection(readVolumeNode.GetImageDataConnection())
      extractVTK.SetComponents(0, 1, 2)
      luminance = vtk.vtkImageLuminance()
      luminance.SetInputConnection(extractVTK.GetOutputPort())
      luminance.Update()
      scalarVolumeNode.SetImageDataConnection(luminance.GetOutputPort()) # apply
      slicer.mrmlScene.RemoveNode(readVolumeNode)

    else:
      scalarVolumeNode = readVolumeNode
      scalarVolumeNode.SetSpacing(spacing)
      scalarVolumeNode.SetName(imageLogFile.Prefix)

    self.applySkyscanTransform(scalarVolumeNode)
    slicer.util.resetSliceViews() #update the field of view

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


class SkyscanReconImportTest(ScriptedLoadableModuleTest):
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
    self.test_SkyscanReconImport1()

  def test_SkyscanReconImport1(self):
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

    logic = SkyscanReconImportLogic()

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
