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
    self.parent.contributors = [""]
    self.parent.helpText = """This module adds sample data to SampleData module"""
    self.parent.acknowledgementText = """
This work was was funded 
"""

    # don't show this module - additional data will be shown in SampleData module
    parent.hidden = True 

    # Add data sets to SampleData module
    iconsPath = os.path.join(os.path.dirname(self.parent.path), 'Resources/Icons')
    import SampleData

    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='Mouse Head microCT Atlas',
      #category='SlicerMorph',
      uris='https://github.com/muratmaga/mouse_CT_atlas/blob/3da1c36c057537384376155f347d08b34817fa5c/data/templates/35_mic_23strain_mus_template_UCHAR.nii.gz?raw=true',
      fileNames='35_mic_23strain_mus_template_UCHAR.nii.gz',
      nodeNames='Mus'
      )
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      sampleName='MicroCT Mouse',
      uris='http://slicermorph.fhl.washington.edu/mCT_mouse.mrb',
      loadFiles=True,
      fileNames='mCT_mouse.mrb',
      #thumbnailFileName=os.path.join(iconsPath, 'CTPCardio.png'),
      loadFileType='SceneFile',
      )

      
