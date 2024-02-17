import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# SlicerMorphSampleData
#

class SlicerMorphSampleData(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SlicerMorph Sample Data"
    self.parent.categories = ["SlicerMorph"]
    self.parent.dependencies = ["SampleData"]
    self.parent.contributors = ["Murat Maga & Sara Rolfe"]
    self.parent.helpText = """This module adds sample data for SlicerMorph into the SampleData module"""
    self.parent.acknowledgementText = """
This module was developed by Sara Rolfe and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """

    # don't show this module - additional data will be shown in SampleData module
    parent.hidden = True

    # Add data sets to SampleData module
    iconsPath = os.path.join(os.path.dirname(self.parent.path), 'Resources/Icons')
    import SampleData
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Gorilla Skull Landmarks Only',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/Gorilla_Skull_LMs.zip?raw=true',
      checksums=None,
      loadFiles=False,
      fileNames='Gorilla_Skull_LMs.zip',
      thumbnailFileName=os.path.join(iconsPath, 'pointcloud.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Gorilla Skull Reference Model',
      category='SlicerMorph',
      uris=['https://github.com/SlicerMorph/SampleData/blob/master/Gor_template_low_res.ply?raw=true','https://raw.githubusercontent.com/SlicerMorph/SampleData/master/Gorilla_template_LM1.fcsv?raw=true'],
      checksums=[None, None],
      loadFiles=[False, False],
      fileNames=['Gor_template_low_res.ply', 'Gorilla_template_LM1.fcsv'],
      nodeNames=['Gor_template_low_res', 'Gorilla_template_LM1'],
      thumbnailFileName=os.path.join(iconsPath, 'gorilla3D.png'),
      loadFileType=['ModelFile', 'MarkupsFile'],
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Mouse Skull Landmarks Only',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/mouse_skull_LMs.zip?raw=true',
      checksums=None,
      loadFiles=False,
      fileNames='mouse_skull_LMs.zip',
      thumbnailFileName=os.path.join(iconsPath, 'pointcloud.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Mouse Skull Reference Model',
      category='SlicerMorph',
      uris=['https://github.com/SlicerMorph/SampleData/blob/master/4074_skull.vtk?raw=true', 'https://raw.githubusercontent.com/SlicerMorph/SampleData/master/4074_S_lm1.fcsv?raw=true'],
      checksums=[None, None],
      loadFiles=[False, False],
      fileNames=['4074_skull.vtk','4074_S_lm1.fcsv'],
      nodeNames=['4074_skull', '4074_S_lm1'],
      thumbnailFileName=os.path.join(iconsPath, 'mouse3D.png'),
      loadFileType=['ModelFile','MarkupsFile'],
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Bruker/Sykscan mCT Recon sample',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/sample_Skyscan_mCT_reconstruction.zip?raw=true',
      checksums=None,
      loadFiles=False,
      fileNames='sample_Skyscan_mCT_reconstruction.zip',
      thumbnailFileName=os.path.join(iconsPath, 'microCT_stack_thumbnail.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
)
      SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Auto3dgm sample',
      category='SlicerMorph',
      uris='https://toothandclaw.github.io/files/samples.zip',
      checksums=None,
      loadFiles=False,
      fileNames='samples.zip',
      thumbnailFileName=os.path.join(iconsPath, 'auto3dgm_thumbnail.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Large Apes Skull LMs',
      category='SlicerMorph',
      uris='https://raw.githubusercontent.com/SlicerMorph/SampleData/master/large_apes_manual_LMs.zip',
      checksums=None,
      loadFiles=False,
      fileNames='large_apes_manual_LMs.zip',
      thumbnailFileName=os.path.join(iconsPath, 'pointcloud.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Gorilla patch semi-landmarks',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/0c1e14bee7a4ea85614ba677b45bc693120a5bba/Gorilla%20patch%20semi-landmarks.zip?raw=true',
      checksums=None,
      loadFiles=False,
      fileNames='Gorilla patch semi-landmarks.zip',
      thumbnailFileName=os.path.join(iconsPath, 'gorillaPatchSML.png'),
      loadFileType='ZipFile',
      customDownloader=self.downloadSampleDataInFolder,
    )

  def downloadSampleDataInFolder(self, source):
    sampleDataLogic = slicer.modules.sampledata.widgetRepresentation().self().logic
    # Retrieve directory
    category = "SlicerMorph"
    savedDirectory = slicer.app.userSettings().value(
          "SampleData/Last%sDownloadDirectory" % category,
          qt.QStandardPaths.writableLocation(qt.QStandardPaths.DocumentsLocation))

    destFolderPath = str(qt.QFileDialog.getExistingDirectory(slicer.util.mainWindow(), 'Destination Folder', savedDirectory))
    if not os.path.isdir(destFolderPath):
      return
    print('Selected data folder: %s' % destFolderPath)
    for uri, fileName, checksum  in zip(source.uris, source.fileNames, source.checksums):
      sampleDataLogic.downloadFile(uri, destFolderPath, fileName, checksum)

    # Save directory
    slicer.app.userSettings().setValue("SampleData/Last%sDownloadDirectory" % category, destFolderPath)
    filepath=destFolderPath+"/setup.py"
    if (os.path.exists(filepath)):
      spec = importlib.util.spec_from_file_location("setup",filepath)
      setup = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(setup)
      setup.setup()
