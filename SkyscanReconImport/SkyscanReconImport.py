import os
import glob
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np


#
# SkyscanReconImport
#

class SkyscanReconImport(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "SkyscanReconImport"  # TODO make this more human readable by adding spaces
        self.parent.categories = ["SlicerMorph.Input and Output"]
        self.parent.dependencies = []
        self.parent.contributors = [
            "Murat Maga (UW), Sara Rolfe (UW)"]  # replace with "Firstname Lastname (Organization)"
        self.parent.helpText = """
This module imports an image sequence from Bruker Skyscan microCT's into Slicer as a scalar 3D volume with correct image spacing. Accepted formats are TIF, PNG, JPG and BMP.
User needs to be point out to the *_Rec.log file found in the reconstruction folder.
"""
        self.parent.helpText += self.getDefaultModuleDocumentationLink()
        self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
"""  # replace with organization, grant and thanks.

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
        checksums='SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
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
        checksums='SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
        # This node name will be used when the data set is loaded
        nodeNames='TemplateKey2'
    )


#
# SkyscanReconImportWidget
#

class SkyscanReconImportWidget(ScriptedLoadableModuleWidget):
    """
  Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # Create the tab widget
        self.tabWidget = qt.QTabWidget()
        self.layout.addWidget(self.tabWidget)

        # Setup for existing parameters
        self.parametersTab = qt.QWidget()
        self.parametersTabLayout = qt.QVBoxLayout(self.parametersTab)
        self.setupParametersTab()  # Ensure this method populates the Parameters tab correctly
        self.tabWidget.addTab(self.parametersTab, "Single Mode")

        # Setup for Batch Mode Tab
        self.batchModeTab = qt.QWidget()
        self.batchModeTabLayout = qt.QVBoxLayout(self.batchModeTab)
        self.setupBatchModeTab()  # Correctly call the setup method for Batch Mode tab
        self.tabWidget.addTab(self.batchModeTab, "Batch Mode")

        # Add vertical spacer
        self.layout.addStretch(1)

    def setupParametersTab(self):
        # Parameters Area
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Parameters"
        self.parametersTabLayout.addWidget(parametersCollapsibleButton)

        # Layout within the parameters collapsible button
        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        # input selector
        self.inputFileSelector = ctk.ctkPathLineEdit()
        self.inputFileSelector.filters = ctk.ctkPathLineEdit().Files
        self.inputFileSelector.setToolTip('Choose log file from a directory of images.')
        parametersFormLayout.addRow("Choose log file from image series:", self.inputFileSelector)

        # Encoding Selector
        self.defaultCodingButton = qt.QRadioButton("Default")
        self.defaultCodingButton.checked = True
        self.utf8CodingButton = qt.QRadioButton("Utf-8")
        self.latin1CodingButton = qt.QRadioButton("Latin-1")
        self.encodingSelector = qt.QVBoxLayout()
        self.encodingSelector.addWidget(self.defaultCodingButton)
        self.encodingSelector.addWidget(self.utf8CodingButton)
        self.encodingSelector.addWidget(self.latin1CodingButton)
        parametersFormLayout.addRow("Select log file encoding type: ", self.encodingSelector)

        # Apply Button
        self.applyButton = qt.QPushButton("Apply")
        self.applyButton.toolTip = "Run the algorithm."
        self.applyButton.enabled = False
        parametersFormLayout.addRow(self.applyButton)

        # Connections
        self.applyButton.connect('clicked(bool)', self.onApplyButton)
        self.inputFileSelector.connect("currentPathChanged(const QString &)", self.onSelect)

    def setupBatchModeTab(self):
        # Directory selector for Batch Mode
        self.directorySelector = ctk.ctkPathLineEdit()
        self.directorySelector.filters = ctk.ctkPathLineEdit.Dirs
        self.directorySelector.setToolTip("Select the main directory for batch processing.")
        self.batchModeTabLayout.addWidget(qt.QLabel("Main Directory:"))
        self.batchModeTabLayout.addWidget(self.directorySelector)

        # Button to find log files
        self.findFilesButton = qt.QPushButton("Find Log Files")
        self.findFilesButton.toolTip = "Search for log files in the specified directory."
        self.batchModeTabLayout.addWidget(self.findFilesButton)

        # Modify the List widget to display found log files with checkboxes
        self.logFilesList = qt.QListWidget()
        self.batchModeTabLayout.addWidget(self.logFilesList)

        # Directory selector for Full Resolution NRRD Export
        self.fullResOutputSelector = ctk.ctkPathLineEdit()
        self.fullResOutputSelector.filters = ctk.ctkPathLineEdit.Dirs
        self.fullResOutputSelector.setToolTip("Select the output directory for full resolution NRRD volumes.")
        self.batchModeTabLayout.addWidget(qt.QLabel("Full Resolution NRRD Output:"))
        self.batchModeTabLayout.addWidget(self.fullResOutputSelector)

        # Directory selector for Downsampled NRRD Export
        self.downsampledOutputSelector = ctk.ctkPathLineEdit()
        self.downsampledOutputSelector.filters = ctk.ctkPathLineEdit.Dirs
        self.downsampledOutputSelector.setToolTip("Select the output directory for downsampled NRRD volumes.")
        self.batchModeTabLayout.addWidget(qt.QLabel("Downsampled NRRD Output:"))
        self.batchModeTabLayout.addWidget(self.downsampledOutputSelector)

        # Downsample Ratio Selection with Checkboxes
        self.downsampleRatioGroup = qt.QGroupBox("Downsample Ratio")
        self.downsampleRatioLayout = qt.QHBoxLayout()  # Use QHBoxLayout for horizontal layout
        self.halfResCheckBox = qt.QCheckBox("1/2 Resolution")
        self.quarterResCheckBox = qt.QCheckBox("1/4 Resolution")
        self.downsampleRatioLayout.addWidget(self.halfResCheckBox)
        self.downsampleRatioLayout.addWidget(self.quarterResCheckBox)
        self.downsampleRatioGroup.setLayout(self.downsampleRatioLayout)
        self.batchModeTabLayout.addWidget(self.downsampleRatioGroup)

        # Start Batch Processing Button
        self.startBatchProcessingButton = qt.QPushButton("Start Batch Processing")
        self.startBatchProcessingButton.toolTip = "Start the batch processing with the specified settings."
        self.batchModeTabLayout.addWidget(self.startBatchProcessingButton)

        # Connections
        self.findFilesButton.clicked.connect(self.onFindFilesButtonClicked)
        self.startBatchProcessingButton.clicked.connect(self.onStartBatchProcessingClicked)

    def onFindFilesButtonClicked(self):
        mainDirectory = self.directorySelector.currentPath
        if mainDirectory:
            logFiles = self.find_rec_log_files(mainDirectory)
            self.logFilesList.clear()  # Clear existing items before adding new ones
            for logFile in logFiles:
                # Create a QListWidgetItem for each log file
                item = qt.QListWidgetItem(logFile)
                item.setFlags(item.flags() | qt.Qt.ItemIsUserCheckable)  # Add checkbox feature
                item.setCheckState(qt.Qt.Unchecked)  # Set the checkbox to unchecked, or qt.Qt.Checked for checked
                self.logFilesList.addItem(item)  # Add the item with a checkbox to the list
        else:
            slicer.util.errorDisplay("Please select a valid directory.")

    def getSelectedLogFiles(self):
        selectedLogFiles = []
        for index in range(self.logFilesList.count):
            item = self.logFilesList.item(index)
            if item.checkState() == qt.Qt.Checked:
                selectedLogFiles.append(item.text())
        return selectedLogFiles

    def getDownsampleRatio(self):
        """
        Returns the downsampling ratio selection as a tuple of booleans.

        Returns:
            tuple: (isHalfResChecked, isQuarterResChecked)
                - isHalfResChecked (bool): True if "1/2 Resolution" is checked, False otherwise.
                - isQuarterResChecked (bool): True if "1/4 Resolution" is checked, False otherwise.
        """
        isHalfResChecked = self.halfResCheckBox.isChecked()
        isQuarterResChecked = self.quarterResCheckBox.isChecked()
        return [isHalfResChecked, isQuarterResChecked]

    @staticmethod
    def find_rec_log_files(main_folder):
        log_files = []
        # First pass to determine the total number of directories (optional for precise progress)
        total_dirs = sum([len(dirs) for r, dirs, f in os.walk(main_folder)])
        progress = slicer.util.createProgressDialog(windowTitle="Searching Log Files",
                                                    labelText="Searching for log files...", maximum=total_dirs)

        dir_count = 0
        for root, dirs, files in os.walk(main_folder):
            if root.endswith('_Rec') or root.endswith('_rec'):
                for log_file in glob.glob(os.path.join(root, '*_rec.log')):
                    log_files.append(log_file)
                    # Update progress dialog with the count of log files found
                    progress.labelText = f"Found {len(log_files)} log file(s)..."
                    slicer.app.processEvents()  # Process UI events to update the dialog text

            dir_count += 1
            progress.value = dir_count
            slicer.app.processEvents()  # Process UI events to update the progress bar

            if progress.wasCanceled:
                break  # Allow cancellation of search

        progress.close()
        return log_files

    def onStartBatchProcessingClicked(self):
        # Check if log files list is populated

        selectedLogFiles = self.getSelectedLogFiles()

        if len(selectedLogFiles) == 0:
            slicer.util.errorDisplay("No log files found. Please find log files before starting batch processing.")
            return

        # Check if output directories are specified
        fullResOutputPath = self.fullResOutputSelector.currentPath.strip()
        downsampledOutputPath = self.downsampledOutputSelector.currentPath.strip()
        if not fullResOutputPath or not downsampledOutputPath:
            slicer.util.errorDisplay("Please specify both full resolution and downsampled output directories.")
            return

        # Check if downsample ratio is selected (this is optional as default value is set)
        downsampleRatios = self.getDownsampleRatio()

        # Proceed with batch processing logic here, utilizing the specified parameters
        self.startBatchProcessing(logFilesList=selectedLogFiles, fullResOutputPath=fullResOutputPath,
                                  downsampledOutputPath=downsampledOutputPath, downsampleRatio=downsampleRatios)

    @staticmethod
    def startBatchProcessing(logFilesList, fullResOutputPath, downsampledOutputPath, downsampleRatio):
        progress = slicer.util.createProgressDialog(windowTitle="Batch Processing",
                                                    labelText="Starting batch processing...", maximum=len(logFilesList))
        progress.setValue(0)  # Initialize progress at 0
        logic = SkyscanReconImportLogic()

        for i, logFile in enumerate(logFilesList):
            try:
                progress.labelText = f"Processing {os.path.basename(logFile)} ({i + 1}/{len(logFilesList)})"
                slicer.app.processEvents()  # Update the progress dialog to reflect the new label text

                # Assuming 'logic.run' processes the log and 'logic.saveVolumes' saves the volumes
                # Update these calls as necessary according to your actual logic's methods and parameters
                logic.run(logFile, 'utf8')  # Placeholder for your processing logic
                logic.saveVolumes(logic.prefix_list[i], fullResOutputPath,
                                  downsampledOutputPath, downsampleRatio)  # Placeholder for saving logic

            except Exception as e:
                print(f"Error processing {logFile}: {e}")  # Print the error message

            finally:
                progress.setValue(i + 1)  # Update the progress value regardless of success or failure

                if progress.wasCanceled:
                    break  # Allow the user to cancel the operation

        progress.close()  # Close the progress dialog once processing is complete

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
        self.X = "NULL"
        self.Y = "NULL"
        self.Z = "NULL"
        self.Resolution = "NULL"
        self.Prefix = "NULL"
        self.IndexLength = "NULL"
        self.SequenceStart = "NULL"
        self.SequenceEnd = "NULL"

    def ImportFromFile(self, LogFilename, encodingType):
        lines = []  # Declare an empty list to read file into
        with open(LogFilename, encoding=encodingType) as in_file:
            for line in in_file:
                lines.append(line.strip("\n"))  # add that line list, get rid of line endings
            for element in lines:  # For each element in list
                if (element.find("Result File Type=") >= 0):
                    self.FileType = element.split('=', 1)[1].lower()  # get standard lowercase
                    print(self.FileType)
                    print(element.split('=', 1)[1])
                if (element.find("Result Image Width (pixels)=") >= 0):
                    self.X = int(element.split('=', 1)[1])
                if (element.find("Result Image Height (pixels)=") >= 0):
                    self.Y = int(element.split('=', 1)[1])
                if (element.find("Sections Count=") >= 0):
                    self.Z = int(element.split('=', 1)[1])
                if (element.find("Pixel Size (um)=") >= 0):
                    self.Resolution = float(element.split('=', 1)[1]) / 1000  # convert from um to mm
                if (element.find("Filename Prefix=") >= 0):
                    self.Prefix = element.split('=', 1)[1]
                if (element.find("Filename Index Length=") >= 0):
                    self.IndexLength = element.split('=', 1)[1]
                if (element.find("First Section=") >= 0):
                    self.SequenceStart = element.split('=', 1)[1]
                if (element.find("Last Section=") >= 0):
                    self.SequenceEnd = element.split('=', 1)[1]
        self.SequenceStart = self.SequenceStart.zfill(int(self.IndexLength))  # pad with zeros to index length
        self.SequenceEnd = self.SequenceEnd.zfill(int(self.IndexLength))  # pad with zeros to index length

    def VerifyParameters(self):
        for attr, value in self.__dict__.items():
            if (str(value) == "NULL"):
                logging.debug("Read Failed: Please check log format")
                logging.debug(attr, value)
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

    def __init__(self):
        self.prefix_list = []

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
        slicer.qMRMLUtils().qImageToVtkImageData(qimage, imageData)

        annotationLogic = slicer.modules.annotations.logic()
        annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

    def applySkyscanTransform(self, volumeNode):
        # set up transform node
        transformNode = slicer.vtkMRMLTransformNode()
        slicer.mrmlScene.AddNode(transformNode)
        volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

        # set up Skyscan transform
        transformMatrixNp = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
        transformMatrixVTK = vtk.vtkMatrix4x4()
        for row in range(4):
            for col in range(4):
                transformMatrixVTK.SetElement(row, col, transformMatrixNp[row, col])

        transformNode.SetMatrixTransformToParent(transformMatrixVTK)

        # harden and clean up
        slicer.vtkSlicerTransformLogic().hardenTransform(volumeNode)
        slicer.mrmlScene.RemoveNode(transformNode)

    def run(self, inputFile, encodingType):
        """
    Run the actual algorithm
    """
        # parse logfile
        logging.info('Processing started')
        imageLogFile = LogDataObject()  # initialize log object
        imageLogFile.ImportFromFile(inputFile, encodingType)  # import image parameters of log object

        if not (imageLogFile.VerifyParameters()):  # check that all parameters were set
            logging.info('Failed: Log file parameters not set')
            return False
        if not (self.isValidImageFileType(imageLogFile.FileType)):  # check for valid file type
            logging.info('Failed: Invalid image type')
            logging.info(imageLogFile.FileType)
            return False

        # read image
        (inputDirectory, logPath) = os.path.split(inputFile)
        imageFileTemplate = os.path.join(inputDirectory,
                                         imageLogFile.Prefix + imageLogFile.SequenceStart + "." + imageLogFile.FileType)
        readVolumeNode = slicer.util.loadVolume(imageFileTemplate)
        # calculate image spacing
        spacing = [imageLogFile.Resolution, imageLogFile.Resolution, imageLogFile.Resolution]

        # accumulate prefixes for each item run (I don't want to change what's returned)
        self.prefix_list.append(imageLogFile.Prefix)

        # if vector image, convert to scalar using luminance (0.30*R + 0.59*G + 0.11*B + 0.0*A)
        # check if loaded volume is vector type, if so convert to scalar
        if readVolumeNode.GetClassName() == 'vtkMRMLVectorVolumeNode':
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
            scalarVolumeNode.SetImageDataConnection(luminance.GetOutputPort())  # apply
            slicer.mrmlScene.RemoveNode(readVolumeNode)

        else:
            scalarVolumeNode = readVolumeNode
            scalarVolumeNode.SetSpacing(spacing)
            scalarVolumeNode.SetName(imageLogFile.Prefix)

        self.applySkyscanTransform(scalarVolumeNode)
        slicer.util.resetSliceViews()  # update the field of view

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
            'ThresholdValue': imageThreshold,
            'ThresholdType': 'Above' if invert else 'Below'
        }
        cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True,
                                 update_display=showResult)
        # We don't need the CLI module node anymore, remove it to not clutter the scene with it
        slicer.mrmlScene.RemoveNode(cliNode)

        stopTime = time.time()
        logging.info(f'Processing completed in {stopTime - startTime:.2f} seconds')

    @staticmethod
    def saveVolumes(node_name, fullRespath, dsResPath, resolution):
        volumeNode = slicer.util.getNode(node_name)

        # Save the full resolution volume
        fullRespath = os.path.join(fullRespath, node_name + ".nrrd")
        slicer.util.exportNode(volumeNode, fullRespath, {"useCompression": 0})

        # Function to crop and save volume at specified resolution
        def cropAndSave(downsampleRatio, suffix):
            # Create a new ROI node and ensure it's not visible
            roiNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")
            roiDisplayNode = roiNode.GetDisplayNode()
            if roiDisplayNode:
                roiDisplayNode.SetVisibility(False)  # Hide in 3D view

            # Set the new markup ROI to the dimensions of the volume loaded
            cropVolumeParameters = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
            cropVolumeParameters.SetInputVolumeNodeID(volumeNode.GetID())
            cropVolumeParameters.SetROINodeID(roiNode.GetID())
            slicer.modules.cropvolume.logic().SnapROIToVoxelGrid(cropVolumeParameters)
            slicer.modules.cropvolume.logic().FitROIToInputVolume(cropVolumeParameters)
            slicer.mrmlScene.RemoveNode(cropVolumeParameters)

            # Set the cropping parameters
            cropVolumeLogic = slicer.modules.cropvolume.logic()
            cropVolumeParameterNode = slicer.vtkMRMLCropVolumeParametersNode()
            cropVolumeParameterNode.SetIsotropicResampling(True)
            cropVolumeParameterNode.SetSpacingScalingConst(downsampleRatio)
            cropVolumeParameterNode.SetROINodeID(roiNode.GetID())
            cropVolumeParameterNode.SetInputVolumeNodeID(volumeNode.GetID())

            # Do the cropping
            cropVolumeLogic.Apply(cropVolumeParameterNode)

            # Create the cropped volume
            croppedVolume = slicer.mrmlScene.GetNodeByID(cropVolumeParameterNode.GetOutputVolumeNodeID())

            # Save the downsampled volume
            dsPath = os.path.join(dsResPath, f"{node_name}{suffix}.nrrd")
            slicer.util.exportNode(croppedVolume, dsPath, {"useCompression": 0})

            # Cleanup: Remove temporary nodes
            slicer.mrmlScene.RemoveNode(croppedVolume)
            slicer.mrmlScene.RemoveNode(roiNode)

        # Check and create downsampled volumes based on resolution flags
        if resolution[0]:  # If 1/2 resolution is selected
            cropAndSave(2, "-ds2")
        if resolution[1]:  # If 1/4 resolution is selected
            cropAndSave(4, "-ds4")

        # Cleanup: Remove the original volume node as it's no longer needed
        slicer.mrmlScene.RemoveNode(volumeNode)


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
