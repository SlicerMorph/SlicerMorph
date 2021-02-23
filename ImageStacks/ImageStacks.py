import os
import unittest
import math
import numpy
import vtk, qt, ctk, slicer
import SimpleITK as sitk
from slicer.ScriptedLoadableModule import *
import logging

#
# ImageStacks
#

class ImageStacks(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ImageStacks" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Input and Output"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module allows you to import stacks of images, such as png, jpg, or tiff, as Slicer scalar
volumes by resampling slice by slice during the input process.  This can allow you to import
much larger volumes because you don't need to load the whole volume before downsampling.
<p>
You can select files by drag-and-dropping folders or files to the application screen and choosing
"Load files using ImageStacks module", or using "Browse for files..." button to select a block of files, or by selecting
a single filename or filename pattern.
<p>
An example single filename would be /opt/data/image-0001.png in which case
it would match image-0002.png, image-0003.png, etc.  You can also type a filename pattern string
using <a href="https://www.cplusplus.com/reference/cstdio/scanf/">scanf formatting</a>,
such as image-%04d.png.  Archetype lists can start from zero or one, or
from the number detected in the selected archetype.
<p>
The module can also apply voxel spacing information and the final voxel spacing is compute according to
downsampling and frame skipping options.
<p>
For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ImageStacks">online documentation</a>.</p>
"""
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This module was developed by Steve Pieper, Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.

#
# ImageStacksWidget
#

class ImageStacksWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModuleWidget.__init__(self,parent)
    self.logic = ImageStacksLogic()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...


    #
    # File area
    #
    filesCollapsibleButton = ctk.ctkCollapsibleButton()
    filesCollapsibleButton.text = "Input files"
    filesCollapsibleButton.collapsed = False
    self.layout.addWidget(filesCollapsibleButton)
    # Layout within the files collapsible button
    filesFormLayout = qt.QFormLayout(filesCollapsibleButton)

    # select one file
    buttonLayout = qt.QHBoxLayout()
    self.archetypeLabel = qt.QLabel("Filename pattern: ")
    buttonLayout.addWidget(self.archetypeLabel)
    self.archetypeText = qt.QLineEdit()
    buttonLayout.addWidget(self.archetypeText)
    self.addFromArchetype = qt.QPushButton("Browse...")
    buttonLayout.addWidget(self.addFromArchetype)
    filesFormLayout.addRow(buttonLayout)
    self.archetypeStartNumber = 0

    # select a range of files
    buttonLayout = qt.QHBoxLayout()
    self.addByBrowsingButton = qt.QPushButton("Browse for files...")
    self.clearButton = qt.QPushButton("Clear")
    buttonLayout.addWidget(self.addByBrowsingButton)
    buttonLayout.addWidget(self.clearButton)
    filesFormLayout.addRow(buttonLayout)

    # file table
    self.fileModel = qt.QStandardItemModel()
    self.fileTable = qt.QTableView()
    self.fileTable.horizontalHeader().stretchLastSection = True
    self.fileTable.horizontalHeader().visible = False
    self.fileTable.setModel(self.fileModel)
    filesFormLayout.addRow(self.fileTable)

    # properties area for feedback
    self.propertiesLabel = qt.QLabel()
    filesFormLayout.addRow(self.propertiesLabel)

    # spacing
    self.spacing = slicer.qMRMLCoordinatesWidget()

    self.spacing.decimalsOption  = ctk.ctkDoubleSpinBox.DecimalsByKey | ctk.ctkDoubleSpinBox.DecimalsByShortcuts | ctk.ctkDoubleSpinBox.DecimalsByValue
    self.spacing.minimum = 0.0
    self.spacing.maximum = 1000000000.0
    self.spacing.quantity = "length"
    self.spacing.unitAwareProperties = slicer.qMRMLCoordinatesWidget.Precision | slicer.qMRMLCoordinatesWidget.Prefix | slicer.qMRMLCoordinatesWidget.Scaling | slicer.qMRMLCoordinatesWidget.Suffix

    self.spacing.decimals = 8
    self.spacing.coordinates = "1,1,1"
    self.spacing.toolTip = "Set the colunm, row, slice spacing in mm; original spacing not including downsample"
    filesFormLayout.addRow("Spacing: ", self.spacing)

    #
    # output area
    #
    outputCollapsibleButton = ctk.ctkCollapsibleButton()
    outputCollapsibleButton.text = "Output"
    outputCollapsibleButton.collapsed = False
    self.layout.addWidget(outputCollapsibleButton)
    outputFormLayout = qt.QFormLayout(outputCollapsibleButton)

    #
    # output volume selector
    #
    self.outputSelector = slicer.qMRMLNodeComboBox()

    self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode",]

    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.showHidden = False
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.selectNodeUponCreation = True
    self.outputSelector.noneEnabled = True
    self.outputSelector.removeEnabled = True
    self.outputSelector.renameEnabled = True
    self.outputSelector.addEnabled = True
    self.outputSelector.noneDisplay = "(Create new volume)"
    self.outputSelector.setMRMLScene( slicer.mrmlScene )
    self.outputSelector.setToolTip( "Pick the output volume to populate or None to autogenerate." )
    outputFormLayout.addRow("Output Volume: ", self.outputSelector)

    self.downsample = qt.QCheckBox()
    self.downsample.toolTip = "Reduces data size by half in each dimension by skipping every other pixel and slice (uses about 1/8 memory)"
    outputFormLayout.addRow("Downsample: ", self.downsample)

    self.reverse = qt.QCheckBox()
    self.reverse.toolTip = "Read the images in reverse order"
    outputFormLayout.addRow("Reverse: ", self.reverse)

    self.sliceSkip = ctk.ctkDoubleSpinBox()
    self.sliceSkip.decimals = 0
    self.sliceSkip.minimum = 0
    self.sliceSkip.toolTip = "Skips the selected number of slices between each pair of output volume slices (use, for example, on long thin samples with more slices than in-plane resolution)"
    outputFormLayout.addRow("Slice skip: ", self.sliceSkip)

    self.loadButton = qt.QPushButton("Load files")
    self.loadButton.toolTip = "Populate the file list above using either the Browse for files or Select archetype buttons to enable this button"
    self.loadButton.enabled = False
    outputFormLayout.addRow(self.loadButton)

    # connections
    self.addByBrowsingButton.connect('clicked()', self.addByBrowsing)
    self.addFromArchetype.connect('clicked()', self.selectArchetype)
    self.archetypeText.connect('textChanged(const QString &)', self.populateFromArchetype)
    self.clearButton.connect('clicked()', self.onClear)
    self.loadButton.connect('clicked()', self.onLoadButton)

    # Add vertical spacer
    self.layout.addStretch(1)

    self.loadButton.enabled = False

  def cleanup(self):
    pass

  def updateFileProperties(self, properties):
    text = ""
    for prop in properties:
      text += f"{prop}: {properties[prop]}\n"
    text = text[:-1]
    self.propertiesLabel.text = text

  def onClear(self):
    self.fileTable.model().clear()
    self.updateFileProperties({})
    self.outputSelector.currentNodeID = ""
    self.loadButton.enabled = False

  def addByBrowsing(self):
    filePaths = qt.QFileDialog().getOpenFileNames()
    self.addFilePaths(filePaths)

  def addFilePaths(self, filePaths):
    for filePath in filePaths:
      item = qt.QStandardItem()
      item.setText(filePath)
      self.fileModel.setItem(self.fileModel.rowCount(), 0, item)
    self.loadButton.enabled = filePaths != []
    properties = self.logic.calculateProperties(filePaths)
    self.updateFileProperties(properties)
    self.updateSpacingFromFilePaths(filePaths)

  def updateSpacingFromFilePaths(self, filePaths):
    if not filePaths:
      return
    spacing = self.logic.getImageSpacing(filePaths[0])
    if not spacing:
      return
    if spacing[0] == spacing[1]:
      # If x and y spacing are the same then we assume that it is an isotropic volume
      # and set z spacing to the same value
      spacingZ = spacing[0]
    else:
      spacingZ = 1.0
    self.spacing.coordinates = f"{spacing[0]},{spacing[1]},{spacingZ}"

  def selectArchetype(self):
    filePath = qt.QFileDialog().getOpenFileName()
    self.archetypeText.text = filePath

  def populateFromArchetype(self):
    """
    User selects a file like "/opt/data/image-0001.tif" and
    this will populate the file list with all files that match
    the numbering pattern in that directory
    """
    self.onClear()
    filePath = self.archetypeText.text
    if filePath.find('%') == -1:
      index = len(filePath) -1
      while index > 0 and (filePath[index] < '0' or filePath[index] > '9'):
        index -= 1
      numberEndIndex = index
      while index > 0 and filePath[index] >= '0' and filePath[index] <= '9':
        index -= 1
      if index <= 0:
        return
      numberStartIndex = index+1
      if filePath[numberStartIndex] == '0':
        formatString = f"%0{numberEndIndex-numberStartIndex+1}d"
      else:
        formatString = "%d"
      archetypeFormat = filePath[:numberStartIndex] + formatString + filePath[numberEndIndex+1:]
      candidateStartNumber = int(filePath[numberStartIndex:numberEndIndex+1])
      while os.path.exists(archetypeFormat % candidateStartNumber):
        candidateStartNumber -= 1
      self.archetypeStartNumber = candidateStartNumber + 1
    else:
      archetypeFormat = filePath
    fileIndex = self.archetypeStartNumber
    filePaths = []
    while True:
      filePath = archetypeFormat % fileIndex
      if os.path.exists(filePath):
        item = qt.QStandardItem()
        item.setText(filePath)
        self.fileModel.setItem(self.fileModel.rowCount(), 0, item)
        filePaths.append(filePath)
      else:
        if fileIndex != 0:
          break
      fileIndex += 1
    self.loadButton.enabled = filePaths != []
    properties = self.logic.calculateProperties(filePaths)
    self.updateFileProperties(properties)
    self.updateSpacingFromFilePaths(filePaths)
    self.archetypeText.text = archetypeFormat

  def currentNode(self):
    # TODO: this should be moved to qMRMLSubjectHierarchyComboBox::currentNode()
    if self.outputSelector.className() == "qMRMLSubjectHierarchyComboBox":
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      selectedItem = self.outputSelector.currentItem()
      outputNode = shNode.GetItemDataNode(selectedItem)
    else:
      return self.outputSelector.currentNode()

  def setCurrentNode(self, node):
    if self.outputSelector.className() == "qMRMLSubjectHierarchyComboBox":
      # not sure how to select in the subject hierarychy
      pass
    else:
      self.outputSelector.setCurrentNode(node)

  def onLoadButton(self):
    paths = []
    for row in range(self.fileModel.rowCount()):
      item = self.fileModel.item(row)
      paths.append(item.text())

    properties = {}
    spacingString = self.spacing.coordinates
    properties['spacing'] = [float(element) for element in spacingString.split(",")]
    properties['downsample'] = self.downsample.checked
    properties['reverse'] = self.reverse.checked
    properties['sliceSkip'] = self.sliceSkip.value
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
      outputNode = self.logic.loadByPaths(paths, self.currentNode(), properties)
      self.setCurrentNode(outputNode)
      qt.QApplication.restoreOverrideCursor()
    except Exception as e:
      qt.QApplication.restoreOverrideCursor()
      message, _, details = str(e).partition('\nDetails:\n')
      slicer.util.errorDisplay("Loading failed: " + message, detailedText=details)
      import traceback
      traceback.print_exc()

#
# File dialog to allow drag-and-drop of folders and files
#
class ImageStacksFileDialog(object):
  """This specially named class is detected by the scripted loadable
  module and is the target for optional drag and drop operations.
  See: Base/QTGUI/qSlicerScriptedFileDialog.h
  and commit http://svn.slicer.org/Slicer4/trunk@21951 and issue #3081
  """

  def __init__(self,qSlicerFileDialog):
    self.qSlicerFileDialog = qSlicerFileDialog
    qSlicerFileDialog.fileType = 'Image stack'
    qSlicerFileDialog.description = 'Load files using ImageStacks module'
    qSlicerFileDialog.action = slicer.qSlicerFileDialog.Read
    self.filesToAdd = []

  def execDialog(self):
    """Not used"""
    logging.debug('execDialog called on %s' % self)

  def isMimeDataAccepted(self):
    """Checks the dropped data and returns true if it is one or
    more directories"""
    self.filesToAdd = ImageStacksFileDialog.pathsFromMimeData(self.qSlicerFileDialog.mimeData())
    self.qSlicerFileDialog.acceptMimeData(len(self.filesToAdd) != 0)

  @staticmethod
  def pathsFromMimeData(mimeData):
    filesToAdd = []
    acceptedFileExtensions = ['jpg', 'jpeg', 'tif', 'tiff', 'png', 'bmp']
    if mimeData.hasFormat('text/uri-list'):
      urls = mimeData.urls()
      for url in urls:
        localPath = url.toLocalFile() # convert QUrl to local path
        pathInfo = qt.QFileInfo()
        pathInfo.setFile(localPath) # information about the path
        if pathInfo.isDir(): # if it is a directory we add the files to the dialog
          directory = qt.QDir(localPath)
          nameFilters = ['*.'+ext for ext in acceptedFileExtensions]
          filenamesInFolder = directory.entryList(nameFilters, qt.QDir.Files, qt.QDir.Name)
          for filenameInFolder in filenamesInFolder:
            filesToAdd.append(directory.absoluteFilePath(filenameInFolder))
        else:
          ext = pathInfo.suffix().lower()
          if ext in acceptedFileExtensions:
            filesToAdd.append(localPath)
    return filesToAdd

  def dropEvent(self):
    slicer.util.selectModule('ImageStacks')
    if len(self.filesToAdd) == 1:
      slicer.modules.imagestacks.widgetRepresentation().self().archetypeText.text = self.filesToAdd[0]
    elif len(self.filesToAdd) > 1:
      slicer.modules.imagestacks.widgetRepresentation().self().addFilePaths(self.filesToAdd)
    self.filesToAdd=[]


#
# ImageStacksLogic
#

class ImageStacksLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def humanizeByteCount(self,byteCount):
    units = "bytes"
    for unit in ['kilobytes', 'megabytes', 'gigabytes', 'terabytes']:
      if byteCount > 1024:
        byteCount /= 1024.
        units = unit
    return(byteCount, units)

  def getImageSpacing(self, filePath):
    try:
      reader = sitk.ImageFileReader()
      reader.SetFileName(filePath)
      image = reader.Execute()
      return image.GetSpacing()
    except:
      return None

  def calculateProperties(self, filePaths):
    properties = {}
    if filePaths == []:
      return properties
    reader = sitk.ImageFileReader()
    reader.SetFileName(filePaths[0])
    image = reader.Execute()
    sliceArray = sitk.GetArrayFromImage(image)
    dimensions = ((*sliceArray.shape[:2]), len(filePaths))
    itemsize = numpy.dtype(sliceArray.dtype).itemsize
    volumeSize = (itemsize * dimensions[0] * dimensions[1] * dimensions[2])
    byteCount, units = self.humanizeByteCount(volumeSize)
    properties['Full volume size'] = f"{dimensions[0]} x {dimensions[1]} x {dimensions[2]} x {sliceArray.dtype} = {byteCount:.3f} {units}"
    resampledDimensions = [i>>1 for i in dimensions]
    byteCount, units = self.humanizeByteCount(resampledDimensions[0]*resampledDimensions[1]*resampledDimensions[2])
    properties['Downsampled volume size'] = f"{resampledDimensions[0]} x {resampledDimensions[1]} x {resampledDimensions[2]} x {sliceArray.dtype} = {byteCount:.3f} {units}"
    return(properties)

  def loadByPaths(self, paths, outputNode, properties={}):
    """
    Load the files in paths to outputNode with optional properties.
    TODO: currently downsample is done with nearest neighbor filtering
    (i.e. skip slices and take every other row/column).
    It would be better to do a high order spline or other
    method, but there is no convenient streaming option for these.
    One option will be do to a box filter by averaging adjacent
    slices/row/columns which should be easy in numpy
    and give good results for a pixel aligned 50% scale operation.
    """

    if paths == []:
      return

    spacing = (1,1,1)
    if 'spacing' in properties:
      spacing = properties['spacing']

    sliceSkip = 0
    if 'sliceSkip' in properties:
      sliceSkip = int(properties['sliceSkip'])
    spacing[2] *= 1+sliceSkip
    paths = paths[::1+sliceSkip]

    reverse = 'reverse' in properties and properties['reverse']
    if reverse:
      paths.reverse()

    downsample = 'downsample' in properties and properties['downsample']
    if downsample:
      paths = paths[::2]
      spacing = [element * 2. for element in spacing]

    volumeArray = None
    sliceIndex = 0
    for path in paths:
      reader = sitk.ImageFileReader()
      reader.SetFileName(path)
      image = reader.Execute()
      sliceArray = sitk.GetArrayFromImage(image)
      if len(sliceArray.shape) == 3:
        sliceArray = sitk.GetArrayFromImage(image)[:,:,0]

      if volumeArray is None:
        sliceShape = sliceArray.shape
        if downsample:
          sliceShape = [math.ceil(element/2) for element in sliceShape]
        shape = (len(paths), *sliceShape)
        volumeArray = numpy.zeros(shape, dtype=sliceArray.dtype)
      if downsample:
        sliceArray = sliceArray[::2,::2]
      if (sliceIndex > 0) and (volumeArray[sliceIndex].shape != sliceArray.shape):
        message = "There are multiple datasets in the folder. Please select a single file as a sample or specify a pattern.\nDetails:\n{0}{1} size is {2} x {3}\n\n{4} size is {5} x {6}".format(
          "After downsampling:\n\n" if downsample else "",
          paths[0], volumeArray[0].shape[0], volumeArray[0].shape[1],
          path, sliceArray.shape[0], sliceArray.shape[1])
        raise ValueError(message)
      volumeArray[sliceIndex] = sliceArray
      sliceIndex += 1

    if not outputNode:
      outputNode = slicer.vtkMRMLScalarVolumeNode()
      slicer.mrmlScene.AddNode(outputNode)
      path = paths[0]
      fileName = os.path.basename(path)
      name = os.path.splitext(fileName)[0]
      outputNode.SetName(name)

    ijkToRAS = vtk.vtkMatrix4x4()
    ijkToRAS.Identity()
    for index in range(3):
      if (spacing[index] < 0):
        spacing[index] = -1. * spacing[index]
        ijkToRAS.SetElement(index, index, -1.)
    outputNode.SetIJKToRASMatrix(ijkToRAS)
    outputNode.SetSpacing(*spacing)

    slicer.util.updateVolumeFromArray(outputNode, volumeArray)
    slicer.util.setSliceViewerLayers(background=outputNode, fit=True)
    return outputNode


class ImageStacksTest(ScriptedLoadableModuleTest):
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
    self.test_ImageStacks1()

  def test_ImageStacks1(self):
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

    directoryPath = '/Volumes/SSD2T/data/SlicerMorph/Sample_for_steve/1326_Rec'
    pathFormat = '%s/1326__rec%04d.png'
    start, end =  (50, 621)

    paths = [ pathFormat % (directoryPath, i) for i in range(start,end+1) ]
    collection = []

    import SimpleITK as sitk
    def readingTarget(paths=paths):
        for path in paths:
            reader = sitk.ImageFileReader()
            reader.SetFileName(path)
            image = reader.Execute()
            collection.append(image)


    import threading
    thread = threading.Thread(target=readingTarget)
    thread.start()

    qt.QTimer.singleShot(5000, lambda : print(len(collection)))
    qt.QTimer.singleShot(25000, thread.join)

    self.delayDisplay('Test passed!')
