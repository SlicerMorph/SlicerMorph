import datetime
import json
import logging
import math
import os
import time
from collections import deque

import numpy as np
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk

# Optional unsupervised AI backend. The module must remain fully functional (geometric
# pipeline only) when scikit-learn is not installed; never import it at module scope
# beyond this guarded try/except, and never attempt to install it automatically.
try:
  from sklearn.ensemble import IsolationForest
  SKLEARN_AVAILABLE = True
except Exception:
  IsolationForest = None
  SKLEARN_AVAILABLE = False

#
# SurfaceResidualAnomalyDetector
#

class SurfaceResidualAnomalyDetector(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Surface Residual Anomaly Detector"
    self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["SlicerMorph"]
    self.parent.helpText = """
      Unsupervised Surface Anomaly Detection from Smoothing Residuals.
      Compares an input model with a smoothed copy of itself and displays the
      per-vertex geometric residual as a robust anomaly heatmap. See the module README for
      details on mesh cleanup, residual denoising, and the interpretation of the results.
      """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
      """


#
# SurfaceResidualAnomalyDetectorWidget
#

class SurfaceResidualAnomalyDetectorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.logic = None
    self.hasRunOnce = False

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    self.logic = SurfaceResidualAnomalyDetectorLogic()

    #
    # Input Area
    #
    inputCollapsibleButton = ctk.ctkCollapsibleButton()
    inputCollapsibleButton.text = "Input"
    self.layout.addWidget(inputCollapsibleButton)
    inputFormLayout = qt.QFormLayout(inputCollapsibleButton)

    self.modelSelector = slicer.qMRMLNodeComboBox()
    self.modelSelector.nodeTypes = ["vtkMRMLModelNode"]
    self.modelSelector.selectNodeUponCreation = True
    self.modelSelector.addEnabled = False
    self.modelSelector.removeEnabled = False
    self.modelSelector.noneEnabled = True
    self.modelSelector.showHidden = False
    self.modelSelector.setMRMLScene(slicer.mrmlScene)
    self.modelSelector.setToolTip("Select the input surface model to analyze.")
    inputFormLayout.addRow("Input model: ", self.modelSelector)

    #
    # Mesh Cleanup Area
    #
    cleanupCollapsibleButton = ctk.ctkCollapsibleButton()
    cleanupCollapsibleButton.text = "Mesh Cleanup"
    self.layout.addWidget(cleanupCollapsibleButton)
    cleanupFormLayout = qt.QFormLayout(cleanupCollapsibleButton)

    self.removeSmallComponentsCheckBox = qt.QCheckBox()
    self.removeSmallComponentsCheckBox.setChecked(True)
    self.removeSmallComponentsCheckBox.setToolTip(
      "Remove small disconnected acquisition fragments before analysis, using vtkPolyDataConnectivityFilter. "
      "The main anatomical surface is preserved; only tiny floating fragments are dropped.")
    cleanupFormLayout.addRow("Remove small disconnected components: ", self.removeSmallComponentsCheckBox)

    self.componentThresholdSlider = ctk.ctkSliderWidget()
    self.componentThresholdSlider.singleStep = 0.01
    self.componentThresholdSlider.decimals = 2
    self.componentThresholdSlider.minimum = 0.01
    self.componentThresholdSlider.maximum = 5.0
    self.componentThresholdSlider.value = 0.1
    self.componentThresholdSlider.suffix = " %"
    self.componentThresholdSlider.setToolTip(
      "Connected components with fewer than this percentage of the total mesh points are removed.")
    cleanupFormLayout.addRow("Component-size threshold: ", self.componentThresholdSlider)

    self.keepLargestOnlyCheckBox = qt.QCheckBox()
    self.keepLargestOnlyCheckBox.setChecked(False)
    self.keepLargestOnlyCheckBox.setToolTip(
      "Keep only the single largest connected component, discarding every other fragment "
      "regardless of size. Overrides the component-size threshold when enabled.")
    cleanupFormLayout.addRow("Keep largest component only: ", self.keepLargestOnlyCheckBox)

    self.removeWeakComponentsCheckBox = qt.QCheckBox()
    self.removeWeakComponentsCheckBox.setChecked(False)
    self.removeWeakComponentsCheckBox.setToolTip(
      "Progressive erosion: peels away vertices with few remaining neighbors over several "
      "iterations to find and remove appendages that are only weakly attached to the main "
      "body through a thin/sparse bridge (near-touching scan-merge debris that strict "
      "connected-component filtering can't catch, since it is never actually disconnected). "
      "Uses the component-size threshold above to decide which resulting pieces count as "
      "'small enough to remove'. Off by default.")
    cleanupFormLayout.addRow("Remove weakly connected components (erosion): ", self.removeWeakComponentsCheckBox)

    self.erosionIterationsSlider = ctk.ctkSliderWidget()
    self.erosionIterationsSlider.singleStep = 1
    self.erosionIterationsSlider.decimals = 0
    self.erosionIterationsSlider.minimum = 1
    self.erosionIterationsSlider.maximum = 20
    self.erosionIterationsSlider.value = 6
    self.erosionIterationsSlider.enabled = False
    self.erosionIterationsSlider.setToolTip("Number of erosion (peeling) passes.")
    cleanupFormLayout.addRow("Erosion iterations: ", self.erosionIterationsSlider)

    self.erosionMinDegreeSlider = ctk.ctkSliderWidget()
    self.erosionMinDegreeSlider.singleStep = 1
    self.erosionMinDegreeSlider.decimals = 0
    self.erosionMinDegreeSlider.minimum = 3
    self.erosionMinDegreeSlider.maximum = 6
    self.erosionMinDegreeSlider.value = 5
    self.erosionMinDegreeSlider.enabled = False
    self.erosionMinDegreeSlider.setToolTip(
      "A vertex is eroded away in a given pass if it has fewer than this many still-remaining "
      "neighbors. A normal, well-connected mesh interior vertex has degree ~6; thin bridges "
      "typically have degree 3-4.")
    cleanupFormLayout.addRow("Erosion min degree: ", self.erosionMinDegreeSlider)

    #
    # Reference Smoothing Area
    #
    smoothingCollapsibleButton = ctk.ctkCollapsibleButton()
    smoothingCollapsibleButton.text = "Reference Smoothing"
    self.layout.addWidget(smoothingCollapsibleButton)
    smoothingFormLayout = qt.QFormLayout(smoothingCollapsibleButton)

    smoothingMethodLayout = qt.QHBoxLayout()
    self.windowedSincOption = qt.QRadioButton(SurfaceResidualAnomalyDetectorLogic.SMOOTHING_WINDOWED_SINC)
    self.windowedSincOption.setChecked(True)
    self.windowedSincOption.setToolTip(
      "vtkWindowedSincPolyDataFilter: non-shrinking smoothing, recommended as the reference surface.")
    self.laplacianOption = qt.QRadioButton(SurfaceResidualAnomalyDetectorLogic.SMOOTHING_LAPLACIAN)
    self.laplacianOption.setToolTip("vtkSmoothPolyDataFilter: classic Laplacian smoothing.")
    smoothingMethodLayout.addWidget(self.windowedSincOption)
    smoothingMethodLayout.addWidget(self.laplacianOption)
    smoothingFormLayout.addRow("Smoothing method: ", smoothingMethodLayout)

    self.smoothingIterationsSlider = ctk.ctkSliderWidget()
    self.smoothingIterationsSlider.singleStep = 1
    self.smoothingIterationsSlider.decimals = 0
    self.smoothingIterationsSlider.minimum = 1
    self.smoothingIterationsSlider.maximum = 100
    self.smoothingIterationsSlider.value = 20
    self.smoothingIterationsSlider.setToolTip("Number of smoothing iterations used to build the reference surface.")
    smoothingFormLayout.addRow("Smoothing iterations: ", self.smoothingIterationsSlider)

    self.passBandSlider = ctk.ctkSliderWidget()
    self.passBandSlider.singleStep = 0.001
    self.passBandSlider.decimals = 3
    self.passBandSlider.minimum = 0.001
    self.passBandSlider.maximum = 0.5
    self.passBandSlider.value = 0.08
    self.passBandSlider.setToolTip("Pass band for the windowed sinc filter. Lower values smooth more aggressively.")
    smoothingFormLayout.addRow("Pass band: ", self.passBandSlider)

    self.relaxationFactorSlider = ctk.ctkSliderWidget()
    self.relaxationFactorSlider.singleStep = 0.01
    self.relaxationFactorSlider.decimals = 2
    self.relaxationFactorSlider.minimum = 0.01
    self.relaxationFactorSlider.maximum = 0.5
    self.relaxationFactorSlider.value = 0.1
    self.relaxationFactorSlider.setToolTip("Relaxation factor for the Laplacian smoothing filter.")
    self.relaxationFactorSlider.enabled = False
    smoothingFormLayout.addRow("Relaxation factor: ", self.relaxationFactorSlider)

    self.boundarySmoothingCheckBox = qt.QCheckBox()
    self.boundarySmoothingCheckBox.setChecked(True)
    self.boundarySmoothingCheckBox.setToolTip("Allow mesh boundary points to move during smoothing.")
    smoothingFormLayout.addRow("Boundary smoothing: ", self.boundarySmoothingCheckBox)

    #
    # Residual Area
    #
    residualCollapsibleButton = ctk.ctkCollapsibleButton()
    residualCollapsibleButton.text = "Residual"
    self.layout.addWidget(residualCollapsibleButton)
    residualFormLayout = qt.QFormLayout(residualCollapsibleButton)

    residualModeLayout = qt.QHBoxLayout()
    self.normalDisplacementOption = qt.QRadioButton("Normal displacement")
    self.normalDisplacementOption.setChecked(True)
    self.normalDisplacementOption.setToolTip(
      "residual = |dot(original_point - smoothed_point, original_normal)|. "
      "Default: emphasizes inward/outward surface deviation and ignores tangential motion.")
    self.euclideanDistanceOption = qt.QRadioButton("Euclidean distance")
    self.euclideanDistanceOption.setToolTip(
      "residual = ||original_point - smoothed_point||")
    residualModeLayout.addWidget(self.normalDisplacementOption)
    residualModeLayout.addWidget(self.euclideanDistanceOption)
    residualFormLayout.addRow("Residual mode: ", residualModeLayout)

    self.denoiseResidualCheckBox = qt.QCheckBox()
    self.denoiseResidualCheckBox.setChecked(True)
    self.denoiseResidualCheckBox.setToolTip(
      "Replace each vertex residual with the median/mean of itself and its mesh neighbors, "
      "to suppress isolated acquisition noise before scoring.")
    residualFormLayout.addRow("Denoise residual map: ", self.denoiseResidualCheckBox)

    self.neighborhoodRingsSlider = ctk.ctkSliderWidget()
    self.neighborhoodRingsSlider.singleStep = 1
    self.neighborhoodRingsSlider.decimals = 0
    self.neighborhoodRingsSlider.minimum = 1
    self.neighborhoodRingsSlider.maximum = 3
    self.neighborhoodRingsSlider.value = 1
    self.neighborhoodRingsSlider.setToolTip("Mesh-neighborhood size (in edge hops) used for residual denoising.")
    residualFormLayout.addRow("Neighborhood rings: ", self.neighborhoodRingsSlider)

    self.filterIterationsSlider = ctk.ctkSliderWidget()
    self.filterIterationsSlider.singleStep = 1
    self.filterIterationsSlider.decimals = 0
    self.filterIterationsSlider.minimum = 1
    self.filterIterationsSlider.maximum = 5
    self.filterIterationsSlider.value = 2
    self.filterIterationsSlider.setToolTip("Number of times the neighborhood filter pass is repeated.")
    residualFormLayout.addRow("Filtering iterations: ", self.filterIterationsSlider)

    filterModeLayout = qt.QHBoxLayout()
    self.medianFilterOption = qt.QRadioButton(SurfaceResidualAnomalyDetectorLogic.FILTER_MODE_MEDIAN)
    self.medianFilterOption.setChecked(True)
    self.meanFilterOption = qt.QRadioButton(SurfaceResidualAnomalyDetectorLogic.FILTER_MODE_MEAN)
    filterModeLayout.addWidget(self.medianFilterOption)
    filterModeLayout.addWidget(self.meanFilterOption)
    residualFormLayout.addRow("Filter mode: ", filterModeLayout)

    #
    # Boundary Handling Area
    #
    boundaryCollapsibleButton = ctk.ctkCollapsibleButton()
    boundaryCollapsibleButton.text = "Boundary Handling"
    self.layout.addWidget(boundaryCollapsibleButton)
    boundaryFormLayout = qt.QFormLayout(boundaryCollapsibleButton)

    self.ignoreBoundaryCheckBox = qt.QCheckBox()
    self.ignoreBoundaryCheckBox.setChecked(True)
    self.ignoreBoundaryCheckBox.setToolTip(
      "Detect open/cropped mesh boundaries (vtkFeatureEdges) and exclude them from residual "
      "statistics, AI features/training, thresholds, and final anomaly masks, so acquisition "
      "or segmentation crop edges are not reported as anomalies.")
    boundaryFormLayout.addRow("Ignore boundary vertices: ", self.ignoreBoundaryCheckBox)

    self.boundaryExclusionRingsSlider = ctk.ctkSliderWidget()
    self.boundaryExclusionRingsSlider.singleStep = 1
    self.boundaryExclusionRingsSlider.decimals = 0
    self.boundaryExclusionRingsSlider.minimum = 0
    self.boundaryExclusionRingsSlider.maximum = 10
    self.boundaryExclusionRingsSlider.value = 3
    self.boundaryExclusionRingsSlider.setToolTip(
      "Graph-expansion steps from the true boundary edge. 0 = true boundary vertices only.")
    boundaryFormLayout.addRow("Boundary exclusion rings: ", self.boundaryExclusionRingsSlider)

    self.showExcludedBoundaryRegionCheckBox = qt.QCheckBox()
    self.showExcludedBoundaryRegionCheckBox.setChecked(False)
    self.showExcludedBoundaryRegionCheckBox.setToolTip(
      "Highlight the excluded boundary region in a distinct color on top of the clean binary "
      "visualization modes.")
    boundaryFormLayout.addRow("Show excluded boundary region: ", self.showExcludedBoundaryRegionCheckBox)

    #
    # Anomaly Detection Area
    #
    anomalyCollapsibleButton = ctk.ctkCollapsibleButton()
    anomalyCollapsibleButton.text = "Anomaly Detection"
    self.layout.addWidget(anomalyCollapsibleButton)
    anomalyFormLayout = qt.QFormLayout(anomalyCollapsibleButton)

    self.percentileSlider = ctk.ctkSliderWidget()
    self.percentileSlider.singleStep = 0.5
    self.percentileSlider.decimals = 1
    self.percentileSlider.minimum = 80
    self.percentileSlider.maximum = 99.5
    self.percentileSlider.value = 95
    self.percentileSlider.setToolTip("Percentile of the robust anomaly score above which points are flagged as anomalous.")
    anomalyFormLayout.addRow("Anomaly percentile: ", self.percentileSlider)

    self.removeSmallClustersCheckBox = qt.QCheckBox()
    self.removeSmallClustersCheckBox.setChecked(True)
    self.removeSmallClustersCheckBox.setToolTip(
      "Remove small disconnected anomalous regions (vertex clusters flagged 1 that touch only other flagged vertices).")
    anomalyFormLayout.addRow("Remove small anomaly clusters: ", self.removeSmallClustersCheckBox)

    self.minClusterSizeSlider = ctk.ctkSliderWidget()
    self.minClusterSizeSlider.singleStep = 1
    self.minClusterSizeSlider.decimals = 0
    self.minClusterSizeSlider.minimum = 5
    self.minClusterSizeSlider.maximum = 1000
    self.minClusterSizeSlider.value = 50
    self.minClusterSizeSlider.setToolTip("Anomalous clusters with fewer vertices than this are cleared back to 0.")
    anomalyFormLayout.addRow("Minimum cluster size: ", self.minClusterSizeSlider)

    #
    # Detection Method Area
    #
    detectionCollapsibleButton = ctk.ctkCollapsibleButton()
    detectionCollapsibleButton.text = "Detection Method"
    self.layout.addWidget(detectionCollapsibleButton)
    detectionFormLayout = qt.QFormLayout(detectionCollapsibleButton)

    self.detectionMethodCombo = qt.QComboBox()
    self.detectionMethodCombo.addItems([
      SurfaceResidualAnomalyDetectorLogic.DETECTION_RESIDUAL_ONLY,
      SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_ONLY,
      SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_FUSION,
    ])
    self.detectionMethodCombo.setToolTip(
      "Robust residual statistics: geometric pipeline only.\n"
      "Unsupervised AI: Isolation Forest over local geometric descriptors (requires scikit-learn).\n"
      "AI plus residual fusion: weighted combination of both signals (requires scikit-learn).")
    detectionFormLayout.addRow("Detection method: ", self.detectionMethodCombo)

    self.aiWeightSlider = ctk.ctkSliderWidget()
    self.aiWeightSlider.singleStep = 0.05
    self.aiWeightSlider.decimals = 2
    self.aiWeightSlider.minimum = 0.0
    self.aiWeightSlider.maximum = 1.0
    self.aiWeightSlider.value = 0.5
    self.aiWeightSlider.setToolTip(
      "fused_score = ai_weight * AI_score + (1 - ai_weight) * residual_score. Only used in "
      "'AI plus residual fusion' mode.")
    detectionFormLayout.addRow("AI weight: ", self.aiWeightSlider)

    self.aiStatusLabel = qt.QLabel()
    self.aiStatusLabel.setWordWrap(True)
    detectionFormLayout.addRow("AI status: ", self.aiStatusLabel)

    #
    # Visualization Area
    #
    visualizationCollapsibleButton = ctk.ctkCollapsibleButton()
    visualizationCollapsibleButton.text = "Visualization"
    self.layout.addWidget(visualizationCollapsibleButton)
    visualizationFormLayout = qt.QFormLayout(visualizationCollapsibleButton)

    self.visualizationModeCombo = qt.QComboBox()
    self.visualizationModeCombo.addItems(SurfaceResidualAnomalyDetectorLogic.VIS_MODE_ORDER)
    self.visualizationModeCombo.setToolTip(
      "Continuous residual anomaly score: boundary-aware robust MAD z-score heatmap.\n"
      "Filtered residual: denoised per-vertex residual heatmap.\n"
      "AI anomaly score / Fused anomaly score: only available after an AI or fusion run.\n"
      "Clean * anomalies: neutral gray surface with anomalous clusters in a contrasting color.\n"
      "Boundary exclusion mask: shows which vertices were excluded from analysis.")
    visualizationFormLayout.addRow("Visualization mode: ", self.visualizationModeCombo)

    self.showSmoothedReferenceCheckBox = qt.QCheckBox()
    self.showSmoothedReferenceCheckBox.setChecked(False)
    self.showSmoothedReferenceCheckBox.setToolTip("Display the smoothed reference surface at low opacity alongside the heatmap.")
    visualizationFormLayout.addRow("Show smoothed reference: ", self.showSmoothedReferenceCheckBox)

    #
    # Run Area
    #
    runCollapsibleButton = ctk.ctkCollapsibleButton()
    runCollapsibleButton.text = "Run"
    self.layout.addWidget(runCollapsibleButton)
    runFormLayout = qt.QFormLayout(runCollapsibleButton)

    self.compareBeforeAfterButton = qt.QPushButton("Show original (before)")
    self.compareBeforeAfterButton.setCheckable(True)
    self.compareBeforeAfterButton.setChecked(False)
    self.compareBeforeAfterButton.toolTip = (
      "Before/after switch. Pressed: shows the true, completely unprocessed original input "
      "model (never touched by this module) at full opacity, and hides the heatmap. "
      "Not pressed: shows the residual analysis heatmap. Toggling only shows/hides the "
      "existing nodes; it never recomputes or modifies any geometry.")
    self.compareBeforeAfterButton.connect('toggled(bool)', self.onCompareBeforeAfterToggled)
    runFormLayout.addRow(self.compareBeforeAfterButton)

    self.displayRangePercentileSlider = ctk.ctkSliderWidget()
    self.displayRangePercentileSlider.singleStep = 0.5
    self.displayRangePercentileSlider.decimals = 1
    self.displayRangePercentileSlider.minimum = 50.0
    self.displayRangePercentileSlider.maximum = 100.0
    self.displayRangePercentileSlider.value = 98.0
    self.displayRangePercentileSlider.setToolTip(
      "Color-range clamp for the continuous heatmaps, as a symmetric percentile "
      "[100-p, p] of the displayed array. Some results can look invisible (all one "
      "saturated color) when a few extreme outliers dominate the default 98th-percentile "
      "range; lower this to increase contrast, or raise it toward 100 to include more "
      "extreme values in the visible range. Only re-colors the existing output, no recompute.")
    runFormLayout.addRow("Display range percentile: ", self.displayRangePercentileSlider)

    self.applyButton = qt.QPushButton("Compute residual map")
    self.applyButton.toolTip = "Compute the surface residual anomaly heatmap."
    self.applyButton.enabled = False
    runFormLayout.addRow(self.applyButton)

    self.resetButton = qt.QPushButton("Reset visualization")
    self.resetButton.toolTip = "Restore the original model and hide the residual outputs."
    self.resetButton.enabled = False
    runFormLayout.addRow(self.resetButton)

    self.exportButton = qt.QPushButton("Export anomalies to JSON...")
    self.exportButton.toolTip = (
      "Export per-vertex points, normals, and every computed scalar array (residuals, "
      "scores, masks, boundary exclusion) to a JSON file, for use as an anomaly-detection "
      "training/analysis dataset.")
    self.exportButton.enabled = False
    runFormLayout.addRow(self.exportButton)

    self.statusLabel = qt.QLabel("Select an input model to begin.")
    self.statusLabel.setWordWrap(True)
    runFormLayout.addRow("Status: ", self.statusLabel)

    # connections
    self.modelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelect)
    self.removeSmallComponentsCheckBox.connect('toggled(bool)', self.onRemoveComponentsToggled)
    self.removeWeakComponentsCheckBox.connect('toggled(bool)', self.onRemoveWeakComponentsToggled)
    self.windowedSincOption.connect('toggled(bool)', self.onSmoothingMethodChanged)
    self.denoiseResidualCheckBox.connect('toggled(bool)', self.onDenoiseToggled)
    self.ignoreBoundaryCheckBox.connect('toggled(bool)', self.onIgnoreBoundaryToggled)
    self.removeSmallClustersCheckBox.connect('toggled(bool)', self.onRemoveClustersToggled)
    self.detectionMethodCombo.connect('currentIndexChanged(int)', self.onDetectionMethodChanged)
    self.visualizationModeCombo.connect('currentIndexChanged(int)', self.onVisualizationModeChanged)
    self.displayRangePercentileSlider.connect('valueChanged(double)', self.onVisualizationModeChanged)
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.resetButton.connect('clicked(bool)', self.onResetButton)
    self.exportButton.connect('clicked(bool)', self.onExportButton)

    # Add vertical spacer
    self.layout.addStretch(1)

    self.onSelect()
    self.onRemoveComponentsToggled(self.removeSmallComponentsCheckBox.checked)
    self.onRemoveWeakComponentsToggled(self.removeWeakComponentsCheckBox.checked)
    self.onSmoothingMethodChanged(self.windowedSincOption.checked)
    self.onDenoiseToggled(self.denoiseResidualCheckBox.checked)
    self.onIgnoreBoundaryToggled(self.ignoreBoundaryCheckBox.checked)
    self.onRemoveClustersToggled(self.removeSmallClustersCheckBox.checked)
    self.setupAIAvailability()

  def onSelect(self):
    inputModel = self.modelSelector.currentNode()
    self.applyButton.enabled = bool(inputModel)
    if inputModel:
      self.statusLabel.text = f"Ready to compute residual map for '{inputModel.GetName()}'."

  def onRemoveComponentsToggled(self, checked):
    self.componentThresholdSlider.enabled = bool(checked) and not self.keepLargestOnlyCheckBox.checked
    self.keepLargestOnlyCheckBox.enabled = bool(checked)

  def onRemoveWeakComponentsToggled(self, checked):
    self.erosionIterationsSlider.enabled = bool(checked)
    self.erosionMinDegreeSlider.enabled = bool(checked)

  def onSmoothingMethodChanged(self, windowedSincChecked):
    self.passBandSlider.enabled = bool(windowedSincChecked)
    self.relaxationFactorSlider.enabled = not bool(windowedSincChecked)

  def onDenoiseToggled(self, checked):
    self.neighborhoodRingsSlider.enabled = bool(checked)
    self.filterIterationsSlider.enabled = bool(checked)
    self.medianFilterOption.enabled = bool(checked)
    self.meanFilterOption.enabled = bool(checked)

  def onIgnoreBoundaryToggled(self, checked):
    self.boundaryExclusionRingsSlider.enabled = bool(checked)

  def onRemoveClustersToggled(self, checked):
    self.minClusterSizeSlider.enabled = bool(checked)

  def setupAIAvailability(self):
    """Disable AI-only/fusion detection options (never remove them) when scikit-learn
    is unavailable, and pick a sensible default mode. The geometric pipeline must stay
    fully operational either way."""
    sklearnAvailable = SurfaceResidualAnomalyDetectorLogic.isSklearnAvailable()
    aiIndex = self.detectionMethodCombo.findText(SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_ONLY)
    fusionIndex = self.detectionMethodCombo.findText(SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_FUSION)
    residualIndex = self.detectionMethodCombo.findText(SurfaceResidualAnomalyDetectorLogic.DETECTION_RESIDUAL_ONLY)

    if sklearnAvailable:
      self.detectionMethodCombo.setCurrentIndex(fusionIndex)
      self.aiStatusLabel.text = "AI available (scikit-learn detected). Default mode: AI plus residual fusion."
    else:
      try:
        model = self.detectionMethodCombo.model()
        if aiIndex >= 0:
          model.item(aiIndex).setEnabled(False)
        if fusionIndex >= 0:
          model.item(fusionIndex).setEnabled(False)
      except Exception as e:
        logging.warning(f"Could not disable AI detection-method options: {e}")
      self.detectionMethodCombo.setCurrentIndex(residualIndex)
      self.aiStatusLabel.text = "AI unavailable - scikit-learn not installed"

    self.onDetectionMethodChanged(self.detectionMethodCombo.currentIndex)

  def onDetectionMethodChanged(self, index=None):
    self.aiWeightSlider.enabled = (
      self.detectionMethodCombo.currentText == SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_FUSION)

  def onCompareBeforeAfterToggled(self, checked):
    self.compareBeforeAfterButton.text = "Show result (after)" if checked else "Show original (before)"
    self.onVisualizationModeChanged()

  def updateVisualizationModeAvailability(self):
    """Only enable AI/fused visualization modes once the corresponding results exist
    for the current output node; never remove the items, just gray them out."""
    report = getattr(self.logic, "lastReport", None) or {}
    aiAvailable = bool(report.get("aiAvailable"))
    fusedAvailable = bool(report.get("fusedAvailable"))
    availability = {
      SurfaceResidualAnomalyDetectorLogic.VIS_MODE_AI_SCORE: aiAvailable,
      SurfaceResidualAnomalyDetectorLogic.VIS_MODE_CLEAN_AI: aiAvailable,
      SurfaceResidualAnomalyDetectorLogic.VIS_MODE_FUSED_SCORE: fusedAvailable,
      SurfaceResidualAnomalyDetectorLogic.VIS_MODE_CLEAN_FUSED: fusedAvailable,
    }
    try:
      model = self.visualizationModeCombo.model()
      for i in range(self.visualizationModeCombo.count):
        text = self.visualizationModeCombo.itemText(i)
        if text in availability:
          model.item(i).setEnabled(availability[text])
    except Exception as e:
      logging.warning(f"Could not update visualization mode availability: {e}")

  def cleanup(self):
    pass

  def buildSettings(self):
    return {
      "residualMode": "euclidean" if self.euclideanDistanceOption.checked else "normal",
      "removeSmallComponents": self.removeSmallComponentsCheckBox.checked,
      "componentThresholdPercent": self.componentThresholdSlider.value,
      "keepLargestOnly": self.keepLargestOnlyCheckBox.checked,
      "removeWeaklyConnectedComponents": self.removeWeakComponentsCheckBox.checked,
      "erosionIterations": int(self.erosionIterationsSlider.value),
      "erosionMinDegree": int(self.erosionMinDegreeSlider.value),
      "smoothingMethod": SurfaceResidualAnomalyDetectorLogic.SMOOTHING_WINDOWED_SINC if self.windowedSincOption.checked else SurfaceResidualAnomalyDetectorLogic.SMOOTHING_LAPLACIAN,
      "smoothingIterations": int(self.smoothingIterationsSlider.value),
      "relaxationFactor": self.relaxationFactorSlider.value,
      "passBand": self.passBandSlider.value,
      "boundarySmoothing": self.boundarySmoothingCheckBox.checked,
      "denoiseResidual": self.denoiseResidualCheckBox.checked,
      "neighborhoodRings": int(self.neighborhoodRingsSlider.value),
      "filterIterations": int(self.filterIterationsSlider.value),
      "filterMode": SurfaceResidualAnomalyDetectorLogic.FILTER_MODE_MEAN if self.meanFilterOption.checked else SurfaceResidualAnomalyDetectorLogic.FILTER_MODE_MEDIAN,
      "ignoreBoundaryVertices": self.ignoreBoundaryCheckBox.checked,
      "boundaryExclusionRings": int(self.boundaryExclusionRingsSlider.value),
      "showExcludedBoundaryRegion": self.showExcludedBoundaryRegionCheckBox.checked,
      "percentile": self.percentileSlider.value,
      "removeSmallClusters": self.removeSmallClustersCheckBox.checked,
      "minClusterSize": int(self.minClusterSizeSlider.value),
      "detectionMethod": self.detectionMethodCombo.currentText,
      "aiWeight": self.aiWeightSlider.value,
      "showSmoothedReference": self.showSmoothedReferenceCheckBox.checked,
      "showOriginal": self.compareBeforeAfterButton.checked,
      "displayRangePercentile": self.displayRangePercentileSlider.value,
      "visualizationMode": self.visualizationModeCombo.currentText,
    }

  def onApplyButton(self):
    inputModel = self.modelSelector.currentNode()
    if not inputModel:
      slicer.util.errorDisplay("Please select an input model.")
      return

    settings = self.buildSettings()

    self.statusLabel.text = "Computing residual map..."
    slicer.app.processEvents()

    try:
      self.logic.run(inputModel, settings, resetCamera=not self.hasRunOnce)
    except Exception as e:
      logging.error(f"Surface Residual Anomaly Detector failed: {e}")
      self.statusLabel.text = f"Error: {e}"
      slicer.util.errorDisplay(f"Residual computation failed:\n{e}")
      return

    self.hasRunOnce = True
    self.resetButton.enabled = True
    self.exportButton.enabled = True
    self.updateVisualizationModeAvailability()
    self.statusLabel.text = self.formatStatusReport(self.logic.lastReport)

  def formatStatusReport(self, report):
    if not report:
      return "Done."
    lines = [
      f"Points: {report['inputPointCount']} -> {report['cleanedPointCount']} after cleanup "
      f"({report['numComponentsRemoved']} small components removed, "
      f"{report.get('numWeakComponentsRemoved', 0)} weakly-connected components eroded)",
      f"Boundary: {report['trueBoundaryCount']} true boundary vertices, "
      f"{report['excludedCount']} excluded after ring expansion, "
      f"{report['validVertexCount']} valid analysis vertices",
      f"Residual anomalies: {report['residualMaskRawCount']} raw -> {report['residualMaskCleanCount']} after cluster cleanup",
      f"Geometric processing time: {report['geometricElapsed']:.2f} s",
    ]
    if report["detectionMethod"] != SurfaceResidualAnomalyDetectorLogic.DETECTION_RESIDUAL_ONLY and not report["sklearnAvailable"]:
      lines.append("AI unavailable - scikit-learn not installed; showing residual statistics only.")
    if report["aiAvailable"]:
      lines.append(
        f"AI features: {', '.join(report['aiFeatureNames']) if report['aiFeatureNames'] else 'none active'}")
      lines.append(
        f"AI training samples: {report['aiTrainingSampleCount']} "
        f"(fit {report['aiFitElapsed']:.2f} s, inference {report['aiInferenceElapsed']:.2f} s)")
    if report["fusedAvailable"]:
      lines.append("Fused anomaly score computed (AI + residual).")
    lines.append(f"Final anomaly vertex count ({report['visualizationMode']} basis available): {report['finalAnomalyVertexCount']}")
    return "\n".join(lines)

  def onResetButton(self):
    inputModel = self.modelSelector.currentNode()
    if not inputModel:
      return
    self.logic.resetVisualization(inputModel)
    self.statusLabel.text = "Visualization reset."

  def onExportButton(self):
    inputModel = self.modelSelector.currentNode()
    if not inputModel or not self.hasRunOnce:
      slicer.util.errorDisplay("Compute the residual map first.")
      return

    inputName = inputModel.GetName()
    residualNode = slicer.mrmlScene.GetFirstNodeByName(f"{inputName} - Residual Analysis")
    if not residualNode or not residualNode.GetPolyData() or residualNode.GetPolyData().GetNumberOfPoints() == 0:
      slicer.util.errorDisplay("No residual analysis output found. Compute the residual map first.")
      return

    defaultPath = os.path.join(slicer.app.defaultScenePath, f"{inputName}_anomalies.json")
    filePath = qt.QFileDialog.getSaveFileName(
      slicer.util.mainWindow(), "Export anomaly data to JSON", defaultPath, "JSON files (*.json)")
    if not filePath:
      return

    try:
      self.logic.exportAnomalyDataToJSON(
        residualNode, inputModel, filePath, self.buildSettings(), self.logic.lastReport)
    except Exception as e:
      logging.error(f"Anomaly data export failed: {e}")
      slicer.util.errorDisplay(f"Export failed:\n{e}")
      return

    self.statusLabel.text = f"Exported anomaly data to {filePath}"

  def onVisualizationModeChanged(self, index=None):
    inputModel = self.modelSelector.currentNode()
    if not inputModel or not self.hasRunOnce:
      return
    inputName = inputModel.GetName()
    residualNode = slicer.mrmlScene.GetFirstNodeByName(f"{inputName} - Residual Analysis")
    smoothedNode = slicer.mrmlScene.GetFirstNodeByName(f"{inputName} - Smoothed Reference")
    if not residualNode or not residualNode.GetPolyData() or residualNode.GetPolyData().GetNumberOfPoints() == 0:
      return
    # Switching modes only re-colors the already-computed arrays; it never recomputes
    # smoothing, features, or the AI fit.
    self.logic.setupVisualization(
      inputModel, residualNode, smoothedNode, self.visualizationModeCombo.currentText,
      self.showSmoothedReferenceCheckBox.checked, self.showExcludedBoundaryRegionCheckBox.checked,
      resetCamera=False, showOriginal=self.compareBeforeAfterButton.checked,
      displayRangePercentile=self.displayRangePercentileSlider.value)


#
# SurfaceResidualAnomalyDetectorLogic
#

class SurfaceResidualAnomalyDetectorLogic(ScriptedLoadableModuleLogic):
  """This class implements the actual computation for the module.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  SURFACE_RESIDUAL_RAW = "Surface_Residual_Raw"
  SURFACE_RESIDUAL_FILTERED = "Surface_Residual_Filtered"
  NORMALIZED_SURFACE_RESIDUAL = "Normalized_Surface_Residual"
  RESIDUAL_ANOMALY_SCORE = "Residual_Anomaly_Score"
  RESIDUAL_ANOMALY_SCORE_RAW = "Residual_Anomaly_Score_Raw"
  RESIDUAL_ANOMALY_SCORE_BOUNDARYAWARE = "Residual_Anomaly_Score_BoundaryAware"
  RESIDUAL_ANOMALY_SCORE_NORMALIZED = "Residual_Anomaly_Score_Normalized"
  RESIDUAL_ANOMALY_MASK_RAW = "Residual_Anomaly_Mask_Raw"
  RESIDUAL_ANOMALY_MASK_CLEAN = "Residual_Anomaly_Mask_Clean"

  BOUNDARY_EXCLUSION_MASK = "Boundary_Exclusion_Mask"

  AI_ANOMALY_SCORE_RAW = "AI_Anomaly_Score_Raw"
  AI_ANOMALY_SCORE_NORMALIZED = "AI_Anomaly_Score_Normalized"
  AI_ANOMALY_MASK_RAW = "AI_Anomaly_Mask_Raw"
  AI_ANOMALY_MASK_CLEAN = "AI_Anomaly_Mask_Clean"

  FUSED_ANOMALY_SCORE = "Fused_Anomaly_Score"
  FUSED_ANOMALY_MASK_RAW = "Fused_Anomaly_Mask_Raw"
  FUSED_ANOMALY_MASK_CLEAN = "Fused_Anomaly_Mask_Clean"

  VIS_MODE_SCORE = "Continuous residual anomaly score"
  VIS_MODE_FILTERED = "Filtered residual"
  VIS_MODE_AI_SCORE = "AI anomaly score"
  VIS_MODE_FUSED_SCORE = "Fused anomaly score"
  VIS_MODE_BINARY = "Clean residual anomalies"
  VIS_MODE_CLEAN_AI = "Clean AI anomalies"
  VIS_MODE_CLEAN_FUSED = "Clean fused anomalies"
  VIS_MODE_BOUNDARY_MASK = "Boundary exclusion mask"

  # Ordered master list of every visualization mode; AI-dependent modes are disabled
  # in the UI (not removed) when no AI results are available for the current run.
  VIS_MODE_ORDER = [
    VIS_MODE_SCORE, VIS_MODE_FILTERED, VIS_MODE_AI_SCORE, VIS_MODE_FUSED_SCORE,
    VIS_MODE_BINARY, VIS_MODE_CLEAN_AI, VIS_MODE_CLEAN_FUSED, VIS_MODE_BOUNDARY_MASK,
  ]
  VIS_MODE_REQUIRES_AI = {VIS_MODE_AI_SCORE, VIS_MODE_FUSED_SCORE, VIS_MODE_CLEAN_AI, VIS_MODE_CLEAN_FUSED}

  SMOOTHING_WINDOWED_SINC = "Windowed sinc"
  SMOOTHING_LAPLACIAN = "Laplacian"

  FILTER_MODE_MEDIAN = "Median"
  FILTER_MODE_MEAN = "Mean"

  DETECTION_RESIDUAL_ONLY = "Robust residual statistics"
  DETECTION_AI_ONLY = "Unsupervised AI"
  DETECTION_AI_FUSION = "AI plus residual fusion"

  BINARY_COLOR_TABLE_NAME = "SurfaceResidualAnomalyDetector_BinaryColors"
  BOUNDARY_COLOR_TABLE_NAME = "SurfaceResidualAnomalyDetector_BoundaryColors"

  AI_RANDOM_SEED = 42
  AI_MAX_TRAINING_SAMPLES = 50000
  AI_MIN_VALID_VERTICES = 10
  MIN_VALID_VERTICES_AFTER_EXCLUSION = 10

  EPSILON = 1e-8

  @staticmethod
  def isSklearnAvailable():
    return SKLEARN_AVAILABLE

  # ---------------------------------------------------------------------
  # Mesh preparation
  # ---------------------------------------------------------------------

  def triangulateMesh(self, inputPolyData):
    """Deep-copy and triangulate the input mesh."""
    workingPolyData = vtk.vtkPolyData()
    workingPolyData.DeepCopy(inputPolyData)

    triangleFilter = vtk.vtkTriangleFilter()
    triangleFilter.SetInputData(workingPolyData)
    triangleFilter.Update()

    result = vtk.vtkPolyData()
    result.DeepCopy(triangleFilter.GetOutput())
    return result

  def filterConnectedComponents(self, polyData, thresholdPercent, keepLargestOnly):
    """Remove small disconnected fragments. By default keeps every component at or
    above thresholdPercent of the total point count; optionally keeps only the single
    largest component. Returns (resultPolyData, numRegionsTotal, numRegionsRemoved)."""
    totalPoints = polyData.GetNumberOfPoints()
    if totalPoints == 0:
      return polyData, 0, 0

    if keepLargestOnly:
      labelFilter = vtk.vtkPolyDataConnectivityFilter()
      labelFilter.SetInputData(polyData)
      labelFilter.SetExtractionModeToAllRegions()
      labelFilter.Update()
      nRegionsTotal = labelFilter.GetNumberOfExtractedRegions()

      connFilter = vtk.vtkPolyDataConnectivityFilter()
      connFilter.SetInputData(polyData)
      connFilter.SetExtractionModeToLargestRegion()
      connFilter.Update()
      cleaned = vtk.vtkPolyData()
      cleaned.DeepCopy(connFilter.GetOutput())
      numRemoved = max(0, nRegionsTotal - 1) if nRegionsTotal > 0 else 0
      return self._dropUnusedPoints(cleaned), nRegionsTotal, numRemoved

    labelFilter = vtk.vtkPolyDataConnectivityFilter()
    labelFilter.SetInputData(polyData)
    labelFilter.SetExtractionModeToAllRegions()
    labelFilter.ColorRegionsOn()
    labelFilter.Update()
    nRegions = labelFilter.GetNumberOfExtractedRegions()

    if nRegions <= 1:
      result = vtk.vtkPolyData()
      result.DeepCopy(polyData)
      return result, nRegions, 0

    regionIdArray = vtk_to_numpy(labelFilter.GetOutput().GetPointData().GetArray("RegionId"))
    counts = np.bincount(regionIdArray, minlength=nRegions)
    thresholdCount = max(1, int(math.ceil((thresholdPercent / 100.0) * totalPoints)))
    keepRegions = np.where(counts >= thresholdCount)[0]

    if len(keepRegions) == 0:
      # Threshold would remove everything: fall back to the largest region so the
      # main anatomical surface is always preserved.
      keepRegions = np.array([int(np.argmax(counts))])

    numRemoved = nRegions - len(keepRegions)

    if len(keepRegions) == nRegions:
      result = vtk.vtkPolyData()
      result.DeepCopy(polyData)
      return result, nRegions, 0

    specifiedFilter = vtk.vtkPolyDataConnectivityFilter()
    specifiedFilter.SetInputData(polyData)
    specifiedFilter.SetExtractionModeToSpecifiedRegions()
    for regionId in keepRegions:
      specifiedFilter.AddSpecifiedRegion(int(regionId))
    specifiedFilter.Update()

    cleaned = vtk.vtkPolyData()
    cleaned.DeepCopy(specifiedFilter.GetOutput())
    return self._dropUnusedPoints(cleaned), nRegions, numRemoved

  def _dropUnusedPoints(self, polyData):
    """vtkPolyDataConnectivityFilter leaves points from discarded regions dangling
    (unreferenced by any cell); strip them so downstream point counts are exact."""
    cleanFilter = vtk.vtkCleanPolyData()
    cleanFilter.SetInputData(polyData)
    cleanFilter.PointMergingOff()
    cleanFilter.Update()
    result = vtk.vtkPolyData()
    result.DeepCopy(cleanFilter.GetOutput())
    return result

  def computeNormals(self, polyData):
    """Compute consistent point normals without changing point count/order."""
    normalsFilter = vtk.vtkPolyDataNormals()
    normalsFilter.SetInputData(polyData)
    normalsFilter.SplittingOff()  # do not duplicate points at sharp edges: keep topology/point count fixed
    normalsFilter.ConsistencyOn()
    normalsFilter.AutoOrientNormalsOn()
    normalsFilter.ComputePointNormalsOn()
    normalsFilter.ComputeCellNormalsOff()
    normalsFilter.Update()

    result = vtk.vtkPolyData()
    result.DeepCopy(normalsFilter.GetOutput())
    return result

  def smoothMesh(self, polyData, method, iterations, relaxationFactor, passBand, boundarySmoothing):
    """Smooth a copy of polyData without altering topology or point count/order."""
    if method == self.SMOOTHING_LAPLACIAN:
      smoothFilter = vtk.vtkSmoothPolyDataFilter()
      smoothFilter.SetInputData(polyData)
      smoothFilter.SetNumberOfIterations(int(iterations))
      smoothFilter.SetRelaxationFactor(relaxationFactor)
      smoothFilter.SetBoundarySmoothing(bool(boundarySmoothing))
      smoothFilter.FeatureEdgeSmoothingOff()
      smoothFilter.Update()
      output = smoothFilter.GetOutput()
    else:
      smoothFilter = vtk.vtkWindowedSincPolyDataFilter()
      smoothFilter.SetInputData(polyData)
      smoothFilter.SetNumberOfIterations(int(iterations))
      smoothFilter.SetPassBand(passBand)
      smoothFilter.SetBoundarySmoothing(bool(boundarySmoothing))
      smoothFilter.FeatureEdgeSmoothingOff()
      smoothFilter.NormalizeCoordinatesOn()
      smoothFilter.Update()
      output = smoothFilter.GetOutput()

    result = vtk.vtkPolyData()
    result.DeepCopy(output)
    return result

  def checkCorrespondence(self, originalPolyData, smoothedPolyData):
    """Verify that original and smoothed polydata share the same number of points and
    the same point/cell ordering, so per-vertex residuals are valid."""
    nOriginal = originalPolyData.GetNumberOfPoints()
    nSmoothed = smoothedPolyData.GetNumberOfPoints()
    if nOriginal == 0:
      raise RuntimeError("Input model has no points.")
    if nOriginal != nSmoothed:
      raise RuntimeError(
        f"Point correspondence lost during smoothing: original mesh has {nOriginal} points, "
        f"smoothed mesh has {nSmoothed} points. Cannot compute a valid per-vertex residual.")
    if originalPolyData.GetNumberOfCells() != smoothedPolyData.GetNumberOfCells():
      raise RuntimeError(
        "Cell count changed during smoothing; mesh topology is not preserved. "
        "Cannot compute a valid per-vertex residual.")

  # ---------------------------------------------------------------------
  # Residual computation
  # ---------------------------------------------------------------------

  def computeResiduals(self, originalPolyData, smoothedPolyData, residualMode):
    origPoints = vtk_to_numpy(originalPolyData.GetPoints().GetData())
    smoothPoints = vtk_to_numpy(smoothedPolyData.GetPoints().GetData())
    displacement = origPoints - smoothPoints

    if residualMode == "euclidean":
      residual = np.linalg.norm(displacement, axis=1)
    else:
      normalsArray = originalPolyData.GetPointData().GetNormals()
      if normalsArray is None:
        raise RuntimeError("Point normals are missing on the input mesh; cannot compute normal-displacement residual.")
      normals = vtk_to_numpy(normalsArray)
      residual = np.abs(np.einsum('ij,ij->i', displacement, normals))

    return residual

  def boundingBoxDiagonal(self, polyData):
    bounds = [0.0] * 6
    polyData.GetBounds(bounds)
    dx = bounds[1] - bounds[0]
    dy = bounds[3] - bounds[2]
    dz = bounds[5] - bounds[4]
    diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)
    if not math.isfinite(diagonal) or diagonal <= self.EPSILON:
      return 1.0
    return diagonal

  def computeRobustAnomalyScore(self, residuals):
    median = np.median(residuals)
    mad = np.median(np.abs(residuals - median))
    robustZ = (residuals - median) / (1.4826 * mad + self.EPSILON)
    return robustZ

  def computeRobustAnomalyScoreMasked(self, residuals, validMask):
    """Same robust z-score, but the median/MAD are computed from validMask entries
    only; the resulting transform is still applied to every vertex."""
    validResiduals = residuals[validMask]
    median = np.median(validResiduals)
    mad = np.median(np.abs(validResiduals - median))
    robustZ = (residuals - median) / (1.4826 * mad + self.EPSILON)
    return robustZ

  # ---------------------------------------------------------------------
  # Mesh-neighborhood adjacency
  # ---------------------------------------------------------------------

  def _extractSymmetricEdges(self, polyData):
    polys = polyData.GetPolys()
    if polys.GetNumberOfCells() == 0:
      return np.zeros((0, 2), dtype=np.int64)
    polysArray = vtk_to_numpy(polys.GetData())
    if polysArray.size == 0 or polysArray.size % 4 != 0 or not np.all(polysArray[0::4] == 3):
      raise RuntimeError("Neighbor adjacency requires an all-triangle mesh; triangulation may have failed.")
    triangles = polysArray.reshape(-1, 4)[:, 1:4].astype(np.int64)
    edges = np.vstack([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    edges = np.unique(edges, axis=0)
    return edges

  def buildAdjacencyCSR(self, polyData):
    """Direct (1-ring) vertex adjacency in compressed sparse row form."""
    nPoints = polyData.GetNumberOfPoints()
    edges = self._extractSymmetricEdges(polyData)
    if edges.shape[0] == 0:
      return np.zeros(nPoints + 1, dtype=np.int64), np.zeros(0, dtype=np.int64)
    order = np.argsort(edges[:, 0], kind='stable')
    sortedEdges = edges[order]
    counts = np.bincount(sortedEdges[:, 0], minlength=nPoints)
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
    neighborIndices = sortedEdges[:, 1]
    return offsets, neighborIndices

  def buildNeighborRings(self, polyData, rings):
    """Per-vertex neighbor sets within `rings` edge hops (excluding self)."""
    nPoints = polyData.GetNumberOfPoints()
    offsets, neighborIndices = self.buildAdjacencyCSR(polyData)
    ringNeighbors = [set(neighborIndices[offsets[v]:offsets[v + 1]].tolist()) for v in range(nPoints)]
    frontier = [set(s) for s in ringNeighbors]
    for _ in range(int(rings) - 1):
      newFrontier = []
      for v in range(nPoints):
        nxt = set()
        for u in frontier[v]:
          nxt.update(neighborIndices[offsets[u]:offsets[u + 1]].tolist())
        nxt -= ringNeighbors[v]
        nxt.discard(v)
        ringNeighbors[v].update(nxt)
        newFrontier.append(nxt)
      frontier = newFrontier
    return ringNeighbors

  def filterResidualSpatially(self, residual, ringNeighbors, filterMode, iterations):
    """Replace each vertex residual with the median/mean of itself and its
    ring-neighborhood, repeated for the requested number of iterations."""
    nPoints = len(ringNeighbors)
    maxNeighbors = max((len(s) for s in ringNeighbors), default=0)
    idxMatrix = np.full((nPoints, maxNeighbors + 1), -1, dtype=np.int64)
    idxMatrix[:, 0] = np.arange(nPoints)
    for v, neighbors in enumerate(ringNeighbors):
      if neighbors:
        neighborArray = np.fromiter(neighbors, dtype=np.int64, count=len(neighbors))
        idxMatrix[v, 1:1 + len(neighborArray)] = neighborArray

    validMask = idxMatrix >= 0
    safeIdx = np.where(validMask, idxMatrix, 0)

    filtered = residual.copy()
    for _ in range(int(iterations)):
      valueMatrix = np.where(validMask, filtered[safeIdx], np.nan)
      if filterMode == self.FILTER_MODE_MEAN:
        filtered = np.nanmean(valueMatrix, axis=1)
      else:
        filtered = np.nanmedian(valueMatrix, axis=1)
    return filtered

  def cleanAnomalyClusters(self, mask, offsets, neighborIndices, minClusterSize):
    """Connected-component filtering of the binary anomaly mask: components smaller
    than minClusterSize (built from direct mesh adjacency between flagged vertices
    only) are cleared back to 0."""
    nPoints = len(mask)
    visited = np.zeros(nPoints, dtype=bool)
    cleanMask = mask.copy()
    anomalousIndices = np.where(mask == 1)[0]
    for start in anomalousIndices:
      if visited[start]:
        continue
      stack = [int(start)]
      visited[start] = True
      component = [int(start)]
      while stack:
        v = stack.pop()
        for u in neighborIndices[offsets[v]:offsets[v + 1]]:
          u = int(u)
          if mask[u] == 1 and not visited[u]:
            visited[u] = True
            component.append(u)
            stack.append(u)
      if len(component) < minClusterSize:
        cleanMask[component] = 0
    return cleanMask

  # ---------------------------------------------------------------------
  # Progressive erosion: isolate and remove weakly-connected components
  # ---------------------------------------------------------------------

  def buildComponentLabels(self, mask, offsets, neighborIndices):
    """BFS-label connected components restricted to vertices where mask is True.
    Returns (labels, numLabels); labels is -1 where mask is False."""
    nPoints = len(mask)
    labels = np.full(nPoints, -1, dtype=np.int64)
    nextLabel = 0
    for start in np.where(mask)[0]:
      if labels[start] != -1:
        continue
      stack = [int(start)]
      labels[start] = nextLabel
      while stack:
        v = stack.pop()
        for u in neighborIndices[offsets[v]:offsets[v + 1]]:
          u = int(u)
          if mask[u] and labels[u] == -1:
            labels[u] = nextLabel
            stack.append(u)
      nextLabel += 1
    return labels, nextLabel

  def growLabelsMultiSource(self, seedLabels, offsets, neighborIndices):
    """Multi-source BFS: propagate every non-negative seed label outward across the
    full graph, so every vertex ends up with the label of its nearest (graph-hop) seed."""
    labels = seedLabels.copy()
    visited = labels >= 0
    queue = deque(np.where(visited)[0].tolist())
    while queue:
      v = queue.popleft()
      lbl = labels[v]
      for u in neighborIndices[offsets[v]:offsets[v + 1]]:
        u = int(u)
        if not visited[u]:
          visited[u] = True
          labels[u] = lbl
          queue.append(u)
    return labels

  def _extractSubMeshByVertexMask(self, polyData, keepMask):
    """Build a new vtkPolyData containing only triangles whose 3 vertices are all
    marked keepMask=True, then drop the now-unused points."""
    polysArray = vtk_to_numpy(polyData.GetPolys().GetData())
    if polysArray.size == 0:
      result = vtk.vtkPolyData()
      result.DeepCopy(polyData)
      return result
    triangles = polysArray.reshape(-1, 4)[:, 1:4].astype(np.int64)
    keepCellMask = keepMask[triangles].all(axis=1)
    keptTriangles = triangles[keepCellMask]

    nCells = keptTriangles.shape[0]
    newPolys = vtk.vtkCellArray()
    if nCells > 0:
      cellArrayData = np.empty((nCells, 4), dtype=np.int64)
      cellArrayData[:, 0] = 3
      cellArrayData[:, 1:] = keptTriangles
      idArray = numpy_to_vtk(cellArrayData.reshape(-1), array_type=vtk.VTK_ID_TYPE, deep=True)
      newPolys.SetCells(nCells, idArray)

    result = vtk.vtkPolyData()
    result.SetPoints(polyData.GetPoints())
    result.GetPointData().PassData(polyData.GetPointData())
    result.SetPolys(newPolys)
    return self._dropUnusedPoints(result)

  def erodeWeaklyConnectedComponents(self, polyData, erosionIterations, minDegree, thresholdPercent):
    """Progressive topological erosion to find and remove appendages that are only
    weakly attached to the main body through a thin/sparse bridge (a handful of
    low-valence vertices) -- the kind of near-touching scan-merge artifact that strict
    connected-component filtering (never actually disconnected) cannot catch.

    Each iteration peels away every currently-remaining vertex whose count of
    still-remaining neighbors is below minDegree (similar to morphological erosion).
    The labels of the surviving 'cores' are then grown back out across the full graph
    (multi-source BFS), splitting the original mesh into regions; any such region other
    than the largest one that is smaller than thresholdPercent of the total point count
    is removed from the ORIGINAL (non-eroded) mesh. Returns (resultPolyData, numRemoved).
    """
    nPoints = polyData.GetNumberOfPoints()
    if nPoints == 0:
      return polyData, 0

    offsets, neighborIndices = self.buildAdjacencyCSR(polyData)

    remaining = np.ones(nPoints, dtype=bool)
    for _ in range(int(erosionIterations)):
      remainingIndices = np.where(remaining)[0]
      if remainingIndices.size == 0:
        break
      degrees = np.array([
        np.count_nonzero(remaining[neighborIndices[offsets[v]:offsets[v + 1]]])
        for v in remainingIndices
      ])
      toErode = remainingIndices[degrees < minDegree]
      if toErode.size == 0:
        break
      remaining[toErode] = False

    if not np.any(remaining):
      # Erosion consumed the entire mesh: no reliable 'core' survives, so skip
      # erosion-based removal entirely rather than deleting everything.
      return polyData, 0

    coreLabels, numCores = self.buildComponentLabels(remaining, offsets, neighborIndices)
    if numCores <= 1:
      return polyData, 0

    fullLabels = self.growLabelsMultiSource(coreLabels, offsets, neighborIndices)
    counts = np.bincount(fullLabels[fullLabels >= 0], minlength=numCores)
    mainLabel = int(np.argmax(counts))
    thresholdCount = max(1, int(math.ceil((thresholdPercent / 100.0) * nPoints)))

    removeLabels = [label for label in range(numCores)
                    if label != mainLabel and counts[label] < thresholdCount]
    if not removeLabels:
      return polyData, 0

    keepMask = ~np.isin(fullLabels, removeLabels)
    result = self._extractSubMeshByVertexMask(polyData, keepMask)
    return result, len(removeLabels)

  # ---------------------------------------------------------------------
  # Boundary detection and ring-based exclusion
  # ---------------------------------------------------------------------

  def detectBoundaryVertices(self, polyData):
    """True (ring 0) open-boundary vertices, detected with vtkFeatureEdges. Returns a
    boolean array of length GetNumberOfPoints(). Closed/watertight meshes correctly
    yield an all-False array."""
    nPoints = polyData.GetNumberOfPoints()
    boundaryMask = np.zeros(nPoints, dtype=bool)
    if nPoints == 0:
      return boundaryMask

    # vtkFeatureEdges builds a new, smaller point set for the extracted edges; tag
    # every point with its original index beforehand so point data (and therefore the
    # tag) is carried through, and the boundary points can be mapped back exactly.
    taggedPolyData = vtk.vtkPolyData()
    taggedPolyData.DeepCopy(polyData)
    originalIds = numpy_to_vtk(np.arange(nPoints, dtype=np.int64), deep=True)
    originalIds.SetName("_OriginalPointId")
    taggedPolyData.GetPointData().AddArray(originalIds)

    featureEdges = vtk.vtkFeatureEdges()
    featureEdges.SetInputData(taggedPolyData)
    featureEdges.BoundaryEdgesOn()
    featureEdges.FeatureEdgesOff()
    featureEdges.ManifoldEdgesOff()
    featureEdges.NonManifoldEdgesOff()
    featureEdges.Update()

    boundaryOutput = featureEdges.GetOutput()
    if boundaryOutput.GetNumberOfPoints() == 0:
      return boundaryMask

    idArray = boundaryOutput.GetPointData().GetArray("_OriginalPointId")
    if idArray is None:
      return boundaryMask
    originalBoundaryIds = vtk_to_numpy(idArray).astype(np.int64)
    boundaryMask[originalBoundaryIds] = True
    return boundaryMask

  def expandBoundaryExclusion(self, offsets, neighborIndices, boundaryMask, rings):
    """Ring-expand a seed boundary mask across the adjacency graph. rings=0 returns the
    seed (true boundary) unchanged; rings=N adds every vertex within N edge hops."""
    excluded = boundaryMask.copy()
    frontier = np.where(boundaryMask)[0]
    for _ in range(int(rings)):
      if frontier.size == 0:
        break
      neighborPieces = [neighborIndices[offsets[v]:offsets[v + 1]] for v in frontier]
      candidates = np.unique(np.concatenate(neighborPieces)) if neighborPieces else np.zeros(0, dtype=np.int64)
      newVertices = candidates[~excluded[candidates]]
      excluded[newVertices] = True
      frontier = newVertices
    return excluded

  # ---------------------------------------------------------------------
  # AI feature extraction
  # ---------------------------------------------------------------------

  def computeMeanCurvature(self, polyData):
    curvatureFilter = vtk.vtkCurvatures()
    curvatureFilter.SetInputData(polyData)
    curvatureFilter.SetCurvatureTypeToMean()
    curvatureFilter.Update()
    curvatureArray = curvatureFilter.GetOutput().GetPointData().GetArray("Mean_Curvature")
    values = vtk_to_numpy(curvatureArray).astype(float) if curvatureArray is not None else np.zeros(polyData.GetNumberOfPoints())
    return np.where(np.isfinite(values), values, 0.0)

  def _buildPaddedNeighborIndex(self, offsets, neighborIndices, nPoints):
    """Dense (nPoints x maxDegree) index matrix (-1 = no neighbor) for vectorized
    per-vertex neighborhood reductions, shared by the normal-variation and roughness
    feature computations."""
    degrees = np.diff(offsets)
    maxDegree = int(degrees.max()) if degrees.size else 0
    idxMatrix = np.full((nPoints, maxDegree), -1, dtype=np.int64)
    for v in range(nPoints):
      start, end = offsets[v], offsets[v + 1]
      count = end - start
      if count > 0:
        idxMatrix[v, :count] = neighborIndices[start:end]
    validMask = idxMatrix >= 0
    safeIdx = np.where(validMask, idxMatrix, 0)
    return validMask, safeIdx, degrees

  def computeNormalVariation(self, polyData, offsets, neighborIndices):
    """1.0 - ||mean(neighbor normals)||: near 0 on smooth surfaces, rises where
    neighboring normals point in inconsistent directions."""
    nPoints = polyData.GetNumberOfPoints()
    normals = vtk_to_numpy(polyData.GetPointData().GetNormals())
    validMask, safeIdx, degrees = self._buildPaddedNeighborIndex(offsets, neighborIndices, nPoints)
    neighborNormals = normals[safeIdx]
    maskExpanded = validMask[:, :, None]
    summedNormals = np.sum(np.where(maskExpanded, neighborNormals, 0.0), axis=1)
    meanNormals = summedNormals / np.maximum(degrees[:, None], 1)
    variation = 1.0 - np.linalg.norm(meanNormals, axis=1)
    return np.where(np.isfinite(variation), variation, 0.0)

  def computeRoughness(self, polyData, offsets, neighborIndices):
    """Mean distance of each vertex's neighbors from its local tangent plane
    (point + normal): a simple, stable high-frequency-noise descriptor."""
    nPoints = polyData.GetNumberOfPoints()
    points = vtk_to_numpy(polyData.GetPoints().GetData())
    normals = vtk_to_numpy(polyData.GetPointData().GetNormals())
    validMask, safeIdx, _ = self._buildPaddedNeighborIndex(offsets, neighborIndices, nPoints)
    neighborPoints = points[safeIdx]
    diff = neighborPoints - points[:, None, :]
    distanceToPlane = np.abs(np.einsum('vnk,vk->vn', diff, normals))
    distanceToPlane = np.where(validMask, distanceToPlane, np.nan)
    with np.errstate(invalid="ignore"):
      roughness = np.nanmean(distanceToPlane, axis=1)
    roughness = np.where(np.isfinite(roughness), roughness, 0.0)
    return roughness

  def computeRadialDistance(self, polyData):
    points = vtk_to_numpy(polyData.GetPoints().GetData())
    centroid = points.mean(axis=0)
    return np.linalg.norm(points - centroid, axis=1)

  def computeAIFeatures(self, polyData, rawResidual, filteredResidual, diagonal, offsets, neighborIndices):
    """Six required per-vertex descriptors, reusing the adjacency already built for
    residual denoising / cluster cleanup. Returns an ordered dict of name -> array."""
    features = {
      "Normalized_Raw_Residual": rawResidual / diagonal,
      "Normalized_Filtered_Residual": filteredResidual / diagonal,
      "Mean_Curvature": self.computeMeanCurvature(polyData),
      "Normal_Variation": self.computeNormalVariation(polyData, offsets, neighborIndices),
      "Local_Roughness": self.computeRoughness(polyData, offsets, neighborIndices),
      "Radial_Distance": self.computeRadialDistance(polyData),
    }
    return features

  def normalizeFeatures(self, featureDict, validMask):
    """Boundary-aware robust (median/MAD) z-normalization, computed from valid
    (non-excluded) vertices only and applied to every vertex. Constant/degenerate
    columns (MAD ~ 0 across valid vertices) are dropped."""
    activeNames = []
    columns = []
    for name, values in featureDict.items():
      values = np.asarray(values, dtype=float)
      values = np.where(np.isfinite(values), values, 0.0)
      validValues = values[validMask]
      if validValues.size == 0:
        continue
      median = np.median(validValues)
      mad = np.median(np.abs(validValues - median))
      if mad < 1e-10:
        continue
      normalized = (values - median) / (1.4826 * mad + self.EPSILON)
      normalized = np.where(np.isfinite(normalized), normalized, 0.0)
      columns.append(normalized)
      activeNames.append(name)

    if not columns:
      return None, []
    featureMatrix = np.column_stack(columns)
    return featureMatrix, activeNames

  # ---------------------------------------------------------------------
  # Unsupervised AI (Isolation Forest) and score fusion
  # ---------------------------------------------------------------------

  def runIsolationForest(self, featureMatrix, validMask, percentile):
    """Fit on a deterministic subset (<= AI_MAX_TRAINING_SAMPLES) of valid vertices,
    then score every vertex. Returns (rawScores, trainingSampleCount, fitElapsed,
    inferenceElapsed) with higher raw score always meaning more anomalous."""
    if not SKLEARN_AVAILABLE:
      raise RuntimeError("scikit-learn is not installed; unsupervised AI mode is unavailable.")

    validIndices = np.where(validMask)[0]
    if validIndices.size < self.AI_MIN_VALID_VERTICES:
      raise RuntimeError(
        f"Too few valid (non-boundary) vertices ({validIndices.size}) to fit the Isolation Forest; "
        f"need at least {self.AI_MIN_VALID_VERTICES}.")

    rng = np.random.default_rng(self.AI_RANDOM_SEED)
    if validIndices.size > self.AI_MAX_TRAINING_SAMPLES:
      trainIndices = rng.choice(validIndices, size=self.AI_MAX_TRAINING_SAMPLES, replace=False)
    else:
      trainIndices = validIndices
    trainFeatures = featureMatrix[trainIndices]

    expectedFraction = 1.0 - (percentile / 100.0)
    contamination = float(np.clip(expectedFraction, 0.001, 0.5))

    forest = IsolationForest(
      n_estimators=100,
      contamination=contamination,
      random_state=self.AI_RANDOM_SEED,
      n_jobs=-1,
      max_samples=min(self.AI_MAX_TRAINING_SAMPLES, trainFeatures.shape[0]),
    )
    fitStartTime = time.perf_counter()
    forest.fit(trainFeatures)
    fitElapsed = time.perf_counter() - fitStartTime

    # score_samples: lower = more abnormal; negate so higher always means more anomalous.
    # Inference always runs on every vertex, never a subsample.
    inferenceStartTime = time.perf_counter()
    rawScores = -forest.score_samples(featureMatrix)
    inferenceElapsed = time.perf_counter() - inferenceStartTime

    return rawScores, int(trainIndices.size), fitElapsed, inferenceElapsed

  def percentileRankNormalize(self, values, validMask):
    """Rank-normalize values to [0, 1] using only validMask entries to define the
    reference distribution; every vertex (including excluded ones) receives a rank."""
    validValues = values[validMask]
    if validValues.size <= 1:
      return np.zeros_like(values, dtype=float)
    sortedValid = np.sort(validValues)
    left = np.searchsorted(sortedValid, values, side="left")
    right = np.searchsorted(sortedValid, values, side="right")
    rank = (left + right) / 2.0
    denom = max(validValues.size - 1, 1)
    return np.clip(rank / denom, 0.0, 1.0)

  # ---------------------------------------------------------------------
  # Node / array helpers
  # ---------------------------------------------------------------------

  def addPointDataArray(self, polyData, name, values):
    vtkArray = numpy_to_vtk(np.ascontiguousarray(values), deep=True)
    vtkArray.SetName(name)
    polyData.GetPointData().AddArray(vtkArray)
    return vtkArray

  def getOrCreateModelNode(self, name):
    existingNode = slicer.mrmlScene.GetFirstNodeByName(name)
    if existingNode and existingNode.IsA("vtkMRMLModelNode"):
      return existingNode
    return slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)

  def getOrCreateBinaryColorTableNode(self):
    colorNode = slicer.mrmlScene.GetFirstNodeByName(self.BINARY_COLOR_TABLE_NAME)
    if not colorNode or not colorNode.IsA("vtkMRMLColorTableNode"):
      colorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLColorTableNode", self.BINARY_COLOR_TABLE_NAME)
      colorNode.SetTypeToUser()
      colorNode.SetNumberOfColors(2)
      colorNode.SetColor(0, "Not anomalous", 0.7, 0.7, 0.7, 1.0)
      colorNode.SetColor(1, "Anomalous", 0.85, 0.05, 0.05, 1.0)
    return colorNode

  def getOrCreateBoundaryColorTableNode(self):
    """0 = included/not anomalous (neutral gray), 1 = excluded boundary region (blue),
    2 = anomalous (red). Used directly (0/1 values) for the plain 'Boundary exclusion
    mask' visualization mode, and reused (0/1/2 values) to highlight excluded vertices
    on top of a binary anomaly mask when 'Show excluded boundary region' is enabled."""
    colorNode = slicer.mrmlScene.GetFirstNodeByName(self.BOUNDARY_COLOR_TABLE_NAME)
    if not colorNode or not colorNode.IsA("vtkMRMLColorTableNode"):
      colorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLColorTableNode", self.BOUNDARY_COLOR_TABLE_NAME)
      colorNode.SetTypeToUser()
      colorNode.SetNumberOfColors(3)
      colorNode.SetColor(0, "Included", 0.7, 0.7, 0.7, 1.0)
      colorNode.SetColor(1, "Excluded (boundary)", 0.25, 0.4, 0.9, 1.0)
      colorNode.SetColor(2, "Anomalous", 0.85, 0.05, 0.05, 1.0)
    return colorNode

  # ---------------------------------------------------------------------
  # Main entry point
  # ---------------------------------------------------------------------

  def run(self, inputModel, settings, resetCamera=False):
    if not inputModel or not inputModel.GetPolyData():
      raise ValueError("A valid input model is required.")

    inputPolyData = inputModel.GetPolyData()
    inputPointCount = inputPolyData.GetNumberOfPoints()
    if inputPointCount == 0:
      raise ValueError("Input model has no points.")

    geometricStartTime = time.perf_counter()

    # clean mesh: deep copy + triangulate
    triangulated = self.triangulateMesh(inputPolyData)

    # remove small connected components
    numComponentsRemoved = 0
    if settings["removeSmallComponents"]:
      cleanedPolyData, _numRegionsTotal, numComponentsRemoved = self.filterConnectedComponents(
        triangulated, settings["componentThresholdPercent"], settings["keepLargestOnly"])
    else:
      cleanedPolyData = triangulated

    if cleanedPolyData.GetNumberOfPoints() == 0:
      raise RuntimeError(
        "Component-size threshold removed the entire mesh. Lower the threshold and try again.")

    # progressive erosion: remove appendages only weakly attached via a thin/sparse bridge
    numWeakComponentsRemoved = 0
    if settings.get("removeWeaklyConnectedComponents", False):
      cleanedPolyData, numWeakComponentsRemoved = self.erodeWeaklyConnectedComponents(
        cleanedPolyData, settings["erosionIterations"], settings["erosionMinDegree"],
        settings["componentThresholdPercent"])
      if cleanedPolyData.GetNumberOfPoints() == 0:
        raise RuntimeError(
          "Progressive erosion removed the entire mesh. Lower the erosion iterations/min "
          "degree or the component-size threshold and try again.")

    # compute normals
    originalPolyData = self.computeNormals(cleanedPolyData)
    cleanedPointCount = originalPolyData.GetNumberOfPoints()

    # smooth reference (non-shrinking windowed sinc by default, or Laplacian)
    smoothedPolyData = self.smoothMesh(
      originalPolyData, settings["smoothingMethod"], settings["smoothingIterations"],
      settings["relaxationFactor"], settings["passBand"], settings["boundarySmoothing"])

    # topology / correspondence check
    self.checkCorrespondence(originalPolyData, smoothedPolyData)

    # adjacency built once, reused for denoising, boundary expansion, AI features and
    # cluster cleanup (never rebuilt below)
    offsets, neighborIndices = self.buildAdjacencyCSR(originalPolyData)

    # boundary detection + ring exclusion
    trueBoundaryMask = self.detectBoundaryVertices(originalPolyData)
    trueBoundaryCount = int(trueBoundaryMask.sum())
    excludedMask = self.expandBoundaryExclusion(
      offsets, neighborIndices, trueBoundaryMask, settings["boundaryExclusionRings"])
    excludedCount = int(excludedMask.sum())

    ignoreBoundary = bool(settings["ignoreBoundaryVertices"])
    validMask = ~excludedMask if ignoreBoundary else np.ones(cleanedPointCount, dtype=bool)
    validVertexCount = int(validMask.sum())
    if validVertexCount < self.MIN_VALID_VERTICES_AFTER_EXCLUSION:
      raise RuntimeError(
        f"Only {validVertexCount} valid (non-excluded) vertices remain after boundary exclusion; "
        f"need at least {self.MIN_VALID_VERTICES_AFTER_EXCLUSION}. Reduce the boundary exclusion "
        f"rings or disable 'Ignore boundary vertices'.")

    # raw per-vertex residual
    rawResidual = self.computeResiduals(originalPolyData, smoothedPolyData, settings["residualMode"])
    diagonal = self.boundingBoxDiagonal(originalPolyData)
    normalizedResidual = rawResidual / diagonal

    # neighborhood-filter (denoise) residual
    if settings["denoiseResidual"]:
      ringNeighbors = self.buildNeighborRings(originalPolyData, settings["neighborhoodRings"])
      filteredResidual = self.filterResidualSpatially(
        rawResidual, ringNeighbors, settings["filterMode"], settings["filterIterations"])
      scoringResidual = filteredResidual
    else:
      filteredResidual = rawResidual.copy()
      scoringResidual = rawResidual

    # robust anomaly score: unrestricted, and boundary-aware (median/MAD computed only
    # from valid vertices; excluded vertices pinned to the minimum valid score so they
    # never appear anomalous). Residual_Anomaly_Score is kept as a boundary-aware alias.
    residualScoreRaw = self.computeRobustAnomalyScore(scoringResidual)
    residualScoreBoundaryAware = self.computeRobustAnomalyScoreMasked(scoringResidual, validMask)
    if ignoreBoundary and excludedCount > 0:
      minValidScore = float(residualScoreBoundaryAware[validMask].min())
      residualScoreBoundaryAware = np.where(validMask, residualScoreBoundaryAware, minValidScore)
    residualAnomalyScore = residualScoreBoundaryAware.copy()

    residualScoreNormalized = self.percentileRankNormalize(residualScoreBoundaryAware, validMask)

    # percentile threshold, computed only from valid vertices, on the unclamped distribution
    residualThreshold = np.percentile(residualScoreBoundaryAware[validMask], settings["percentile"])
    residualMaskRaw = (residualScoreBoundaryAware > residualThreshold).astype(np.int32)
    residualMaskRaw = np.where(validMask, residualMaskRaw, 0).astype(np.int32)

    if settings["removeSmallClusters"]:
      residualMaskClean = self.cleanAnomalyClusters(
        residualMaskRaw, offsets, neighborIndices, settings["minClusterSize"])
    else:
      residualMaskClean = residualMaskRaw.copy()
    residualMaskClean = np.where(validMask, residualMaskClean, 0).astype(np.int32)

    geometricElapsed = time.perf_counter() - geometricStartTime

    # ------------------------------------------------------------------
    # Optional unsupervised AI + fusion
    # ------------------------------------------------------------------
    detectionMethod = settings["detectionMethod"]
    wantsAI = detectionMethod in (self.DETECTION_AI_ONLY, self.DETECTION_AI_FUSION)
    runAI = wantsAI and SKLEARN_AVAILABLE
    runFusion = detectionMethod == self.DETECTION_AI_FUSION and SKLEARN_AVAILABLE

    if wantsAI and not SKLEARN_AVAILABLE:
      logging.warning(
        "AI detection requested but scikit-learn is not installed; "
        "falling back to robust residual statistics only.")

    aiFeatureNames = []
    aiTrainingSampleCount = 0
    aiFitElapsed = 0.0
    aiInferenceElapsed = 0.0
    aiScoreRaw = None
    aiScoreNormalized = None
    aiMaskRaw = None
    aiMaskClean = None
    fusedScore = None
    fusedMaskRaw = None
    fusedMaskClean = None

    if runAI:
      featureDict = self.computeAIFeatures(
        originalPolyData, rawResidual, filteredResidual, diagonal, offsets, neighborIndices)
      featureMatrix, aiFeatureNames = self.normalizeFeatures(featureDict, validMask)

      if featureMatrix is not None:
        try:
          aiScoreRaw, aiTrainingSampleCount, aiFitElapsed, aiInferenceElapsed = self.runIsolationForest(
            featureMatrix, validMask, settings["percentile"])
        except Exception as e:
          logging.error(f"Isolation Forest failed: {e}")
          aiScoreRaw = None

      if aiScoreRaw is not None:
        aiScoreNormalized = self.percentileRankNormalize(aiScoreRaw, validMask)
        aiScoreNormalized = np.where(validMask, aiScoreNormalized, 0.0)

        aiThreshold = np.percentile(aiScoreRaw[validMask], settings["percentile"])
        aiMaskRaw = (aiScoreRaw > aiThreshold).astype(np.int32)
        aiMaskRaw = np.where(validMask, aiMaskRaw, 0).astype(np.int32)
        if settings["removeSmallClusters"]:
          aiMaskClean = self.cleanAnomalyClusters(aiMaskRaw, offsets, neighborIndices, settings["minClusterSize"])
        else:
          aiMaskClean = aiMaskRaw.copy()
        aiMaskClean = np.where(validMask, aiMaskClean, 0).astype(np.int32)

        if runFusion:
          aiWeight = float(np.clip(settings["aiWeight"], 0.0, 1.0))
          fusedScore = aiWeight * aiScoreNormalized + (1.0 - aiWeight) * residualScoreNormalized
          fusedScore = np.where(validMask, fusedScore, 0.0)

          fusedThreshold = np.percentile(fusedScore[validMask], settings["percentile"])
          fusedMaskRaw = (fusedScore > fusedThreshold).astype(np.int32)
          fusedMaskRaw = np.where(validMask, fusedMaskRaw, 0).astype(np.int32)
          if settings["removeSmallClusters"]:
            fusedMaskClean = self.cleanAnomalyClusters(
              fusedMaskRaw, offsets, neighborIndices, settings["minClusterSize"])
          else:
            fusedMaskClean = fusedMaskRaw.copy()
          fusedMaskClean = np.where(validMask, fusedMaskClean, 0).astype(np.int32)

    # ------------------------------------------------------------------
    # Assemble arrays and output nodes
    # ------------------------------------------------------------------
    residualPolyData = vtk.vtkPolyData()
    residualPolyData.DeepCopy(originalPolyData)
    self.addPointDataArray(residualPolyData, self.SURFACE_RESIDUAL_RAW, rawResidual)
    self.addPointDataArray(residualPolyData, self.SURFACE_RESIDUAL_FILTERED, filteredResidual)
    self.addPointDataArray(residualPolyData, self.NORMALIZED_SURFACE_RESIDUAL, normalizedResidual)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_SCORE_RAW, residualScoreRaw)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_SCORE_BOUNDARYAWARE, residualScoreBoundaryAware)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_SCORE, residualAnomalyScore)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_SCORE_NORMALIZED, residualScoreNormalized)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_MASK_RAW, residualMaskRaw)
    self.addPointDataArray(residualPolyData, self.RESIDUAL_ANOMALY_MASK_CLEAN, residualMaskClean)
    self.addPointDataArray(residualPolyData, self.BOUNDARY_EXCLUSION_MASK, excludedMask.astype(np.int32))

    if aiScoreRaw is not None:
      self.addPointDataArray(residualPolyData, self.AI_ANOMALY_SCORE_RAW, aiScoreRaw)
      self.addPointDataArray(residualPolyData, self.AI_ANOMALY_SCORE_NORMALIZED, aiScoreNormalized)
      self.addPointDataArray(residualPolyData, self.AI_ANOMALY_MASK_RAW, aiMaskRaw)
      self.addPointDataArray(residualPolyData, self.AI_ANOMALY_MASK_CLEAN, aiMaskClean)

    if fusedScore is not None:
      self.addPointDataArray(residualPolyData, self.FUSED_ANOMALY_SCORE, fusedScore)
      self.addPointDataArray(residualPolyData, self.FUSED_ANOMALY_MASK_RAW, fusedMaskRaw)
      self.addPointDataArray(residualPolyData, self.FUSED_ANOMALY_MASK_CLEAN, fusedMaskClean)

    residualPolyData.GetPointData().SetActiveScalars(self.RESIDUAL_ANOMALY_SCORE)

    inputName = inputModel.GetName()
    residualNode = self.getOrCreateModelNode(f"{inputName} - Residual Analysis")
    residualNode.SetAndObservePolyData(residualPolyData)
    if not residualNode.GetDisplayNode():
      residualNode.CreateDefaultDisplayNodes()

    smoothedNode = self.getOrCreateModelNode(f"{inputName} - Smoothed Reference")
    smoothedNode.SetAndObservePolyData(smoothedPolyData)
    if not smoothedNode.GetDisplayNode():
      smoothedNode.CreateDefaultDisplayNodes()

    aiResultsAvailable = aiScoreRaw is not None
    visualizationMode = settings["visualizationMode"]
    if visualizationMode in self.VIS_MODE_REQUIRES_AI and not aiResultsAvailable:
      visualizationMode = self.VIS_MODE_SCORE

    self.setupVisualization(
      inputModel, residualNode, smoothedNode, visualizationMode,
      settings["showSmoothedReference"], settings["showExcludedBoundaryRegion"], resetCamera,
      showOriginal=settings.get("showOriginal", False),
      displayRangePercentile=settings.get("displayRangePercentile", 98.0))

    self.lastReport = {
      "inputPointCount": inputPointCount,
      "cleanedPointCount": cleanedPointCount,
      "numComponentsRemoved": numComponentsRemoved,
      "numWeakComponentsRemoved": numWeakComponentsRemoved,
      "trueBoundaryCount": trueBoundaryCount,
      "excludedCount": excludedCount,
      "validVertexCount": validVertexCount,
      "aiFeatureNames": aiFeatureNames,
      "aiTrainingSampleCount": aiTrainingSampleCount,
      "geometricElapsed": geometricElapsed,
      "aiFitElapsed": aiFitElapsed,
      "aiInferenceElapsed": aiInferenceElapsed,
      "residualMaskRawCount": int(residualMaskRaw.sum()),
      "residualMaskCleanCount": int(residualMaskClean.sum()),
      "finalAnomalyVertexCount": int((fusedMaskClean if fusedMaskClean is not None
                                       else aiMaskClean if aiMaskClean is not None
                                       else residualMaskClean).sum()),
      "aiAvailable": aiResultsAvailable,
      "fusedAvailable": fusedScore is not None,
      "sklearnAvailable": SKLEARN_AVAILABLE,
      "detectionMethod": detectionMethod,
      "visualizationMode": visualizationMode,
    }

    return residualNode, smoothedNode

  # ---------------------------------------------------------------------
  # Visualization
  # ---------------------------------------------------------------------

  def setupVisualization(self, inputModel, residualNode, smoothedNode, visualizationMode,
                          showSmoothedReference, showExcludedBoundaryRegion, resetCamera,
                          showOriginal=False, displayRangePercentile=98.0):
    # Never modify the original input model's polydata; only toggle its display.
    inputDisplayNode = inputModel.GetDisplayNode()
    if inputDisplayNode:
      inputDisplayNode.SetVisibility(True)
      inputDisplayNode.SetOpacity(1.0 if showOriginal else 0.15)

    if residualNode.GetDisplayNode():
      residualNode.GetDisplayNode().SetVisibility(not showOriginal)

    if not showOriginal:
      self.applyScalarVisualization(
        residualNode, visualizationMode, showExcludedBoundaryRegion, displayRangePercentile)

    # Smoothed reference: optional, low-opacity, unscored.
    smoothedDisplayNode = smoothedNode.GetDisplayNode()
    smoothedDisplayNode.SetScalarVisibility(False)
    smoothedDisplayNode.SetColor(0.8, 0.8, 0.8)
    smoothedDisplayNode.SetOpacity(0.3)
    smoothedDisplayNode.SetVisibility(bool(showSmoothedReference))

    if resetCamera:
      layoutManager = slicer.app.layoutManager()
      threeDWidget = layoutManager.threeDWidget(0)
      if threeDWidget:
        threeDWidget.threeDView().resetFocalPoint()
        threeDWidget.threeDView().resetCamera()

  # Binary/clean visualization modes, mapped to the mask array they display.
  BINARY_VIS_MODE_ARRAYS = {
    "Clean residual anomalies": RESIDUAL_ANOMALY_MASK_CLEAN,
    "Clean AI anomalies": AI_ANOMALY_MASK_CLEAN,
    "Clean fused anomalies": FUSED_ANOMALY_MASK_CLEAN,
  }

  # Continuous heatmap visualization modes, mapped to the scalar array they display.
  CONTINUOUS_VIS_MODE_ARRAYS = {
    "Filtered residual": SURFACE_RESIDUAL_FILTERED,
    "AI anomaly score": AI_ANOMALY_SCORE_NORMALIZED,
    "Fused anomaly score": FUSED_ANOMALY_SCORE,
  }

  def applyScalarVisualization(self, residualNode, visualizationMode, showExcludedBoundaryRegion=False,
                                displayRangePercentile=98.0):
    displayNode = residualNode.GetDisplayNode()
    displayNode.SetVisibility(True)
    displayNode.SetScalarVisibility(True)
    pointData = residualNode.GetPolyData().GetPointData()

    if visualizationMode in self.BINARY_VIS_MODE_ARRAYS:
      maskArrayName = self.BINARY_VIS_MODE_ARRAYS[visualizationMode]
      maskArray = pointData.GetArray(maskArrayName)
      if maskArray is None:
        # Requested mask not available (e.g. AI/fused results missing): fall back safely
        # rather than raising, since this path can be reached from a plain mode switch.
        visualizationMode = self.VIS_MODE_SCORE
      else:
        cleanMask = vtk_to_numpy(maskArray).astype(np.int32)
        boundaryArray = pointData.GetArray(self.BOUNDARY_EXCLUSION_MASK)
        if showExcludedBoundaryRegion and boundaryArray is not None:
          excluded = vtk_to_numpy(boundaryArray).astype(bool)
          # 0 = included/not anomalous, 1 = excluded boundary, 2 = anomalous.
          displayValues = np.where(excluded, 1, cleanMask * 2).astype(np.int32)
          self.addPointDataArray(residualNode.GetPolyData(), "_BoundaryHighlightDisplay", displayValues)
          displayNode.SetActiveScalar("_BoundaryHighlightDisplay", vtk.vtkAssignAttribute.POINT_DATA)
          displayNode.SetAndObserveColorNodeID(self.getOrCreateBoundaryColorTableNode().GetID())
          displayNode.SetScalarRangeFlag(slicer.vtkMRMLDisplayNode.UseManualScalarRange)
          displayNode.SetScalarRange(0, 2)
        else:
          displayNode.SetActiveScalar(maskArrayName, vtk.vtkAssignAttribute.POINT_DATA)
          displayNode.SetAndObserveColorNodeID(self.getOrCreateBinaryColorTableNode().GetID())
          displayNode.SetScalarRangeFlag(slicer.vtkMRMLDisplayNode.UseManualScalarRange)
          displayNode.SetScalarRange(0, 1)
        return

    if visualizationMode == self.VIS_MODE_BOUNDARY_MASK:
      if pointData.GetArray(self.BOUNDARY_EXCLUSION_MASK) is not None:
        displayNode.SetActiveScalar(self.BOUNDARY_EXCLUSION_MASK, vtk.vtkAssignAttribute.POINT_DATA)
        displayNode.SetAndObserveColorNodeID(self.getOrCreateBoundaryColorTableNode().GetID())
        displayNode.SetScalarRangeFlag(slicer.vtkMRMLDisplayNode.UseManualScalarRange)
        displayNode.SetScalarRange(0, 1)  # only Included(0)/Excluded(1) values occur here
        return
      visualizationMode = self.VIS_MODE_SCORE

    arrayName = self.CONTINUOUS_VIS_MODE_ARRAYS.get(visualizationMode, self.RESIDUAL_ANOMALY_SCORE)
    scalarArray = pointData.GetArray(arrayName)
    if scalarArray is None:
      arrayName = self.RESIDUAL_ANOMALY_SCORE
      scalarArray = pointData.GetArray(arrayName)

    displayNode.SetActiveScalar(arrayName, vtk.vtkAssignAttribute.POINT_DATA)

    colorNode = slicer.mrmlScene.GetFirstNodeByName("ColdToHotRainbow")
    if colorNode:
      displayNode.SetAndObserveColorNodeID(colorNode.GetID())

    values = vtk_to_numpy(scalarArray)
    displayRangePercentile = float(np.clip(displayRangePercentile, 50.0, 100.0))
    lowPercentile, highPercentile = np.percentile(values, [100.0 - displayRangePercentile, displayRangePercentile])
    if highPercentile <= lowPercentile:
      highPercentile = lowPercentile + self.EPSILON
    displayNode.SetScalarRangeFlag(slicer.vtkMRMLDisplayNode.UseManualScalarRange)
    displayNode.SetScalarRange(lowPercentile, highPercentile)

    try:
      colorLegendNode = slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(displayNode)
      if colorLegendNode:
        colorLegendNode.SetTitleText("Surface residual anomaly")
    except Exception as e:
      logging.warning(f"Could not create color legend: {e}")

  def resetVisualization(self, inputModel):
    inputDisplayNode = inputModel.GetDisplayNode()
    if inputDisplayNode:
      inputDisplayNode.SetVisibility(True)
      inputDisplayNode.SetOpacity(1.0)

    inputName = inputModel.GetName()
    residualNode = slicer.mrmlScene.GetFirstNodeByName(f"{inputName} - Residual Analysis")
    if residualNode and residualNode.GetDisplayNode():
      residualNode.GetDisplayNode().SetVisibility(False)

    smoothedNode = slicer.mrmlScene.GetFirstNodeByName(f"{inputName} - Smoothed Reference")
    if smoothedNode and smoothedNode.GetDisplayNode():
      smoothedNode.GetDisplayNode().SetVisibility(False)

  # ---------------------------------------------------------------------
  # Export
  # ---------------------------------------------------------------------

  def exportAnomalyDataToJSON(self, residualNode, inputModel, filePath, settings, lastReport):
    """Dump every point-data array currently on the residual-analysis output (points,
    normals, residuals, scores, masks, boundary exclusion) to a JSON file, along with
    the settings/report used to produce them. Intended as a labeled per-vertex dataset
    for downstream anomaly-detection training/analysis; does not modify any node."""
    polyData = residualNode.GetPolyData()
    if polyData is None or polyData.GetNumberOfPoints() == 0:
      raise RuntimeError("No residual analysis data to export. Run the detector first.")

    points = vtk_to_numpy(polyData.GetPoints().GetData())
    normalsArray = polyData.GetPointData().GetNormals()
    normals = vtk_to_numpy(normalsArray) if normalsArray is not None else None

    arrays = {}
    pointData = polyData.GetPointData()
    for i in range(pointData.GetNumberOfArrays()):
      vtkArray = pointData.GetArray(i)
      name = vtkArray.GetName() if vtkArray is not None else None
      # Skip ephemeral/internal display-only arrays (leading underscore).
      if not name or name.startswith("_"):
        continue
      arrays[name] = vtk_to_numpy(vtkArray).tolist()

    data = {
      "metadata": {
        "inputModelName": inputModel.GetName() if inputModel else None,
        "exportTimestamp": datetime.datetime.now().isoformat(),
        "pointCount": int(polyData.GetNumberOfPoints()),
        "settings": settings,
        "report": lastReport or {},
      },
      "points": points.tolist(),
      "normals": normals.tolist() if normals is not None else None,
      "arrays": arrays,
    }

    def _jsonDefault(value):
      if hasattr(value, "item"):
        return value.item()
      return str(value)

    with open(filePath, "w") as f:
      json.dump(data, f, default=_jsonDefault)

    return data


