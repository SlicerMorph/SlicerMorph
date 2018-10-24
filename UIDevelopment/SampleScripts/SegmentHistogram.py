import numpy as np
#load scene
slicer.util.loadScene("D:/SlicerWorkspace/SampleData/Quad.mrb")

#Get master volume node
masterVolumeNode = slicer.util.getNode("ResampledQuadricornis")

# Create segmentation
segmentationNode = slicer.util.getNode("Segmentation")


# Create segment editor widget
segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
# Can show widget for debugging
# segmentEditorWidget.show()
segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
slicer.mrmlScene.AddNode(segmentEditorNode)
segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
segmentEditorWidget.setSegmentationNode(segmentationNode)
segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

# Set up masking parameters
segmentEditorWidget.setActiveEffectByName("Mask volume")
effect = segmentEditorWidget.activeEffect()
# set fill value to be outside the valid intensity range
intensityRange = masterVolumeNode.GetImageData().GetScalarRange()
effect.setParameter("FillValue", str(intensityRange[0]-1))
# Blank out voxels that are outside the segment
effect.setParameter("Operation", "FILL_OUTSIDE")
# Create a volume that will store temporary masked volumes
maskedVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Temporary masked volume")
effect.self().outputVolumeSelector.setCurrentNode(maskedVolume)

# Create chart node for histogram
plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode", "Histogram")
#plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

# Create histogram plot data series for each masked volume
for segmentIndex in range(segmentationNode.GetSegmentation().GetNumberOfSegments()):
  segmentID = segmentationNode.GetSegmentation().GetNthSegmentID(segmentIndex)
  segmentEditorWidget.setCurrentSegmentID(segmentID)
  # Apply mask
  effect.self().onApply()
  # Compute histogram values
  histogram = np.histogram(arrayFromVolume(maskedVolume), bins=255, range=intensityRange, density="True")
  # Save results to a new table node
  segment = segmentationNode.GetSegmentation().GetNthSegment(segmentIndex)
  tableNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", segment.GetName() + " histogram table")
  updateTableFromArray(tableNode, histogram)
  tableNode.GetTable().GetColumn(0).SetName("Count") 
  tableNode.GetTable().GetColumn(1).SetName("Intensity")
  # Create new plot data series node
  plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", segment.GetName())
  plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
  plotSeriesNode.SetXColumnName("Intensity")
  plotSeriesNode.SetYColumnName("Count")
  plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
  plotSeriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleNone)
  plotSeriesNode.SetUniqueColor()
  plotSeriesNode.SetPlotType("Bar")
  # Add plot to chart
  plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

# Show chart in layout
slicer.modules.plots.logic().ShowChartInLayout(plotChartNode)
plotChartNode.SetXAxisTitle("Intensity")
plotChartNode.SetYAxisTitle("Count")

# Delete temporary node
slicer.mrmlScene.RemoveNode(maskedVolume)
slicer.mrmlScene.RemoveNode(segmentEditorNode)