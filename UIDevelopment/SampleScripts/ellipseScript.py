FN = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLMarkupsFiducialNode')
landmarkNumber = FN.GetNumberOfFiducials()
pt=[0,0,0]
points = vtk.vtkPoints()
points.SetNumberOfPoints(landmarkNumber)
scales = vtk.vtkDoubleArray()
scales.SetName("Scales")

tensors = vtk.vtkDoubleArray()
tensors.SetNumberOfTuples(landmarkNumber)
tensors.SetNumberOfComponents(9)
tensors.SetName("Tensors")

for landmark in range(0,landmarkNumber):
  FN.GetMarkupPoint(landmark,0,pt)
  points.SetPoint(landmark,pt)
  scales.InsertNextValue(landmark)
  tensors.InsertTuple9(landmark,landmark,0,0,0,30,0,0,0,10)

polydata=vtk.vtkPolyData()
polydata.SetPoints(points)
polydata.GetPointData().SetScalars(scales)
polydata.GetPointData().SetTensors(tensors)

sphereSource = vtk.vtkSphereSource()
sphereSource.SetThetaResolution(64)
sphereSource.SetPhiResolution(64)

glyph = vtk.vtkTensorGlyph()
#glyph.SetScaleModeToScaleByScalar()
glyph.SetSourceConnection(sphereSource.GetOutputPort())
glyph.SetInputData(polydata)
glyph.ExtractEigenvaluesOff()
glyph.Update()

modelNode = slicer.vtkMRMLModelNode()
slicer.mrmlScene.AddNode(modelNode)
modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
modelDisplayNode.SetScalarVisibility(True)
modelDisplayNode.SetActiveScalarName('Scales')
modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
slicer.mrmlScene.AddNode(modelDisplayNode)
modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
modelNode.SetAndObservePolyData(glyph.GetOutput())
