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
This work was was funded 
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
      loadFiles=False,
      fileNames='Gorilla_Skull_LMs.zip',
      thumbnailFileName=os.path.join(iconsPath, 'pointcloud.png'),
      loadFileType='zip',
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Gorilla Skull Reference Model',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/gorilla_reference.mrb?raw=true',
      loadFiles=True,
      fileNames='gorilla_reference.mrb',
      thumbnailFileName=os.path.join(iconsPath, 'gorilla3D.png'),
      loadFileType='SceneFile',
)  
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Mouse Skull Landmarks Only',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/mouse_skull_LMs.zip?raw=true',
      loadFiles=False,
      fileNames='mouse_skull_LMs.zip',
      thumbnailFileName=os.path.join(iconsPath, 'pointcloud.png'),
      loadFileType='zip',
)
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Mouse Skull Reference Model',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/mouse_skull_reference.mrb?raw=true',
      loadFiles=True,
      fileNames='mouse_skull_reference.mrb',
      thumbnailFileName=os.path.join(iconsPath, 'mouse3D.png'),
      loadFileType='SceneFile',
)  
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Bruker/Sykscan mCT Recon sample',
      category='SlicerMorph',
      uris='https://github.com/SlicerMorph/SampleData/blob/master/sample_Skyscan_mCT_reconstruction.zip?raw=true',
      loadFiles=False,
      fileNames='sample_Skyscan_mCT_reconstruction.zip',
      #thumbnailFileName=os.path.join(iconsPath, 'CTPCardio.png'),
      loadFileType='zip',
)
