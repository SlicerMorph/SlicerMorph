import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# GEVolImport
#

class GEVolImport(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "GEVolImport"  
    self.parent.categories = ["SlicerMorph.Input and Output"]  
    self.parent.dependencies = []  
    self.parent.contributors = ["Chi Zhang (SCRI), Murat Maga (UW)"]  
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """
This module imports VOL files output by the GE tome microCT scanner into 3D Slicer. It parses the PCR file to obtain the 3D image dimensions, voxel spacing, data format and other relevant metadata about the VOL file and generate a NHDR file to load the VOL file into Slicer.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
This module was developed by Chi Zhang and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
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

  # GEVolImport1
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='GEVolImport',
    sampleName='GEVolImport1',
    # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
    # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
    thumbnailFileName=os.path.join(iconsPath, 'GEVolImport1.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
    fileNames='GEVolImport1.nrrd',
    # Checksum to ensure file integrity. Can be computed by this command:
    #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
    checksums = 'SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
    # This node name will be used when the data set is loaded
    nodeNames='GEVolImport1'
  )

  # GEVolImport2
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    # Category and sample name displayed in Sample Data module
    category='GEVolImport',
    sampleName='GEVolImport2',
    thumbnailFileName=os.path.join(iconsPath, 'GEVolImport2.png'),
    # Download URL and target file name
    uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
    fileNames='GEVolImport2.nrrd',
    checksums = 'SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
    # This node name will be used when the data set is loaded
    nodeNames='GEVolImport2'
  )

#
# GEVolImportWidget
#

class GEVolImportWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

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
    # input selector
    #

    # File dialog to select a file template for series
    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.filters  = ctk.ctkPathLineEdit().Files
    self.inputFileSelector.nameFilters = ("*.pcr", )
    self.inputFileSelector.setToolTip( "Select .pcr file from a directory of a .vol file." )
    parametersFormLayout.addRow("Select .pcr file:", self.inputFileSelector)

    #
    # output volume selector
    #
    # self.outputSelector = slicer.qMRMLNodeComboBox()
    # self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    # self.outputSelector.selectNodeUponCreation = True
    # self.outputSelector.addEnabled = True
    # self.outputSelector.removeEnabled = True
    # self.outputSelector.noneEnabled = True
    # self.outputSelector.showHidden = False
    # self.outputSelector.showChildNodeTypes = False
    # self.outputSelector.renameEnabled = True
    # self.outputSelector.setMRMLScene( slicer.mrmlScene )
    # self.outputSelector.setToolTip( "Pick the output to the algorithm." )
    # parametersFormLayout.addRow("Output Volume: ", self.outputSelector)

    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    #self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    #self.enableScreenshotsFlagCheckBox.checked = 0
    #self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    #parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Generate NHDR file")
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

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = bool(self.inputFileSelector.currentPath)


  def onApplyButton(self):
    logic = GEVolImportLogic()
    #enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    #logic.run(self.inputFileSelector.currentPath, enableScreenshotsFlag)
    logic.generateNHDRHeader(self.inputFileSelector.currentPath)


#Import .pcr file pointing to a .vol file

class PCRDataObject:
  """This class i
     """
  def __init__(self):
    self.X  = "NULL"
    self.Y = "NULL"
    self.Z = "NULL"
    self.VoxelSize = "NULL"

  def ImportFromFile(self, pcrFilename):
    #Import and parse .pcr file. File name is 
    lines = [] 					#Declare an empty list to read file into
    with open (pcrFilename, 'rt') as in_file:
      for line in in_file:
        lines.append(line.strip("\n"))     # add that line list, get rid of line endings
      self.form = lines[33].split('=')[1]
      for element in lines:  # For each element in list
        if(element.find("Volume_SizeX=")>=0):
          self.X = int(element.split('=', 1)[1])
        if(element.find("Volume_SizeY=")>=0):
          self.Y = int(element.split('=', 1)[1])
        if(element.find("Volume_SizeZ")>=0):
          self.Z = int(element.split('=', 1)[1])
        if(element.find("VoxelSizeRec=")>=0):
          self.voxelSize = float(element.split('=', 1)[1])


  #def VerifyParameters(self):
    #for attr, value in self.__dict__.items():
        #if(str(value) == "NULL"):
          #logging.debug("Read Failed: Please check log format")
          #logging.debug(attr,value)
          #return False
    #return True


#
# GEVolImportLogic
#

class GEVolImportLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  #def __init__(self):
    #"""
    #Called when the logic class is instantiated. Can be used for initializing member variables.
    #"""
    #ScriptedLoadableModuleLogic.__init__(self)

  

  #def setDefaultParameters(self, parameterNode):
    #"""
    #Initialize parameter node with default settings.
    #"""
    #if not parameterNode.GetParameter("Threshold"):
      #parameterNode.SetParameter("Threshold", "100.0")
    #if not parameterNode.GetParameter("Invert"):
      #parameterNode.SetParameter("Invert", "false")


  def generateNHDRHeader(self, inputFile):
    """
    Generate entrie of .nhdr file from the .pcr file.Information from .pcr file
    Information from .pcr file: x, y, z, voxel size, .vol file name.
    Parameter "inputfile"" is the file path specificed by the input file selector wideget
    """
    
    logging.info('Processing started')
    imagePCRFile = PCRDataObject()   #initialize PCR object
    imagePCRFile.ImportFromFile(inputFile)  #import image parameters of PCR object
    
    #if not(imagePCRFile.VerifyParameters()): #check that all parameters were set
      #logging.info('Failed: PCR file parameters not set')
      #return False
    #if not(self.isValidImageFileType(imagePCRFile.FileType)): #check for valid file type
      #logging.info('Failed: Invalid image type')
      #logging.info(imagePCRFile.FileType)
      #return False
    
    filePathName, fileExtension = os.path.splitext(inputFile)
    nhdrPathName = filePathName + ".nhdr"  #The directory of the .nhdr file
      
    if fileExtension == ".pcr":
      if imagePCRFile.form == '3' or imagePCRFile.form == '5' or imagePCRFile.form =='10':
        with open(nhdrPathName, "w") as headerFile:
          headerFile.write("NRRD0004\n")
          headerFile.write("# Complete NRRD file format specification at:\n")
          headerFile.write("# http://teem.sourceforge.net/nrrd/format.html\n")
          if imagePCRFile.form == '5':
            headerFile.write("type: ushort\n")
          elif imagePCRFile.form == '10':
            headerFile.write("type: float\n")
          else:
            headerFile.write("type: uchar\n") #form =3
          headerFile.write("dimension: 3\n")
          headerFile.write("space: left-posterior-superior\n")
          sizeX = imagePCRFile.X
          sizeY = imagePCRFile.Y
          sizeZ = imagePCRFile.Z
          headerFile.write("sizes: {} {} {}\n".format(sizeX, sizeY, sizeZ))
          volSpace = imagePCRFile.voxelSize
          headerFile.write("space directions: ({}, 0.0, 0.0) (0.0, {}, 0.0) (0.0, 0.0, {})\n".format(volSpace, volSpace, volSpace))
          headerFile.write("kinds: domain domain domain\n")
          headerFile.write("endian: little\n")
          headerFile.write("encoding: raw\n")
          headerFile.write("space origin: (0.0, 0.0, 0.0)\n")
          volPathName = filePathName + ".vol" #The path of the .vol file
          volPathSplit = []
          volPathSplit = volPathName.split('/') #split the file directroy by '/', the last of which is the .vol file name
          volFileName = volPathSplit[len(volPathSplit)-1] #The name of the .vol file
          headerFile.write("data file: {}\n".format(volFileName))
        
        print(".nhdr file path is: {}".format(nhdrPathName))
        #Automatically loading .vol file using the generated .nhdr file.
        slicer.util.loadVolume(nhdrPathName)
        print("{} loaded\n".format(volFileName))
      else:
        print("The format of this dataset is currently not supported by this module. Currently only float (format=10), unsigned 16 bit integer (format=5) and unsigned 8 bit integer (format=1) data types are supported. Please contact us with this dataset to enable this data type. ")
    else:
      print("This is not a PCR file, please re-select a PCR file")
    
    #Automatically rendering volume after .vol file is loaded
    #volRendering = slicer.modules.volumrendering.logic()
    #showNode = volRendering.CreateDefaultVolumeRenderingNodes(VolumNode)
    
    #def showVolumeRendering(volumeNode):
      #volRenLogic = slicer.modules.volumerendering.logic()
      #displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
      #displayNode.SetVisibility(True)
    
    #filePathSplit = []
    #filePathSplit = filePathName.split('/')
    #NodeName = filePathSplit[len(filePathSplit)-1] #File name without extension = node name
    #print("Node name is {}".format(NodeName))
    
    #volNode = slicer.mrmlScene.GetFirstNodeByName(NodeName) #Accessing the loaded node
    #showVolumeRendering(volNode)
    #print("Volume rendering done")

