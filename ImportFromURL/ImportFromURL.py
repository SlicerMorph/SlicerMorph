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
    self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
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
    filename, extension = os.path.splitext(fileNames)
    if(extension in ['.zip', '.gz']):
      fileTypes = 'ZipFile'
    elif(extension in ['.mrb'] ):
      fileTypes = 'SceneFile'
    elif(extension in ['.dcm', '.nrrd', '.mhd', '.mha', '.hdr', '.img', '.bmp', '.jpg', '.jpeg', '.png', '.tif', '.tiff']):
      fileTypes = 'VolumeFile'
    elif(extension in ['.vtk', '.vtp', '.obj', '.ply', '.stl'] ):
      fileTypes = 'ModelFile'   
    elif(extension in ['.fcsv', '.json'] ):
      fileTypes = 'MarkupsFile'
    else:
      logging.debug('Could not download data. Not a supported file type.')
      
    sampleDataLogic = SampleData.SampleDataLogic()
    loadedNodes = sampleDataLogic.downloadFromURL(
    nodeNames= nodeNames,
    fileNames= fileNames,
    loadFileTypes=fileTypes,
    loadFiles = True,
    uris= url)
            
    # Check if download from URL returned a node collection. If not, then file was downloaded but not imported.
    if isinstance(loadedNodes[0], str):
      logging.debug('Could not import data into the scene. Downloaded to: ' + loadedNodes[0])  
    elif fileTypes == 'VolumeFile':
      self.autoRenderVolume(loadedNodes[0])
        
  def autoRenderVolume(self, volumeNode):
    print("Auto- render node: "+volumeNode.GetName())
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
    logic = ImportFromURLLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
