import os
import unittest
import math
import numpy
import vtk, qt, ctk, slicer
import SimpleITK as sitk
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
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

class ImageStacksWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModuleWidget.__init__(self,parent)
    VTKObservationMixin.__init__(self)

    self.logic = ImageStacksLogic()
    self.outputROINode = None  # observed ROI node

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
    self.archetypeText = qt.QLineEdit()
    buttonLayout.addWidget(self.archetypeText)
    self.addFromArchetype = qt.QPushButton("Browse...")
    buttonLayout.addWidget(self.addFromArchetype)
    self.archetypeStartNumber = 0

    filesFormLayout.addRow("Filename pattern: ", buttonLayout)

    # file list group
    fileListGroupBox = ctk.ctkCollapsibleGroupBox()
    fileListGroupBox.title = "File list"
    fileListLayout = qt.QVBoxLayout()
    fileListGroupBox.setLayout(fileListLayout)
    filesFormLayout.addRow("", fileListGroupBox)

    self.addByBrowsingButton = qt.QPushButton("Select files...")
    fileListLayout.addWidget(self.addByBrowsingButton)

    self.fileTable = qt.QTextBrowser()
    fileListLayout.addWidget(self.fileTable)

    fileListGroupBox.collapsed = True

    # original volume size
    self.originalVolumeSizeLabel = qt.QLabel()
    filesFormLayout.addRow("Size: ", self.originalVolumeSizeLabel)

    # reverse slice order
    self.reverseCheckBox = qt.QCheckBox()
    self.reverseCheckBox.toolTip = "Read the images in reverse order (flips loaded volume along IS axis)"
    filesFormLayout.addRow("Reverse: ", self.reverseCheckBox)

    # original spacing
    self.spacingWidget = slicer.qMRMLCoordinatesWidget()
    self.spacingWidget.setMRMLScene(slicer.mrmlScene)
    self.spacingWidget.decimalsOption  = ctk.ctkDoubleSpinBox.DecimalsByKey | ctk.ctkDoubleSpinBox.DecimalsByShortcuts | ctk.ctkDoubleSpinBox.DecimalsByValue
    self.spacingWidget.minimum = 0.0
    self.spacingWidget.maximum = 1000000000.0
    self.spacingWidget.quantity = "length"
    self.spacingWidget.unitAwareProperties = slicer.qMRMLCoordinatesWidget.Precision | slicer.qMRMLCoordinatesWidget.Prefix | slicer.qMRMLCoordinatesWidget.Scaling | slicer.qMRMLCoordinatesWidget.Suffix
    self.spacingWidget.coordinates = "1,1,1"
    self.spacingWidget.toolTip = "Set the colunm, row, slice spacing; original spacing not including downsample"
    filesFormLayout.addRow("Spacing: ", self.spacingWidget)

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
    self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode", "vtkMRMLVectorVolumeNode"]
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

    #
    # output ROI selector
    #
    self.outputROISelector = slicer.qMRMLNodeComboBox()
    self.outputROISelector.nodeTypes = ["vtkMRMLAnnotationROINode", "vtkMRMLMarkupsROINode"]
    self.outputROISelector.showChildNodeTypes = False
    self.outputROISelector.showHidden = False
    self.outputROISelector.showChildNodeTypes = False
    self.outputROISelector.noneEnabled = True
    self.outputROISelector.removeEnabled = True
    self.outputROISelector.renameEnabled = True
    self.outputROISelector.addEnabled = False
    self.outputROISelector.noneDisplay = "(Full volume)"
    self.outputROISelector.setMRMLScene( slicer.mrmlScene )
    self.outputROISelector.setToolTip( "Set the region of the volume that will be loaded")
    outputFormLayout.addRow("Region of interest: ", self.outputROISelector)

    #
    # Quality selector
    #
    qualityLayout = qt.QVBoxLayout()
    self.qualityPreviewRadioButton = qt.QRadioButton("preview")
    self.qualityHalfRadioButton = qt.QRadioButton("half resolution")
    self.qualityFullRadioButton = qt.QRadioButton("full resolution")
    qualityLayout.addWidget(self.qualityPreviewRadioButton)
    qualityLayout.addWidget(self.qualityHalfRadioButton)
    qualityLayout.addWidget(self.qualityFullRadioButton)
    self.qualityPreviewRadioButton.setChecked(True)
    outputFormLayout.addRow("Quality: ", qualityLayout)

    self.sliceSkipSpinBox = qt.QSpinBox()
    self.sliceSkipSpinBox.toolTip = "Skips the selected number of slices between each pair of output volume slices (use, for example, on long thin samples with more slices than in-plane resolution)"
    outputFormLayout.addRow("Slice skip: ", self.sliceSkipSpinBox)

    # Force grayscale output
    self.grayscaleCheckBox = qt.QCheckBox()
    self.grayscaleCheckBox.toolTip = "Force reading the image in grayscale. Only makes a difference if the input has color (RGB or RGBA) voxels."
    self.grayscaleCheckBox.checked = True
    outputFormLayout.addRow("Grayscale: ", self.grayscaleCheckBox)

    # output volume size
    self.outputVolumeSizeLabel = qt.QLabel()
    outputFormLayout.addRow("Output size: ", self.outputVolumeSizeLabel)

    # output volume spacing
    self.outputSpacingWidget = slicer.qMRMLCoordinatesWidget()
    self.outputSpacingWidget.setMRMLScene(slicer.mrmlScene)
    self.outputSpacingWidget.readOnly = True
    self.outputSpacingWidget.frame = False
    self.outputSpacingWidget.decimalsOption  = ctk.ctkDoubleSpinBox.DecimalsByKey | ctk.ctkDoubleSpinBox.DecimalsByShortcuts | ctk.ctkDoubleSpinBox.DecimalsByValue
    self.outputSpacingWidget.minimum = 0.0
    self.outputSpacingWidget.maximum = 1000000000.0
    self.outputSpacingWidget.quantity = "length"
    self.outputSpacingWidget.unitAwareProperties = slicer.qMRMLCoordinatesWidget.Precision | slicer.qMRMLCoordinatesWidget.Prefix | slicer.qMRMLCoordinatesWidget.Scaling | slicer.qMRMLCoordinatesWidget.Suffix
    self.outputSpacingWidget.coordinates = "1,1,1"
    self.outputSpacingWidget.toolTip = "Slice spacing of the volume that will be loaded"
    outputFormLayout.addRow("Output spacing: ", self.outputSpacingWidget)

    self.loadButton = qt.QPushButton("Load files")
    self.loadButton.toolTip = "Load files as a 3D volume"
    self.loadButton.enabled = False
    outputFormLayout.addRow(self.loadButton)

    # connections
    self.reverseCheckBox.connect('toggled(bool)', self.updateLogicFromWidget)
    self.sliceSkipSpinBox.connect("valueChanged(int)", self.updateLogicFromWidget)
    self.spacingWidget.connect("coordinatesChanged(double*)", self.updateLogicFromWidget)
    self.qualityPreviewRadioButton.connect("toggled(bool)", lambda toggled, widget=self.qualityPreviewRadioButton: self.onQualityToggled(toggled, widget))
    self.qualityHalfRadioButton.connect("toggled(bool)", lambda toggled, widget=self.qualityHalfRadioButton: self.onQualityToggled(toggled, widget))
    self.qualityFullRadioButton.connect("toggled(bool)", lambda toggled, widget=self.qualityFullRadioButton: self.onQualityToggled(toggled, widget))
    self.grayscaleCheckBox.connect('toggled(bool)', self.updateLogicFromWidget)
    self.outputROISelector.connect("currentNodeChanged(vtkMRMLNode*)", self.setOutputROINode)
    self.addByBrowsingButton.connect('clicked()', self.addByBrowsing)
    self.addFromArchetype.connect('clicked()', self.selectArchetype)
    self.archetypeText.connect('textChanged(const QString &)', self.populateFromArchetype)
    self.loadButton.connect('clicked()', self.onLoadButton)

    # Add vertical spacer
    self.layout.addStretch(1)

    self.loadButton.enabled = False

  def cleanup(self):
    self.setOutputROINode(None)
    self.removeObservers()

  def updateWidgetFromLogic(self):
    # Original volume size
    if (self.logic.originalVolumeDimensions[0] == 0
      and self.logic.originalVolumeDimensions[1] == 0
      and self.logic.originalVolumeDimensions[2] == 0):
      self.originalVolumeSizeLabel.text = ""
      self.outputVolumeSizeLabel.text = ""
      self.outputSpacingWidget.coordinates = "1,1,1"
      self.loadButton.enabled = False
      return

    self.originalVolumeSizeLabel.text = ImageStacksLogic.humanizeImageSize(self.logic.originalVolumeDimensions, self.logic.originalVolumeNumberOfScalarComponents, self.logic.originalVolumeVoxelDataType)

    outputIJKToRAS, outputExtent, outputNumberOfScalarComponents = self.logic.outputVolumeGeometry()
    outputVolumeDimensions = [outputExtent[i*2+1]-outputExtent[i*2]+1 for i in range(3)]
    self.outputVolumeSizeLabel.text = ImageStacksLogic.humanizeImageSize(outputVolumeDimensions, outputNumberOfScalarComponents, self.logic.originalVolumeVoxelDataType)
    outputSpacing = [numpy.linalg.norm(outputIJKToRAS[0:3,i]) for i in range(3)]
    self.outputSpacingWidget.coordinates = f"{outputSpacing[0]},{outputSpacing[1]},{outputSpacing[2]}"

    self.loadButton.enabled = True


  def updateLogicFromWidget(self):
    self.logic.reverseSliceOrder = self.reverseCheckBox.checked
    self.logic.outputGrayscale = self.grayscaleCheckBox.checked
    self.logic.sliceSkip = self.sliceSkipSpinBox.value
    spacingString = self.spacingWidget.coordinates
    self.logic.setOriginalVolumeSpacing([float(element) for element in spacingString.split(",")])
    self.updateWidgetFromLogic()

  def onQualityToggled(self, toggled, widget):
    if not toggled:
      return
    if widget==self.qualityPreviewRadioButton:
      quality = 'preview'
    elif widget==self.qualityHalfRadioButton:
      quality = 'half'
    else:
      quality = 'full'
    self.logic.outputQuality = quality
    self.updateWidgetFromLogic()

  def onClear(self):
    self.fileTable.clear()
    self.outputSelector.currentNodeID = ""
    self.logic.filePaths = []
    self.updateWidgetFromLogic()

  def addByBrowsing(self):
    self.onClear()
    filePaths = qt.QFileDialog().getOpenFileNames()
    self.setFilePaths(filePaths)

  def setFilePaths(self, filePaths):
    self.fileTable.plainText = '\n'.join(filePaths)
    self.logic.filePaths = filePaths

    # Use the spacing that we find in the image
    spacing = self.logic.originalVolumeRecommendedSpacing
    self.spacingWidget.coordinates = f"{spacing[0]},{spacing[1]},{spacing[2]}"

    self.updateWidgetFromLogic()

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
        filePaths.append(filePath)
      else:
        if fileIndex != 0:
          break
      fileIndex += 1
    self.setFilePaths(filePaths)
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

  def setOutputROINode(self, roiNode):
    if self.outputROINode:
      self.removeObserver(self.outputROINode, vtk.vtkCommand.ModifiedEvent, self.onOutputROIModified)
    self.outputROINode = roiNode
    if self.outputROINode:
      self.addObserver(self.outputROINode, vtk.vtkCommand.ModifiedEvent, self.onOutputROIModified)
    self.onOutputROIModified()

  def onOutputROIModified(self, unused1=None, unused2=None):
    outputBounds = None
    if self.outputROINode:
      center = [0.0, 0.0, 0.0]
      radius = [0.0, 0.0, 0.0]
      self.outputROINode.GetXYZ(center)
      self.outputROINode.GetRadiusXYZ(radius)
      outputBounds = [
        center[0]-radius[0], center[0]+radius[0],
        center[1]-radius[1], center[1]+radius[1],
        center[2]-radius[2], center[2]+radius[2]
        ]
    self.logic.outputVolumeBounds = outputBounds
    self.updateWidgetFromLogic()

  def onLoadButton(self):
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
      outputNode = self.logic.loadVolume(self.currentNode())
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
class ImageStacksFileDialog:
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

    # Filter out files that are known to cause complications
    # Currently, there is only one rule, but it is expected that more filtering rules will be added in the future.
    filteredFilesToAdd = []
    for filePath in filesToAdd:
      fileName = qt.QFileInfo(filePath).fileName()

      # Ignore cone-beam image in Bruker Skyscan folder
      # such as `left_side_damaged__rec_spr.bmp`
      if fileName.endswith("spr.bmp"):
        # skip this file
        logging.debug(f"Skipping {filePath} - it looks like a Bruker Skyscan cone-beam image, not an image slice")
        continue

      filteredFilesToAdd.append(filePath)

    return filteredFilesToAdd

  def dropEvent(self):
    slicer.util.selectModule('ImageStacks')
    moduleWidget = slicer.modules.imagestacks.widgetRepresentation().self()
    moduleWidget.onClear()
    if len(self.filesToAdd) == 1:
      moduleWidget.archetypeText.text = self.filesToAdd[0]
    elif len(self.filesToAdd) > 1:
      moduleWidget.setFilePaths(self.filesToAdd)
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

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    self._filePaths = []
    self.originalVolumeDimensions = [0, 0, 0]
    self.originalVolumeIJKToRAS = numpy.diag([-1.0, -1.0, 1.0, 1.0])
    self.originalVolumeRecommendedSpacing = [1.0, 1.0, 1.0]
    self.originalVolumeVoxelDataType = numpy.dtype('uint8')
    self.sliceSkip = 0
    self.reverseSliceOrder = False
    self.outputGrayscale = True  # force loading image as grayscale
    self.outputQuality = 'preview' # valid values: preview, half, full
    # Bounds is stored as None (no bounds)
    # or [min_R, max_R, min_A, max_A, min_S, max_S] if there is a valid bounding box.
    # This variable uses RAS coordinate system (Slicer's internal coordinate system)
    # but image coordinate system in files is always LPS, therefore we invert the
    # sign of the first two axes when we compute image extents.
    self.outputVolumeBounds = None

  @staticmethod
  def humanizeByteCount(byteCount):
    units = "bytes"
    for unit in ['kilobytes', 'megabytes', 'gigabytes', 'terabytes']:
      if byteCount > 1024:
        byteCount /= 1024.
        units = unit
    return(byteCount, units)

  @staticmethod
  def humanizeImageSize(dimensions, numberOfScalarComponents, scalarType):
    """Create human-readable string explaining the image extent and size"""
    itemsize = scalarType.itemsize
    volumeSize = (itemsize * dimensions[0] * dimensions[1] * dimensions[2] * numberOfScalarComponents)
    byteCount, units = ImageStacksLogic.humanizeByteCount(volumeSize)
    if numberOfScalarComponents == 1:
      return f"{dimensions[0]} x {dimensions[1]} x {dimensions[2]} x {scalarType} = {byteCount:.3f} {units}"
    else:
      return f"{dimensions[0]} x {dimensions[1]} x {dimensions[2]} x {numberOfScalarComponents} x {scalarType} = {byteCount:.3f} {units}"

  @property
  def filePaths(self):
    return self._filePaths

  @filePaths.setter
  def filePaths(self, filePaths):
    """Store file paths and compute originalVolumeDimensions and originalVolumeRecommendedSpacing."""

    self._filePaths = filePaths
    self.originalVolumeDimensions = [0, 0, 0]
    self.originalVolumeRecommendedSpacing = [1.0, 1.0, 1.0]

    if not self._filePaths:
      return

    reader = sitk.ImageFileReader()
    reader.SetFileName(self._filePaths[0])
    image = reader.Execute()
    sliceArray = sitk.GetArrayFromImage(image)

    self.originalVolumeDimensions = [sliceArray.shape[1], sliceArray.shape[0], len(filePaths)]
    self.originalVolumeNumberOfScalarComponents = sliceArray.shape[2] if len(sliceArray.shape) == 3 else 1
    self.originalVolumeVoxelDataType = numpy.dtype(sliceArray.dtype)

    firstSliceSpacing = image.GetSpacing()
    self.originalVolumeRecommendedSpacing = [firstSliceSpacing[1], firstSliceSpacing[0], 1.0]

    if firstSliceSpacing[0] == firstSliceSpacing[1]:
      # If x and y spacing are the same then we assume that it is an isotropic volume
      # and set z spacing to the same value
      self.originalVolumeRecommendedSpacing[2] = firstSliceSpacing[0]

  def setOriginalVolumeSpacing(self, spacing):
    # Volume is in LPS, therefore we invert the first two axes
    self.originalVolumeIJKToRAS = numpy.diag([-spacing[0], -spacing[1], spacing[2], 1.0])

  def outputVolumeGeometry(self):
    # spacing
    spacingScale = numpy.array([1.0, 1.0, 1+self.sliceSkip])
    if self.outputQuality == 'half':
      spacingScale *= 2.0
    elif self.outputQuality == 'preview':
      spacingScale *= 4.0
    ijkToRAS = numpy.dot(self.originalVolumeIJKToRAS, numpy.diag([spacingScale[0], spacingScale[1], spacingScale[2], 1.0]))

    # extent
    fullExtent = [0, 0, 0, 0, 0, 0]
    for i in range(3):
      fullExtent[i*2+1] = int(math.floor(self.originalVolumeDimensions[i]/spacingScale[i])) - 1
    if self.outputVolumeBounds:
      rasToIJK = numpy.linalg.inv(ijkToRAS)
      extentIJK = vtk.vtkBoundingBox()
      for cornerR in [self.outputVolumeBounds[0], self.outputVolumeBounds[1]]:
        for cornerA in [self.outputVolumeBounds[2], self.outputVolumeBounds[3]]:
          for cornerS in [self.outputVolumeBounds[4], self.outputVolumeBounds[5]]:
            cornerIJK = numpy.dot(rasToIJK, [cornerR, cornerA, cornerS, 1.0])[0:3]
            extentIJK.AddPoint(cornerIJK)
      extent = [0,0,0,0,0,0]
      for i in range(3):
        extent[i*2] = int(math.floor(extentIJK.GetBound(i*2)-0.5))
        if extent[i*2] < fullExtent[i*2]:
          extent[i*2] = fullExtent[i*2]
        extent[i*2+1] = int(math.ceil(extentIJK.GetBound(i*2+1)+0.5))
        if extent[i*2+1] > fullExtent[i*2+1]:
          extent[i*2+1] = fullExtent[i*2+1]
    else:
      extent = fullExtent

    # origin
    originRAS = numpy.dot(ijkToRAS, [extent[0], extent[2], extent[4], 1.0])[0:3]
    ijkToRAS[0:3,3] = originRAS

    numberOfScalarComponents = 1 if self.outputGrayscale else self.originalVolumeNumberOfScalarComponents

    return ijkToRAS, extent, numberOfScalarComponents

  def loadVolume(self, outputNode=None):
    """
    Load the files in paths to outputNode.
    TODO: currently downsample is done with nearest neighbor filtering
    (i.e. skip slices and take every other row/column).
    It would be better to do a high order spline or other
    method, but there is no convenient streaming option for these.
    One option will be do to a box filter by averaging adjacent
    slices/row/columns which should be easy in numpy
    and give good results for a pixel aligned 50% scale operation.
    """

    ijkToRAS, extent, numberOfScalarComponents = self.outputVolumeGeometry()
    outputSpacing = [numpy.linalg.norm(ijkToRAS[0:3,i]) for i in range(3)]
    originalVolumeSpacing = [numpy.linalg.norm(self.originalVolumeIJKToRAS[0:3, i]) for i in range(3)]

    stepSize = [int(outputSpacing[i] / originalVolumeSpacing[i]) for i in range(3)]

    paths = self._filePaths[::stepSize[2]]

    if self.reverseSliceOrder:
      paths.reverse()

    volumeArray = None
    sliceIndex = 0
    firstArrayFullShape = None
    for inputSliceIndex, path in enumerate(paths):
      if inputSliceIndex < extent[4] or inputSliceIndex > extent[5]:
        # out of selected bounds
        continue
      reader = sitk.ImageFileReader()
      reader.SetFileName(path)
      image = reader.Execute()
      sliceArray = sitk.GetArrayFromImage(image)
      if len(sliceArray.shape) == 3 and self.outputGrayscale:
        # We convert to grayscale by simply taking the first component, which is appropriate for cases when grayscale image is stored as R=G=B,
        # but to convert real RGB images it could better to compute the mean or luminance.
        sliceArray = sitk.GetArrayFromImage(image)[:,:,0]
      currentArrayFullShape = sliceArray.shape
      if firstArrayFullShape is None:
        firstArrayFullShape = currentArrayFullShape

      if volumeArray is None:
        shape = [extent[5]-extent[4]+1, extent[3]-extent[2]+1, extent[1]-extent[0]+1]
        if len(sliceArray.shape) == 3:
          shape.append(sliceArray.shape[2])
        volumeArray = numpy.zeros(shape, dtype=sliceArray.dtype)
      if len(sliceArray.shape) == 3:
        # vector volume
        sliceArray = sliceArray[
          extent[2]*stepSize[1]:(extent[3]+1)*stepSize[1]:stepSize[1],
          extent[0]*stepSize[0]:(extent[1]+1)*stepSize[0]:stepSize[0], :]
      else:
        # grayscale volume
        sliceArray = sliceArray[
                     extent[2] * stepSize[1]:(extent[3] + 1) * stepSize[1]:stepSize[1],
                     extent[0] * stepSize[0]:(extent[1] + 1) * stepSize[0]:stepSize[0]]
      if (sliceIndex > 0) and (volumeArray[sliceIndex].shape != sliceArray.shape):
        logging.debug("After downsampling, {} size is {} x {}\n\n{} size is {} x {} ({} scalar components)".format(
          paths[0], volumeArray[0].shape[0], volumeArray[0].shape[1],
          path, sliceArray.shape[0], sliceArray.shape[1],
          sliceArray.shape[2] if len(sliceArray.shape)==3 else 1))
        message = "There are multiple datasets in the folder. Please select a single file as a sample or specify a pattern.\nDetails:\n{0} size is {1} x {2} ({6} scalar components)\n\n{3} size is {4} x {5} ({7} scalar components)".format(
          paths[0], firstArrayFullShape[0], firstArrayFullShape[1],
          path, currentArrayFullShape[0], currentArrayFullShape[1],
          firstArrayFullShape.shape[2] if len(firstArrayFullShape.shape)==3 else 1,
          currentArrayFullShape.shape[2] if len(currentArrayFullShape.shape)==3 else 1)
        raise ValueError(message)
      volumeArray[sliceIndex] = sliceArray
      sliceIndex += 1

    if not outputNode:
      if len(volumeArray.shape) == 3:
        outputNode = slicer.vtkMRMLScalarVolumeNode()
      else:
        outputNode = slicer.vtkMRMLVectorVolumeNode()
      slicer.mrmlScene.AddNode(outputNode)
      path = paths[0]
      fileName = os.path.basename(path)
      name = os.path.splitext(fileName)[0]
      outputNode.SetName(name)

    # Check if output volume is the correct type
    if len(volumeArray.shape) == 4:
      if not outputNode.IsA("vtkMRMLVectorVolumeNode"):
        raise ValueError("Select a vector volume as output volume or force grayscale output.")
      # Set voxel vector type to RGB/RGBA
      if volumeArray.shape[3] == 3:
        outputNode.SetVoxelVectorType(outputNode.VoxelVectorTypeColorRGB)
      elif volumeArray.shape[3] == 4:
        outputNode.SetVoxelVectorType(outputNode.VoxelVectorTypeColorRGBA)
    else:
      if outputNode.IsA("vtkMRMLVectorVolumeNode"):
        raise ValueError("Select a scalar volume as output volume.")

    ijkToRAS = slicer.util.vtkMatrixFromArray(ijkToRAS)
    outputNode.SetIJKToRASMatrix(ijkToRAS)
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
