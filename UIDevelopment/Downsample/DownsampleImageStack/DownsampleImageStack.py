import SimpleITK as sitk
import sitkUtils
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
#
# DownsampleImageStack
#

class DownsampleImageStack(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "DownsampleImageStack" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Examples"]
    self.parent.dependencies = []
    self.parent.contributors = ["John Doe (AnyWare Corp.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
It performs a simple thresholding on the input volume and optionally captures a screenshot.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# DownsampleImageStackWidget
#

class DownsampleImageStackWidget(ScriptedLoadableModuleWidget):
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
    # input directory selector
    #
    self.inputDirectory = ctk.ctkDirectoryButton()
    self.inputDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Input Directory:", self.inputDirectory)
    
    #self.inputFiles = ctk.ctkFileDialog()
    #parametersFormLayout.addRow("Input Files:", self.inputFiles)
    #
    # output volume selector
    #
    self.outputSelector = slicer.qMRMLNodeComboBox()
    self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.outputSelector.selectNodeUponCreation = True
    self.outputSelector.addEnabled = True
    self.outputSelector.removeEnabled = True
    self.outputSelector.noneEnabled = True
    self.outputSelector.showHidden = False
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.setMRMLScene( slicer.mrmlScene )
    self.outputSelector.setToolTip( "Pick the output to the algorithm." )
    parametersFormLayout.addRow("Output Volume: ", self.outputSelector)

    #
    # shrink factor
    #
    self.resampleFactorWidget = ctk.ctkCoordinatesWidget()
    self.resampleFactorWidget.coordinates = '1,1,1'
    self.resampleFactorWidget.minimum = 1
    self.resampleFactorWidget.singleStep = 1
    self.resampleFactorWidget.setToolTip("Select Downsample factor in the XYZ directions")
    parametersFormLayout.addRow("Downsample factor:", self.resampleFactorWidget)
    
    #
    # spacing factor
    #
    self.spacingWidget = ctk.ctkCoordinatesWidget()
    self.spacingWidget.coordinates = '1,1,1'
    self.spacingWidget.minimum = 0
    self.spacingWidget.singleStep = .0001
    self.spacingWidget.decimals = 5
    self.spacingWidget.setToolTip("Spacing in the XYZ directions")
    parametersFormLayout.addRow("Spacing:", self.spacingWidget)
    
    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.outputSelector.currentNode()

  def onApplyButton(self):
    logic = DownsampleImageStackLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    shrinkFactorX = int(self.resampleFactorWidget.coordinates.split(',')[0])
    shrinkFactorY = int(self.resampleFactorWidget.coordinates.split(',')[1])
    shrinkFactorZ = int(self.resampleFactorWidget.coordinates.split(',')[2])
    spacingX = self.spacingWidget.coordinates.split(',')[0]
    spacingY = self.spacingWidget.coordinates.split(',')[1]
    spacingZ = self.spacingWidget.coordinates.split(',')[2]
    logic.run(
      self.inputDirectory.directory, 
      self.outputSelector.currentNode(), 
      int(shrinkFactorX),
      int(shrinkFactorY),
      int(shrinkFactorZ),   
      float(spacingX),
      float(spacingY),
      float(spacingZ),
      enableScreenshotsFlag)

#
# DownsampleImageStackLogic
#

class DownsampleImageStackLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def hasImageData(self,volumeNode):
    """This is an example logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      logging.debug('hasImageData failed: no volume node')
      return False
    if volumeNode.GetImageData() is None:
      logging.debug('hasImageData failed: no image data in volume node')
      return False
    return True

  def isValidInputOutputData(self, inputVolumeNode, outputVolumeNode):
    """Validates if the output is not the same as input
    """
    if not inputVolumeNode:
      logging.debug('isValidInputOutputData failed: no input volume node defined')
      return False
    if not outputVolumeNode:
      logging.debug('isValidInputOutputData failed: no output volume node defined')
      return False
    if inputVolumeNode.GetID()==outputVolumeNode.GetID():
      logging.debug('isValidInputOutputData failed: input and output volume is the same. Create a new volume for output to avoid this error.')
      return False
    return True

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

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

  def resample_sitk(self, sitkImage, factorX, factorY, factorZ):
     #take an image in sitk, resample in each dimension and return resampled sitk image
    pixelid = sitkImage.GetPixelIDValue()
    origin = sitkImage.GetOrigin()
    direction = sitkImage.GetDirection()
    spacing = np.array(sitkImage.GetSpacing())
    size = np.array(sitkImage.GetSize(), dtype=np.int)
    
    newSpacing = [spacing[0]*factorX, spacing[1]*factorY, spacing[2]*factorX]
    newSize = size*(spacing/newSpacing)
    # set image dimensions in integers
    newSize = np.ceil(newSize).astype(np.int) 
    newSize = [int(s) for s in newSize] 
    resizeFilter = sitk.ResampleImageFilter()
    resizeFilter.SetOutputPixelType(pixelid)
    resizeFilter.SetOutputSpacing(newSpacing)
    resizeFilter.SetOutputDirection(direction)
    resizeFilter.SetOutputOrigin(origin)
    resizeFilter.SetSize(newSize)
    resizedImage = resizeFilter.Execute(sitkImage)
    
    return(resizedImage)
    
  def run(self, inputDirectory, outputVolume, shrinkFactorX, shrinkFactorY, shrinkFactorZ, spacingX, spacingY, spacingZ, enableScreenshots=0):
    """
    Run the actual algorithm
    """

    logging.info('Processing started')
    countFiles = 0
    listImages =[]
    
    # set up filter to append downsampled slices
    appendFilter = sitk.TileImageFilter()

    # walk directory of images
    for root, dirs, files in os.walk(inputDirectory):  
      for filename in files:
        # check the extension
        (base, ext) = os.path.splitext(filename)
        if ext in ('.tif', '.bmp', '.jpg', 'tiff', '.jpeg'):
          countFiles += 1
          filePath = os.path.join(inputDirectory, filename)
          properties = {'singleFile': True} 
          # read single slice
          [success, tempVolumeNode] = slicer.util.loadVolume(filePath, properties, returnNode=True)
          spacing = [(spacingX), (spacingY), (spacingZ)]
          tempVolumeNode.SetSpacing(spacing)
          # if needed, convert to scalar using luminance (0.30*R + 0.59*G + 0.11*B + 0.0*A)
          if ext not in ('.tif', 'tiff'):
            extractVTK = vtk.vtkImageExtractComponents()
            extractVTK.SetInputConnection(tempVolumeNode.GetImageDataConnection())
            extractVTK.SetComponents(0, 1, 2)
            luminance = vtk.vtkImageLuminance()
            luminance.SetInputConnection(extractVTK.GetOutputPort())
            luminance.Update()
            tempVolumeNode.SetImageDataConnection(luminance.GetOutputPort())
          # import to sitk
          tempImage = sitkUtils.PullVolumeFromSlicer(tempVolumeNode)
          # downsample slice
          shrunkImage = self.resample_sitk(tempImage, shrinkFactorX, shrinkFactorY, shrinkFactorZ)
          listImages.append(shrunkImage)
          slicer.mrmlScene.RemoveNode(tempVolumeNode)
       

    # stack images into 3d volume
    tileFilter = sitk.TileImageFilter()
    # specify layout in number of tiles per dimension, 0 for unrestricted
    layout = [1,1,0]
    tileFilter.SetLayout(layout)
    volumeImage = tileFilter.Execute(listImages)    
    sitkUtils.PushVolumeToSlicer(volumeImage,outputVolume)


    # Capture screenshot
    if enableScreenshots:
      self.takeScreenshot('DownsampleImageStackTest-Start','MyScreenshot',-1)

    logging.info('Processing completed')

    return True


class DownsampleImageStackTest(ScriptedLoadableModuleTest):
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
    self.test_DownsampleImageStack1()

  def test_DownsampleImageStack1(self):
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
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = DownsampleImageStackLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
