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
      with slicer.util.tryWithErrorDisplay(("Failed to compute results."), waitCursor=True):
          logic = GEVolImportLogic()
          nhdrPathName = logic.generateNHDRHeader(self.inputFileSelector.currentPath)
          slicer.util.loadVolume(nhdrPathName)


class PCRDataObject:
    """Import .pcr file pointing to a .vol file"""
    def __init__(self):
        self.clear()

    def clear(self):
        self.dimensions  = [None, None, None]
        self.spacing = None
        self.scalarType = None

    def load(self, filePath):
        """Import and parse .vol or .pcr file."""

        fileName, fileExtension = os.path.splitext(filePath)
        if fileExtension.lower() == ".vol":
            filePath = fileName + ".pcr"
            if not os.path.isfile(filePath):
                # pcr file is not found
                raise FileNotFoundError(f"PCR file {filePath} was not found for VOL file")


        # Verify that a vol file exists there
        volPathName = fileName + ".vol"
        if not os.path.exists(volPathName):
            raise FileNotFoundError(f"VOL file {volPathName} was not found for PCR file")

        # Parse
        self.clear()
        lines = []
        with open (filePath) as in_file:
            for line in in_file:
                lines.append(line.strip("\n"))
        for element in lines:
            if(element.find("Volume_SizeX=")>=0):
                self.dimensions[0] = int(element.split('=', 1)[1])
            if(element.find("Volume_SizeY=")>=0):
                self.dimensions[1] = int(element.split('=', 1)[1])
            if(element.find("Volume_SizeZ")>=0):
                self.dimensions[2] = int(element.split('=', 1)[1])
            if(element.find("VoxelSizeRec=")>=0):
                self.spacing = float(element.split('=', 1)[1])
            if(element.find("Format=")>=0):
                scalarTypeCode = int(element.split('=')[1])
                if scalarTypeCode == 5:
                    self.scalarType = vtk.VTK_UNSIGNED_SHORT
                elif scalarTypeCode == 10:
                    self.scalarType = vtk.VTK_FLOAT
                elif scalarTypeCode == 1:
                    self.scalarType = vtk.VTK_UNSIGNED_CHAR
                else:
                    raise RuntimeError(f"Unknown Format code: {scalarTypeCode}")

        # Validate parsing results
        if self.dimensions[0] is None:
            raise RuntimeError("Volume_SizeX field is not found in file")
        if self.dimensions[1] is None:
            raise RuntimeError("Volume_SizeY field is not found in file")
        if self.dimensions[2] is None:
            raise RuntimeError("Volume_SizeZ field is not found in file")
        if self.spacing is None:
           pcaFilePath = fileName + ".pca"
           vgiFilePath = fileName + ".vgi"
           if os.path.isfile(pcaFilePath):
               with open (pcaFilePath) as in_file:
                   for line in in_file:
                       lines.append(line.strip("\n"))
               for element in lines:
                   if(element.find("VoxelSizeX=")>=0):
                       self.spacing = float(element.split('=')[1])
           elif os.path.isfile(vgiFilePath):
               with open (vgiFilePath) as in_file:
                   for line in in_file:
                       lines.append(line.strip("\n"))
               for element in lines:
                   if(element.find("resolution")>=0):
                       self.spacing = float(element.split(' ')[2])
           else:
               raise RuntimeError("VoxelSizeRec field is not found in file")
        if self.scalarType is None:
            raise RuntimeError("Format field is not found in file")


class GEVolImportLogic(ScriptedLoadableModuleLogic):

  def generateNHDRHeader(self, inputFile):
    """
    Generate entry of .nhdr file from the .pcr file.Information from .pcr file
    Information from .pcr file: x, y, z, voxel size, .vol file name.
    Parameter "inputfile" is the file path specified by the input file selector wideget
    """

    logging.info('Processing started')

    # Parse PCR file
    imagePCRFile = PCRDataObject()
    imagePCRFile.load(inputFile)

    # Create NRRD header
    filePathName, fileExtension = os.path.splitext(inputFile)
    nhdrPathName = filePathName + ".nhdr"
    with open(nhdrPathName, "w") as headerFile:
        headerFile.write("NRRD0004\n")
        headerFile.write("# Complete NRRD file format specification at:\n")
        headerFile.write("# http://teem.sourceforge.net/nrrd/format.html\n")
        if imagePCRFile.scalarType == vtk.VTK_UNSIGNED_SHORT:
          headerFile.write("type: ushort\n")
        elif imagePCRFile.scalarType == vtk.VTK_FLOAT:
          headerFile.write("type: float\n")
        elif imagePCRFile.scalarType == vtk.VTK_UNSIGNED_CHAR:
          headerFile.write("type: uchar\n")
        headerFile.write("dimension: 3\n")
        headerFile.write("space: left-posterior-superior\n")
        headerFile.write(f"sizes: {imagePCRFile.dimensions[0]} {imagePCRFile.dimensions[1]} {imagePCRFile.dimensions[2]}\n")
        volSpace = imagePCRFile.spacing
        headerFile.write(f"space directions: ({volSpace},0.0,0.0) (0.0,{volSpace},0.0) (0.0,0.0,{volSpace})\n")
        headerFile.write("kinds: domain domain domain\n")
        headerFile.write("endian: little\n")
        headerFile.write("encoding: raw\n")
        headerFile.write("space origin: (0.0, 0.0, 0.0)\n")
        volPathName = filePathName + ".vol"
        volPathSplit = []
        volPathSplit = volPathName.split('/')
        volFileName = volPathSplit[len(volPathSplit)-1]
        headerFile.write(f"data file: {volFileName}\n")

        logging.debug(f".nhdr file path is: {nhdrPathName}")

    return nhdrPathName

#
# Reader plugin
# (identified by its special name <moduleName>FileReader)
#

class GEVolImportFileReader:

    def __init__(self, parent):
        self.parent = parent

    def description(self):
        return 'GE tome microCT image'

    def fileType(self):
        return 'GeVolMicroCT'

    def extensions(self):
        return ['GE tome microCT image (*.vol)', 'GE tome microCT image (*.pcr)']

    def canLoadFileConfidence(self, filePath):
        if not self.parent.supportedNameFilters(filePath):
            return 0.0
        try:
            imagePCRFile = PCRDataObject()
            imagePCRFile.load(filePath)
        except Exception as e:
            return 0.0

        # This is recognized as a GE microCT file, so we return higher confidence than the default 0.5
        return 0.9

    def load(self, properties):
        try:
            filePath = properties['fileName']
            logic = GEVolImportLogic()
            nhdrPathName = logic.generateNHDRHeader(filePath)
            loadedVolume = slicer.util.loadVolume(nhdrPathName)

        except Exception as e:
            logging.error('Failed to load file: ' + str(e))
            import traceback
            traceback.print_exc()
            return False

        self.parent.loadedNodes = [loadedVolume.GetID()]
        return True
