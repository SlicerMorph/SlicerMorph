import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin



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
    self.parent.acknowledgementText = """
This module was developed by Chi Zhang and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
"""

    slicer.app.connect("startupCompleted()", registerSampleData)

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')


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



class GEVolImportWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)
    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    # File dialog to select a file template for series
    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.filters  = ctk.ctkPathLineEdit().Files
    self.inputFileSelector.nameFilters = ("*.pcr", )
    self.inputFileSelector.setToolTip( "Select .pcr file from a directory of a .vol file." )
    parametersFormLayout.addRow("Select .pcr file:", self.inputFileSelector)

    self.applyButton = qt.QPushButton("Generate NHDR file")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
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
    logic.generateNHDRHeader(self.inputFileSelector.currentPath)

#Import .pcr file pointing to a .vol file

class PCRDataObject:
  def __init__(self):
    self.X  = "NULL"
    self.Y = "NULL"
    self.Z = "NULL"
    self.VoxelSize = "NULL"

  def ImportFromFile(self, pcrFilename):
    #Import and parse .pcr file. File name is
    lines = []
    with open (pcrFilename) as in_file:
      for line in in_file:
        lines.append(line.strip("\n"))
      self.form = lines[33].split('=')[1]
      for element in lines:
        if(element.find("Volume_SizeX=")>=0):
          self.X = int(element.split('=', 1)[1])
        if(element.find("Volume_SizeY=")>=0):
          self.Y = int(element.split('=', 1)[1])
        if(element.find("Volume_SizeZ")>=0):
          self.Z = int(element.split('=', 1)[1])
        if(element.find("VoxelSizeRec=")>=0):
          self.voxelSize = float(element.split('=', 1)[1])

class GEVolImportLogic(ScriptedLoadableModuleLogic):
  def generateNHDRHeader(self, inputFile):
    """
    Generate entry of .nhdr file from the .pcr file.Information from .pcr file
    Information from .pcr file: x, y, z, voxel size, .vol file name.
    Parameter "inputfile" is the file path specified by the input file selector wideget
    """

    logging.info('Processing started')
    #initialize PCR object
    imagePCRFile = PCRDataObject()
    #import image parameters of PCR object
    imagePCRFile.ImportFromFile(inputFile)

    filePathName, fileExtension = os.path.splitext(inputFile)
    #The directory of the .nhdr file
    nhdrPathName = filePathName + ".nhdr"

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
            headerFile.write("type: uchar\n")
          headerFile.write("dimension: 3\n")
          headerFile.write("space: left-posterior-superior\n")
          sizeX = imagePCRFile.X
          sizeY = imagePCRFile.Y
          sizeZ = imagePCRFile.Z
          headerFile.write(f"sizes: {sizeX} {sizeY} {sizeZ}\n")
          volSpace = imagePCRFile.voxelSize
          headerFile.write(f"space directions: ({volSpace}, 0.0, 0.0) (0.0, {volSpace}, 0.0) (0.0, 0.0, {volSpace})\n")
          headerFile.write("kinds: domain domain domain\n")
          headerFile.write("endian: little\n")
          headerFile.write("encoding: raw\n")
          headerFile.write("space origin: (0.0, 0.0, 0.0)\n")
          volPathName = filePathName + ".vol"
          volPathSplit = []
          volPathSplit = volPathName.split('/')
          volFileName = volPathSplit[len(volPathSplit)-1]
          headerFile.write(f"data file: {volFileName}\n")
        print(f".nhdr file path is: {nhdrPathName}")
        #Automatically loading .vol file using the generated .nhdr file.
        slicer.util.loadVolume(nhdrPathName)
        print(f"{volFileName} loaded\n")
      else:
        print("The format of this dataset is currently not supported by this module. Currently only float (format=10), unsigned 16 bit integer (format=5) and unsigned 8 bit integer (format=1) data types are supported. Please contact us with this dataset to enable this data type.")
    else:
      print("This is not a PCR file, please re-select a PCR file")

