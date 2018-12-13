FN = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLMarkupsFiducialNode')
landmarkNumber = FN.GetNumberOfFiducials()

pt=[0,0,0]
points = vtk.vtkPoints()
points.SetNumberOfPoints(landmarkNumber*2)
lines = vtk.vtkCellArray()

magnitude = vtk.vtkFloatArray()
magnitude.SetName("Magnitude");
magnitude.SetNumberOfComponents(1);
magnitude.SetNumberOfValues(landmarkNumber);

for landmark in range(0,landmarkNumber):
  FN.GetMarkupPoint(landmark,0,pt)
  endpt=[pt[0]+landmark,pt[1]+landmark,pt[2]+landmark]
  points.SetPoint(landmark,pt)
  points.SetPoint((landmark+landmarkNumber),endpt)
  line = vtk.vtkLine()
  line.GetPointIds().SetId(0,landmark)
  line.GetPointIds().SetId(1,(landmark+landmarkNumber))
  lines.InsertNextCell(line)
  magnitude.InsertValue(landmark,abs(pt[0]-endpt[0]) + abs(pt[1]-endpt[1]) + abs(pt[2]-endpt[2]))
  

polydata=vtk.vtkPolyData()
polydata.SetPoints(points)
polydata.SetLines(lines)
polydata.GetCellData().AddArray(magnitude)



tubeFilter = vtk.vtkTubeFilter()
tubeFilter.SetInputData(polydata)
tubeFilter.SetRadius(0.5)
tubeFilter.SetNumberOfSides(20)
tubeFilter.CappingOn()
tubeFilter.Update()
modelNode = slicer.vtkMRMLModelNode()
slicer.mrmlScene.AddNode(modelNode)
modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
slicer.mrmlScene.AddNode(modelDisplayNode)
modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
modelNode.SetAndObservePolyData(tubeFilter.GetOutput())

modelDisplayNode.SetActiveScalarName('Magnitude')
modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
modelDisplayNode.SetScalarVisibility(True)