class SurfaceResidualAnomalyDetectorTest(ScriptedLoadableModuleTest):
  """
    This is the test case for the module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

  def setUp(self):
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector1()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector2_fragmentRemoval()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector3_boundaryExclusion()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector4_bumpDetectionAndClusterCleanup()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector5_aiFallback()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector6_outputNodeStabilityAndVisualizationSwitch()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector7_tooFewValidVerticesError()
    self.setUp()
    self.test_SurfaceResidualAnomalyDetector8_erosionRemovesWeaklyConnectedAppendage()

  def defaultSettings(self):
    return {
      "residualMode": "normal",
      "removeSmallComponents": True,
      "componentThresholdPercent": 0.1,
      "keepLargestOnly": False,
      "removeWeaklyConnectedComponents": False,
      "erosionIterations": 6,
      "erosionMinDegree": 5,
      "smoothingMethod": SurfaceResidualAnomalyDetectorLogic.SMOOTHING_WINDOWED_SINC,
      "smoothingIterations": 20,
      "relaxationFactor": 0.1,
      "passBand": 0.08,
      "boundarySmoothing": True,
      "denoiseResidual": True,
      "neighborhoodRings": 1,
      "filterIterations": 2,
      "filterMode": SurfaceResidualAnomalyDetectorLogic.FILTER_MODE_MEDIAN,
      "ignoreBoundaryVertices": True,
      "boundaryExclusionRings": 3,
      "showExcludedBoundaryRegion": False,
      "percentile": 95,
      "removeSmallClusters": True,
      "minClusterSize": 50,
      "detectionMethod": SurfaceResidualAnomalyDetectorLogic.DETECTION_RESIDUAL_ONLY,
      "aiWeight": 0.5,
      "showSmoothedReference": True,
      "showOriginal": False,
      "displayRangePercentile": 98.0,
      "visualizationMode": SurfaceResidualAnomalyDetectorLogic.VIS_MODE_SCORE,
    }

  def test_SurfaceResidualAnomalyDetector1(self):
    self.delayDisplay("Starting the test")

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(40)
    sphereSource.SetPhiResolution(40)
    sphereSource.Update()

    # Perturb one vertex to create a synthetic anomaly.
    perturbedPolyData = vtk.vtkPolyData()
    perturbedPolyData.DeepCopy(sphereSource.GetOutput())
    points = perturbedPolyData.GetPoints()
    p = list(points.GetPoint(0))
    p = [c * 1.8 for c in p]
    points.SetPoint(0, p)

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestSphere")
    inputModel.SetAndObservePolyData(perturbedPolyData)
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False  # single connected sphere; nothing to remove
    residualNode, smoothedNode = logic.run(inputModel, settings, resetCamera=False)

    self.assertEqual(
      residualNode.GetPolyData().GetNumberOfPoints(),
      inputModel.GetPolyData().GetNumberOfPoints())

    scoreArray = residualNode.GetPolyData().GetPointData().GetArray("Residual_Anomaly_Score")
    self.assertIsNotNone(scoreArray)

    cleanMaskArray = residualNode.GetPolyData().GetPointData().GetArray("Residual_Anomaly_Mask_Clean")
    self.assertIsNotNone(cleanMaskArray)

    rawResidualArray = residualNode.GetPolyData().GetPointData().GetArray("Surface_Residual_Raw")
    filteredResidualArray = residualNode.GetPolyData().GetPointData().GetArray("Surface_Residual_Filtered")
    self.assertIsNotNone(rawResidualArray)
    self.assertIsNotNone(filteredResidualArray)

    self.delayDisplay('Test 1 passed')

  def test_SurfaceResidualAnomalyDetector2_fragmentRemoval(self):
    self.delayDisplay("Starting fragment-removal test")

    bigSphere = vtk.vtkSphereSource()
    bigSphere.SetRadius(5.0)
    bigSphere.SetThetaResolution(30)
    bigSphere.SetPhiResolution(30)
    bigSphere.Update()

    tinyFragment = vtk.vtkSphereSource()
    tinyFragment.SetRadius(0.2)
    tinyFragment.SetCenter(15, 0, 0)
    tinyFragment.SetThetaResolution(6)
    tinyFragment.SetPhiResolution(6)
    tinyFragment.Update()

    append = vtk.vtkAppendPolyData()
    append.AddInputData(bigSphere.GetOutput())
    append.AddInputData(tinyFragment.GetOutput())
    append.Update()

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestFragmentedMesh")
    inputModel.SetAndObservePolyData(append.GetOutput())
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = True
    # The tiny fragment is ~3% of the combined point count; use a threshold safely above
    # that so it is dropped while the ~97% main sphere is kept.
    settings["componentThresholdPercent"] = 4.0
    residualNode, smoothedNode = logic.run(inputModel, settings, resetCamera=False)

    # The tiny fragment should have been removed; residual output should have fewer
    # points than the original combined mesh, and never zero.
    residualPointCount = residualNode.GetPolyData().GetNumberOfPoints()
    inputPointCount = inputModel.GetPolyData().GetNumberOfPoints()
    self.assertGreater(residualPointCount, 0)
    self.assertLess(residualPointCount, inputPointCount)

    self.delayDisplay('Test 2 passed')

  def test_SurfaceResidualAnomalyDetector3_boundaryExclusion(self):
    self.delayDisplay("Starting boundary-exclusion test")

    # Closed sphere: must have zero true boundary vertices.
    closedSphere = vtk.vtkSphereSource()
    closedSphere.SetThetaResolution(20)
    closedSphere.SetPhiResolution(20)
    closedSphere.Update()
    closedModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestClosedSphere")
    closedModel.SetAndObservePolyData(closedSphere.GetOutput())
    closedModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False
    closedResidualNode, _ = logic.run(closedModel, settings, resetCamera=False)
    closedBoundaryArray = vtk_to_numpy(
      closedResidualNode.GetPolyData().GetPointData().GetArray("Boundary_Exclusion_Mask"))
    self.assertEqual(int(closedBoundaryArray.sum()), 0)

    # Open (cropped) sphere: must have a nonzero true boundary, and a larger excluded
    # region at rings=3 than at rings=0.
    openSphere = vtk.vtkSphereSource()
    openSphere.SetThetaResolution(20)
    openSphere.SetPhiResolution(20)
    openSphere.SetEndPhi(150)
    openSphere.Update()
    openModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestOpenSphere")
    openModel.SetAndObservePolyData(openSphere.GetOutput())
    openModel.CreateDefaultDisplayNodes()

    settings["boundaryExclusionRings"] = 0
    ring0Node, _ = logic.run(openModel, settings, resetCamera=False)
    ring0Count = int(np.sum(vtk_to_numpy(
      ring0Node.GetPolyData().GetPointData().GetArray("Boundary_Exclusion_Mask"))))
    self.assertGreater(ring0Count, 0)

    settings["boundaryExclusionRings"] = 3
    ring3Node, _ = logic.run(openModel, settings, resetCamera=False)
    ring3Count = int(np.sum(vtk_to_numpy(
      ring3Node.GetPolyData().GetPointData().GetArray("Boundary_Exclusion_Mask"))))
    self.assertGreater(ring3Count, ring0Count)

    # No excluded vertex may be flagged anomalous in the clean mask.
    excludedMask = vtk_to_numpy(
      ring3Node.GetPolyData().GetPointData().GetArray("Boundary_Exclusion_Mask")).astype(bool)
    cleanMask = vtk_to_numpy(
      ring3Node.GetPolyData().GetPointData().GetArray("Residual_Anomaly_Mask_Clean"))
    self.assertEqual(int(cleanMask[excludedMask].sum()), 0)

    self.delayDisplay('Test 3 passed')

  def test_SurfaceResidualAnomalyDetector4_bumpDetectionAndClusterCleanup(self):
    self.delayDisplay("Starting bump-detection and cluster-cleanup test")

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetRadius(5.0)
    sphereSource.SetThetaResolution(40)
    sphereSource.SetPhiResolution(40)
    sphereSource.Update()

    polyData = vtk.vtkPolyData()
    polyData.DeepCopy(sphereSource.GetOutput())
    points = polyData.GetPoints()
    coords = vtk_to_numpy(points.GetData())

    # A single-vertex spike is exactly what median denoising is designed to suppress as
    # noise, so use a small spatially-coherent bump (survives denoising and the min
    # cluster size) to represent a genuine anatomical anomaly.
    poleIndex = int(np.argmax(coords[:, 2]))
    poleCoord = coords[poleIndex].copy()
    distFromPole = np.linalg.norm(coords - poleCoord, axis=1)
    sigma = 1.2
    bumpMagnitude = 2.0 * np.exp(-(distFromPole ** 2) / (2 * sigma ** 2))
    radialDir = coords / (np.linalg.norm(coords, axis=1, keepdims=True) + 1e-9)
    bumpedCoords = coords + radialDir * bumpMagnitude[:, None]
    for i in range(len(bumpedCoords)):
      points.SetPoint(i, bumpedCoords[i].tolist())
    bumpPeakCoord = bumpedCoords[poleIndex]

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestBumpedSphere")
    inputModel.SetAndObservePolyData(polyData)
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False
    settings["minClusterSize"] = 20
    residualNode, _ = logic.run(inputModel, settings, resetCamera=False)

    cleanedPoints = vtk_to_numpy(residualNode.GetPolyData().GetPoints().GetData())
    bumpVertex = int(np.argmin(np.linalg.norm(cleanedPoints - bumpPeakCoord, axis=1)))

    scoreArray = vtk_to_numpy(
      residualNode.GetPolyData().GetPointData().GetArray("Residual_Anomaly_Score"))
    argmaxScore = int(np.argmax(scoreArray))
    argmaxDistance = np.linalg.norm(cleanedPoints[argmaxScore] - bumpPeakCoord)
    self.assertLess(argmaxDistance, sigma, "the highest-scoring vertex should lie within the bumped region")

    cleanMask = vtk_to_numpy(
      residualNode.GetPolyData().GetPointData().GetArray("Residual_Anomaly_Mask_Clean"))
    self.assertEqual(int(cleanMask[bumpVertex]), 1, "the bump peak should be flagged anomalous")

    # The bump should form a spatially coherent cluster, not a single isolated point.
    nearBump = np.linalg.norm(cleanedPoints - bumpPeakCoord, axis=1) < sigma * 2
    self.assertGreaterEqual(int(np.sum(cleanMask[nearBump])), 10)

    self.delayDisplay('Test 4 passed')

  def test_SurfaceResidualAnomalyDetector5_aiFallback(self):
    self.delayDisplay("Starting AI fallback test")

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(30)
    sphereSource.SetPhiResolution(30)
    sphereSource.Update()

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestAISphere")
    inputModel.SetAndObservePolyData(sphereSource.GetOutput())
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False
    settings["detectionMethod"] = SurfaceResidualAnomalyDetectorLogic.DETECTION_AI_FUSION

    # Must never raise, regardless of whether scikit-learn is actually installed in
    # this environment: the geometric pipeline must remain fully operational either way.
    residualNode, _ = logic.run(inputModel, settings, resetCamera=False)
    pointData = residualNode.GetPolyData().GetPointData()

    self.assertIsNotNone(pointData.GetArray("Residual_Anomaly_Score"))
    self.assertIsNotNone(pointData.GetArray("Residual_Anomaly_Mask_Clean"))

    aiArrayPresent = pointData.GetArray("AI_Anomaly_Score_Raw") is not None
    self.assertEqual(aiArrayPresent, SurfaceResidualAnomalyDetectorLogic.isSklearnAvailable(),
                      "AI arrays should be present iff scikit-learn is available")
    self.assertEqual(logic.lastReport["sklearnAvailable"], SurfaceResidualAnomalyDetectorLogic.isSklearnAvailable())
    self.assertEqual(logic.lastReport["aiAvailable"], aiArrayPresent)

    self.delayDisplay('Test 5 passed')

  def test_SurfaceResidualAnomalyDetector6_outputNodeStabilityAndVisualizationSwitch(self):
    self.delayDisplay("Starting output-node stability / visualization-switch test")

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(20)
    sphereSource.SetPhiResolution(20)
    sphereSource.Update()

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestStableSphere")
    inputModel.SetAndObservePolyData(sphereSource.GetOutput())
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False

    firstResidualNode, firstSmoothedNode = logic.run(inputModel, settings, resetCamera=True)
    secondResidualNode, secondSmoothedNode = logic.run(inputModel, settings, resetCamera=False)

    # Output node names/identities must remain stable across repeated execution.
    self.assertEqual(firstResidualNode.GetID(), secondResidualNode.GetID())
    self.assertEqual(firstSmoothedNode.GetID(), secondSmoothedNode.GetID())
    self.assertEqual(
      len(slicer.util.getNodesByClass("vtkMRMLModelNode")),
      3,  # input + residual analysis + smoothed reference, never duplicated
    )

    # Switching visualization mode must not recompute the analysis: array values must
    # be byte-identical before and after.
    beforeValues = vtk_to_numpy(
      secondResidualNode.GetPolyData().GetPointData().GetArray("Surface_Residual_Raw")).copy()
    logic.setupVisualization(
      inputModel, secondResidualNode, secondSmoothedNode,
      SurfaceResidualAnomalyDetectorLogic.VIS_MODE_FILTERED,
      showSmoothedReference=True, showExcludedBoundaryRegion=False, resetCamera=False)
    afterValues = vtk_to_numpy(
      secondResidualNode.GetPolyData().GetPointData().GetArray("Surface_Residual_Raw"))
    np.testing.assert_array_equal(beforeValues, afterValues)

    self.delayDisplay('Test 6 passed')

  def test_SurfaceResidualAnomalyDetector7_tooFewValidVerticesError(self):
    self.delayDisplay("Starting too-few-valid-vertices error test")

    # A small, mostly-open strip: with a large boundary exclusion ring count, nearly
    # every vertex should end up excluded, and the module must stop with a clear error
    # instead of silently computing statistics from too few points.
    planeSource = vtk.vtkPlaneSource()
    planeSource.SetResolution(4, 4)
    planeSource.Update()

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestTinyOpenStrip")
    inputModel.SetAndObservePolyData(planeSource.GetOutput())
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False
    settings["boundaryExclusionRings"] = 10
    settings["ignoreBoundaryVertices"] = True

    with self.assertRaises(RuntimeError):
      logic.run(inputModel, settings, resetCamera=False)

    self.delayDisplay('Test 7 passed')

  def test_SurfaceResidualAnomalyDetector8_erosionRemovesWeaklyConnectedAppendage(self):
    self.delayDisplay("Starting progressive-erosion test")

    # Main sphere with a small blob attached only through a sparse "ladder" bridge (a
    # handful of low-valence vertices) -- a single connected component by strict
    # vtkPolyDataConnectivityFilter standards, but weakly connected in practice, similar
    # to near-touching scan-merge debris.
    mainSphere = vtk.vtkSphereSource()
    mainSphere.SetRadius(5.0)
    mainSphere.SetThetaResolution(30)
    mainSphere.SetPhiResolution(30)
    mainSphere.Update()
    tri0 = vtk.vtkTriangleFilter()
    tri0.SetInputData(mainSphere.GetOutput())
    tri0.Update()
    mainPoly = vtk.vtkPolyData()
    mainPoly.DeepCopy(tri0.GetOutput())
    mainPts = vtk_to_numpy(mainPoly.GetPoints().GetData())
    attachPointIdx = int(np.argmax(mainPts[:, 0]))
    attachCoord = mainPts[attachPointIdx].copy()

    blob = vtk.vtkSphereSource()
    blob.SetRadius(0.6)
    blob.SetCenter(attachCoord[0] + 3.0, attachCoord[1], attachCoord[2])
    blob.SetThetaResolution(10)
    blob.SetPhiResolution(10)
    blob.Update()
    triBlob = vtk.vtkTriangleFilter()
    triBlob.SetInputData(blob.GetOutput())
    triBlob.Update()
    blobPoly = vtk.vtkPolyData()
    blobPoly.DeepCopy(triBlob.GetOutput())
    blobPts = vtk_to_numpy(blobPoly.GetPoints().GetData())
    blobCenterTarget = np.array([attachCoord[0] + 2.4, attachCoord[1], attachCoord[2]])
    blobAttachIdx = int(np.argmin(np.linalg.norm(blobPts - blobCenterTarget, axis=1)))
    nMain = mainPts.shape[0]
    blobAttachGlobal = nMain + blobAttachIdx

    nSegments = 5
    xs = np.linspace(attachCoord[0] + 0.4, attachCoord[0] + 2.0, nSegments)
    width = 0.08
    ladderTop = np.column_stack([
      xs, np.full(nSegments, attachCoord[1] + width), np.full(nSegments, attachCoord[2])])
    ladderBottom = np.column_stack([
      xs, np.full(nSegments, attachCoord[1] - width), np.full(nSegments, attachCoord[2])])
    bridgePts = np.vstack([ladderTop, ladderBottom])
    bridgeStart = nMain + blobPts.shape[0]
    topIdx = bridgeStart + np.arange(nSegments)
    bottomIdx = bridgeStart + nSegments + np.arange(nSegments)
    combinedPts = np.vstack([mainPts, blobPts, bridgePts])

    vtkPts = vtk.vtkPoints()
    for p in combinedPts:
      vtkPts.InsertNextPoint(p.tolist())

    cells = vtk.vtkCellArray()

    def addTri(a, b, c):
      cells.InsertNextCell(3)
      cells.InsertCellPoint(int(a))
      cells.InsertCellPoint(int(b))
      cells.InsertCellPoint(int(c))

    for t in vtk_to_numpy(mainPoly.GetPolys().GetData()).reshape(-1, 4)[:, 1:4]:
      addTri(*t)
    for t in vtk_to_numpy(blobPoly.GetPolys().GetData()).reshape(-1, 4)[:, 1:4]:
      addTri(t[0] + nMain, t[1] + nMain, t[2] + nMain)
    addTri(attachPointIdx, topIdx[0], bottomIdx[0])
    for i in range(nSegments - 1):
      addTri(topIdx[i], topIdx[i + 1], bottomIdx[i])
      addTri(bottomIdx[i], topIdx[i + 1], bottomIdx[i + 1])
    addTri(topIdx[-1], blobAttachGlobal, bottomIdx[-1])

    combined = vtk.vtkPolyData()
    combined.SetPoints(vtkPts)
    combined.SetPolys(cells)

    # Sanity: strictly a single connected component, so plain component-size filtering
    # alone cannot remove the blob.
    connCheck = vtk.vtkPolyDataConnectivityFilter()
    connCheck.SetInputData(combined)
    connCheck.SetExtractionModeToAllRegions()
    connCheck.Update()
    self.assertEqual(connCheck.GetNumberOfExtractedRegions(), 1)

    inputModel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TestWeaklyAttachedBlob")
    inputModel.SetAndObservePolyData(combined)
    inputModel.CreateDefaultDisplayNodes()

    logic = SurfaceResidualAnomalyDetectorLogic()
    settings = self.defaultSettings()
    settings["removeSmallComponents"] = False
    settings["removeWeaklyConnectedComponents"] = True
    settings["erosionIterations"] = 6
    settings["erosionMinDegree"] = 5
    settings["componentThresholdPercent"] = 15.0

    residualNode, _ = logic.run(inputModel, settings, resetCamera=False)

    residualPointCount = residualNode.GetPolyData().GetNumberOfPoints()
    inputPointCount = inputModel.GetPolyData().GetNumberOfPoints()
    self.assertGreater(residualPointCount, 0)
    self.assertLess(residualPointCount, inputPointCount)
    self.assertGreaterEqual(residualPointCount, nMain - 5)
    self.assertGreater(logic.lastReport["numWeakComponentsRemoved"], 0)

    self.delayDisplay('Test 8 passed')
