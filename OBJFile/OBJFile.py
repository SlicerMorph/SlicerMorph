import logging
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

class OBJFile(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    parent.title = 'OBJFile'
    parent.categories = ['Testing.TestCases']
    parent.dependencies = []
    parent.contributors = ["Chi Zhang (SCRI), Steve Pieper (Isomics)"]
    parent.helpText = '''
    This module is used to implement diffusion nifti reading and writing using the conversion tool from PNL at BWH.
    '''
    parent.acknowledgementText = '''
    Thanks to:

    Billah, Tashrif; Bouix; Sylvain; Rathi, Yogesh; Various MRI Conversion Tools, https://github.com/pnlbwh/conversion, 2019, DOI: 10.5281/zenodo.2584003

    Supported by NIH Grant 5R01MH119222
    '''
    self.parent = parent

# def _NIfTIFileInstallPackage():
#   try:
#     import conversion
#   except ModuleNotFoundError:
#     slicer.util.pip_install("git+https://github.com/pnlbwh/conversion.git@v2.3")


class OBJFileWidget(ScriptedLoadableModuleWidget):
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Default reload&test widgets are enough.
    # Note that reader and writer is not reloaded.

class OBJFileFileReader(object):

  def __init__(self, parent):
    self.parent = parent

  def description(self):
    return 'OBJ textured model'

  def fileType(self):
    return 'OBJ'

  def extensions(self):
    return ['OBJ (*.obj)']

  def canLoadFile(self, filePath):
    # assume yes if it ends in .obj
    # TODO: check for .bval and .bvec in same directory
    return True

  def load(self, properties):
    """
    uses properties:
        obj_path - path to the .obj file
        name (optional) - name for the loaded node
        bval (optional) - path to the bval file, defaults to match fileName
        bvec  (optional)- path to the bvec file, defaults to match fileName
    """
    try:

      # _NIfTIFileInstallPackage()
      # import conversion
      # import nibabel
      # import numpy


      obj_path = properties['fileName'] #obj file path

      # Get node base name from filename
      # if 'name' in properties.keys():
      #   baseName = properties['name']
      # else:
      #   baseName = os.path.splitext(os.path.basename(filePath))[0]
      # baseName = slicer.mrmlScene.GenerateUniqueName(baseName)
      # diffusionNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLDiffusionWeightedVolumeNode', baseName)
      
      obj_dir = os.path.dirname(obj_path)
      obj_filename = os.path.basename(obj_path)
      base_name = os.path.splitext(obj_filename)[0]
      extension = os.path.splitext(obj_filename)[1]
      
      #Add model node
      obj_node = slicer.util.loadModel(obj_path)
      
      #Meanwhie, if the model node ends in obj, search and map texture to it
      if extension == ".obj":
        mtl_filename = base_name + ".mtl"
        mtl_path = os.path.join(obj_dir, mtl_filename)
        
        #parse the mtl file to look for texture image file name
        if os.path.exists(mtl_path):
          with open(mtl_path) as f:
            lines = f.read().splitlines() 
        
        texture_filename = lines[len(lines)-1].split(" ")[1]
        texture_path = os.path.join(obj_dir, texture_filename)
      
        import ImageStacks
        logic = ImageStacks.ImageStacksLogic()
        vectorVolNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode")
        # logic._init_
        logic.outputQuality = 'full'
        logic.outputGrayscale = False
        logic.filePaths = [texture_path]
        logic.loadVolume(outputNode=vectorVolNode, progressCallback = None)
        
        
        import TextureModel
        textureModelLogic = TextureModel.TextureModelLogic()
        textureModelLogic.applyTexture(obj_node, vectorVolNode, None)
        
        slicer.mrmlScene.RemoveNode(vectorVolNode)
          
      
      # measurementFrame = vtk.vtkMatrix4x4()
      # measurementFrame.Identity()
      # measurementFrame.SetElement(0,0,-1)
      # measurementFrame.SetElement(1,1,-1)
      # diffusionNode.SetMeasurementFrameMatrix(measurementFrame)
      # 
      # niftiImage = nibabel.load(filePath)
      # 
      # affine = niftiImage.affine
      # ijkToRAS = vtk.vtkMatrix4x4()
      # for row in range(4):
      #   for column in range(4):
      #     ijkToRAS.SetElement(row, column, affine[row][column])
      # diffusionNode.SetIJKToRASMatrix(ijkToRAS)
      # 
      # fdata = niftiImage.get_fdata()
      # diffusionArray = numpy.transpose(fdata, axes=[2,1,0,3])
      # 
      # diffusionImage = vtk.vtkImageData()
      # dshape = diffusionArray.shape
      # diffusionImage.SetDimensions(dshape[2],dshape[1],dshape[0])
      # diffusionImage.AllocateScalars(vtk.VTK_FLOAT, dshape[3])
      # diffusionNode.SetAndObserveImageData(diffusionImage)
      # 
      # nodeArray = slicer.util.arrayFromVolume(diffusionNode)
      # nodeArray[:] = diffusionArray
      # slicer.util.arrayFromVolumeModified(diffusionNode)
      # 
      # 
      # pathBase = filePath[:-len(".nii.gz")]
      # bvalPath = f"{pathBase}.bval"
      # bvecPath = f"{pathBase}.bvec"
      # bval = conversion.bval_bvec_io.read_bvals(bvalPath)
      # bvec = conversion.bval_bvec_io.read_bvecs(bvecPath)
      # 
      # diffusionNode.SetNumberOfGradients(len(bval))
      # for index in range(len(bval)):
      #   diffusionNode.SetBValue(index, bval[index])
      #   diffusionNode.SetDiffusionGradient(index, bvec[index])
      # 
      # diffusionNode.CreateDefaultDisplayNodes()

    except Exception as e:
      logging.error('Failed to load file: '+str(e))
      import traceback
      traceback.print_exc()
      return False

    self.parent.loadedNodes = [obj_node.GetID()]
    # return True
    return True


# class OBJFileWriter(object):
# 
#   def __init__(self, parent):
#     self.parent = parent
# 
#   def description(self):
#     return 'OBJ textured model'
# 
#   def fileType(self):
#     return 'OBJ'
# 
#   def extensions(self, obj):
#     return ['OBJ (*.obj)']
# 
#   def canWriteObject(self, obj):
#     # Only enable this writer in testing mode
#     if not slicer.app.testingEnabled():
#       return False
# 
#     return bool(obj.IsA("vtkMRMLModelNode"))
# 
#   def write(self, properties):
#     return Fale
# 
# 
# class OBJFileTest(ScriptedLoadableModuleTest):
#   def runTest(self):
#     """Run as few or as many tests as needed here.
#     """
#     self.setUp()
#     self.test_Writer()
#     self.test_Reader()
#     self.tearDown()
#     self.delayDisplay('Testing complete')
# 
#   def setUp(self):
#     self.tempDir = slicer.util.tempDirectory()
#     slicer.mrmlScene.Clear()
# 
#   def tearDown(self):
#     import shutil
#     shutil.rmtree(self.tempDir, True)
# 
#   def test_WriterReader(self):
#     # Writer and reader tests are put in the same function to ensure
#     # that writing is done before reading (it generates input data for reading).
# 
#     # TODO: rewrite this for NIfTI
