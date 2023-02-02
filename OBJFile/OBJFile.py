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
    parent.contributors = ["Chi Zhang (SCRI), Steve Pieper (Isomics), A. Murat Maga (UW)"]
    parent.helpText = '''
    This module is used to import OBJ file while automatically map .
    '''
    parent.acknowledgementText = '''
    Thanks to:

    Steve Pieper and Andras Lasso (functions from TextureModel module of SlicerIGT used in this script to map texture)
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
    """
    try:

      obj_path = properties['fileName'] #obj file path
      
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
        
        #parse the mtl file to get texture image file name
        if os.path.exists(mtl_path):
          with open(mtl_path) as f:
            lines = f.read().splitlines()
        
        lines = [i for i in lines if i!='']
        
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
        
        
        #Map texture to the imported OBJ file
        modelDisplayNode = obj_node.GetDisplayNode()
        modelDisplayNode.SetBackfaceCulling(0)
        textureImageFlipVert = vtk.vtkImageFlip()
        textureImageFlipVert.SetFilteredAxis(1)
        textureImageFlipVert.SetInputConnection(vectorVolNode.GetImageDataConnection())
        modelDisplayNode.SetTextureImageDataConnection(textureImageFlipVert.GetOutputPort())
        
        slicer.mrmlScene.RemoveNode(vectorVolNode)

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
