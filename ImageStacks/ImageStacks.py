import os
import re
import unittest
import math
import numpy
import vtk, qt, ctk, slicer
import slicer.packaging
import SimpleITK as sitk
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import logging


def naturalSortKey(path):
  """Sort key that orders filenames by their trailing numeric token before the
  extension (with full natural-sort as a tiebreaker), so that ``slice_2.tif``
  comes before ``slice_10.tif`` regardless of zero-padding. Used at every entry
  point that builds a slice list, so order is deterministic across OSes and
  irrespective of how the dialog or drag-drop happened to return paths."""
  name = os.path.basename(path)
  stem, _ = os.path.splitext(name)
  match = re.search(r'(\d+)(?!.*\d)', stem)
  trailing = int(match.group(1)) if match else -1
  fullSplit = [int(token) if token.isdigit() else token.lower()
               for token in re.split(r'(\d+)', name)]
  return (trailing, fullSplit)


def imageStackSanityReport(filePaths):
  """Compare the collected slice list against the contents of its source
  folder(s). Returns a (status, message) tuple where status is one of
  'ok', 'mismatch', 'multifolder', 'empty'. The message is a short
  human-readable string suitable for a status label."""
  if not filePaths:
    return ('empty', '')
  parentDirs = {os.path.dirname(p) for p in filePaths}
  if len(parentDirs) > 1:
    return ('multifolder', f"Detected {len(filePaths)} files from {len(parentDirs)} folders")
  parent = next(iter(parentDirs))
  ext = os.path.splitext(filePaths[0])[1].lower()
  if not ext or not parent or not os.path.isdir(parent):
    return ('ok', f"Detected {len(filePaths)} files")
  try:
    siblings = [entry.name for entry in os.scandir(parent)
                if entry.is_file() and os.path.splitext(entry.name)[1].lower() == ext]
  except OSError:
    return ('ok', f"Detected {len(filePaths)} files")
  if len(filePaths) == len(siblings):
    return ('ok', f"Detected {len(filePaths)} / {len(siblings)} {ext} files in folder")
  loadedNames = {os.path.basename(p) for p in filePaths}
  missing = sorted(name for name in siblings if name not in loadedNames)
  preview = ', '.join(missing[:5])
  more = '' if len(missing) <= 5 else f", +{len(missing)-5} more"
  message = (f"Detected {len(filePaths)} / {len(siblings)} {ext} files in folder "
             f"⚠  (not included: {preview}{more})")
  return ('mismatch', message)

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
This module was developed by Steve Pieper, Sara Rolfe and Murat Maga for SlicerMorph. Development of SlicerMorph is supported by NSF grants 1759883 and 2301405 to Murat Maga.
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
    self.loadingIsInProgress = False
    self.cancelRequested = False

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
    # disable wrapping
    self.fileTable.setLineWrapMode(qt.QTextBrowser.NoWrap)
    fileListLayout.addWidget(self.fileTable)

    self.fileStatusLabel = qt.QLabel()
    self.fileStatusLabel.setWordWrap(True)
    self.fileStatusLabel.setTextInteractionFlags(qt.Qt.TextSelectableByMouse)
    fileListLayout.addWidget(self.fileStatusLabel)

    fileListGroupBox.collapsed = True

    # original volume size
    self.originalVolumeSizeLabel = qt.QLabel()
    filesFormLayout.addRow("Size: ", self.originalVolumeSizeLabel)

    # reverse slice order
    self.reverseCheckBox = qt.QCheckBox()
    self.reverseCheckBox.toolTip = "Read the images in reverse order (flips loaded volume along IS axis)"
    filesFormLayout.addRow("Reverse: ", self.reverseCheckBox)

    # original spacing
    self.spacingWidgetsLayout = qt.QHBoxLayout()

    self.isotropicSpacingWidget = slicer.qMRMLSpinBox()
    self.isotropicSpacingWidget.setMRMLScene(slicer.mrmlScene)
    self.isotropicSpacingWidget.decimalsOption  = ctk.ctkDoubleSpinBox.DecimalsByKey | ctk.ctkDoubleSpinBox.DecimalsByShortcuts | ctk.ctkDoubleSpinBox.DecimalsByValue
    self.isotropicSpacingWidget.minimum = 0.0
    self.isotropicSpacingWidget.maximum = 1000000000.0
    self.isotropicSpacingWidget.quantity = "length"
    self.isotropicSpacingWidget.unitAwareProperties = slicer.qMRMLCoordinatesWidget.Precision | slicer.qMRMLCoordinatesWidget.Prefix | slicer.qMRMLCoordinatesWidget.Scaling | slicer.qMRMLCoordinatesWidget.Suffix
    self.isotropicSpacingWidget.value = 0
    self.isotropicSpacingWidget.singleStep = 0.1
    self.isotropicSpacingWidget.decimals = 1
    self.isotropicSpacingWidget.toolTip = "Set the same value as column, row, slice spacing; original spacing not including downsample. The value must be greater than 0."
    self.spacingWidgetsLayout.addWidget(self.isotropicSpacingWidget)

    self.anisotropicSpacingWidget = slicer.qMRMLCoordinatesWidget()
    self.anisotropicSpacingWidget.setMRMLScene(slicer.mrmlScene)
    self.anisotropicSpacingWidget.decimalsOption  = self.isotropicSpacingWidget.decimalsOption
    self.anisotropicSpacingWidget.minimum = self.isotropicSpacingWidget.minimum
    self.anisotropicSpacingWidget.maximum = self.isotropicSpacingWidget.maximum
    self.anisotropicSpacingWidget.quantity = self.isotropicSpacingWidget.quantity
    self.anisotropicSpacingWidget.unitAwareProperties = self.isotropicSpacingWidget.unitAwareProperties
    self.anisotropicSpacingWidget.coordinates = f"{self.isotropicSpacingWidget.value},{self.isotropicSpacingWidget.value},{self.isotropicSpacingWidget.value}"
    self.anisotropicSpacingWidget.singleStep = self.isotropicSpacingWidget.singleStep
    self.anisotropicSpacingWidget.decimals = self.isotropicSpacingWidget.decimals
    self.anisotropicSpacingWidget.toolTip = "Set the column, row, slice spacing; original spacing not including downsample. All values must be greater than 0."
    self.anisotropicSpacingWidget.hide()
    self.spacingWidgetsLayout.addWidget(self.anisotropicSpacingWidget)

    self.isotropicSpacingButton = qt.QPushButton()
    self.isotropicSpacingButton.setCheckable(True)
    self.isotropicSpacingButton.checked = True
    self.isotropicSpacingButton.setIconSize(qt.QSize(16, 16))
    self.isotropicSpacingButton.toolTip = "Toggle between using the same spacing value for all axes and using different spacing value for each axis"
    self.isotropicSpacingButton.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
    self.isotropicSpacingButton.setStyleSheet("QPushButton:checked { image: url(:Icons/LinkOn.png); } QPushButton:!checked { image: url(:Icons/LinkOff.png); }")
    self.spacingWidgetsLayout.addWidget(self.isotropicSpacingButton)

    self.spacingWidgetsLayout.addItem(qt.QSpacerItem(10, 10, qt.QSizePolicy.Minimum, qt.QSizePolicy.Expanding))

    self.autoDetectSpacingButton = qt.QPushButton("Auto-detect")
    self.autoDetectSpacingButton.toolTip = "Set spacing based on image metadata"
    self.spacingWidgetsLayout.addWidget(self.autoDetectSpacingButton)

    filesFormLayout.addRow("Spacing: ", self.spacingWidgetsLayout)

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
    self.outputROISelector.nodeTypes = ["vtkMRMLMarkupsROINode"]
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

    self.progressBar = qt.QProgressBar()
    self.progressBar.hide()
    self.progressBar.maximum = 100
    outputFormLayout.addRow(self.progressBar)

    # connections
    self.reverseCheckBox.connect('toggled(bool)', self.updateLogicFromWidget)
    self.sliceSkipSpinBox.connect("valueChanged(int)", self.updateLogicFromWidget)
    self.anisotropicSpacingWidget.connect("coordinatesChanged(double*)", self.updateLogicFromWidget)
    self.isotropicSpacingWidget.connect("valueChanged(double)", self.updateLogicFromWidget)
    self.isotropicSpacingButton.connect('toggled(bool)', self.onIsotropicSpacingToggled)
    self.autoDetectSpacingButton.connect('clicked()', self.onAutoDetectSpacing)
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
    self.updateLogicFromWidget()

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
      self.outputSpacingWidget.coordinates = "0,0,0"
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
    if self.isotropicSpacingButton.checked:
      # isotropic spacing
      spacing = [self.isotropicSpacingWidget.value, self.isotropicSpacingWidget.value, self.isotropicSpacingWidget.value]
    else:
      # anisotropic spacing
      spacingString = self.anisotropicSpacingWidget.coordinates
      spacing = [float(element) for element in spacingString.split(",")]
    self.logic.setOriginalVolumeSpacing(spacing)
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
    self.fileStatusLabel.setText("")
    self.fileStatusLabel.setStyleSheet("")
    self.outputSelector.currentNodeID = ""
    self.logic.filePaths = []
    self.updateWidgetFromLogic()

  def addByBrowsing(self):
    self.onClear()
    filePaths = qt.QFileDialog().getOpenFileNames()
    self.setFilePaths(filePaths)

  def setFilePaths(self, filePaths):
    # Order from QFileDialog, drag-drop, or directory enumeration is not
    # guaranteed to be slice order — natural-sort here so every entry point
    # ends up with the same deterministic ordering.
    filePaths = sorted(filePaths, key=naturalSortKey)
    self.fileTable.plainText = '\n'.join(filePaths)
    self.logic.filePaths = filePaths

    status, message = imageStackSanityReport(filePaths)
    self.fileStatusLabel.setText(message)
    if status == 'mismatch':
      self.fileStatusLabel.setStyleSheet("QLabel { color: #b35900; }")
    else:
      self.fileStatusLabel.setStyleSheet("")

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
    fileExtension = os.path.splitext(filePath)[1]
    isNrrd = fileExtension.lower() == ".nhdr" or fileExtension.lower() == ".nrrd"
    if filePath.find('%') == -1 and not isNrrd:
      # start searching for the first number before the file extension (the file extension itself
      # can contain numbers that should be ignored, such as .jp2)
      index = filePath.rfind(".") - 1
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
    if "%" in archetypeFormat:
      while True:
        filePath = archetypeFormat % fileIndex
        if os.path.exists(filePath):
          filePaths.append(filePath)
        else:
          if fileIndex != 0:
            break
        fileIndex += 1
    else:
      filePaths = [ archetypeFormat ]
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

    if self.loadingIsInProgress:
      self.cancelRequested = True
      return

    self.loadingIsInProgress = True
    self.progressBar.value = 0
    self.progressBar.show()
    self.loadButton.text = "Cancel loading"

    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
      slicer.app.pauseRender()
      outputNode = self.logic.loadVolume(self.currentNode(), progressCallback=self.onProgress)
      self.setCurrentNode(outputNode)
      qt.QApplication.restoreOverrideCursor()
    except Exception as e:
      qt.QApplication.restoreOverrideCursor()
      message, _, details = str(e).partition('\nDetails:\n')
      slicer.util.errorDisplay("Loading failed: " + message, detailedText=details)
      import traceback
      traceback.print_exc()

    slicer.app.resumeRender()
    self.cancelRequested = False
    self.loadingIsInProgress = False
    self.progressBar.hide()
    self.loadButton.text = "Load files"

  def onProgress(self, percentComplete):
    self.progressBar.value = int(self.progressBar.maximum * percentComplete)
    slicer.app.processEvents()
    return not self.cancelRequested

  def onIsotropicSpacingToggled(self, checked):
    """Toggle between isotropic and anisotropic spacing widgets"""
    self.isotropicSpacingWidget.setVisible(checked)
    self.anisotropicSpacingWidget.setVisible(not checked)
    if checked:
      # Copy values from anisotropic to isotropic when switching
      self.isotropicSpacingWidget.value = float(self.anisotropicSpacingWidget.coordinates.split(",")[0])
    else:
      # Copy values from isotropic to anisotropic when switching
      self.anisotropicSpacingWidget.coordinates = f"{self.isotropicSpacingWidget.value},{self.isotropicSpacingWidget.value},{self.isotropicSpacingWidget.value}"

  def onAutoDetectSpacing(self):
    """Set spacing values based on image metadata"""
    if not self.logic.originalVolumeRecommendedSpacing:
      return

    recommendedSpacing = self.logic.originalVolumeRecommendedSpacing

    if recommendedSpacing[0] == recommendedSpacing[1] and (recommendedSpacing[2] == recommendedSpacing[0] or recommendedSpacing[2] == 0.0):
      # It seems that spacing is isotropic
      print(f"iso {recommendedSpacing}")
      self.isotropicSpacingButton.checked = True
      print(f"self.isotropicSpacingWidget.value = {recommendedSpacing[0]}")
      self.isotropicSpacingWidget.value = recommendedSpacing[0]
      print(f"self.isotropicSpacingWidget.value post = {recommendedSpacing[0]}")
    else:
      # For anisotropic, use the recommended spacing directly
      print(f"niso {recommendedSpacing}")
      self.isotropicSpacingButton.checked = False
      self.anisotropicSpacingWidget.coordinates = f"{recommendedSpacing[0]},{recommendedSpacing[1]},{recommendedSpacing[2]}"

    if (recommendedSpacing[0] > 0.0 or recommendedSpacing[1] > 0.0) and recommendedSpacing[2] == 0.0:
      # This is a 2D image stack
      slicer.util.warningDisplay("2D file formats do not always report the correct image spacing."
        " Please cross-reference the spacing value with the scan metadata provided to you and correct if necessary.",
        dontShowAgainSettingsKey = "ImageStacks/DontShow2DImageSpacingWarning")

    self.updateLogicFromWidget()

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
    #acceptedFileExtensions = ['jpg', 'jpeg', 'tif', 'tiff', 'png', 'bmp', 'jp2', 'nrrd', 'nhdr']
    acceptedFileExtensions = ['jpg', 'jpeg', 'tif', 'tiff', 'png', 'bmp', 'jp2']
    if mimeData.hasFormat('text/uri-list'):
      urls = mimeData.urls()
      for url in urls:
        localPath = url.toLocalFile() # convert QUrl to local path
        pathInfo = qt.QFileInfo()
        pathInfo.setFile(localPath) # information about the path
        if pathInfo.isDir(): # if it is a directory we add the files to the dialog
          directory = qt.QDir(localPath)
          nameFilters = ['*.'+ext for ext in acceptedFileExtensions]
          # Enumerate unsorted; setFilePaths applies natural sort. Qt's QDir.Name
          # is locale-aware and lex-only, so it mis-orders mixed-width numeric names.
          filenamesInFolder = directory.entryList(nameFilters, qt.QDir.Files, qt.QDir.Unsorted)
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
    self.originalVolumeRecommendedSpacing = [0.0, 0.0, 0.0]
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
    # True when the file list is a single multi-page TIFF whose pages are the Z
    # slices of a 3D volume. Read page-by-page via tifffile to keep the
    # streaming memory profile of the regular per-file slice loop.
    self.isMultiFrameTiff = False

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
    self.originalVolumeRecommendedSpacing = [0.0, 0.0, 0.0]
    self.isMultiFrameTiff = False

    if not self._filePaths:
      return

    filePath = self._filePaths[0]
    fileName, fileExtension = os.path.splitext(filePath)
    extLower = fileExtension.lower()

    if extLower == ".nhdr" or extLower == ".nrrd":
        reader = sitk.ImageFileReader()
        reader.SetFileName(filePath)
        reader.ReadImageInformation()

        self.originalVolumeDimensions = reader.GetSize()
        self.originalVolumeNumberOfScalarComponents = reader.GetNumberOfComponents()

        pixelType=reader.GetPixelID()
        self.originalVolumeVoxelDataType = sitk.GetArrayFromImage(sitk.Image(1,1,1,pixelType)).dtype
        self.originalVolumeRecommendedSpacing = reader.GetSpacing()
        return

    if len(self._filePaths) == 1 and extLower in (".tif", ".tiff"):
      if self._tryReadMultiPageTiffMetadata(filePath):
        return

    reader = sitk.ImageFileReader()
    reader.SetFileName(filePath)
    image = reader.Execute()
    sliceArray = sitk.GetArrayFromImage(image)

    self.originalVolumeDimensions = [sliceArray.shape[1], sliceArray.shape[0], len(filePaths)]
    self.originalVolumeNumberOfScalarComponents = sliceArray.shape[2] if len(sliceArray.shape) == 3 else 1
    self.originalVolumeVoxelDataType = numpy.dtype(sliceArray.dtype)

    firstSliceSpacing = image.GetSpacing()
    self.originalVolumeRecommendedSpacing = [firstSliceSpacing[1], firstSliceSpacing[0], 0.0]

  def _ensureTifffile(self):
    """Ensure tifffile is importable; installs from the module's requirements file if needed.
    Returns the imported tifffile module."""
    requirementsPath = os.path.join(
      os.path.dirname(slicer.util.modulePath("ImageStacks")),
      "Resources", "requirements_ImageStacks.txt")
    reqs = slicer.packaging.load_requirements(requirementsPath)
    slicer.packaging.pip_ensure(reqs, requester="ImageStacks")
    import tifffile
    return tifffile

  def _tryReadMultiPageTiffMetadata(self, filePath):
    """Inspect a single TIFF file using tifffile and, if it is a multi-page
    TIFF whose pages are Z slices, populate originalVolume* fields and set
    isMultiFrameTiff. Returns True if the file was handled as multi-page."""
    try:
      tifffile = self._ensureTifffile()
    except Exception as e:
      logging.warning(f"ImageStacks: tifffile unavailable, falling back to SimpleITK path ({e})")
      return False

    try:
      tif = tifffile.TiffFile(filePath)
    except Exception as e:
      logging.warning(f"ImageStacks: tifffile could not open {filePath}: {e}")
      return False

    with tif:
      pages = tif.pages
      pageCount = len(pages)
      if pageCount < 2:
        # Single-page TIFF; let the regular SimpleITK path handle it.
        return False

      page0 = pages[0]
      # page0.shape is (H, W) for scalar pages, (H, W, C) for multi-sample pages.
      shape = page0.shape
      if len(shape) < 2:
        return False
      height, width = shape[0], shape[1]
      samples = shape[2] if len(shape) == 3 else 1

      self.isMultiFrameTiff = True
      self.originalVolumeDimensions = [width, height, pageCount]
      self.originalVolumeNumberOfScalarComponents = samples
      self.originalVolumeVoxelDataType = numpy.dtype(page0.dtype)

      sx, sy = self._readTiffXYSpacing(page0)
      sz = self._readTiffZSpacing(page0, tif)
      self.originalVolumeRecommendedSpacing = [sx, sy, sz]

    return True

  @staticmethod
  def _rationalToFloat(value):
    """TIFF rationals can come back as a (num, denom) tuple or a numpy scalar
    depending on tifffile version. Return a float or 0.0 if not convertible."""
    try:
      if isinstance(value, tuple) and len(value) == 2:
        num, denom = value
        return float(num) / float(denom) if float(denom) != 0.0 else 0.0
      return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
      return 0.0

  @classmethod
  def _readTiffXYSpacing(cls, page):
    """Derive X/Y spacing in millimeters from a TIFF page's resolution tags.
    Returns (sx, sy); each is 0.0 if not determinable."""
    tags = page.tags

    def tagValue(name):
      if name in tags:
        return tags[name].value
      return None

    xres = cls._rationalToFloat(tagValue("XResolution"))
    yres = cls._rationalToFloat(tagValue("YResolution"))
    unit = tagValue("ResolutionUnit")
    # ResolutionUnit: 1 = no unit (treat as undefined), 2 = inch, 3 = centimeter.
    if unit == 2:
      unitToMm = 25.4
    elif unit == 3:
      unitToMm = 10.0
    else:
      # Without a unit we cannot convert to mm reliably. Fall back to 0 so the
      # user is prompted to set spacing manually.
      return 0.0, 0.0
    sx = unitToMm / xres if xres > 0 else 0.0
    sy = unitToMm / yres if yres > 0 else 0.0
    return sx, sy

  @classmethod
  def _readTiffZSpacing(cls, page, tif):
    """Try to read Z spacing from common multi-page TIFF conventions
    (ImageJ hyperstack ImageDescription, OME-TIFF). Returns 0.0 if unknown."""
    # ImageJ writes a `spacing=` token in ImageDescription on the first page.
    desc = None
    if "ImageDescription" in page.tags:
      desc = page.tags["ImageDescription"].value
      if isinstance(desc, bytes):
        try:
          desc = desc.decode("utf-8", errors="replace")
        except Exception:
          desc = None
    if desc:
      match = re.search(r"(?im)^\s*spacing\s*=\s*([0-9.+eE-]+)", desc)
      if match:
        try:
          return float(match.group(1))
        except ValueError:
          pass
      # ImageJ also sometimes writes `unit=micron` etc. — leave that to the user
      # for now; the magnitude alone is what most micro-CT exports need.

    # OME-TIFF carries PhysicalSizeZ in tif.ome_metadata as XML. tifffile exposes
    # parsed series spacings via tif.series[0].axes / .shape, but the spacing
    # itself needs OME XML parsing which we skip in this prototype.
    return 0.0

  def setOriginalVolumeSpacing(self, spacing):
    # Volume is in LPS, therefore we invert the first two axes
    self.originalVolumeIJKToRAS = numpy.diag([-spacing[0], -spacing[1], spacing[2], 1.0])

  def outputVolumeGeometry(self):
    # spacing
    spacingScale = numpy.array([1.0, 1.0, 1.0 + self.sliceSkip])
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

  def loadVolume(self, outputNode=None, progressCallback=None):
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

    validSpacing = all([spacingComponent > 0 for spacingComponent in originalVolumeSpacing])
    if not validSpacing:
      raise ValueError("Invalid original volume spacing. All values must be greater than 0.")

    stepSize = [int(outputSpacing[i] / originalVolumeSpacing[i]) for i in range(3)]

    filePath = self._filePaths[0]
    fileExtension = os.path.splitext(filePath)[1]
    isNrrd = fileExtension.lower() == ".nhdr" or fileExtension.lower() == ".nrrd"
    isMultiFrameTiff = self.isMultiFrameTiff

    # Open the multi-page TIFF once and reuse its file handle across slices, so
    # tifffile decodes only the requested page on each .asarray() call.
    tiffHandle = None
    if isMultiFrameTiff:
      tifffile = self._ensureTifffile()
      tiffHandle = tifffile.TiffFile(filePath)

    try:
      if isNrrd or isMultiFrameTiff:
        paths = ([filePath] * self.originalVolumeDimensions[2])
      else:
        paths = self._filePaths

      # Keep every stepSize[2]'th slice
      paths = paths[::stepSize[2]]

      # For multi-page TIFF the path list is identical strings, so we need an
      # explicit page index for each position. Mirror the same stride/reverse
      # transform applied to `paths` so the two stay in lockstep.
      tiffPageIndices = None
      if isMultiFrameTiff:
        tiffPageIndices = list(range(0, self.originalVolumeDimensions[2], stepSize[2]))

      if self.reverseSliceOrder:
        paths.reverse()
        if tiffPageIndices is not None:
          tiffPageIndices.reverse()

      volumeArray = None
      sliceIndex = 0
      firstArrayFullShape = None

      for inputSliceIndex, path in enumerate(paths):

        if progressCallback:
          toContinue = progressCallback(inputSliceIndex/len(paths))
          if not toContinue:
            raise ValueError("User requested cancel")

        if inputSliceIndex < extent[4] or inputSliceIndex > extent[5]:
          # out of selected bounds
          continue

        if isNrrd:
          sliceArray = self.loadNrrdSlice(path, inputSliceIndex * stepSize[2])
        elif isMultiFrameTiff:
          try:
            sliceArray = tiffHandle.pages[tiffPageIndices[inputSliceIndex]].asarray()
          except (ImportError, ValueError) as e:
            # tifffile delegates JPEG/JPEG2000/WebP decode to the optional
            # imagecodecs package. Surface an actionable message instead of
            # the raw exception so the user can opt in to that dependency
            # manually (we keep it out of the default requirements because
            # its wheels can drag in a numpy ABI change).
            if "imagecodecs" in str(e).lower():
              raise ValueError(
                "This TIFF uses a compression that requires the optional "
                "'imagecodecs' package. Install it from the Slicer Python "
                "console with:\n    slicer.util.pip_install('imagecodecs')"
              ) from e
            raise
        else:
          reader = sitk.ImageFileReader()
          reader.SetFileName(path)
          image = reader.Execute()

          sliceArray = sitk.GetArrayFromImage(image)

        if len(sliceArray.shape) == 3 and self.outputGrayscale:
          # We convert to grayscale by simply taking the first component, which is appropriate for cases when grayscale image is stored as R=G=B,
          # but to convert real RGB images it could better to compute the mean or luminance.
          sliceArray = sliceArray[:,:,0]
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
          message = "There are multiple datasets in the folder. Please select a single file as a sample or specify a pattern.\nDetails:\n"
          message += f"{paths[0]} size is {firstArrayFullShape[0]} x {firstArrayFullShape[1]} ({firstArrayFullShape[2] if len(firstArrayFullShape)==3 else 1} scalar components)\n\n"
          message += f"{path} size is {currentArrayFullShape[0]} x {currentArrayFullShape[1]} ({currentArrayFullShape[2] if len(currentArrayFullShape)==3 else 1} scalar components)"
          raise ValueError(message)

        volumeArray[sliceIndex] = sliceArray
        sliceIndex += 1
    finally:
      if tiffHandle is not None:
        tiffHandle.close()

    newVolume = False
    if not outputNode:
      newVolume = True
      if len(volumeArray.shape) == 3:
        outputNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
      else:
        outputNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode")
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
    if newVolume:
      # Disable compression to speed up saving/loading
      if outputNode.AddDefaultStorageNode():
        outputNode.GetStorageNode().SetUseCompression(0)
    slicer.util.setSliceViewerLayers(background=outputNode, fit=True)
    return outputNode

  def loadNrrdSlice(self, filename, sliceIndex):

    requirementsPath = os.path.join(
      os.path.dirname(slicer.util.modulePath("ImageStacks")),
      "Resources", "requirements_ImageStacks.txt")
    reqs = slicer.packaging.load_requirements(requirementsPath)
    slicer.packaging.pip_ensure(reqs, requester="ImageStacks")
    import nrrd

    from typing import Optional, IO
    from nrrd import NRRDError
    from nrrd.reader import _NRRD_REQUIRED_FIELDS, _determine_datatype, _READ_CHUNKSIZE
    import zlib
    import numpy as np
    import io
    import bz2

    def read_data(header: dict, fh: Optional[IO] = None, filename: Optional[str] = None,
                  index_order: str = 'F', extract_slice_range: Optional[list] = None) -> np.ndarray:
        """Read data from file into :class:`numpy.ndarray`

        The two parameters :obj:`fh` and :obj:`filename` are optional depending on the parameters but it never hurts to
        specify both. The file handle (:obj:`fh`) is necessary if the header is attached with the NRRD data. However, if
        the NRRD data is detached from the header, then the :obj:`filename` parameter is required to obtain the absolute
        path to the data file.

        See :ref:`background/how-to-use:reading nrrd files` for more information on reading NRRD files.

        Parameters
        ----------
        header : :class:`dict` (:class:`str`, :obj:`Object`)
            Parsed fields/values obtained from :meth:`read_header` function
        fh : file-object, optional
            File object pointing to first byte of data. Only necessary if data is attached to header.
        filename : :class:`str`, optional
            Filename of the header file. Only necessary if data is detached from the header. This is used to get the
            absolute data path.
        index_order : {'C', 'F'}, optional
            Specifies the index order of the resulting data array. Either 'C' (C-order) where the dimensions are ordered
            from slowest-varying to fastest-varying (e.g. (z, y, x)), or 'F' (Fortran-order) where the dimensions are
            ordered from fastest-varying to slowest-varying (e.g. (x, y, z)).

        Returns
        -------
        data : :class:`numpy.ndarray`
            Data read from NRRD file

        See Also
        --------
        :meth:`read`, :meth:`read_header`
        """

        if index_order not in ['F', 'C']:
            raise NRRDError('Invalid index order')

        # Check that the required fields are in the header
        for field in _NRRD_REQUIRED_FIELDS:
            if field not in header:
                raise NRRDError(f'Header is missing required field: {field}')

        if header['dimension'] != len(header['sizes']):
            raise NRRDError(f'Number of elements in sizes does not match dimension. Dimension: {header["dimension"]}, '
                            f'len(sizes): {len(header["sizes"])}')

        # Determine the data type from the header
        dtype = _determine_datatype(header)

        # Determine the byte skip, line skip and the data file
        # These all can be written with or without the space according to the NRRD spec, so we check them both
        line_skip = header.get('lineskip', header.get('line skip', 0))
        byte_skip = header.get('byteskip', header.get('byte skip', 0))
        data_filename = header.get('datafile', header.get('data file', None))

        # If the data file is separate from the header file, then open the data file to read from that instead
        if data_filename is not None:
            # If the pathname is relative, then append the current directory from the filename
            if not os.path.isabs(data_filename):
                if filename is None:
                    raise NRRDError('Filename parameter must be specified when a relative data file path is given')

                data_filename = os.path.join(os.path.dirname(filename), data_filename)

            # Override the fh parameter with the data filename
            # Note that this is opened without a "with" block, thus it must be closed manually in all circumstances
            fh = open(data_filename, 'rb')

        # Get the total number of data points by multiplying the size of each dimension together
        total_data_points = header['sizes'].prod(dtype=np.int64)

        # Skip the number of lines requested when line_skip >= 0
        # Irrespective of the NRRD file having attached/detached header
        # Lines are skipped before getting to the beginning of the data
        if line_skip >= 0:
            for _ in range(line_skip):
                fh.readline()
        else:
            # Must close the file because if the file was opened above from detached filename, there is no "with" block to
            # close it for us
            fh.close()

            raise NRRDError('Invalid lineskip, allowed values are greater than or equal to 0')

        extract = extract_slice_range is not None
        if extract:
            frame_item_count = header['sizes'][0] * header['sizes'][1]
            byte_offset_for_extract = int(extract_slice_range[0]) * int(frame_item_count) * int(dtype.itemsize)
            extract_item_count = (extract_slice_range[1] - extract_slice_range[0]) * frame_item_count
        else:
            byte_offset_for_extract = 0
            extract_item_count = total_data_points
            # dtype.itemsize

        # Skip the requested number of bytes or seek backward, and then parse the data using NumPy
        if byte_skip < -1:
            # Must close the file because if the file was opened above from detached filename, there is no "with" block to
            # close it for us
            fh.close()
            raise NRRDError('Invalid byteskip, allowed values are greater than or equal to -1')
        elif byte_skip >= 0:
            fh.seek(byte_skip + byte_offset_for_extract, os.SEEK_CUR)
        elif byte_skip == -1 and header['encoding'] not in ['gzip', 'gz', 'bzip2', 'bz2']:
            fh.seek(-dtype.itemsize * total_data_points + byte_offset_for_extract, os.SEEK_END)
        else:
            # The only case left should be: byte_skip == -1 and header['encoding'] == 'gzip'
            byte_skip = -dtype.itemsize * total_data_points + byte_offset_for_extract

        # If a compression encoding is used, then byte skip AFTER decompressing
        if header['encoding'] == 'raw':
            if isinstance(fh, io.BytesIO):
                raw_data = bytearray(fh.read(extract_item_count * dtype.itemsize))
                data = np.frombuffer(raw_data, dtype)
            else:
                data = np.fromfile(fh, dtype, count = extract_item_count)
        elif header['encoding'] in ['ASCII', 'ascii', 'text', 'txt']:

            if extract:
                # Must close the file because if the file was opened above from detached filename, there is no "with" block to
                # close it for us
                fh.close()

                raise NRRDError(f'Slice extraction is not supported for ASCII data')

            if isinstance(fh, io.BytesIO):
                data = np.fromstring(fh.read(), dtype, sep=' ')
            else:
                data = np.fromfile(fh, dtype, sep=' ')
        else:
            # Handle compressed data now

            if extract:
                # Must close the file because if the file was opened above from detached filename, there is no "with" block to
                # close it for us
                fh.close()

                raise NRRDError(f'Slice extraction is not supported for compressed data')

            # Construct the decompression object based on encoding
            if header['encoding'] in ['gzip', 'gz']:
                decompobj = zlib.decompressobj(zlib.MAX_WBITS | 16)
            elif header['encoding'] in ['bzip2', 'bz2']:
                decompobj = bz2.BZ2Decompressor()
            else:
                # Must close the file because if the file was opened above from detached filename, there is no "with" block
                # to close it for us
                fh.close()

                raise NRRDError(f'Unsupported encoding: {header["encoding"]}')

            # Loop through the file and read a chunk at a time (see _READ_CHUNKSIZE why it is read in chunks)
            decompressed_data = bytearray()

            # Read all the remaining data from the file
            # Obtain the length of the compressed data since we will be using it repeatedly, more efficient
            compressed_data = fh.read()
            compressed_data_len = len(compressed_data)
            start_index = 0

            # Loop through data and decompress it chunk by chunk
            while start_index < compressed_data_len:
                # Calculate the end index = start index plus chunk size
                # Set to the string length to read the remaining chunk at the end
                end_index = min(start_index + _READ_CHUNKSIZE, compressed_data_len)

                # Decompress and append data
                decompressed_data += decompobj.decompress(compressed_data[start_index:end_index])

                # Update start index
                start_index = end_index

            # Delete the compressed data since we do not need it anymore
            # This could potentially be using a lot of memory
            del compressed_data

            # Byte skip is applied AFTER the decompression. Skip first x bytes of the decompressed data and parse it using
            # NumPy
            data = np.frombuffer(decompressed_data[byte_skip:], dtype)

        # Close the file, even if opened using "with" block, closing it manually does not hurt
        fh.close()

        if extract_item_count != data.size:
            raise NRRDError(f'Size of the data does not equal the product of all the dimensions: '
                            f'{total_data_points}-{data.size}={total_data_points - data.size}')

        # In the NRRD header, the fields are specified in Fortran order, i.e, the first index is the one that changes
        # fastest and last index changes slowest. This needs to be taken into consideration since numpy uses C-order
        # indexing.

        # The array shape from NRRD (x,y,z) needs to be reversed as numpy expects (z,y,x).
        sizes = [header['sizes'][0], header['sizes'][1], extract_slice_range[1]-extract_slice_range[0]]
        data = np.reshape(data, tuple(sizes[::-1]))

        # Transpose data to enable Fortran indexing if requested.
        if index_order == 'F':
            data = data.T

        return data

    import nrrd
    with open(filename, 'rb') as fh:
        header = nrrd.read_header(fh)
        sliceArray = read_data(header, fh, filename, index_order = "C", extract_slice_range = [sliceIndex, sliceIndex + 1])
        sliceArray = sliceArray.squeeze()

    return sliceArray


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
