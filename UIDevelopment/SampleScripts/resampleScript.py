# This example demonstrates how to read a directory of images, 
# downsample each slice and form a volume from downsampled slices

import os
import SimpleITK as sitk
import sitkUtils

path = 'D:/SlicerWorkspace/SampleData/tiffs/partialTif/'
shrinkFactor = 10
countFiles = 0
listImages =[]

# set up filter to append downsampled slices sitkUInt8
appendFilter = sitk.TileImageFilter()

# walk directory of images
for root, dirs, files in os.walk(path):  
  for filename in files:
    # check the extension
    (base, ext) = os.path.splitext(filename)
    if ext in ('.tif', '.bmp'):
      countFiles += 1
      filePath = os.path.join(path, filename)
      properties = {'singleFile': True} 
      # read single slice
      [success, tempVolumeNode] = slicer.util.loadVolume(filePath, properties, returnNode=True)
      
      # downsample slice
      shrinkFilter = sitk.ShrinkImageFilter()
      shrinkFilter.SetShrinkFactor(shrinkFactor)
      shrunkImage = shrinkFilter.Execute(tempImage)
      listImages.append(shrunkImage)
      slicer.mrmlScene.RemoveNode(tempVolumeNode)
       

tileFilter = sitk.TileImageFilter()
layout = [1,1,0]
tileFilter.SetLayout(layout)
volumeImage = tileFilter.Execute(listImages)
outputNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode', 'Tiled Volume')
sitkUtils.PushVolumeToSlicer(volumeImage,outputNode)
    
    