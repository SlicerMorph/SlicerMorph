import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import math
import subprocess, shutil, socket, platform, time, os

import re
import csv
import glob
import fnmatch
import json

import Support.vtk_lib as vtk_lib
import Support.gpa_lib as gpa_lib
import  numpy as np
from datetime import datetime
import scipy.linalg as sp
from vtk.util import numpy_support

#
# GPA
#
#define global variable for node management
GPANodeCollection=vtk.vtkCollection() #collect nodes created by module

class GPA(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "GPA" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.Geometric Morphometrics"]
    self.parent.dependencies = []
    self.parent.contributors = [" Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module performs standard Generalized Procrustes Analysis (GPA) based on Dryden and Mardia, 2016
<p>For more information see the <a href="https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/GPA">online documentation.</a>.</p>
"""
    #self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe, and Murat Maga for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.

# Define custom layouts for GPA modules in slicer global namespace
    slicer.customLayoutSM = """
      <layout type=\"vertical\" split=\"true\" >
       <item splitSize=\"500\">
         <layout type=\"horizontal\">
           <item>
            <view class=\"vtkMRMLViewNode\" singletontag=\"1\">
             <property name=\"viewlabel\" action=\"default\">1</property>
            </view>
           </item>
           <item>
            <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">"
             <property name=\"viewlabel\" action=\"default\">2</property>"
            </view>
          </item>
         </layout>
       </item>
       <item splitSize=\"500\">
        <layout type=\"horizontal\">
         <item>
          <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">
           <property name=\"orientation\" action=\"default\">Axial</property>
           <property name=\"viewlabel\" action=\"default\">R</property>
           <property name=\"viewcolor\" action=\"default\">#F34A33</property>
          </view>
         </item>
           <item>
            <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
             <property name=\"viewlabel\" action=\"default\">1</property>
            </view>
           </item>
         <item>
          <view class=\"vtkMRMLTableViewNode\" singletontag=\"TableViewerWindow_1\">"
           <property name=\"viewlabel\" action=\"default\">T</property>"
          </view>"
         </item>"
        </layout>
       </item>
      </layout>
  """

    slicer.customLayoutTableOnly = """
      <layout type=\"horizontal\" >
       <item>
        <view class=\"vtkMRMLTableViewNode\" singletontag=\"TableViewerWindow_1\">"
         <property name=\"viewlabel\" action=\"default\">T</property>"
        </view>"
       </item>"
      </layout>
  """

    slicer.customLayoutPlotOnly = """
      <layout type=\"horizontal\" >
       <item>
        <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
         <property name=\"viewlabel\" action=\"default\">1</property>
        </view>"
       </item>"
      </layout>
  """

class PCSliderController:
    """
    Controller that links an existing QComboBox, QSlider, and QDoubleSpinBox.
    - Keeps slider and spinbox in sync via mapped values
    - Exposes optional callbacks:
        onSliderChanged -> called on slider.valueChanged
        onComboBoxChanged -> called on comboBox.currentIndexChanged
    - Provides helpers: setRange, setValue, sliderValue, comboBoxIndex, populateComboBox, clear
    """
    def __init__(self, comboBox, slider, spinBox, dynamic_min=0.0, dynamic_max=1.0,
                 onSliderChanged=None, onComboBoxChanged=None):
        self.comboBox = comboBox
        self.slider = slider
        self.spinBox = spinBox
        self.dynamic_min = float(dynamic_min)
        self.dynamic_max = float(dynamic_max)

        # Configure widgets but do not create them
        self.slider.setMinimum(-100)
        self.slider.setMaximum(100)
        self.spinBox.setDecimals(3)
        self.spinBox.setMinimum(self.dynamic_min)
        self.spinBox.setMaximum(self.dynamic_max)
        self.spinBox.setSingleStep(0.01)  # for finer keyboard control

        # Keep slider and spinbox mapped to each other
        self.slider.valueChanged.connect(self.updateSpinBoxFromSlider)
        self.spinBox.valueChanged.connect(self.updateSliderFromSpinBox)

        # Optional external callbacks, matching legacy SliderGroup behavior
        if onSliderChanged:
            self.slider.valueChanged.connect(onSliderChanged)
        if onComboBoxChanged:
            self.comboBox.currentIndexChanged.connect(onComboBoxChanged)

    def setRange(self, new_min, new_max):
      self.dynamic_min = float(new_min)
      self.dynamic_max = float(new_max)

      # Update spinbox bounds
      self.spinBox.blockSignals(True)
      self.spinBox.setMinimum(self.dynamic_min)
      self.spinBox.setMaximum(self.dynamic_max)
      self.spinBox.blockSignals(False)

      # Compute where slider should be for dynamic value 0 (works for asymmetric ranges)
      s0 = self.map_dynamic_to_slider(0.0)
      s0 = max(min(s0, self.slider.maximum), self.slider.minimum)

      # Final reset: set exact 0.0 via spinbox, and align slider to s0
      self.spinBox.blockSignals(True)
      self.slider.blockSignals(True)
      try:
          self.spinBox.setValue(0.0)
          self.slider.setValue(s0)
      finally:
          self.slider.blockSignals(False)
          self.spinBox.blockSignals(False)

    def setValue(self, dynamic_value):
        """Set using the dynamic value domain."""
        sv = self.map_dynamic_to_slider(float(dynamic_value))
        self.slider.setValue(sv)

    def sliderValue(self):
        """Return the current dynamic value shown in the spinbox."""
        try:
            return float(self.spinBox.value())
        except TypeError:
            return float(self.spinBox.value)

    def comboBoxIndex(self):
        """Return current combobox index as int."""
        try:
            return int(self.comboBox.currentIndex())
        except TypeError:
            return int(self.comboBox.currentIndex)

    def populateComboBox(self, items):
        self.comboBox.clear()
        for it in items:
            self.comboBox.addItem(str(it))

    def clear(self):
        self.spinBox.setValue(0.0)
        self.comboBox.clear()

    def map_slider_to_dynamic(self, slider_value):
        """Map [-100, 100] to [dynamic_min, dynamic_max], snapping near zero."""
        normalized = (float(slider_value) + 100.0) / 200.0
        val = self.dynamic_min + normalized * (self.dynamic_max - self.dynamic_min)
        if abs(val) < 1e-12:
            return 0.0
        return val

    def map_dynamic_to_slider(self, dynamic_value):
        """Map [dynamic_min, dynamic_max] to [-100, 100] with rounding."""
        if self.dynamic_max == self.dynamic_min:
            return 0
        normalized = (float(dynamic_value) - self.dynamic_min) / (self.dynamic_max - self.dynamic_min)
        return int(round(normalized * 200.0 - 100.0))

    def updateSpinBoxFromSlider(self, slider_value):
        dynamic_value = self.map_slider_to_dynamic(slider_value)
        # If the slider is exactly centered, force a clean 0.0
        if int(slider_value) == 0 or abs(dynamic_value) < 1e-6:
            dynamic_value = 0.0
        self.spinBox.blockSignals(True)
        self.spinBox.setValue(dynamic_value)
        self.spinBox.blockSignals(False)

    def updateSliderFromSpinBox(self, spinbox_value):
        slider_value = self.map_dynamic_to_slider(spinbox_value)
        self.slider.blockSignals(True)
        self.slider.setValue(slider_value)
        self.slider.blockSignals(False)

class LMData:
  def __init__(self):
    self.lm=0
    self.lmOrig=0
    self.val=0
    self.vec=0
    self.alignCoords=0
    self.mShape=0
    self.tangentCoord=0
    self.shift=0
    self.centriodSize=0

  def initializeFromDataFrame(self, outputData, meanShape, eigenVectors, eigenValues):
    try:
      self.centriodSize = outputData.centroid.to_numpy()
      self.centriodSize=self.centriodSize.reshape(-1,1)
      LMHeaders = [name for name in outputData.columns if 'LM ' in name]
      points = outputData[LMHeaders].to_numpy().transpose()
      self.lm = points.reshape(int(points.shape[0]/3), 3, -1, order='C')
      self.lmOrig = self.lm
      self.mShape = meanShape[['X','Y','Z']].to_numpy()
      self.val = eigenValues.Scores.to_numpy()
      vectors = [name for name in eigenVectors.columns if 'PC ' in name]
      self.vec = eigenVectors[vectors].to_numpy()
      self.sortedEig = gpa_lib.pairEig(self.val, self.vec)
      self.procdist = outputData.proc_dist.to_numpy()
      self.procdist=self.procdist.reshape(-1,1)
      return 1
    except:
      print("Error loading results")
      self.ui.GPALogTextbox.insertPlainText("Error loading results: Failed to initialize from file \n")
      return 0

  def calcLMVariation(self, SampleScaleFactor, BoasOption):
    i,j,k=self.lmOrig.shape
    varianceMat=np.zeros((i,j))
    for subject in range(k):
      tmp=pow((self.lmOrig[:,:,subject]-self.mShape),2)
      varianceMat=varianceMat+tmp
    # if GPA scaling has been skipped, don't apply image size scaling factor
    if(BoasOption):
      varianceMat =np.sqrt(varianceMat/(k-1))
    else:
      varianceMat = SampleScaleFactor*np.sqrt(varianceMat/(k-1))
    return varianceMat

  def doGpa(self,BoasOption):
    i,j,k=self.lmOrig.shape
    self.centriodSize=np.zeros(k)
    for subjectNum in range(k):
      self.centriodSize[subjectNum]=np.linalg.norm(self.lmOrig[:,:,subjectNum]-self.lmOrig[:,:,subjectNum].mean(axis=0))
    if not BoasOption:
      self.lm, self.mShape=gpa_lib.runGPA(self.lmOrig)
    else:
      self.lm, self.mShape=gpa_lib.runGPANoScale(self.lmOrig)
    self.procdist = gpa_lib.procDist(self.lm, self.mShape)

  def calcEigen(self):
    i, j, k = self.lmOrig.shape
    twoDim=gpa_lib.makeTwoDim(self.lm)
    covMatrix=gpa_lib.calcCov(twoDim)
    if k>i*j: # limit results returned if sample number is less than observations
      self.val, self.vec = sp.eigh(covMatrix)
    else:
      self.val, self.vec=sp.eigh(covMatrix, eigvals=(i * j - k, i * j - 1))
    self.val=self.val[::-1]
    self.vec=self.vec[:, ::-1]
    self.sortedEig = gpa_lib.pairEig(self.val, self.vec)

  def ExpandAlongPCs(self, numVec,scaleFactor,SampleScaleFactor):
    b=0
    i,j,k=self.lm.shape
    tmp=np.zeros((i,j))
    points=np.zeros((i,j))
    self.vec=np.real(self.vec)
    # scale eigenvector
    for y in range(len(numVec)):
      if numVec[y] != 0:
        pcComponent = numVec[y] - 1
        tmp[:,0]=tmp[:,0]+float(scaleFactor[y])*self.vec[0:i,pcComponent]*SampleScaleFactor/3
        tmp[:,1]=tmp[:,1]+float(scaleFactor[y])*self.vec[i:2*i,pcComponent]*SampleScaleFactor/3
        tmp[:,2]=tmp[:,2]+float(scaleFactor[y])*self.vec[2*i:3*i,pcComponent]*SampleScaleFactor/3
    self.shift=tmp

  def ExpandAlongSinglePC(self,pcNumber,pcRange,SampleScaleFactor):
    b=0
    i,j,k=self.lm.shape
    shift=np.zeros((i,j))
    points=np.zeros((i,j))
    self.vec=np.real(self.vec)
    # scale eigenvector
    pcComponent = pcNumber - 1
    print("scaling factor: ", pcRange)
    shift[:,0]=shift[:,0]+float(pcRange)*self.vec[0:i,pcComponent]*SampleScaleFactor/3
    shift[:,1]=shift[:,1]+float(pcRange)*self.vec[i:2*i,pcComponent]*SampleScaleFactor/3
    shift[:,2]=shift[:,2]+float(pcRange)*self.vec[2*i:3*i,pcComponent]*SampleScaleFactor/3
    return shift

  def writeOutData(self, outputFolder, files):
    # make headers for eigenvector matrix
    headerPC = []
    headerLM = [""]
    for i in range(self.vec.shape[1]):
      headerPC.append("PC " + str(i + 1))
    for i in range(int(self.vec.shape[0] / 3)):
      headerLM.append("LM " + str(i + 1) + "_X")
      headerLM.append("LM " + str(i + 1) + "_Y")
      headerLM.append("LM " + str(i + 1) + "_Z")
    r,c=self.vec.shape
    temp=np.empty(shape=(r+1,c), dtype = object)
    temp[0,:] = np.array(headerPC)
    # Reshape to (X, Y, Z) ordering
    n_coords, n_pcs = self.vec.shape
    n_landmarks = n_coords // 3
    reshaped = self.vec.reshape((n_landmarks, 3, n_pcs), order='F')  # from (3n, p) to (n, 3, p)
    flattened = reshaped.reshape((n_landmarks * 3, n_pcs), order='C')  # from (n, 3, p) to (3n, p)

    for currentRow in range(flattened.shape[0]):
      temp[currentRow + 1, :] = flattened[currentRow, :]
    temp = np.column_stack((np.array(headerLM), temp))
    np.savetxt(outputFolder + os.sep + "eigenvector.csv", temp, delimiter=",", fmt='%s')
    temp = np.column_stack((np.array(headerPC), self.val))
    np.savetxt(outputFolder + os.sep + "eigenvalues.csv", temp, delimiter=",", fmt='%s')

    headerLM = []
    headerCoordinate = ["", "X", "Y", "Z"]
    for i in range(len(self.mShape)):
      headerLM.append("LM " + str(i + 1))
    temp = np.column_stack((np.array(headerLM), self.mShape))
    temp = np.vstack((np.array(headerCoordinate), temp))
    np.savetxt(outputFolder + os.sep + "meanShape.csv", temp, delimiter=",", fmt='%s')

    percentVar = self.val / self.val.sum()
    files = np.array(files)
    i = files.shape
    files = files.reshape(i[0], 1)
    k, j, i = self.lmOrig.shape

    coords = self.flattenArray(self.lm)
    self.procdist = self.procdist.reshape(i, 1)
    self.centriodSize = self.centriodSize.reshape(i, 1)
    tmp = np.column_stack((files, self.procdist, self.centriodSize, np.transpose(coords)))
    header = np.array(['Sample_name', 'proc_dist', 'centroid'])
    i1, j = tmp.shape
    coodrsL = (j - 3) / 3.0
    l = np.zeros(int(3 * coodrsL))

    l = list(l)

    for x in range(int(coodrsL)):
      loc = x + 1
      l[3 * x] = "LM " + str(loc) + "_X"
      l[3 * x + 1] = "LM " + str(loc) + "_Y"
      l[3 * x + 2] = "LM " + str(loc) + "_Z"
    l = np.array(l)
    header = np.column_stack((header.reshape(1, 3), l.reshape(1, int(3 * coodrsL))))
    tmp1 = np.vstack((header, tmp))
    np.savetxt(outputFolder + os.sep + "outputData.csv", tmp1, fmt="%s", delimiter=",")

    # calc PC scores
    twoDcoors = gpa_lib.makeTwoDim(self.lm)
    scores = np.dot(np.transpose(twoDcoors), self.vec)
    scores = np.real(scores)
    headerPC.insert(0, "Sample_name")
    temp = np.column_stack((files.reshape(i, 1), scores))
    temp = np.vstack((headerPC, temp))
    np.savetxt(outputFolder + os.sep + "pcScores.csv", temp, fmt="%s", delimiter=",")

  def flattenArray(self, dataArray):
    i,j,k=dataArray.shape
    tmp=np.zeros((i*j,k))
    for x in range(k):
        vec=np.reshape(dataArray[:,:,x],(i*j),order='A')
        tmp[:,x]=vec
    return tmp

  def closestSample(self,files):
    import operator
    min_index, min_value = min(enumerate(self.procdist), key=operator.itemgetter(1))
    tmp=files[min_index]
    return tmp

  def calcEndpoints(self,LM,pc, scaleFactor, MonsterObj):
    i,j=LM.shape
    tmp=np.zeros((i,j))
    tmp[:,0]=self.vec[0:i,pc]
    tmp[:,1]=self.vec[i:2*i,pc]
    tmp[:,2]=self.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3.0

#
# GPAWidget
#
class GPAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at: https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def __init__(self, parent=None):
      ScriptedLoadableModuleWidget.__init__(self, parent)
      self.ui = None

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Initialize zoom factor for widget
    self.widgetZoomFactor = 0
    # Import pandas if needed
    try:
      import pandas
    except:
      progressDialog = slicer.util.createProgressDialog(
          windowTitle="Installing...",
          labelText="Installing Pandas Python package...",
          maximum=0,
      )
      slicer.app.processEvents()
      try:
        slicer.util.pip_install(["pandas"])
        progressDialog.close()
      except:
        slicer.util.infoDisplay("Issue while installing Pandas Python package. Please install manually.")
        progressDialog.close()

    # Load widget from .ui file (created by Qt Designer).
    uiWidget = slicer.util.loadUI(self.resourcePath("UI/GPA.ui"))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Ensure patsy is available (just like you do for pandas)
    try:
      import patsy  # noqa
    except Exception:
      try:
        progressDialog = slicer.util.createProgressDialog(windowTitle="Installing...",
                                                          labelText="Installing patsy (formula parser)...",
                                                          maximum=0)
        slicer.app.processEvents()
        slicer.util.pip_install(["patsy"])
        progressDialog.close()
      except Exception:
        try:
          progressDialog.close()
        except Exception:
          pass

    # Initialize the LR tab UI (safe no-op if tab not present)
    self._lr_initTab()
    self._r_initPanel()

    # Add custom layout buttons to menu
    self.addLayoutButton(500, 'GPA Module View', 'Custom layout for GPA module', 'LayoutSlicerMorphView.png', slicer.customLayoutSM)
    self.addLayoutButton(501, 'Table Only View', 'Custom layout for GPA module', 'LayoutTableOnlyView.png', slicer.customLayoutTableOnly)
    self.addLayoutButton(502, 'Plot Only View', 'Custom layout for GPA module', 'LayoutPlotOnlyView.png', slicer.customLayoutPlotOnly)

    ################################### Setup tab connections
    self.ui.LMbutton.connect('clicked(bool)', self.onSelectLandmarkFiles)
    self.ui.clearButton.connect('clicked(bool)', self.onClearButton)
    self.ui.outputPathButton.connect('clicked(bool)', self.onSelectOutputDirectory)
    self.ui.factorNames.connect('textChanged(const QString &)', self.factorStringChanged)
    self.ui.generateCovariatesTableButton.connect('clicked(bool)', self.onGenerateCovariatesTable)
    self.ui.selectCovariatesButton.connect('clicked(bool)', self.onSelectCovariatesTable)
    self.ui.loadButton.connect('clicked(bool)', self.onLoad)
    self.ui.openResultsButton.connect('clicked(bool)', self.onOpenResults)
    self.ui.resultsButton.connect('clicked(bool)', self.onSelectResultsDirectory)
    self.ui.loadResultsButton.connect('clicked(bool)', self.onLoadFromFile)

    ################################### Explore tab connections
    self.ui.plotMeanButton3D.connect('clicked(bool)', self.toggleMeanPlot)
    self.ui.showMeanLabelsButton.connect('clicked(bool)', self.toggleMeanLabels)
    self.ui.meanShapeColor.connect('colorChanged(QColor)', self.toggleMeanColor)
    self.ui.scaleMeanShapeSlider.connect('valueChanged(double)', self.scaleMeanGlyph)
    self.ui.scaleSlider.connect('valueChanged(double)', self.onPlotDistribution)
    self.ui.plotDistributionButton.connect('clicked(bool)', self.onPlotDistribution)
    self.ui.plotButton.connect('clicked(bool)', self.plot)
    self.ui.lolliButton.connect('clicked(bool)', self.lolliPlot)

    ################################### Visualize tab connections
    self.ui.landmarkVisualizationType.connect('toggled(bool)', self.onToggleVisualization)
    self.ui.modelVisualizationType.connect('toggled(bool)', self.onToggleVisualization)
    self.ui.grayscaleSelector.connect('validInputChanged(bool)', self.onModelSelected)
    self.ui.FudSelect.connect('validInputChanged(bool)', self.onModelSelected)
    self.ui.selectorButton.connect('clicked(bool)', self.onSelect)
    self.ui.startRecordButton.connect('clicked(bool)', self.onStartRecording)
    self.ui.stopRecordButton.connect('clicked(bool)', self.onStopRecording)
    self.ui.resetButton.connect('clicked(bool)', self.reset)
    self.ui.updateMagnificationButton.connect("clicked()", self.onUpdateMagnificationClicked)
    self.PCList=[]

    # Keep a persistent controller instance
    self.pcController = PCSliderController(
        comboBox=self.ui.pcComboBox,
        slider=self.ui.pcSlider,
        spinBox=self.ui.pcSpinBox,
        dynamic_min=-1.0,
        dynamic_max=1.0,
        onSliderChanged=lambda _: self.updatePCScaling(),
        onComboBoxChanged=lambda _: self.setupPCTransform(),
    )
    self.pcController.populateComboBox(self.PCList)
    self.ui.pcComboBox.setCurrentIndex(0)
    self.setupPCTransform()
    self.updatePCScaling()


    # Core state defaults
    self.LM = None
    self.sampleSizeScaleFactor = 1.0
    self.meanLandmarkNode = None
    self.cloneLandmarkNode = None
    self.copyLandmarkNode = None
    self.cloneModelNode = None
    self.modelDisplayNode = None
    self.cloneModelDisplayNode = None
    self.factorTableNode = None
    self.gridTransformNode = None
    self.files = []
    self.inputFilePaths = []
    self.outputDirectory = None
    self.resultsDirectory = None
    self.scatterDataAll = np.zeros((0, 3))
    self.currentPC = 1
    self.pcMin = 0.0
    self.pcMax = 0.0
    self.pcScoreAbsMax = 0.0
    self._resetting = False
    self.ui.spinMagnification.setValue(1.0)


  # ---- Safe node helpers ----
  def _node(self, attr_name):
    n = getattr(self, attr_name, None)
    if n and slicer.mrmlScene.IsNodePresent(n):
      return n
    return None

  def _display(self, node_or_attr):
    node = node_or_attr
    if isinstance(node_or_attr, str):
      node = self._node(node_or_attr)
    if not node:
      return None
    try:
      return node.GetDisplayNode()
    except Exception:
      return None

  # module update helper functions
  def assignLayoutDescription(self):
    customLayoutId1=500
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(customLayoutId1)

    #link whatever is in the 3D views
    viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
    viewNode2 = slicer.mrmlScene.GetFirstNodeByName("View2")
    viewNode1.SetAxisLabelsVisible(False)
    viewNode2.SetAxisLabelsVisible(False)
    viewNode1.SetLinkedControl(True)
    viewNode2.SetLinkedControl(True)

    # Assign nodes to appropriate views
    redNode = layoutManager.sliceWidget('Red').sliceView().mrmlSliceNode()
    dn = self._display('meanLandmarkNode')
    if dn:
      dn.SetViewNodeIDs([viewNode1.GetID(), redNode.GetID()])
    cd = self._display('cloneLandmarkNode')
    if cd:
      cd.SetViewNodeIDs([viewNode2.GetID()])

    # check for loaded reference model
    model_disp = getattr(self, 'modelDisplayNode', None)
    if model_disp:
      model_disp.SetViewNodeIDs([viewNode1.GetID()])
    clone_model_disp = getattr(self, 'cloneModelDisplayNode', None)
    if clone_model_disp:
      clone_model_disp.SetViewNodeIDs([viewNode2.GetID()])

    # fit the red slice node to show the plot projections
    rasBounds = [0,]*6
    self.meanLandmarkNode.GetRASBounds(rasBounds)

    redNode.GetSliceToRAS().SetElement(0, 3, (rasBounds[1]+rasBounds[0]) / 2.)
    redNode.GetSliceToRAS().SetElement(1, 3, (rasBounds[3]+rasBounds[2]) / 2.)
    redNode.GetSliceToRAS().SetElement(2, 3, (rasBounds[5]+rasBounds[4]) / 2.)
    rSize = rasBounds[1]-rasBounds[0]
    aSize = rasBounds[3]-rasBounds[2]
    dimensions = redNode.GetDimensions()
    aspectRatio = float(dimensions[0]) / float(dimensions[1])
    if rSize > aSize:
      redNode.SetFieldOfView(rSize, rSize/aspectRatio, 1.)
    else:
      redNode.SetFieldOfView(aSize*aspectRatio, aSize, 1.)
    redNode.UpdateMatrices()

    # reset 3D cameras
    threeDWidget = layoutManager.threeDWidget(0)
    if bool(threeDWidget.name == 'ThreeDWidget1'):
      threeDView = threeDWidget.threeDView()
      threeDView.resetFocalPoint()
      threeDView.resetCamera()
    else:
      threeDWidget  = layoutManager.threeDWidget(1)
      threeDView = threeDWidget.threeDView()
      threeDView.resetFocalPoint()
      threeDView.resetCamera()

  def textIn(self,label, dispText, buttonText):
    """ a function to set up the appearance of a QlineEdit widget.
    """
    # set up text line
    textInLine=qt.QLineEdit();
    textInLine.setText(dispText)
    #textInLine.toolTip = toolTip
    # set up label
    lineLabel=qt.QLabel()
    lineLabel.setText(label)

    # make clickable button
    if buttonText == "":
      buttonText = "..."
    button=qt.QPushButton(buttonText)
    return textInLine, lineLabel, button

  def updateList(self):
    i,j,k=self.LM.lm.shape
    self.PCList=[]
    self.pcController.populateComboBox(self.PCList)
    self.PCList.append('None')
    self.LM.val=np.real(self.LM.val)
    percentVar=self.LM.val/self.LM.val.sum()
    self.ui.vectorOne.clear()
    self.ui.vectorTwo.clear()
    self.ui.vectorThree.clear()
    self.ui.XcomboBox.clear()
    self.ui.YcomboBox.clear()

    self.ui.vectorOne.addItem('None')
    self.ui.vectorTwo.addItem('None')
    self.ui.vectorThree.addItem('None')
    if len(percentVar)<self.pcNumber:
      self.pcNumber=len(percentVar)
    for x in range(self.pcNumber):
      tmp=f"{percentVar[x]*100:.1f}"
      string='PC '+str(x+1)+': '+str(tmp)+"%" +" var"
      self.PCList.append(string)
      self.ui.XcomboBox.addItem(string)
      self.ui.YcomboBox.addItem(string)
      self.ui.vectorOne.addItem(string)
      self.ui.vectorTwo.addItem(string)
      self.ui.vectorThree.addItem(string)

  def factorStringChanged(self):
    if self.ui.factorNames.text != "" and getattr(self, 'inputFilePaths', None) and self.inputFilePaths is not []:
      self.ui.generateCovariatesTableButton.enabled = True
    else:
      self.ui.generateCovariatesTableButton.enabled = False

  def populateDistanceTable(self, files):
    sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    sortedArray['filename']=files
    sortedArray['procdist']=self.LM.procdist[:,0]
    sortedArray.sort(order='procdist')

    tableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Procrustes Distance Table')
    GPANodeCollection.AddItem(tableNode)
    col1=tableNode.AddColumn()
    col1.SetName('ID')

    col2=tableNode.AddColumn()
    col2.SetName('Procrustes Distance')
    tableNode.SetColumnType('ID',vtk.VTK_STRING)
    tableNode.SetColumnType('Procrustes Distance',vtk.VTK_FLOAT)

    for i in range(len(files)):
      tableNode.AddEmptyRow()
      tableNode.SetCellText(i,0,sortedArray['filename'][i])
      tableNode.SetCellText(i,1,str(sortedArray['procdist'][i]))

    barPlot = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLPlotSeriesNode', 'Distances')
    GPANodeCollection.AddItem(barPlot)
    barPlot.SetAndObserveTableNodeID(tableNode.GetID())
    barPlot.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeBar)
    barPlot.SetLabelColumnName('ID') #displayed when hovering mouse
    barPlot.SetYColumnName('Procrustes Distance') # for bar plots, index is the x-value
    chartNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLPlotChartNode', 'Procrustes Distance Chart')
    GPANodeCollection.AddItem(chartNode)
    chartNode.SetTitle('Procrustes Distances')
    chartNode.SetLegendVisibility(False)
    chartNode.SetYAxisTitle('Distance')
    chartNode.SetXAxisTitle('Subjects')
    chartNode.AddAndObservePlotSeriesNodeID(barPlot.GetID())
    layoutManager = slicer.app.layoutManager()
    self.assignLayoutDescription()
    #set up custom layout
    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(chartNode.GetID())
    #add table to new layout
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(tableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()

  def reset(self):
    # delete the two data objects

    # reset text fields
    self.outputDirectory=None
    self.ui.outText.setText(" ")
    self.LM_dir_name=None
    self.ui.openResultsButton.enabled = False

    self.ui.grayscaleSelector.setCurrentPath("")
    self.ui.FudSelect.setCurrentPath("")
    self.ui.grayscaleSelector.enabled = False
    self.ui.FudSelect.enabled = False
    self.pcController.clear()
    self.ui.vectorOne.clear()
    self.ui.vectorTwo.clear()
    self.ui.vectorThree.clear()
    self.ui.XcomboBox.clear()
    self.ui.YcomboBox.clear()
    self.ui.selectFactor.clear()
    self.ui.factorNames.setText("")
    self.ui.scaleSlider.value=3
    self.ui.scaleMeanShapeSlider.value=3
    self.ui.meanShapeColor.color=qt.QColor(250,128,114)
    self.ui.scaleSlider.enabled = False

    # Disable buttons for workflow
    self.ui.plotButton.enabled = False
    self.inputFactorButton.enabled = False
    self.ui.lolliButton.enabled = False
    self.ui.plotDistributionButton.enabled = False
    self.ui.plotMeanButton3D.enabled = False
    self.ui.showMeanLabelsButton.enabled = False
    self.ui.loadButton.enabled = False
    self.ui.landmarkVisualizationType.enabled = False
    self.ui.modelVisualizationType.enabled = False
    self.ui.selectorButton.enabled = False
    self.ui.stopRecordButton.enabled = False
    self.ui.startRecordButton.enabled = False

    #delete data from previous runs
    self.nodeCleanUp()

  def nodeCleanUp(self):
    # clear all nodes created by the module
    for node in GPANodeCollection:

      GPANodeCollection.RemoveItem(node)
      slicer.mrmlScene.RemoveNode(node)

  def addLayoutButton(self, layoutID, buttonAction, toolTip, imageFileName, layoutDiscription):
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(layoutID, layoutDiscription)

    viewToolBar = slicer.util.mainWindow().findChild('QToolBar', 'ViewToolBar')
    layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
    layoutSwitchActionParent = layoutMenu
    # use `layoutMenu` to add inside layout list, use `viewToolBar` to add next the standard layout list
    layoutSwitchAction = layoutSwitchActionParent.addAction(buttonAction) # add inside layout list

    moduleDir = os.path.dirname(slicer.util.modulePath(self.__module__))
    iconPath = os.path.join(moduleDir, 'Resources/Icons', imageFileName)
    layoutSwitchAction.setIcon(qt.QIcon(iconPath))
    layoutSwitchAction.setToolTip(toolTip)
    layoutSwitchAction.connect('triggered()', lambda layoutId = layoutID: slicer.app.layoutManager().setLayout(layoutId))
    layoutSwitchAction.setData(layoutID)

  # Setup Analysis callbacks and helpers
  def onClearButton(self):
    self.ui.inputFileTable.clear()
    self.inputFilePaths = []
    self.ui.clearButton.enabled = False

  def onSelectLandmarkFiles(self):
    self.ui.inputFileTable.clear()
    self.inputFilePaths = []
    filter = "Landmarks (*.json *.mrk.json *.fcsv )"
    self.inputFilePaths = sorted(qt.QFileDialog().getOpenFileNames(None, "Window name", "", filter))
    self.ui.inputFileTable.plainText = '\n'.join(self.inputFilePaths)
    self.ui.clearButton.enabled = True
    #enable load button if required fields are complete
    filePathsExist = bool(self.inputFilePaths is not [] )
    self.ui.loadButton.enabled = bool (filePathsExist and getattr(self, 'outputDirectory', None))
    if filePathsExist:
      self.LM_dir_name = os.path.dirname(self.inputFilePaths[0])
      basename, self.extension = os.path.splitext(self.inputFilePaths[0])
      if self.extension == '.json':
        basename, secondExtension = os.path.splitext(basename)
        if secondExtension == '.mrk':
          self.extension =  secondExtension + self.extension
      self.files=[]
      for path in self.inputFilePaths:
        basename, ext = os.path.splitext(os.path.basename(path))
        if self.extension == '.mrk.json':
          basename, ext = os.path.splitext(basename)
        self.files.append(basename)
      self.factorStringChanged()

  def onSelectOutputDirectory(self):
    self.outputDirectory=qt.QFileDialog().getExistingDirectory()
    self.ui.outText.setText(self.outputDirectory)
    try:
      filePathsExist = self.inputFilePaths is not []
      self.ui.loadButton.enabled = bool (filePathsExist and self.outputDirectory)
    except AttributeError:
      self.ui.loadButton.enabled = False

  def onSelectCovariatesTable(self):
    dialog = qt.QFileDialog()
    filter = "csv(*.csv)"
    self.covariateTableFile = qt.QFileDialog.getOpenFileName(dialog, "", "", filter)
    if self.covariateTableFile:
      self.ui.selectCovariatesText.setText(self.covariateTableFile)
    else:
     self.covariateTableFile =  self.ui.selectCovariatesText.text

  def onGenerateCovariatesTable(self):
    numberOfInputFiles = len(self.inputFilePaths)
    if numberOfInputFiles<1:
      qt.QMessageBox.critical(slicer.util.mainWindow(),
      'Error', 'Please select landmark files for analysis before generating covariate table')
      logging.debug('No input files are selected')
      self.ui.GPALogTextbox.insertPlainText("Error: No input files were selected for generating the covariate table\n")
      return
    #if #check for rows, columns
    factorList = self.ui.factorNames.text.split(",")
    if len(factorList)<1:
      qt.QMessageBox.critical(slicer.util.mainWindow(),
      'Error', 'Please specify at least one factor name to generate a covariate table template')
      logging.debug('No factor names are provided for covariate table template')
      self.ui.GPALogTextbox.insertPlainText("Error: No factor names were provided for the covariate table template\n")
      return
    sortedArray = np.zeros(len(self.files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    sortedArray['filename']=self.files
    ##check for an existing factor table, if so remove
    #if getattr(self, 'factorTableNode', None):
    #  slicer.mrmlScene.RemoveNode(self.factorTableNode)
    self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Factor Table')
    col=self.factorTableNode.AddColumn()
    col.SetName('ID')
    for i in range(len(self.files)):
      self.factorTableNode.AddEmptyRow()
      self.factorTableNode.SetCellText(i,0,sortedArray['filename'][i])
    for i in range(len(factorList)):
      col=self.factorTableNode.AddColumn()
      col.SetName(factorList[i])
    dateTimeStamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
    covariateFolder = os.path.join(slicer.app.cachePath, dateTimeStamp)
    self.covariateTableFile = os.path.join(covariateFolder, "covariateTable.csv")
    try:
      os.makedirs(covariateFolder)
      self.covariateTableFile = os.path.join(covariateFolder, "covariateTable.csv")
      slicer.util.saveNode(self.factorTableNode, self.covariateTableFile)
    except:
      self.ui.GPALogTextbox.insertPlainText("Covariate table output failed: Could not write {self.factorTableNode} to {self.covariateTableFile}\n")
    slicer.mrmlScene.RemoveNode(self.factorTableNode)
    self.ui.selectCovariatesText.setText(self.covariateTableFile)
    qpath = qt.QUrl.fromLocalFile(os.path.dirname(covariateFolder+os.path.sep))
    qt.QDesktopServices().openUrl(qpath)
    self.ui.GPALogTextbox.insertPlainText(f"Covariate table template generated in folder: \n{covariateFolder}\n Please fill in covariate columns, save, and load table in the next step to proceed.\n")

  def onLoadCovariatesTable(self):
    numberOfInputFiles = len(self.inputFilePaths)
    runAnalysis=True
    #columnsToRemove = []
    if numberOfInputFiles<1:
      logging.debug('No input files are selected')
      self.ui.GPALogTextbox.insertPlainText("Error: No input files are selected for the covariate table\n")
      return runAnalysis
    try:
      # refresh covariateTableFile from GUI
      self.covariateTableFile =  self.ui.selectCovariatesText.text
      self.factorTableNode = slicer.util.loadTable(self.covariateTableFile)
    except AttributeError:
      logging.debug(f'Covariate table import failed for: {self.covariateTableFile}')
      runAnalysis = slicer.util.confirmYesNoDisplay(f"Error: Covariate import failed. Table could not be loaded from {self.covariateTableFile}. \n\nYou can continue analysis without covariates or stop and edit your selected table. \n\nWould you like to proceed with the analysis?")
      return runAnalysis
    #check for at least one covariate factor
    numberOfColumns = self.factorTableNode.GetNumberOfColumns()
    if numberOfColumns<2:
      logging.debug('Covariate table import failed, covariate table must have at least one factor column')
      runAnalysis = slicer.util.confirmYesNoDisplay("Error: Covariate import failed. Table is required to have at least one factor column. \n\nYou can continue analysis without covariates or stop and edit your table. \n\nWould you like to proceed with the analysis?")
      return runAnalysis
    #check for same number of covariate rows and input filenames
    indexColumn = self.factorTableNode.GetTable().GetColumn(0)
    if indexColumn.GetNumberOfTuples() != numberOfInputFiles:
      logging.debug('Covariate table import failed, covariate table row number does not match number of input files')
      self.ui.GPALogTextbox.insertPlainText(f"Error: Covariate table import failed, covariate table row number does not match number of input files\n")
      runAnalysis = slicer.util.confirmYesNoDisplay(f"Error: Covariate import failed. The number of rows in the table is required to match the number of selected input files. \n\nYou can continue analysis without covariates or stop and edit your sample selection and/or covariate table. \n\nWould you like to proceed with the analysis?")
      return runAnalysis
    #check that input filenames match factor row names
    for i, inputFile in enumerate(self.inputFilePaths):
      if indexColumn.GetValue(i) not in inputFile:
        print(indexColumn.GetValue(i), inputFile)
        self.ui.GPALogTextbox.insertPlainText(f"Covariate import failed. Covariate filenames do not match input files \n Expected {inputFile}, got {indexColumn.GetValue(i)} \n")
        logging.debug("Covariate table import failed, covariate filenames do not match input files")
        runAnalysis = slicer.util.confirmYesNoDisplay(f"Error: Covariate import failed. The row names in the table are required to match the selected input filenames. \n\nYou can continue analysis without covariates or stop and edit your covariate table. \n\nWould you like to proceed with the analysis?")
        return runAnalysis
    for i in range(1,numberOfColumns):
      if self.factorTableNode.GetTable().GetColumnName(i) == "":
        self.ui.GPALogTextbox.insertPlainText(f"Covariate import failed, covariate {i} is not labeled\n")
        logging.debug(f"Covariate import failed, covariate {i} is not labeled")
        runAnalysis = slicer.util.confirmYesNoDisplay(f"Error: Covariate import failed. Covariate {i} has no label. Covariates table is required to have a header row with covariate names. \n\nYou can continue analysis without covariates or stop and edit your table. \n\nWould you like to proceed with the analysis?")
        return runAnalysis
      hasNumericValue = False
      for j in range(self.factorTableNode.GetTable().GetNumberOfRows()):
        if self.factorTableNode.GetTable().GetValue(j,i) == "":
          subjectID = self.factorTableNode.GetTable().GetValue(j,0).ToString()
          self.ui.GPALogTextbox.insertPlainText(f"Covariate table import failed, covariate {self.factorTableNode.GetTable().GetColumnName(i)} has no value for {subjectID}\n")
          logging.debug(f"Covariate table import failed, covariate {self.factorTableNode.GetTable().GetColumnName(i)} has no value for {subjectID}")
          runAnalysis = slicer.util.confirmYesNoDisplay(f"Error: Covariate import failed. Covariate {self.factorTableNode.GetTable().GetColumnName(i)} has no value for {subjectID}. Missing observation(s) in the covariates table are not allowed. \n\nYou can continue analysis without covariates or stop and edit your sample selection and/or covariate table. \n\nWould you like to proceed with the analysis?")
          return runAnalysis
        if self.factorTableNode.GetTable().GetValue(j,i).ToString().isnumeric():
          hasNumericValue = True
      if hasNumericValue:
        self.ui.GPALogTextbox.insertPlainText(f"Covariate: {self.factorTableNode.GetTable().GetColumnName(i)} contains numeric values and will not be loaded for plotting\n")
        logging.debug(f"Covariate: {self.factorTableNode.GetTable().GetColumnName(i)} contains numeric values and will not be loaded for plotting\n")
        qt.QMessageBox.critical(slicer.util.mainWindow(),
        "Warning: ", f"Covariate: {self.factorTableNode.GetTable().GetColumnName(i)} contains numeric values and will not be loaded for plotting")
      else:
        self.ui.selectFactor.addItem(self.factorTableNode.GetTable().GetColumnName(i))
    self.ui.GPALogTextbox.insertPlainText("Covariate table loaded and validated\n")
    self.ui.GPALogTextbox.insertPlainText(f"Table contains {self.factorTableNode.GetNumberOfColumns()-1} covariates: ")
    for i in range(1,self.factorTableNode.GetNumberOfColumns()):
      self.ui.GPALogTextbox.insertPlainText(f"{self.factorTableNode.GetTable().GetColumnName(i)} ")
    self.ui.GPALogTextbox.insertPlainText("\n")

    if hasattr(self, '_lr_refreshFromCovariates'):
      self._lr_refreshFromCovariates()

    return runAnalysis

  def onSelectResultsDirectory(self):
    self.resultsDirectory=qt.QFileDialog().getExistingDirectory()
    self.ui.resultsText.setText(self.resultsDirectory)
    try:
      self.ui.loadResultsButton.enabled = bool (self.resultsDirectory)
    except AttributeError:
      self.ui.loadResultsButton.enabled = False

  def onOpenResults(self):
    qpath = qt.QUrl.fromLocalFile(os.path.dirname(self.outputFolder+os.path.sep))
    qt.QDesktopServices().openUrl(qpath)

  def setupCovariatesFromResults(self, tablePath):
    # Load table
    try:
      self.factorTableNode = slicer.util.loadTable(tablePath)
    except Exception:
      self.ui.GPALogTextbox.insertPlainText(
        f"Covariate import failed. Table could not be loaded from {tablePath}\n"
      )
      return False
    numRows = self.factorTableNode.GetTable().GetColumn(0).GetNumberOfTuples()
    if numRows != len(self.files):
      self.ui.GPALogTextbox.insertPlainText(
        "Error: Covariate table import failed. Row count does not match number of samples in results.\n"
      )
      return False
    indexCol = self.factorTableNode.GetTable().GetColumn(0)
    for i, fname in enumerate(self.files):
      if indexCol.GetValue(i) not in fname:
        self.ui.GPALogTextbox.insertPlainText(
          f"Covariate import failed. Expected row like {fname}, got {indexCol.GetValue(i)}\n"
        )
        return False
    self.ui.selectFactor.clear()
    self.ui.selectFactor.addItem("")  # “no factor”
    for c in range(1, self.factorTableNode.GetNumberOfColumns()):
      name = self.factorTableNode.GetTable().GetColumnName(c)
      # if any cell in column is numeric, treat as numeric and skip
      has_numeric = False
      for r in range(numRows):
        if self.factorTableNode.GetTable().GetValue(r, c).ToString().isnumeric():
          has_numeric = True
          break
      if not has_numeric and name:
        self.ui.selectFactor.addItem(name)

    self.ui.GPALogTextbox.insertPlainText("Covariate table loaded for results session\n")

    if hasattr(self, '_lr_refreshFromCovariates'):
      self._lr_refreshFromCovariates()

    return True

  def onLoadFromFile(self):
    self.initializeOnLoad() #clean up module from previous runs
    logic = GPALogic()
    import pandas

    # Load data
    outputDataPath = os.path.join(self.resultsDirectory, 'outputData.csv')
    meanShapePath = os.path.join(self.resultsDirectory, 'meanShape.csv')
    eigenVectorPath = os.path.join(self.resultsDirectory, 'eigenvector.csv')
    eigenValuePath = os.path.join(self.resultsDirectory, 'eigenvalues.csv')
    eigenValueNames = ['Index', 'Scores']
    try:
      eigenValues = pandas.read_csv(eigenValuePath, names=eigenValueNames)
      eigenVector = pandas.read_csv(eigenVectorPath)
      meanShape = pandas.read_csv(meanShapePath)
      outputData = pandas.read_csv(outputDataPath)
    except:
      logging.debug('Result import failed: Missing file')
      self.ui.GPALogTextbox.insertPlainText(f"Result import failed: Missing file in output folder\n")
      return

    # Try to load skip scaling and skip LM options from log file, if present
    self.BoasOption = False
    self.LMExclusionList=[]
    logFilePath = os.path.join(self.resultsDirectory, 'analysis.json')
    try:
      with open(logFilePath) as json_file:
        logData = json.load(json_file)
      self.BoasOption = logData['GPALog'][0]['Boas']
      self.LMExclusionList = logData['GPALog'][0]['ExcludedLM']
    except:
      logging.debug('Log import failed: Cannot read the log file')
      self.ui.GPALogTextbox.insertPlainText("logging.debug('Log import failed: Cannot read the log file\n")

    # Initialize variables
    self.LM=LMData()
    success = self.LM.initializeFromDataFrame(outputData, meanShape, eigenVector, eigenValues)
    if not success:
      return

    self.files = outputData.Sample_name.tolist()
    shape = self.LM.lmOrig.shape
    print('Loaded ' + str(shape[2]) + ' subjects with ' + str(shape[0]) + ' landmark points.')
    self.ui.GPALogTextbox.insertPlainText(f"Loaded {shape[2]} subjects with {shape[0]} landmark points.\n")

    # If a covariate table was written with these results, load and setup
    covariatePath = os.path.join(self.resultsDirectory, "covariateTable.csv")
    if os.path.exists(covariatePath):
      self.ui.selectCovariatesText.setText(covariatePath)  # show path in UI
      if self.setupCovariatesFromResults(covariatePath):
        try:
          self.ui.selectFactor.currentIndexChanged.connect(lambda _: self.plot())
        except Exception:
          pass
    # GPA parameters
    self.pcNumber=10
    self.updateList()

    # Default to PC1 and initialize transform so slider works immediately
    try:
        if self.ui.pcComboBox.count > 1:
            self.ui.pcComboBox.setCurrentIndex(1)
        self.setupPCTransform()
    except Exception:
        pass
# get mean landmarks as a fiducial node
    self.meanLandmarkNode=slicer.mrmlScene.GetFirstNodeByName('Mean Landmark Node')
    if self.meanLandmarkNode is None:
      self.meanLandmarkNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.meanLandmarkNode.SetName('Mean Landmark Node')
      slicer.mrmlScene.AddNode(self.meanLandmarkNode)
      GPANodeCollection.AddItem(self.meanLandmarkNode)
      modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
      GPANodeCollection.AddItem(modelDisplayNode)
    self.meanLandmarkNode.GetDisplayNode().SetSliceProjection(True)
    self.meanLandmarkNode.GetDisplayNode().SetSliceProjectionOpacity(1)

    #set scaling factor using mean of landmarks
    self.rawMeanLandmarks = self.LM.mShape
    logic = GPALogic()
    if self.BoasOption:
        self.sampleSizeScaleFactor = 1.0
    else:
      self.sampleSizeScaleFactor = logic.dist2(self.rawMeanLandmarks).max()
    print("Scale Factor: " + str(self.sampleSizeScaleFactor))
    self.ui.GPALogTextbox.insertPlainText(f"Scale Factor: {self.sampleSizeScaleFactor}\n")
    for landmarkNumber in range (shape[0]):
      name = str(landmarkNumber+1) #start numbering at 1
      self.meanLandmarkNode.AddControlPoint(self.rawMeanLandmarks[landmarkNumber,:], name)
    self.meanLandmarkNode.SetDisplayVisibility(1)
    self.meanLandmarkNode.LockedOn() #lock position so when displayed they cannot be moved
    self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(1)
    self.meanLandmarkNode.GetDisplayNode().SetTextScale(3)
    #initialize mean LM display
    self.scaleMeanGlyph()
    self.toggleMeanColor()
    # Set up cloned mean landmark node for pc warping
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.meanLandmarkNode)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.copyLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    GPANodeCollection.AddItem(self.copyLandmarkNode)
    self.copyLandmarkNode.SetName('PC Warped Landmarks')
    self.copyLandmarkNode.SetDisplayVisibility(0)

    #set up procrustes distance plot
    filename=self.LM.closestSample(self.files)
    self.populateDistanceTable(self.files)
    print("Closest sample to mean:" + filename)
    self.ui.GPALogTextbox.insertPlainText(f"Closest sample to mean: {filename}\n")

    #Setup for scatter plots
    shape = self.LM.lm.shape
    self.LM.calcEigen()
    self.scatterDataAll= np.zeros(shape=(shape[2],self.pcNumber))
    for i in range(self.pcNumber):
      data=gpa_lib.plotTanProj(self.LM.lm,self.LM.sortedEig,i,1)
      self.scatterDataAll[:,i] = data[:,0]

    # Set up layout
    self.assignLayoutDescription()
    # Apply zoom for morphospace if scaling not skipped
    if(not self.BoasOption):
      cameras=slicer.mrmlScene.GetNodesByClass('vtkMRMLCameraNode')
      self.widgetZoomFactor = 2000*self.sampleSizeScaleFactor
      for camera in cameras:
        camera.GetCamera().Zoom(self.widgetZoomFactor)

    #initialize mean LM display
    self.scaleMeanGlyph()
    self.toggleMeanColor()

    # Enable buttons for workflow
    self.ui.plotButton.enabled = True
    self.ui.lolliButton.enabled = True
    self.ui.plotDistributionButton.enabled = True
    self.ui.plotMeanButton3D.enabled = True
    self.ui.showMeanLabelsButton.enabled = True
    self.ui.selectorButton.enabled = True
    self.ui.landmarkVisualizationType.enabled = True
    self.ui.modelVisualizationType.enabled = True

    if hasattr(self, '_lr_refreshFromCovariates'):
      self._lr_refreshFromCovariates()

  def onLoad(self):
    self.initializeOnLoad() #clean up module from previous runs
    logic = GPALogic()
    # check for loaded covariate table if table path is specified
    if self.ui.selectCovariatesText.text != "":
      runAnalysis = self.onLoadCovariatesTable()
      if not runAnalysis:
        return
    # get landmarks
    self.LM=LMData()
    lmToExclude=self.ui.excludeLMText.text
    if len(lmToExclude) != 0:
      self.LMExclusionList=lmToExclude.split(",")
      print("Excluded landmarks: ", self.LMExclusionList)
      self.ui.GPALogTextbox.insertPlainText(f"Excluded landmarks: {self.LMExclusionList}\n")
      self.LMExclusionList=[int(x) for x in self.LMExclusionList]
      lmNP=np.asarray(self.LMExclusionList)
    else:
      self.LMExclusionList=[]
    try:
      self.LM.lmOrig, self.landmarkTypeArray = logic.loadLandmarks(self.inputFilePaths, self.LMExclusionList, self.extension)
    except:
      logging.debug('Load landmark data failed: Could not create an array from landmark files')
      self.ui.GPALogTextbox.insertPlainText(f"Load landmark data failed: Could not create an array from landmark files\n")
      return
    shape = self.LM.lmOrig.shape
    print('Loaded ' + str(shape[2]) + ' subjects with ' + str(shape[0]) + ' landmark points.')
    self.ui.GPALogTextbox.insertPlainText(f"Loaded {shape[2]} subjects with {shape[0]} landmark points.\n")

    # Do GPA
    self.BoasOption=self.ui.BoasOptionCheckBox.isChecked()
    self.LM.doGpa(self.BoasOption)
    self.LM.calcEigen()
    self.pcNumber=10
    self.updateList()

    # Default to PC1 and initialize transform so slider works immediately
    try:
        if self.ui.pcComboBox.count > 1:
            self.ui.pcComboBox.setCurrentIndex(1)
        self.setupPCTransform()
    except Exception:
        pass
    if(self.BoasOption):
          self.ui.GPALogTextbox.insertPlainText("Using Boas coordinates \n")
          print("Using Boas coordinates")

    #set scaling factor using mean of landmarks
    self.rawMeanLandmarks = self.LM.lmOrig.mean(2)
    logic = GPALogic()
    if self.BoasOption:
      self.sampleSizeScaleFactor = 1.0
    else:
      self.sampleSizeScaleFactor = logic.dist2(self.rawMeanLandmarks).max()
    print("Scale Factor: " + str(self.sampleSizeScaleFactor))
    self.ui.GPALogTextbox.insertPlainText(f"Scale Factor for visualizations: {self.sampleSizeScaleFactor}\n")

    # get mean landmarks as a fiducial node
    self.meanLandmarkNode=slicer.mrmlScene.GetFirstNodeByName('Mean Landmark Node')
    if self.meanLandmarkNode is None:
      self.meanLandmarkNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.meanLandmarkNode.SetName('Mean Landmark Node')
      slicer.mrmlScene.AddNode(self.meanLandmarkNode)
      GPANodeCollection.AddItem(self.meanLandmarkNode)
      modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
      GPANodeCollection.AddItem(modelDisplayNode)
    self.meanLandmarkNode.GetDisplayNode().SetSliceProjection(True)
    self.meanLandmarkNode.GetDisplayNode().SetSliceProjectionOpacity(1)
    for landmarkNumber in range(shape[0]):
      name = str(landmarkNumber+1) #start numbering at 1
      self.meanLandmarkNode.AddControlPoint(vtk.vtkVector3d(self.rawMeanLandmarks[landmarkNumber,:]), name)
    self.meanLandmarkNode.SetDisplayVisibility(1)
    self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(1)
    self.meanLandmarkNode.GetDisplayNode().SetTextScale(3)
    self.meanLandmarkNode.LockedOn() #lock position so when displayed they cannot be moved

    # Set up cloned mean landmark node for pc warping
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.meanLandmarkNode)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.copyLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    GPANodeCollection.AddItem(self.copyLandmarkNode)
    self.copyLandmarkNode.SetName('PC Warped Landmarks')
    self.copyLandmarkNode.SetDisplayVisibility(0)

    # Set up output
    dateTimeStamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
    self.outputFolder = os.path.join(self.outputDirectory, dateTimeStamp)
    try:
      os.makedirs(self.outputFolder)
      self.LM.writeOutData(self.outputFolder, self.files)
      # covariate table
      if getattr(self, 'factorTableNode', None):
        try:
          print(f"saving {self.factorTableNode.GetID()} to {self.outputFolder + os.sep}covariateTable.csv")
          slicer.util.saveNode(self.factorTableNode, self.outputFolder + os.sep + "covariateTable.csv")
          GPANodeCollection.AddItem(self.factorTableNode)
        except:
          self.ui.GPALogTextbox.insertPlainText("Covariate table output failed: Could not write {self.factorTableNode} to {self.outputFolder+os.sep}covariateTable.csv\n")
      self.writeAnalysisLogFile(self.LM_dir_name, self.outputFolder, self.files)
      self.ui.openResultsButton.enabled = True
    except:
      logging.debug('Result directory failed: Could not access output folder')
      print("Error creating result directory")
      self.ui.GPALogTextbox.insertPlainText("Result directory failed: Could not access output folder\n")

    # Get closest sample to mean
    filename=self.LM.closestSample(self.files)
    self.populateDistanceTable(self.files)
    print("Closest sample to mean:" + filename)
    self.ui.GPALogTextbox.insertPlainText(f"Closest sample to mean: {filename}\n")

    #Setup for scatter plots
    shape = self.LM.lm.shape
    self.scatterDataAll= np.zeros(shape=(shape[2],self.pcNumber))
    for i in range(self.pcNumber):
      data=gpa_lib.plotTanProj(self.LM.lm,self.LM.sortedEig,i,1)
      self.scatterDataAll[:,i] = data[:,0]

    # Set up layout
    self.assignLayoutDescription()
    # Apply zoom for morphospace if scaling not skipped
    if(not self.BoasOption):
      cameras=slicer.mrmlScene.GetNodesByClass('vtkMRMLCameraNode')
      self.widgetZoomFactor = 2000*self.sampleSizeScaleFactor
      for camera in cameras:
        camera.GetCamera().Zoom(self.widgetZoomFactor)

    #initialize mean LM display
    self.scaleMeanGlyph()
    self.toggleMeanColor()

    # Enable buttons for workflow
    self.ui.plotButton.enabled = True
    self.ui.lolliButton.enabled = True
    self.ui.plotDistributionButton.enabled = True
    self.ui.plotMeanButton3D.enabled = True
    self.ui.showMeanLabelsButton.enabled = True
    self.ui.selectorButton.enabled = True
    self.ui.landmarkVisualizationType.enabled = True
    self.ui.modelVisualizationType.enabled = True

    if hasattr(self, '_lr_refreshFromCovariates'):
      self._lr_refreshFromCovariates()


  def initializeOnLoad(self):
    # clear rest of module when starting GPA analysis

    self.ui.grayscaleSelector.setCurrentPath("")
    self.ui.FudSelect.setCurrentPath("")

    self.ui.landmarkVisualizationType.setChecked(True)

    self.pcController.clear()

    self.ui.vectorOne.clear()
    self.ui.vectorTwo.clear()
    self.ui.vectorThree.clear()
    self.ui.XcomboBox.clear()
    self.ui.YcomboBox.clear()

    self.ui.scaleSlider.value=3
    self.ui.scaleMeanShapeSlider.value=3
    self.ui.meanShapeColor.color=qt.QColor(250,128,114)

    self.nodeCleanUp()

    # Reset zoom
    if self.widgetZoomFactor > 0:
      cameras=slicer.mrmlScene.GetNodesByClass('vtkMRMLCameraNode')
      for camera in cameras:
        camera.GetCamera().Zoom(1/self.widgetZoomFactor)
      self.widgetZoomFactor = 0

  def writeAnalysisLogFile(self, inputPath, outputPath, files):
    # generate log file
    [pointNumber, dim, subjectNumber] = self.LM.lmOrig.shape
    if getattr(self, 'factorTableNode', None):
      covariatePath = "covariateTable.csv"
    else:
      covariatePath = ""
    logData = {
      "@schema": "https://raw.githubusercontent.com/slicermorph/slicermorph/master/GPA/Resources/Schema/GPALog-schema-v1.0.0.json#",
      "GPALog" : [
        {
        "Date": datetime.now().strftime('%Y-%m-%d'),
        "Time": datetime.now().strftime('%H:%M:%S'),
        "InputPath": inputPath,
        "OutputPath": outputPath.replace("\\","/"),
        "Files": [f + self.extension for f in files],
        "LMFormat": self.extension,
        "NumberLM": pointNumber + len(self.LMExclusionList),
        "ExcludedLM": self.LMExclusionList,
        "Boas": bool(self.BoasOption),
        "MeanShape": "meanShape.csv",
        "Eigenvalues": "eigenvalues.csv",
        "Eigenvectors": "eigenvectors.csv",
        "OutputData": "outputData.csv",
        "PCScores": "pcScores.csv",
        "SemiLandmarks": self.landmarkTypeArray,
        "CovariatesFile": covariatePath
        }
      ]
    }
    logFilePath = outputPath+os.sep+"analysis.json"
    with open(logFilePath, 'w') as logFile:
      print(json.dumps(logData, indent=2), file=logFile)
    logFile.close()


  # ---- PC magnification helpers (class-level) ----
  def onUpdateMagnificationClicked(self):
    self.setupPCTransform()

  def setupPCTransform(self):
    # Determine currently selected PC (combo index > 0 means a PC is selected)
    pc_index = self.pcController.comboBoxIndex()
    if pc_index <= 0:
      return
    self.currentPC = pc_index
    # Determine PC score range from loaded scatter data
    self.pcMax = float(np.max(self.scatterDataAll, axis=0)[self.currentPC - 1])
    self.pcMin = float(np.min(self.scatterDataAll, axis=0)[self.currentPC - 1])
    self.pcScoreAbsMax = max(abs(self.pcMin), abs(self.pcMax))

    # Build displacement grid for current PC
    self.displacementGridData = self.getGridTransform(self.currentPC)

    needNewNode = (self._node('gridTransformNode') is None)
    if needNewNode:
      self.gridTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLGridTransformNode", "GridTransform")
      GPANodeCollection.AddItem(self.gridTransformNode)

    # Assign the displacement grid
    self.gridTransformNode.GetTransformFromParent().SetDisplacementGridData(self.displacementGridData)

    # Attach transform to the warped landmark/model nodes if present
    targetModelChecked = False
    try:
      targetModelChecked = bool(self.ui.modelVisualizationType.isChecked())
    except Exception:
      # Fall back to attribute access pattern used elsewhere
      targetModelChecked = bool(getattr(self.ui.modelVisualizationType, "checked", False))

    # Landmarks: prefer cloneLandmarkNode, fall back to copyLandmarkNode if used in older code
    lm_node = getattr(self, "cloneLandmarkNode", None) or getattr(self, "copyLandmarkNode", None)
    if lm_node is not None:
      lm_node.SetAndObserveTransformNodeID(self.gridTransformNode.GetID())

    # Model (if present and selected)
    if targetModelChecked and getattr(self, "cloneModelNode", None) and self.cloneModelNode is not None:
      self.cloneModelNode.SetAndObserveTransformNodeID(self.gridTransformNode.GetID())

    # Update the UI-driven range for live scaling
    self.pcController.setRange(self.pcMin, self.pcMax)
    self.pcController.setValue(0)
    self.updatePCScaling()

  def getGridTransform(self, pcValue: int):
    logic = GPALogic()
    # Read magnification from UI
    try:
      magnification = float(self.ui.spinMagnification.value)
    except Exception:
      # Defensive fallback for odd UI bindings
      magnification = float(getattr(self.ui, "spinMagnification", 1.0))

    # Shift mean landmarks along selected PC at the maximum score
    shiftMax = self.LM.ExpandAlongSinglePC(pcValue, self.pcScoreAbsMax * magnification, self.sampleSizeScaleFactor)
    target = self.rawMeanLandmarks + shiftMax
    targetLMVTK = logic.convertNumpyToVTK(target)
    sourceLMVTK = logic.convertNumpyToVTK(self.rawMeanLandmarks)

    VTKTPS = vtk.vtkThinPlateSplineTransform()
    VTKTPS.SetSourceLandmarks(targetLMVTK)
    VTKTPS.SetTargetLandmarks(sourceLMVTK)
    VTKTPS.SetBasisToR()

    # Choose bounds from model if in model mode; otherwise from the landmark clone/copy
    try:
      modelChecked = bool(self.ui.modelVisualizationType.isChecked())
    except Exception:
      modelChecked = bool(getattr(self.ui.modelVisualizationType, "checked", False))
    bounds_node = None
    if modelChecked and getattr(self, "cloneModelNode", None) and self.cloneModelNode is not None:
      bounds_node = self.cloneModelNode
    else:
      bounds_node = getattr(self, "cloneLandmarkNode", None) or getattr(self, "copyLandmarkNode", None)
    if bounds_node is None:
      raise RuntimeError("No landmark or model node available to derive bounds for the grid transform.")
    modelBounds = self.getExpandedBounds(bounds_node)

    origin = (modelBounds[0], modelBounds[2], modelBounds[4])
    size = (modelBounds[1] - modelBounds[0], modelBounds[3] - modelBounds[2], modelBounds[5] - modelBounds[4])
    dimension = 50
    extent = [0, dimension - 1, 0, dimension - 1, 0, dimension - 1]
    spacing = (size[0] / dimension, size[1] / dimension, size[2] / dimension)

    transformToGrid = vtk.vtkTransformToGrid()
    transformToGrid.SetInput(VTKTPS)
    transformToGrid.SetGridOrigin(origin)
    transformToGrid.SetGridSpacing(spacing)
    transformToGrid.SetGridExtent(extent)
    transformToGrid.Update()

    return transformToGrid.GetOutput()

  def getExpandedBounds(self, node, paddingFactor: float = 0.1):
    bounds = [0.0] * 6
    node.GetRASBounds(bounds)
    xRange = bounds[1] - bounds[0]
    yRange = bounds[3] - bounds[2]
    zRange = bounds[5] - bounds[4]
    bounds[0] -= xRange * paddingFactor
    bounds[1] += xRange * paddingFactor
    bounds[2] -= yRange * paddingFactor
    bounds[3] += yRange * paddingFactor
    bounds[4] -= zRange * paddingFactor
    bounds[5] += zRange * paddingFactor
    return bounds

  def updatePCScaling(self):
    if not getattr(self, 'gridTransformNode', None):
      return
    # Use the controller's current value mapped to the PC score range
    try:
      dynamic_value = float(self.pcController.getValue())
    except Exception:
      # Backward compatibility if someone left an old name around
      dynamic_value = float(getattr(self.pcController, "sliderValue", lambda: 0)())
    if getattr(self, "pcScoreAbsMax", 0) and self.pcScoreAbsMax > 1e-6:
      sf = dynamic_value / self.pcScoreAbsMax
    else:
      sf = 0.0
    sf = max(min(sf, 1.0), -1.0)
    self.gridTransformNode.GetTransformFromParent().SetDisplacementScale(sf)


    try:
      self.gridTransformNode.Modified()
    except Exception:
      pass

  # Explore Data callbacks and helpers
  def plot(self):
    logic = GPALogic()
    # get values from box
    xValue=self.ui.XcomboBox.currentIndex
    yValue=self.ui.YcomboBox.currentIndex
    shape = self.LM.lm.shape

    if (self.ui.selectFactor.currentIndex > 0) and getattr(self, 'factorTableNode', None):
      factorName = self.ui.selectFactor.currentText
      factorCol = self.factorTableNode.GetTable().GetColumnByName(factorName)
      factorArray=[]
      for i in range(factorCol.GetNumberOfTuples()):
        factorArray.append(factorCol.GetValue(i).rstrip())
      factorArrayNP = np.array(factorArray)
      if(len(np.unique(factorArrayNP))>1 ): #check values of factors for scatter plot
        logic.makeScatterPlotWithFactors(self.scatterDataAll,self.files,factorArrayNP,'PCA Scatter Plots',"PC"+str(xValue+1),"PC"+str(yValue+1),self.pcNumber)
      else:   #if the user input a factor requiring more than 3 groups, do not use factor
        qt.QMessageBox.critical(slicer.util.mainWindow(),
        'Error', 'Please use more than one unique factor')
        logic.makeScatterPlot(self.scatterDataAll,self.files,'PCA Scatter Plots',"PC"+str(xValue+1),"PC"+str(yValue+1),self.pcNumber)
    else:
      logic.makeScatterPlot(self.scatterDataAll,self.files,'PCA Scatter Plots',"PC"+str(xValue+1),"PC"+str(yValue+1),self.pcNumber)

  def lolliPlot(self):
    pb1=self.ui.vectorOne.currentIndex
    pb2=self.ui.vectorTwo.currentIndex
    pb3=self.ui.vectorThree.currentIndex

    pcList=[pb1,pb2,pb3]
    logic = GPALogic()

    meanLandmarkNode=slicer.mrmlScene.GetFirstNodeByName('Mean Landmark Node')
    meanLandmarkNode.SetDisplayVisibility(1)
    componentNumber = 1
    for pc in pcList:
      logic.lollipopGraph(self.LM, self.rawMeanLandmarks, pc, self.sampleSizeScaleFactor, componentNumber, self.ui.TwoDType.isChecked())
      componentNumber+=1

  def toggleMeanPlot(self):
    node = self._node('meanLandmarkNode')
    if not node:
      return
    vis = node.GetDisplayVisibility()
    if vis:
      node.SetDisplayVisibility(False)
      clone = self._node('cloneLandmarkNode')
      if clone:
        clone.SetDisplayVisibility(False)
    else:
      node.SetDisplayVisibility(True)
      disp = self._display(node)
      if disp:
        disp.SetGlyphScale(self.ui.scaleMeanShapeSlider.value)
        color = self.ui.meanShapeColor.color
        disp.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])
      clone = self._node('cloneLandmarkNode')
      if clone:
        clone.SetDisplayVisibility(True)
        cdisp = self._display(clone)
        if cdisp:
          cdisp.SetGlyphScale(self.ui.scaleMeanShapeSlider.value)
          cdisp.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])

  def toggleMeanLabels(self):
    node = self._node('meanLandmarkNode')
    if not node:
      return
    disp = self._display(node)
    if not disp:
      return
    visibility = disp.GetPointLabelsVisibility()
    if visibility:
      disp.SetPointLabelsVisibility(0)
      clone = self._node('cloneLandmarkNode')
      if clone:
        cdisp = self._display(clone)
        if cdisp:
          cdisp.SetPointLabelsVisibility(0)
    else:
      disp.SetPointLabelsVisibility(1)
      disp.SetTextScale(3)
      clone = self._node('cloneLandmarkNode')
      if clone:
        cdisp = self._display(clone)
        if cdisp:
          cdisp.SetPointLabelsVisibility(1)
          cdisp.SetTextScale(3)

  def toggleMeanColor(self):
    node = self._node('meanLandmarkNode')
    if not node:
      return
    disp = self._display(node)
    if not disp:
      return
    color = self.ui.meanShapeColor.color
    disp.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])
    clone = self._node('cloneLandmarkNode')
    if clone:
      cdisp = self._display(clone)
      if cdisp:
        cdisp.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])

  def scaleMeanGlyph(self):
    node = self._node('meanLandmarkNode')
    if not node:
      return
    disp = self._display(node)
    if not disp:
      return
    disp.SetGlyphScale(self.ui.scaleMeanShapeSlider.value)
    clone = self._node('cloneLandmarkNode')
    if clone:
      cdisp = self._display(clone)
      if cdisp:
        cdisp.SetGlyphScale(self.ui.scaleMeanShapeSlider.value)

  def onModelSelected(self):
    self.ui.selectorButton.enabled = bool( self.ui.grayscaleSelector.currentPath and self.ui.FudSelect.currentPath)

  def onToggleVisualization(self):
    if self.ui.landmarkVisualizationType.isChecked():
      self.ui.selectorButton.enabled = True
    else:
      self.ui.grayscaleSelector.enabled = True
      self.ui.FudSelect.enabled = True
      self.ui.selectorButton.enabled = bool( self.ui.grayscaleSelector.currentPath != "") and bool(self.ui.FudSelect.currentPath != "")

  def onPlotDistribution(self):
    if self.LM is None:
      return
    self.ui.scaleSlider.enabled = True
    if self.ui.NoneType.isChecked():
      self.unplotDistributions()
    elif self.ui.CloudType.isChecked():
      self.plotDistributionCloud(2*self.ui.scaleSlider.value)
    else:
      self.plotDistributionGlyph(2*self.ui.scaleSlider.value)

  def unplotDistributions(self):
    modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Point Cloud')
    if modelNode:
      slicer.mrmlScene.RemoveNode(modelNode)
    modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Ellipse')
    if modelNode:
      slicer.mrmlScene.RemoveNode(modelNode)
    modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Sphere')
    if modelNode:
      slicer.mrmlScene.RemoveNode(modelNode)

  def plotDistributionCloud(self, sliderScale):
    self.unplotDistributions()
    i,j,k=self.LM.lmOrig.shape
    pt=[0,0,0]
    #set up vtk point array for each landmark point
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(i*k)
    indexes = vtk.vtkDoubleArray()
    indexes.SetName('LM Index')
    pointCounter = 0

    for subject in range(0,k):
      for landmark in range(0,i):
        pt=self.LM.lmOrig[landmark,:,subject]
        points.SetPoint(pointCounter,pt)
        indexes.InsertNextValue(landmark+1)
        pointCounter+=1

    #add points to polydata
    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().SetScalars(indexes)

    #set up glyph for visualizing point cloud
    sphereSource = vtk.vtkSphereSource()
    if sliderScale != 1: # if scaling for visualization
      sphereSource.SetRadius(sliderScale*self.sampleSizeScaleFactor/500)
    else:
      sphereSource.SetRadius(sliderScale*self.sampleSizeScaleFactor/300)
    glyph = vtk.vtkGlyph3D()
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)
    glyph.ScalingOff()
    glyph.Update()

    #display
    modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Point Cloud')
    if modelNode is None:
      modelNode = slicer.vtkMRMLModelNode()
      modelNode.SetName('Landmark Point Cloud')
      slicer.mrmlScene.AddNode(modelNode)
      GPANodeCollection.AddItem(modelNode)
      modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
      GPANodeCollection.AddItem(modelDisplayNode)
      modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
      viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
      modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])

    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('LM Index')
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeLabels.txt')

    modelNode.SetAndObservePolyData(glyph.GetOutput())

  def plotDistributionGlyph(self, sliderScale):
    if self.LM is None:
      return
    self.unplotDistributions()
    varianceMat = self.LM.calcLMVariation(self.sampleSizeScaleFactor, self.BoasOption)
    i,j,k=self.LM.lmOrig.shape
    pt=[0,0,0]
    #set up vtk point array for each landmark point
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(i)
    scales = vtk.vtkDoubleArray()
    scales.SetName("Scales")
    index = vtk.vtkDoubleArray()
    index.SetName("Index")

    #set up tensor array to scale ellipses
    tensors = vtk.vtkDoubleArray()
    tensors.SetNumberOfTuples(i)
    tensors.SetNumberOfComponents(9)
    tensors.SetName("Tensors")

    # get fiducial node for mean landmarks, make just labels visible
    self.meanLandmarkNode.SetDisplayVisibility(1)
    self.ui.scaleMeanShapeSlider.value=0
    for landmark in range(i):
      pt=self.rawMeanLandmarks[landmark,:]
      points.SetPoint(landmark,pt)
      scales.InsertNextValue(sliderScale*(varianceMat[landmark,0]+varianceMat[landmark,1]+varianceMat[landmark,2])/3)
      tensors.InsertTuple9(landmark,sliderScale*varianceMat[landmark,0],0,0,0,sliderScale*varianceMat[landmark,1],0,0,0,sliderScale*varianceMat[landmark,2])
      index.InsertNextValue(landmark+1)

    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().AddArray(index)

    if self.ui.EllipseType.isChecked():
      polydata.GetPointData().SetScalars(index)
      polydata.GetPointData().SetTensors(tensors)
      glyph = vtk.vtkTensorGlyph()
      glyph.ExtractEigenvaluesOff()
      modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Ellipse')
      if modelNode is None:
        modelNode = slicer.vtkMRMLModelNode()
        modelNode.SetName('Landmark Variance Ellipse')
        slicer.mrmlScene.AddNode(modelNode)
        GPANodeCollection.AddItem(modelNode)
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
        GPANodeCollection.AddItem(modelDisplayNode)

    else:
      polydata.GetPointData().SetScalars(scales)
      polydata.GetPointData().AddArray(index)
      glyph = vtk.vtkGlyph3D()
      modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Sphere')
      if modelNode is None:
        modelNode = slicer.vtkMRMLModelNode()
        modelNode.SetName('Landmark Variance Sphere')
        slicer.mrmlScene.AddNode(modelNode)
        GPANodeCollection.AddItem(modelNode)
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
        GPANodeCollection.AddItem(modelDisplayNode)

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(64)
    sphereSource.SetPhiResolution(64)

    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)
    glyph.Update()

    modelNode.SetAndObservePolyData(glyph.GetOutput())
    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('Index') #color by landmark number
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeLabels.txt')

  # Interactive Visualization callbacks and helpers

  def onSelect(self):
    self.cloneLandmarkNode = self.copyLandmarkNode
    self.cloneLandmarkNode.CreateDefaultDisplayNodes()
    if self.ui.modelVisualizationType.isChecked():
      # get landmark node selected
      logic = GPALogic()
      self.sourceLMNode= slicer.util.loadMarkups(self.ui.FudSelect.currentPath)
      # check if landmark number is valid
      if self.sourceLMNode.GetNumberOfControlPoints() != self.LM.lmOrig.shape[0]:
        # error message
        logging.debug("Number of landmarks selected for 3D visualization does not match the analysis\n")
        slicer.util.messageBox(f"Error: Expected {self.LM.lmOrig.shape[0]} landmarks but loaded file has {self.sourceLMNode.GetNumberOfControlPoints()}")
        slicer.mrmlScene.RemoveNode(self.sourceLMNode)
        return
      self.initializeOnSelect()
      GPANodeCollection.AddItem(self.sourceLMNode)
      self.sourceLMnumpy=logic.convertFudicialToNP(self.sourceLMNode)

      # remove any excluded landmarks
      j=len(self.LMExclusionList)
      if (j != 0):
        indexToRemove=[]
        for i in range(j):
          indexToRemove.append(self.LMExclusionList[i]-1)
        self.sourceLMnumpy=np.delete(self.sourceLMnumpy,indexToRemove,axis=0)

      # set up transform
      targetLMVTK=logic.convertNumpyToVTK(self.rawMeanLandmarks)
      sourceLMVTK=logic.convertNumpyToVTK(self.sourceLMnumpy)
      VTKTPSMean = vtk.vtkThinPlateSplineTransform()
      VTKTPSMean.SetSourceLandmarks( sourceLMVTK )
      VTKTPSMean.SetTargetLandmarks( targetLMVTK )
      VTKTPSMean.SetBasisToR()  # for 3D transform

      # transform from selected to mean
      self.transformMeanNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'Mean TPS Transform')
      GPANodeCollection.AddItem(self.transformMeanNode)
      self.transformMeanNode.SetAndObserveTransformToParent( VTKTPSMean )

      # load model node
      self.modelNode=slicer.util.loadModel(self.ui.grayscaleSelector.currentPath)
      GPANodeCollection.AddItem(self.modelNode)
      self.modelDisplayNode = self.modelNode.GetDisplayNode()
      self.modelNode.SetAndObserveTransformNodeID(self.transformMeanNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(self.modelNode)

      # create a PC warped model as clone of the selected model node
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      itemIDToClone = shNode.GetItemByDataNode(self.modelNode)
      clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
      self.cloneModelNode = shNode.GetItemDataNode(clonedItemID)
      self.cloneModelNode.SetName('PC Warped Model')
      self.cloneModelDisplayNode =  self.cloneModelNode.GetDisplayNode()
      self.cloneModelDisplayNode.SetColor([0,0,1])
      GPANodeCollection.AddItem(self.cloneModelNode)
      visibility = self.meanLandmarkNode.GetDisplayVisibility()
      self.cloneLandmarkNode.SetDisplayVisibility(visibility)
      # clean up
      GPANodeCollection.RemoveItem(self.sourceLMNode)
      slicer.mrmlScene.RemoveNode(self.sourceLMNode)

    else:
      self.initializeOnSelect()
      self.cloneLandmarkNode.SetDisplayVisibility(1)
      self.meanLandmarkNode.SetDisplayVisibility(1)

    #set mean landmark color and scale from GUI
    self.scaleMeanGlyph()
    self.toggleMeanColor()
    visibility = self.meanLandmarkNode.GetDisplayNode().GetPointLabelsVisibility()
    self.cloneLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(visibility)
    self.cloneLandmarkNode.GetDisplayNode().SetTextScale(3)

    if self.ui.scaleMeanShapeSlider.value == 0:  # If the scale is set to 0, reset to default scale
      self.ui.scaleMeanShapeSlider.value = 3

    self.cloneLandmarkNode.GetDisplayNode().SetGlyphScale(self.ui.scaleMeanShapeSlider.value)

    #apply custom layout
    self.assignLayoutDescription()

    # Set up transform for PCA warping
    self.transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'PC TPS Transform')
    GPANodeCollection.AddItem(self.transformNode)

    # Enable PCA warping and recording
    self.pcController.populateComboBox(self.PCList)
    self.applyEnabled = True
    self.ui.startRecordButton.enabled = True

  def onStartRecording(self):
    #set up sequences for template model and PC TPS transform
    self.modelSequence=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSequenceNode","GPAModelSequence")
    self.modelSequence.SetHideFromEditors(0)
    GPANodeCollection.AddItem(self.modelSequence)
    self.transformSequence = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSequenceNode","GPATFSequence")
    self.transformSequence.SetHideFromEditors(0)
    GPANodeCollection.AddItem(self.transformSequence)

    #Set up a new sequence browser and add sequences
    browserNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSequenceBrowserNode", "GPASequenceBrowser")
    browserLogic=slicer.modules.sequences.logic()
    if getattr(self, 'cloneModelNode', None):
      browserLogic.AddSynchronizedNode(self.modelSequence,self.cloneModelNode,browserNode)
    browserLogic.AddSynchronizedNode(self.modelSequence,self.cloneLandmarkNode,browserNode)
    browserLogic.AddSynchronizedNode(self.transformSequence,self.gridTransformNode,browserNode)
    browserNode.SetRecording(self.transformSequence,'true')
    browserNode.SetRecording(self.modelSequence,'true')

    #Set up widget to record
    browserWidget=slicer.modules.sequences.widgetRepresentation()
    browserWidget.setActiveBrowserNode(browserNode)
    recordWidget = browserWidget.findChild('qMRMLSequenceBrowserPlayWidget')
    recordWidget.setRecordingEnabled(1)
    GPANodeCollection.AddItem(self.modelSequence)
    GPANodeCollection.AddItem(self.transformSequence)
    GPANodeCollection.AddItem(browserNode)

    #enable stop recording
    self.ui.stopRecordButton.enabled = True
    self.ui.startRecordButton.enabled = False

  def onStopRecording(self):
    browserWidget=slicer.modules.sequences.widgetRepresentation()
    recordWidget = browserWidget.findChild('qMRMLSequenceBrowserPlayWidget')
    recordWidget.setRecordingEnabled(0)
    slicer.util.selectModule(slicer.modules.sequences)
    self.ui.stopRecordButton.enabled = False
    self.ui.startRecordButton.enabled = True

  def initializeOnSelect(self):
    #remove nodes from previous runs
    temporaryNode=slicer.mrmlScene.GetFirstNodeByName('Mean TPS Transform')
    if(temporaryNode):
      GPANodeCollection.RemoveItem(temporaryNode)
      slicer.mrmlScene.RemoveNode(temporaryNode)

    temporaryNode=slicer.mrmlScene.GetFirstNodeByName('GPA Warped Volume')
    if(temporaryNode):
      GPANodeCollection.RemoveItem(temporaryNode)
      slicer.mrmlScene.RemoveNode(temporaryNode)

    temporaryNode=slicer.mrmlScene.GetFirstNodeByName('PC TPS Transform')
    if(temporaryNode):
      GPANodeCollection.RemoveItem(temporaryNode)
      slicer.mrmlScene.RemoveNode(temporaryNode)

  # ---------------------- Geomorph LR: Autocomplete + Validation ----------------------

  def _lr_qt_text(self, obj):
    """Return a clean string whether .text is a slot or a value."""
    t = getattr(obj, 'text', None)
    if callable(t):
      try:
        return str(t())
      except Exception:
        pass
    if t is not None:
      return str(t)
    return str(obj)

  def _lr_ensurePatsy(self):
    try:
      import patsy  # noqa
      return True
    except Exception:
      try:
        progress = slicer.util.createProgressDialog(windowTitle="Installing...",
                                                    labelText="Installing patsy (formula parser)...",
                                                    maximum=0)
        slicer.app.processEvents()
        slicer.util.pip_install(["patsy"])
        progress.close()
        import patsy  # noqa
        return True
      except Exception:
        try:
          progress.close()
        except Exception:
          pass
        return False

  def _lr_initTab(self):
    """Wire up the Geomorph LR tab to the multi-line UI (with Fit button)."""
    if not hasattr(self.ui, 'geomorphLRTab'):
      return

    # Map controls
    self._lr_formula = self.ui.lrFormulaEdit  # QPlainTextEdit
    self._lr_status = self.ui.lrStatusLabel
    self._lr_validateBtn = self.ui.lrValidateButton
    self._lr_copyBtn = self.ui.lrCopyButton
    self._lr_resetBtn = self.ui.lrResetButton
    self._lr_possibleList = self.ui.lrPossibleCovariatesList

    # NEW: fit widgets
    self._lr_fitBtn = self.ui.lrFitButton
    self._lr_fitStatus = self.ui.lrFitStatusLabel

    # Live validation on keystroke
    try:
      self._lr_formula.textChanged.connect(self._lr_onFormulaEdited)
    except Exception:
      pass

    # Buttons
    self._lr_validateBtn.clicked.connect(self._lr_onValidateClicked)
    self._lr_copyBtn.clicked.connect(self._lr_onCopyClicked)
    self._lr_resetBtn.clicked.connect(self._lr_onResetClicked)
    self._lr_fitBtn.clicked.connect(self._lr_onFitInRClicked)

    # Defaults
    self._lr_copyBtn.setEnabled(False)
    self._lr_setStatus("Waiting for input…", ok=None)
    self._lr_setFormulaText("Coords ~ Size")
    self._lr_fitBtn.setEnabled(False)
    self._lr_fitStatus.setText("Not ready")

    # Whitelist, completer, first validation
    self._lr_refreshFromCovariates()
    self._lr_refreshFitButton()

  def _lr_setStatus(self, msg, ok=None):
    self._lr_status.setText(msg)
    css_ok = "QLineEdit, QPlainTextEdit { border: 2px solid #2e7d32; border-radius: 3px; }"
    css_bad = "QLineEdit, QPlainTextEdit { border: 2px solid #c62828; border-radius: 3px; }"
    if ok is True:
      self._lr_formula.setStyleSheet(css_ok);
      self._lr_copyBtn.setEnabled(True)
    elif ok is False:
      self._lr_formula.setStyleSheet(css_bad);
      self._lr_copyBtn.setEnabled(False)
    else:
      self._lr_formula.setStyleSheet("");
      self._lr_copyBtn.setEnabled(False)

  def _lr_onResetClicked(self):
    self._lr_formula.blockSignals(True)
    self._lr_setFormulaText("Coords ~ Size")
    self._lr_formula.blockSignals(False)
    self._lr_onFormulaEdited()

  def _lr_onCopyClicked(self):
    qt.QApplication.clipboard().setText(self._lr_getFormulaText())

  def _lr_onValidateClicked(self):
    self._lr_onFormulaEdited(force=True)


  def _lr_getCovariateNames(self):
    """Fetch covariate names from factorTableNode (skip the first ID column)."""
    names = []
    ftn = getattr(self, 'factorTableNode', None)
    if not ftn:
      return names
    try:
      table = ftn.GetTable()
      ncols = ftn.GetNumberOfColumns()
      for c in range(1, ncols):
        nm = str(table.GetColumnName(c)).strip()
        if nm:
          names.append(nm)
    except Exception:
      pass
    return names

  def _lr_computeWhitelist(self):
    """
    Return just the allowed main-effect names (mains).
    Interactions are validated on-the-fly by checking that both sides are mains.
    """
    covs = self._lr_getCovariateNames()
    mains = ["Size"] + covs
    return mains

  def _lr_applyCompleter(self):
      """Create a QCompleter once; we'll update its model on each keystroke."""
      # Dispose any prior instance to avoid stale C++ wrappers
      try:
          old = getattr(self, '_lr_completer', None)
          if old is not None:
              old.setParent(None)
              old.deleteLater()
      except Exception:
          pass
      self._lr_completer = None
      self._lr_completer_model = None

      model = qt.QStringListModel(self._lr_formula)  # parent to editor so it lives
      comp = qt.QCompleter(model, self._lr_formula)
      comp.setCaseSensitivity(qt.Qt.CaseSensitive)
      try:
          comp.setCompletionMode(qt.QCompleter.PopupCompletion)
      except Exception:
          pass

      self._lr_completer_model = model
      self._lr_completer = comp
      comp.setWidget(self._lr_formula)

      # Insert completion on pick
      try:
          comp.activated[str].connect(self._lr_insertCompletion)
      except Exception:
          comp.activated.connect(lambda s: self._lr_insertCompletion(str(s)))

      # Update the model and show popup near caret as the user types (connect once)
      if not getattr(self, '_lr_popup_connected', False):
          try:
              self._lr_formula.textChanged.connect(self._lr_completerMaybePopup)
              self._lr_popup_connected = True
          except Exception:
              pass

      # Seed the model initially
      self._lr_updateCompleterModel()

  def _lr_refreshFromCovariates(self):
      """Rebuild the reference list and (re)attach the completer."""
      mains = self._lr_computeWhitelist()

      # Read-only list: show mains only
      self._lr_possibleList.clear()
      for nm in mains:
          self._lr_possibleList.addItem(nm)

      # (Re)attach a completer; its model will be updated dynamically as you type
      self._lr_applyCompleter()

      # Validate whatever is in the box
      self._lr_onFormulaEdited()

  def _lr_extract_term_names(self, patsy_term):
    """Return list of plain factor names for a patsy term (robust across versions)."""
    names = []
    for fac in getattr(patsy_term, 'factors', []):
      # Prefer .code (raw string), fall back to str() scraping
      nm = getattr(fac, 'code', None)
      if nm is None:
        nm = getattr(fac, 'name', None)
        if callable(nm):
          try:
            nm = nm()
          except Exception:
            nm = None
      if nm is None:
        nm = str(fac)
        # Try to strip wrapper like EvalFactor('X')
        if "EvalFactor(" in nm and "'" in nm:
          try:
            nm = nm.split("'", 2)[1]
          except Exception:
            pass
      names.append(str(nm).strip())
    return names

  def _lr_validateFormula(self, formula):
    """
    Validate with patsy (parse-only):
    - LHS must be 'Coords' (accept string aliases 'Shape', etc.).
    - Each RHS main effect must be either a bare main ('Size', 'Species', ...)
      or a supported transform of a main (e.g., log(Size), I(Size**2), C(Species), bs(Age, df=4)).
    - Interactions must be PAIRWISE (A:B). Each side may be a transform,
      but all underlying base variables must be in mains.
    Returns (ok: bool, message: str).
    """
    if not self._lr_ensurePatsy():
      return (False, "patsy is not available and could not be installed.")

    import patsy
    txt = (formula or "").strip()
    if not txt:
      return (False, "Enter a formula, e.g., Coords ~ Size + Sex.")
    if "~" not in txt:
      return (False, "Formula must contain '~'. Example: Coords ~ Size + Sex.")

    try:
      desc = patsy.ModelDesc.from_formula(txt)
    except Exception as e:
      return (False, f"Syntax error: {e}")

    # LHS checks
    lhs_terms = getattr(desc, "lhs_termlist", [])
    if len(lhs_terms) != 1:
      return (False, "Left-hand side must be a single variable: 'Coords'.")
    lhs_names = self._lr_extract_term_names(lhs_terms[0])
    if len(lhs_names) != 1 or lhs_names[0] not in ["Coords", "Shape", "SHAPE", "shape"]:
      return (False, "LHS should be 'Coords'. If you used 'Shape', it will be treated as an alias.")

    # Allowed mains (whitelist)
    mains_allowed = set(self._lr_computeWhitelist())

    # Validate RHS terms
    for term in getattr(desc, "rhs_termlist", []):
      names = self._lr_extract_term_names(term)
      # Intercept-only terms (e.g., '+ 1' or '-1') come through as empty name lists
      if len(names) == 0:
        continue

      # MAIN EFFECT
      if len(names) == 1:
        fac = names[0]
        bases = self._lr_factor_base_vars(fac, mains_allowed)
        if not bases:
          return (False, f"Unknown variable or unsupported transform: '{fac}'.")
        # If someone wrote I(Size+Age), bases would be {'Size','Age'}; that's ambiguous as a single main.
        if len(bases) > 1:
          return (False, f"Ambiguous transformed main effect '{fac}'. Use one variable or split the term.")
        continue

      # INTERACTION (pairwise only)
      if not self._lr_is_pairwise_term(names):
        return (False, "Only pairwise interactions (A:B) are allowed.")

      left_bases = self._lr_factor_base_vars(names[0], mains_allowed)
      right_bases = self._lr_factor_base_vars(names[1], mains_allowed)
      if not left_bases:
        return (False, f"Unknown variable or transform on left side of interaction: '{names[0]}'.")
      if not right_bases:
        return (False, f"Unknown variable or transform on right side of interaction: '{names[1]}'.")
      if len(left_bases) > 1 or len(right_bases) > 1:
        return (False, f"Ambiguous transformed interaction '{':'.join(names)}'. Use one base variable per side.")

    return (True, "OK")

  def _lr_onFormulaEdited(self, force=False):
    txt = self._lr_getFormulaText()
    ok, msg = self._lr_validateFormula(txt)
    self._lr_setStatus(msg, ok=ok)
    self._lr_refreshFitButton()

  # ---------- LR UI sizing + multi-line input (no .ui changes needed) ----------

  def _lr_upgradeFormulaWidget(self):
      """
    Replace single-line lrFormulaLine with a multi-line QPlainTextEdit in the same
    grid cell (row 0, col 1 as defined in the .ui). Works across PythonQt.
    """
      # Already upgraded?
      if hasattr(self.ui, 'lrFormulaEdit'):
          self._lr_formula = self.ui.lrFormulaEdit
          return

      if not (hasattr(self.ui, 'lrFormulaLine') and hasattr(self.ui, 'lrFormulaGrid')):
          return

      edit = qt.QPlainTextEdit()
      edit.setObjectName('lrFormulaEdit')
      edit.setMinimumHeight(72)
      edit.setMaximumHeight(120)
      edit.setSizePolicy(qt.QSizePolicy.Policy.Expanding, qt.QSizePolicy.Policy.Fixed)
      try:
          edit.setPlaceholderText("Coords ~ Size + Sex + Species")
      except Exception:
          pass

      grid = self.ui.lrFormulaGrid

      # Remove old widget and insert new one at the known position (row 0, col 1)
      old = self.ui.lrFormulaLine
      try:
          grid.removeWidget(old)
      except Exception:
          pass
      old.deleteLater()
      grid.addWidget(edit, 0, 1, 1, 1)

      self.ui.lrFormulaEdit = edit
      self._lr_formula = edit
      edit.textChanged.connect(lambda: self._lr_onFormulaEdited())

      # Optional: monospace font
      try:
          f = edit.font
          f.setFamily("Menlo")
          edit.setFont(f)
      except Exception:
          pass

  def _lr_shrinkCovariateList(self, max_height_px=140):
    """Make the 'Possible Covariates' box compact."""
    if hasattr(self.ui, 'lrPossibleCovariatesList'):
      self.ui.lrPossibleCovariatesList.setMaximumHeight(int(max_height_px))
      self.ui.lrPossibleCovariatesList.setSizePolicy(
        qt.QSizePolicy.Policy.Preferred, qt.QSizePolicy.Policy.Fixed
      )
    if hasattr(self.ui, 'lrReferenceGroup'):
      self.ui.lrReferenceGroup.setSizePolicy(
        qt.QSizePolicy.Policy.Preferred, qt.QSizePolicy.Policy.Fixed
      )

  def _lr_getFormulaText(self):
    w = self._lr_formula
    # QTextEdit/QPlainTextEdit vs QLineEdit
    if hasattr(w, 'toPlainText'):
      return str(w.toPlainText())
    if hasattr(w, 'text'):
      try:
        return str(w.text())
      except Exception:
        return str(w.text)
    return ""

  def _lr_setFormulaText(self, s):
    w = self._lr_formula
    if hasattr(w, 'setPlainText'):
      w.setPlainText(s)
    elif hasattr(w, 'setText'):
      try:
        w.setText(s)
      except Exception:
        w.setText = s  # PythonQt oddity fallback

  def _lr_completerMaybePopup(self):
    comp = getattr(self, '_lr_completer', None)
    if comp is None:
      return

    # Recompute candidates for the current context
    self._lr_updateCompleterModel()

    # Set the prefix to the current token; hide if empty
    prefix = self._lr_currentTokenPrefix()
    try:
      comp.setCompletionPrefix(prefix)
    except Exception:
      return

    if not prefix:
      try:
        comp.popup().hide()
      except Exception:
        pass
      return

    # Anchor popup near caret in widget-local coordinates
    try:
      r = self._lr_formula.cursorRect(self._lr_formula.textCursor())
    except Exception:
      try:
        r = self._lr_formula.cursorRect()
      except Exception:
        r = qt.QRect(0, 0, 1, 1)

    try:
      top_left_in_editor = self._lr_formula.viewport().mapTo(self._lr_formula, r.bottomLeft())
      r = qt.QRect(top_left_in_editor, qt.QSize(max(280, r.width()), max(22, r.height())))
    except Exception:
      r = qt.QRect(0, 0, 280, 22)

    comp.complete(r)  # expects widget-local rect

  def _lr_currentTokenPrefix(self):
    import re
    text = self._lr_getFormulaText()
    try:
      cursor = self._lr_formula.textCursor()
      pos = cursor.position()
      left = text[:pos]
    except Exception:
      left = text
    token = re.split(r'[\s\+\:\~\*\(\)]+', left)[-1]
    return token or ""

  def _lr_insertCompletion(self, completion: str):
    """Insert the selected completion at the caret, replacing the partial token."""
    try:
      cursor = self._lr_formula.textCursor()
      # Delete the current token prefix to the left of the caret
      prefix = self._lr_currentTokenPrefix()
      if prefix:
        cursor.movePosition(qt.QTextCursor.Left, qt.QTextCursor.KeepAnchor, len(prefix))
      cursor.insertText(completion)
      self._lr_formula.setTextCursor(cursor)
    except Exception:
      # Very defensive fall back
      try:
        self._lr_formula.insertPlainText(completion)
      except Exception:
        pass

  def _lr_contextBeforePrefix(self):
    """
    Return the single char immediately before the current token prefix
    (e.g., ':', '*', '+', '~'), or '' if none.
    """
    text = self._lr_getFormulaText()
    try:
      cursor = self._lr_formula.textCursor()
      pos = cursor.position()
      left = text[:pos]
    except Exception:
      left = text

    import re
    # Current token (chars since last operator/space)
    token = re.split(r'[\s\+\:\~\*\(\)]+', left)[-1]
    before = left[:-len(token)] if token else left
    return before[-1:] if before else ''

  def _lr_updateCompleterModel(self):
    """
    Compute context-aware candidates without enumerating A:B pairs:
    - Always offer operators ['~', '+', ':', '-1'].
    - Offer mains (Size + loaded covariates).
    - When a new term is starting (after '~', '+', ':', '*'), also offer common transform openers 'log(', 'C(', 'I(', 'bs(' ...).
    """
    mains = self._lr_computeWhitelist()
    ops = ["~", "+", ":", "-1"]

    # function openers for convenience
    func_tokens = [f + "(" for f in sorted(self._lr_allowed_function_names())]

    context_char = self._lr_contextBeforePrefix()
    if context_char in (":", "*", "+", "~", "(") or self._lr_currentTokenPrefix() == "":
      candidates = ops + func_tokens + mains
    else:
      candidates = ops + mains

    if self._lr_completer_model is not None:
      self._lr_completer_model.setStringList(candidates)

  def _lr_allowed_function_names(self):
    """Names of transforms we accept syntactically in validation."""
    return {
      "log", "log10", "log1p", "exp", "sqrt",  # common math transforms
      "I",  # identity for arithmetic
      "C",  # categorical
      "scale", "center",  # centering/scaling helpers
      "bs", "cr", "poly"  # spline/basis helpers
    }

  def _lr_factor_base_vars(self, factor_str, mains_allowed):
    """
    Return the set of underlying variable names referenced by a factor string.
    Examples:
      'Size'            -> {'Size'}
      'log(Size)'       -> {'Size'}
      'C(Species)'      -> {'Species'}
      'I(Size**2)'      -> {'Size'}
      'bs(Age, df=4)'   -> {'Age'}
      'scale(log(Size))'-> {'Size'}
    If we cannot find any base variable from mains, returns empty set.
    """
    s = str(factor_str).strip()

    # Plain main effect
    if s in mains_allowed:
      return {s}

    # Fast path for single-arg helpers: func(Var, ...)
    import re
    func_call = re.match(r'\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\((.*)\)\s*$', s)
    if func_call:
      func_name = func_call.group(1).split('.')[-1]  # allow np.log, numpy.log etc.
      inner = func_call.group(2)
      # If this is a known helper, look for the *first identifier* inside and accept it if it's a main
      if func_name in self._lr_allowed_function_names():
        # Grab all identifiers in the inner expression; keep only ones that are mains
        ids = set(re.findall(r'[A-Za-z_]\w*', inner))
        ids = {tok for tok in ids if tok in mains_allowed}
        if ids:
          return ids  # may have >1 if someone wrote I(Size+Age); we'll flag later if needed

    # Generic fallback: pull identifiers and keep the ones that are mains
    ids = set(re.findall(r'[A-Za-z_]\w*', s))
    ids = {tok for tok in ids if tok in mains_allowed}
    return ids

  def _lr_is_pairwise_term(self, names):
    """
    Return True if this is a pairwise interaction term (exactly two factors).
    'names' are the factor strings from patsy for one term.
    """
    return len(names) == 2

  # ---------------------- R / Rserve bridge (pyRserve) ----------------------

  def _r_initPanel(self):
    """Wire the R/Rserve controls if they exist in the UI."""
    if not hasattr(self.ui, "rserveGroup"):
      return  # UI not updated yet; safe no-op

    # Runtime state
    self._rserve_proc = None
    self._rserve_started_by_us = False
    self._r_conn = None
    self._r_last_error = ""
    self._geomorph_ok = False  # gate for Launch Rserve

    # Set sensible defaults
    try:
      self.ui.rPortSpin.setMinimum(1024)
      self.ui.rPortSpin.setMaximum(65535)
      if int(self.ui.rPortSpin.value) == 0:
        self.ui.rPortSpin.setValue(6311)
    except Exception:
      pass

    # Hook buttons
    self.ui.rDetectButton.clicked.connect(self._r_onDetectR)
    self.ui.rLaunchButton.clicked.connect(self._r_onLaunchClicked)
    self.ui.rShutdownButton.clicked.connect(self._r_onShutdownClicked)
    self.ui.rConnectButton.clicked.connect(self._r_onConnectClicked)
    self.ui.rDisconnectButton.clicked.connect(self._r_onDisconnectClicked)
    self.ui.rRefreshButton.clicked.connect(self._r_refreshRStatus)
    # Check-only for geomorph
    self.ui.rCheckGeomorphButton.clicked.connect(self._r_onCheckGeomorph)

    # Initial status
    self._r_onDetectR()  # finds Rscript and sets label
    self._r_onCheckGeomorph()  # populates geomorph status + gating
    self._refreshButtons()
    self._refreshStatusLabels()

  def _r_onDetectR(self):
    """Try to auto-locate Rscript; fill the path box and update status."""
    path = self._r_find_rscript()
    if path:
        try:
            self.ui.rscriptPath.setCurrentPath(path)
        except Exception:
            try:
                self.ui.rscriptPath.currentPath = path
            except Exception:
                pass
        self._setLabel(self.ui.rExeStatusLabel, f"Found: {path}")
    else:
        self._setLabel(self.ui.rExeStatusLabel, "Not found on PATH/R_HOME; set path manually.")

    # Immediately re-check geomorph with the new Rscript
    self._r_onCheckGeomorph()
    self._refreshStatusLabels()
    self._refreshButtons()

  def _r_onLaunchClicked(self):
    """Start Rserve on the chosen port using the selected Rscript, with rgl headless."""
    port = int(self.ui.rPortSpin.value)
    allow_remote = bool(getattr(self.ui.rAllowRemote, "isChecked", lambda: False)())
    rscript = self._r_getRscriptFromUI()
    if not rscript or not os.path.exists(rscript):
        self._setLabel(self.ui.rRserveStatusLabel, "Cannot launch: Rscript path invalid.")
        return

    # Launch Rserve after forcing rgl into headless/null backend for the whole session
    args = f"--RS-port {port} --no-save" + (" --RS-enable-remote" if allow_remote else "")
    code = (
        "Sys.setenv(RGL_USE_NULL='TRUE'); "
        "options(rgl.useNULL=TRUE); "
        f"Rserve::Rserve(args='{args}')"
    )
    cmd = [rscript, "-e", code]

    try:
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if platform.system()=="Windows" else 0
        self._rserve_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        self._rserve_started_by_us = True

        # Wait briefly for the port to open
        t0 = time.time()
        while time.time() - t0 < 8.0:
            if self._is_port_open("127.0.0.1", port):
                self._setLabel(self.ui.rRserveStatusLabel, f"Rserve is running on port {port}.")
                break
            time.sleep(0.25)
        else:
            self._setLabel(self.ui.rRserveStatusLabel, "Launch attempted, but port not open yet.")
    except Exception as e:
        self._setLabel(self.ui.rRserveStatusLabel, f"Launch failed: {e}")
    finally:
        self._refreshButtons()


  def _r_onShutdownClicked(self):
    """Attempt a graceful shutdown; fall back to killing the child we spawned."""
    port = int(self.ui.rPortSpin.value)
    ok = False

    # Try via pyRserve shutdown if possible
    try:
      pyR = self._r_ensure_pyRserve()
      if pyR:
        conn = self._r_conn or pyR.connect(host="127.0.0.1", port=port, timeout=2.0)
        try:
          if hasattr(conn, "shutdown"):
            conn.shutdown()
            ok = True
          conn.close()
        except Exception:
          pass
    except Exception:
      pass

    # If we started it and it's still listening, kill the process
    if not ok and self._rserve_started_by_us and self._rserve_proc is not None:
      try:
        if platform.system() == "Windows":
          self._rserve_proc.terminate()
        else:
          self._rserve_proc.terminate()
        self._rserve_proc.wait(timeout=4.0)
        ok = True
      except Exception:
        try:
          self._rserve_proc.kill()
        except Exception:
          pass

    # Cleanup flags
    self._rserve_proc = None
    self._rserve_started_by_us = False

    # Update status
    if ok:
      self._setLabel(self.ui.rRserveStatusLabel, "Rserve shut down.")
    else:
      self._setLabel(self.ui.rRserveStatusLabel, "Shutdown request sent (or process kill attempted).")
    # Close any lingering connection
    self._safeCloseRConn()
    self._refreshButtons()
    self._refreshStatusLabels()

  def _r_onConnectClicked(self):
    """Open a pyRserve connection; prefer IPv4 and show clear errors."""
    self._setLabel(self.ui.rConnStatusLabel, "Connecting…")
    pyR = self._r_ensure_pyRserve()
    if not pyR:
      self._setLabel(self.ui.rConnStatusLabel, f"pyRserve not available. {getattr(self, '_r_last_error', '')}")
      self._refreshButtons()
      self._refreshStatusLabels()
      return

    port = int(self.ui.rPortSpin.value)
    last_exc = None
    for host in ("127.0.0.1", "localhost", "::1"):
      try:
        self._safeCloseRConn()
        self._r_conn = pyR.connect(host, port) if hasattr(pyR, "connect") else pyR.rconnect(host, port)
        try:
          _ = self._r_conn.eval("1+1")
        except Exception:
          pass
        self._setLabel(self.ui.rConnStatusLabel, f"Connected to {host}:{port}")
        # NEW: immediately check geomorph INSIDE this Rserve
        self._r_onCheckGeomorph()
        self._refreshButtons()
        self._refreshStatusLabels()
        return
      except Exception as e:
        last_exc = e

    self._r_conn = None
    self._setLabel(self.ui.rConnStatusLabel, f"Connect failed on port {port}: {last_exc}")
    self.ui.GPALogTextbox.insertPlainText(f"[Rserve] Connect failed on {port}: {last_exc}\n")
    self._refreshButtons()
    self._refreshStatusLabels()

  def _r_onDisconnectClicked(self):
    """Close the pyRserve connection only."""
    self._safeCloseRConn()
    self._setLabel(self.ui.rConnStatusLabel, "Disconnected.")
    self._refreshButtons()
    self._refreshStatusLabels()

  def _r_refreshRStatus(self):
    """Manual refresh of status labels."""
    self._refreshStatusLabels()
    self._refreshButtons()

  def _refreshStatusLabels(self):
    # Rscript status
    rscript = self._r_getRscriptFromUI()
    if rscript and os.path.exists(rscript):
      self._setLabel(self.ui.rExeStatusLabel, f"Found: {rscript}")
    else:
      self._setLabel(self.ui.rExeStatusLabel, "Not found; set path and 'Auto-detect' if needed.")

    # Rserve status
    port = int(self.ui.rPortSpin.value)
    running = self._is_port_open("127.0.0.1", port)
    self._setLabel(self.ui.rRserveStatusLabel, f"Listening on {port}" if running else "Not listening")

    # Connection status
    if self._r_conn:
      try:
        _ = self._r_conn.eval("1+1")  # small ping
        self._setLabel(self.ui.rConnStatusLabel, "Connected")
      except Exception:
        self._setLabel(self.ui.rConnStatusLabel, "Connection lost")
        self._safeCloseRConn()
    else:
      self._setLabel(self.ui.rConnStatusLabel, "Not connected")

    # Also refresh LR Fit gating when anything here changes
    try:
      self._lr_refreshFitButton()
    except Exception:
      pass

  def _refreshButtons(self):
    """Enable/disable buttons according to current state (no geomorph gate for launch)."""
    port = int(self.ui.rPortSpin.value)
    rscript_ok     = bool(self._r_getRscriptFromUI() and os.path.exists(self._r_getRscriptFromUI()))
    rserve_running = self._is_port_open("127.0.0.1", port)
    connected      = bool(self._r_conn)
    self._setEnabled(self.ui.rLaunchButton,   rscript_ok and not rserve_running)
    self._setEnabled(self.ui.rShutdownButton, rserve_running)
    self._setEnabled(self.ui.rConnectButton,  rserve_running and not connected)
    self._setEnabled(self.ui.rDisconnectButton, connected)
    self._setEnabled(self.ui.rCheckGeomorphButton, rscript_ok or connected)

  def _r_getRscriptFromUI(self):
    """Read and normalize the Rscript path from the UI."""
    p = None
    try:
        p = self.ui.rscriptPath.currentPath
    except Exception:
        try:
            p = str(self.ui.rscriptPath.text())
        except Exception:
            p = None
    if not p:
        return None
    # normalize: expand ~, strip whitespace, resolve symlinks
    p = os.path.expanduser(str(p).strip())
    p = os.path.realpath(p)
    return p


  def _r_find_rscript(self):
    """Try PATH, R_HOME and common install locations for Rscript."""
    # 1. PATH
    p = shutil.which("Rscript") or shutil.which("Rscript.exe")
    if p:
      return p

    # 2. R_HOME
    r_home = os.environ.get("R_HOME", "")
    if r_home:
      candidates = [
        os.path.join(r_home, "bin", "Rscript"),
        os.path.join(r_home, "bin", "Rscript.exe"),
        os.path.join(r_home, "bin", "x64", "Rscript.exe"),
      ]
      for c in candidates:
        if os.path.exists(c):
          return c

    # 3. Typical locations
    if platform.system() == "Windows":
      roots = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
      ]
      for root in roots:
        if not root:
          continue
        try:
          # Look for R\R-*\bin\Rscript.exe
          for ver in os.listdir(os.path.join(root, "R")):
            c1 = os.path.join(root, "R", ver, "bin", "Rscript.exe")
            c2 = os.path.join(root, "R", ver, "bin", "x64", "Rscript.exe")
            if os.path.exists(c2):
              return c2
            if os.path.exists(c1):
              return c1
        except Exception:
          pass
    else:
      for c in ("/opt/homebrew/bin/Rscript", "/usr/local/bin/Rscript", "/usr/bin/Rscript"):
        if os.path.exists(c):
          return c

    return None

  def _is_port_open(self, host, port, timeout=0.25):
    """True if something is listening on host:port."""
    try:
      with socket.create_connection((host, int(port)), timeout=timeout):
        return True
    except Exception:
      return False

  def _safeCloseRConn(self):
    """Close pyRserve connection safely."""
    if getattr(self, "_r_conn", None) is not None:
      try:
        self._r_conn.close()
      except Exception:
        pass
      self._r_conn = None

  def _setLabel(self, labelWidget, text):
    try:
      labelWidget.setText(str(text))
    except Exception:
      try:
        labelWidget.text = str(text)
      except Exception:
        pass

  def _setEnabled(self, widget, enabled: bool):
    try:
      widget.setEnabled(bool(enabled))
    except Exception:
      try:
        widget.enabled = bool(enabled)
      except Exception:
        pass

  def _r_ensure_pyRserve(self):
    """Import (or auto-install) pyRserve for connection management, with a NumPy 2.0
    compatibility shim applied **before** importing pyRserve (matches your working script)."""
    # --- NumPy 2.0 compat shim for pyRserve (must be set before importing pyRserve) ---
    try:
      import numpy as _np
      from types import SimpleNamespace as _SimpleNamespace
      if not hasattr(_np, "string_"):  _np.string_ = _np.bytes_
      if not hasattr(_np, "unicode_"): _np.unicode_ = str
      if not hasattr(_np, "int"):      _np.int = int
      if not hasattr(_np, "bool"):     _np.bool = bool
      if not hasattr(_np, "float"):    _np.float = float
      if not hasattr(_np, "object"):   _np.object = object
      if not hasattr(_np, "compat"):
        _np.compat = _SimpleNamespace(long=int)
      elif not hasattr(_np.compat, "long"):
        _np.compat.long = int
    except Exception:
      pass
    # -------------------------------------------------------------------------------

    # Already imported?
    try:
      import sys
      if "pyRserve" in sys.modules:
        import pyRserve as _pyRserve  # noqa
        return _pyRserve
    except Exception:
      pass

    # Try normal import, else auto-install
    try:
      import pyRserve as _pyRserve  # noqa
      return _pyRserve
    except Exception:
      try:
        progress = slicer.util.createProgressDialog(
          windowTitle="Installing...",
          labelText="Installing pyRserve...",
          maximum=0,
        )
        slicer.app.processEvents()
        slicer.util.pip_install(["pyRserve"])
        progress.close()
        import pyRserve as _pyRserve  # noqa
        return _pyRserve
      except Exception as e:
        try:
          progress.close()
        except Exception:
          pass
        self._r_last_error = str(e)
        return None

  def _r_onCheckGeomorph(self):
    """
    Status: RRPP is required; geomorph is optional.
    - Rscript self-test is informative only (won't block fitting).
    - If connected to Rserve, we list versions from installed.packages() (no loading).
    """

    def _fmt(xs):
      return ("\n  - " + "\n  - ".join(xs)) if xs else " (none)"

    # Safe CLI load test (robust parser)
    cli_ok, cli_info = self._r_cli_pkg_selftest()
    cli_rhome = cli_info.get("r_home", "?")
    cli_libs = cli_info.get("libpaths", [])
    cli_okG = cli_info.get("load_ok", {}).get("geomorph", False)
    cli_okR = cli_info.get("load_ok", {}).get("RRPP", False)
    cli_vG = cli_info.get("geomorph", "")
    cli_vR = cli_info.get("RRPP", "")

    # Rserve: what's installed (no load)
    conn = getattr(self, "_r_conn", None)
    rsrv_vG = rsrv_vR = ""
    rsrv_rhome = "?"
    rsrv_libs = []
    if conn:
      try:
        s = str(conn.eval(
          "ip <- rownames(installed.packages());"
          "g <- if ('geomorph' %in% ip) as.character(packageVersion('geomorph')) else '';"
          "r <- if ('RRPP'     %in% ip) as.character(packageVersion('RRPP'))     else '';"
          "paste(g, r, R.home('bin'), paste(.libPaths(), collapse=';'), sep='|')"
        )).strip()
        parts = s.split("|")
        if len(parts) >= 4:
          rsrv_vG = parts[0]
          rsrv_vR = parts[1]
          rsrv_rhome = parts[2]
          rsrv_libs = parts[3].split(";") if parts[3] else []
      except Exception as e:
        self.ui.GPALogTextbox.insertPlainText(f"[Rserve] installed.packages() failed: {e}\n")

    # Label
    bits = []
    bits.append("Rserve connected" if conn else "Rserve not connected")
    if cli_ok:
      bits.append(f"Rscript load test: RRPP {'OK' if cli_okR else 'FAIL'}, geomorph {'OK' if cli_okG else 'FAIL'}")
    else:
      bits.append("Rscript check failed")

    if conn:
      if rsrv_vR:
        bits.append(f"Rserve has RRPP {rsrv_vR}")
      else:
        bits.append("Rserve missing RRPP")
      if rsrv_vG:
        bits.append(f"geomorph {rsrv_vG} (optional)")
      else:
        bits.append("geomorph not installed (optional)")

    self._setLabel(self.ui.rGeomorphStatusLabel, " | ".join(bits))

    # Detailed paths
    self.ui.GPALogTextbox.insertPlainText(
      f"[Rscript] R.home(bin): {cli_rhome}\n"
      f"[Rscript] .libPaths():{_fmt(cli_libs)}\n"
    )
    if not cli_ok:
      self.ui.GPALogTextbox.insertPlainText(f"[Rscript] raw:\n{cli_info.get('raw', '(no output)')}\n")
    if conn:
      self.ui.GPALogTextbox.insertPlainText(
        f"[Rserve ] R.home(bin): {rsrv_rhome}\n"
        f"[Rserve ] .libPaths():{_fmt(rsrv_libs)}\n"
      )

    # Gate: RRPP present in Rserve is sufficient to proceed
    self._geomorph_ok = bool(conn) and bool(rsrv_vR)
    self._refreshButtons()
    try:
      self._lr_refreshFitButton()
    except Exception:
      pass

  def _r_check_geomorph_via_rscript(self):
    """
    Check geomorph using the currently selected Rscript (CLI) WITHOUT loading it.
    Returns (installed: bool, version: str, r_home_bin: str, raw: str).
    """
    rscript = self._r_getRscriptFromUI()
    if not (rscript and os.path.exists(rscript)):
        return (False, "", "", "Rscript not set or not found")

    code = (
      "ip <- rownames(installed.packages());"
      "if ('geomorph' %in% ip) {"
      "  cat('OK|', as.character(packageVersion('geomorph')), '|', R.home('bin'), sep='')"
      "} else cat('MISS')"
    )
    try:
        p = subprocess.run([rscript, "-e", code], capture_output=True, text=True)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        # Startup chatter may precede our marker; search for OK| / MISS anywhere.
        ok_pos = out.find("OK|")
        if ok_pos >= 0:
            tail = out[ok_pos+3:]
            parts = tail.split("|")
            ver   = parts[0] if len(parts) > 0 else "?"
            rhome = parts[1] if len(parts) > 1 else "?"
            return (True, ver, rhome, out)
        if out.find("MISS") >= 0:
            return (False, "", "", out)
        # Unknown output → treat as not installed but show raw
        return (False, "", "", out if out else "MISS")
    except Exception as e:
        return (False, "", "", f"Rscript check error: {e}")

  def _r_check_geomorph_via_rserve(self):
    """
    Check geomorph inside the CONNECTED Rserve session WITHOUT loading it.
    Returns (installed: bool, version: str, r_home_bin: str, libpaths: list[str], raw: str).
    If not connected, installed == None.
    """
    conn = getattr(self, "_r_conn", None)
    if not conn:
        return (None, "", "", [], "not connected")
    try:
        s = str(conn.eval(
            "ip <- rownames(installed.packages());"
            "if ('geomorph' %in% ip) {"
            "  paste0('OK|', as.character(packageVersion('geomorph')), '|',"
            "         R.home('bin'), '|', paste(.libPaths(), collapse=';'))"
            "} else {"
            "  paste0('MISS|', R.home('bin'), '|', paste(.libPaths(), collapse=';'))"
            "}"
        )).strip()
        parts = s.split("|")
        if s.startswith("OK|"):
            ver  = parts[1] if len(parts) > 1 else "?"
            rbin = parts[2] if len(parts) > 2 else "?"
            libs = parts[3].split(";") if len(parts) > 3 else []
            return (True, ver, rbin, libs, s)
        # MISS path
        rbin = parts[1] if len(parts) > 1 else "?"
        libs = parts[2].split(";") if len(parts) > 2 else []
        return (False, "", rbin, libs, s)
    except Exception as e:
        return (False, "", "", [], f"Rserve check error: {e}")


  def _r_onInstallGeomorph(self):
    """Install 'geomorph' from CRAN using Rscript, then re-check."""
    rscript = self._r_getRscriptFromUI()
    if not (rscript and os.path.exists(rscript)):
      self._setLabel(self.ui.rGeomorphStatusLabel, "Rscript not set")
      return

    progress = None
    try:
      progress = slicer.util.createProgressDialog(windowTitle="Installing R package",
                                                  labelText="Installing 'geomorph' from CRAN…",
                                                  maximum=0)
      slicer.app.processEvents()
      cmd = [rscript, "-e", "install.packages('geomorph', repos='https://cloud.r-project.org', dependencies=TRUE)"]
      rc = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      if rc == 0:
        self._setLabel(self.ui.rGeomorphStatusLabel, "Install completed; re-checking…")
        self.ui.GPALogTextbox.insertPlainText("[R] geomorph install completed.\n")
      else:
        self._setLabel(self.ui.rGeomorphStatusLabel, f"Install exited with code {rc}")
        self.ui.GPALogTextbox.insertPlainText(f"[R] geomorph install returned code {rc}\n")
    except Exception as e:
      self._setLabel(self.ui.rGeomorphStatusLabel, f"Install failed: {e}")
      self.ui.GPALogTextbox.insertPlainText(f"[R] geomorph install failed: {e}\n")
    finally:
      try:
        progress.close()
      except Exception:
        pass
      # Re-check and refresh buttons after any attempt
      self._r_onCheckGeomorph()
      self._refreshButtons()

  def _lr_canFit(self) -> bool:
    """True if formula is valid and Rserve is connected."""
    # Check formula validity
    try:
      fml = self._lr_getFormulaText()
      ok, _msg = self._lr_validateFormula(fml)
    except Exception:
      ok = False
    if not ok:
      return False
    # Check connection
    return bool(getattr(self, "_r_conn", None))

  def _lr_refreshFitButton(self):
    """Enable/disable Fit button based on prerequisites; update label lightly."""
    try:
      can = self._lr_canFit()
      self.ui.lrFitButton.setEnabled(bool(can))
      if can:
        self.ui.lrFitStatusLabel.setText("Ready")
      else:
        self.ui.lrFitStatusLabel.setText("Not ready")
    except Exception:
      pass

  def _lr_findCovariatesPath(self) -> str:
    """Prefer explicit selection in the UI; else look for outputFolder/covariateTable.csv."""
    paths = []
    try:
      p = str(self.ui.selectCovariatesText.text)
      if p:
        paths.append(p)
    except Exception:
      pass
    try:
      p2 = os.path.join(self.outputFolder, "covariateTable.csv")
      paths.append(p2)
    except Exception:
      pass
    for p in paths:
      if p and os.path.isfile(p):
        return p
    return ""

  def _lr_get_base_variables_from_formula(self, formula: str):
    """
    Return set of base variable names referenced on RHS of the formula,
    excluding 'Coords' (or Shape aliases) and 'Size'.
    """
    if not self._lr_ensurePatsy():
      return set()

    import patsy, re
    txt = (formula or "").strip()
    desc = patsy.ModelDesc.from_formula(txt)

    mains_allowed = set(self._lr_computeWhitelist())  # ["Size"] + covariates from table
    bases = set()

    # Collect bases from each RHS term
    for term in getattr(desc, "rhs_termlist", []):
      names = self._lr_extract_term_names(term)  # strings of factors possibly wrapped
      if len(names) == 0:
        continue
      if len(names) == 1:
        bases |= self._lr_factor_base_vars(names[0], mains_allowed)
      elif self._lr_is_pairwise_term(names):
        bases |= self._lr_factor_base_vars(names[0], mains_allowed)
        bases |= self._lr_factor_base_vars(names[1], mains_allowed)

    # Scrub out LHS/aliases and Size
    drop = {"Coords", "Shape", "SHAPE", "shape", "Size", "size"}
    return {b for b in bases if b not in drop}

  def _lr_onFitInRClicked(self):
    """
    Fit in R using RRPP::procD.lm with a plain matrix response (no geomorph).
    - Y is an n × (3p) numeric matrix (coords flattened); predictors live in a data.frame (.df).
    - This avoids arrayspecs() and any attempt to load the 'geomorph' DLLs that are segfaulting.
    - Each R step is wrapped so if Rserve crashes, the UI log shows exactly where.
    """
    import numpy as np
    import pandas as pd

    # ---- Guards ---------------------------------------------------------------
    if not getattr(self, "LM", None):
      self.ui.lrFitStatusLabel.setText("No GPA data")
      return

    fml_raw = self._lr_getFormulaText()
    ok, msg = self._lr_validateFormula(fml_raw)
    if not ok:
      self.ui.lrFitStatusLabel.setText("Invalid formula")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] Invalid formula: {msg}\n")
      return

    conn = getattr(self, "_r_conn", None)
    if not conn:
      self.ui.lrFitStatusLabel.setText("Rserve not connected")
      return

    # ---- Build response Y (n × 3p) and Size ----------------------------------
    arr = np.asarray(self.LM.lm)  # (p, 3, n)
    if arr.ndim != 3 or arr.shape[1] != 3:
      self.ui.lrFitStatusLabel.setText("Bad landmark array")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] Unexpected LM.lm shape: {arr.shape}\n")
      return
    p, _, n = arr.shape
    Y = arr.transpose(2, 0, 1).reshape(n, 3 * p, order="C")  # n × 3p

    size_vec = np.asarray(self.LM.centriodSize, dtype=float).reshape(-1)
    if size_vec.shape[0] != n:
      self.ui.lrFitStatusLabel.setText("Bad centroid size")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] centroid size length {size_vec.shape[0]} != specimens {n}\n")
      return

    files = list(getattr(self, "files", [])) or [f"spec_{i + 1}" for i in range(n)]

    # ---- Non-Size predictors required by formula -----------------------------
    base_vars = self._lr_get_base_variables_from_formula(fml_raw)  # excludes 'Size'
    cov_df = None
    cov_path = ""
    if base_vars:
      cov_path = self._lr_findCovariatesPath()
      if not cov_path:
        self.ui.lrFitStatusLabel.setText("Missing covariate table")
        self.ui.GPALogTextbox.insertPlainText("[LR] No covariate CSV found; cannot satisfy formula variables.\n")
        return
      try:
        cov_df = pd.read_csv(cov_path)
        if cov_df.shape[1] < 2:
          raise ValueError("Covariate CSV needs ID col + covariate columns.")
        cov_df = cov_df.set_index(cov_df.columns[0])
        missing = [f for f in files if f not in cov_df.index]
        if missing:
          raise ValueError(f"IDs missing in covariate table (first 10): {missing[:10]}")
        cov_df = cov_df.loc[files]  # align to specimen order
      except Exception as e:
        self.ui.lrFitStatusLabel.setText("Covariate load error")
        self.ui.GPALogTextbox.insertPlainText(f"[LR] Failed to read/align covariates: {e}\n")
        return

    step = self._r_step  # run one R command, log errors precisely

    # ---- Keep rgl headless (defensive; RRPP itself doesn't need it) ----------
    if not step(conn, "Headless rgl",
                'options(rgl.useNULL=TRUE); '
                'Sys.setenv(RGL_USE_NULL="TRUE"); '
                'Sys.setenv(RGL_ALWAYS_SOFTWARE="TRUE")'):
      self.ui.lrFitStatusLabel.setText("R data error (rgl)")
      return

    # ---- Require RRPP (we do NOT load/require geomorph here) ------------------
    ok, _ = self._r_try('if (!"RRPP" %in% rownames(installed.packages())) '
                        'stop("RRPP not installed in this Rserve")',
                        "check RRPP")
    if not ok:
      self.ui.lrFitStatusLabel.setText("RRPP missing")
      return

    # ---- Ship response and size to R ------------------------------------------
    try:
      conn.r.Y = Y
      conn.r.size = size_vec
    except Exception as e:
      self.ui.lrFitStatusLabel.setText("R data error (send)")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] send Y/size: {repr(e)}\n")
      return

    # Ensure Y is numeric matrix
    if not step(conn, "Prepare Y", 'Y <- base::as.matrix(Y); storage.mode(Y) <- "double"'):
      self.ui.lrFitStatusLabel.setText("R data error (Y)")
      return

    # ---- Build predictor data.frame (.df) in R --------------------------------
    if not step(conn, "Init .df", '.df <- base::data.frame(Size = base::as.numeric(size))'):
      self.ui.lrFitStatusLabel.setText("R data error (.df)")
      return

    if base_vars and cov_df is not None:
      for var in sorted(base_vars):
        if var not in cov_df.columns:
          self.ui.lrFitStatusLabel.setText("Missing covariate column")
          self.ui.GPALogTextbox.insertPlainText(f"[LR] Column '{var}' not found in covariate CSV.\n")
          return
        s = cov_df[var]
        tmpname = f".py_{var}"
        # numeric first
        try:
          s_num = pd.to_numeric(s, errors="raise").to_numpy().astype(float)
          conn.r.__setattr__(tmpname, s_num)
          ok = step(conn, f"set .df${var} (num)", f'.df[["{var}"]] <- base::as.numeric({tmpname})')
        except Exception:
          conn.r.__setattr__(tmpname, s.astype(str).tolist())
          ok = step(conn, f"set .df${var} (factor)",
                    f'.df[["{var}"]] <- base::factor(base::as.character(base::unlist({tmpname})))')
        if not ok:
          self.ui.lrFitStatusLabel.setText("R data error (.df set)")
          return

    # Basic sanity
    if not step(conn, "check nrows",
                'if (base::nrow(.df) != base::nrow(Y)) '
                '  stop(sprintf("Row mismatch: nrow(.df)=%d, nrow(Y)=%d", nrow(.df), nrow(Y)))'):
      self.ui.lrFitStatusLabel.setText("Row mismatch")
      return
    if not step(conn, "check NA",
                'if (any(!stats::complete.cases(.df))) '
                '  stop("Missing values in predictors are not allowed")'):
      self.ui.lrFitStatusLabel.setText("Missing values")
      return

    # ---- Normalize LHS aliases to 'Y' and build formula -----------------------
    import re as _re
    fml = _re.sub(r'^\s*(Coords|Shape|SHAPE|shape)\s*~', 'Y ~', fml_raw.strip())
    try:
      conn.r.__setattr__('fml', fml)
    except Exception as e:
      self.ui.lrFitStatusLabel.setText("R data error (formula)")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] set fml: {repr(e)}\n")
      return

    if not step(conn, "build formula", 'mod <- stats::as.formula(fml)'):
      self.ui.lrFitStatusLabel.setText("Bad formula")
      return
    if not step(conn, "predictor presence",
                'miss <- base::setdiff(all.vars(mod)[-1], base::names(.df)); '
                'if (length(miss)) stop(paste("Predictors missing in .df:", paste(miss, collapse=", ")))'):
      self.ui.lrFitStatusLabel.setText("Predictor mismatch")
      return

    # ---- Fit with RRPP ONLY ---------------------------------------------------
    if not step(conn, "fit procD.lm", 'fit <- RRPP::procD.lm(mod, data=.df)'):
      self.ui.lrFitStatusLabel.setText("Fit failed/crashed")
      self.ui.GPALogTextbox.insertPlainText(
        "[LR] Rserve died while fitting. This almost always indicates a broken compiled package in your R.\n"
        "     Because we avoided 'geomorph', check RRPP and its compiled deps in the R shown above (Rserve R.home).\n"
      )
      return

    # ---- Extract coefficients / names -----------------------------------------
    if not step(conn, "extract",
                'coef_mat <- fit$coefficients; '
                'X <- stats::model.matrix(mod, data=.df); '
                'coef_names <- if (!is.null(base::rownames(coef_mat))) base::rownames(coef_mat) else base::colnames(X)'):
      self.ui.lrFitStatusLabel.setText("Extract error")
      return

    try:
      coef_mat = np.asarray(conn.eval('coef_mat'))
      coef_names = list(conn.eval('as.character(coef_names)'))
    except Exception as e:
      self.ui.lrFitStatusLabel.setText("Pull-back error")
      self.ui.GPALogTextbox.insertPlainText(f"[LR] pull coef: {repr(e)}\n")
      return

    # ---- Cache for downstream use --------------------------------------------
    self._lr_last_fit = {
      "formula": fml,
      "coef_mat": coef_mat,
      "coef_names": coef_names,
      "n_specimens": n,
      "p_landmarks": p,
      "covariates": [(v, ("numeric" if (cov_df is not None and pd.api.types.is_numeric_dtype(cov_df[v])) else "factor"))
                     for v in sorted(base_vars)] if base_vars else [],
      "covariate_path": cov_path
    }
    print(f"[LR] RRPP::procD.lm OK: coef_mat {coef_mat.shape}, terms={len(coef_names)}")
    self.ui.lrFitStatusLabel.setText("Fit complete")

  def _r_try(self, code: str, tag: str = ""):
    """
    Evaluate R 'code' in .GlobalEnv with tryCatch; return (ok: bool, msg: str).
    Keeps objects (.df, Y, etc.) persistent across calls and surfaces useful errors.
    """
    conn = getattr(self, "_r_conn", None)
    if not conn:
      return (False, "No Rserve connection")

    # Pass the code as a variable to avoid quoting issues
    conn.r.__setattr__(".pycode", code)

    # IMPORTANT: evaluate in .GlobalEnv (not a local()) so assignments persist
    res = str(conn.eval(
      'tryCatch({ eval(parse(text=.pycode), envir=.GlobalEnv); "OK" }, '
      '         error=function(e) paste("ERR:", conditionMessage(e)))'
    )).strip()

    if tag and res != "OK":
      try:
        self.ui.GPALogTextbox.insertPlainText(f"[LR] {tag}: {res}\n")
      except Exception:
        pass

    return (res == "OK", res)

  def _r_step(self, conn, tag: str, code: str) -> bool:
    """
    Run a single R statement in .GlobalEnv, logging *where* a crash or error occurs.
    Returns True on success, False on error (including EndOfDataError).
    """
    try:
      conn.r.__setattr__(".pycode", code)
      res = str(conn.eval(
        'tryCatch({ eval(parse(text=.pycode), envir=.GlobalEnv); "OK" }, '
        '         error=function(e) paste("ERR:", conditionMessage(e)))'
      )).strip()
      if res != "OK":
        try:
          self.ui.GPALogTextbox.insertPlainText(f"[LR] {tag}: {res}\n")
        except Exception:
          pass
        return False
      # Also echo success lightly to help pinpoint the last good stage when debugging
      try:
        self.ui.GPALogTextbox.insertPlainText(f"[LR] {tag}: OK\n")
      except Exception:
        pass
      return True
    except Exception as e:
      # This is where EndOfDataError shows up if Rserve died
      try:
        self.ui.GPALogTextbox.insertPlainText(f"[LR] {tag}: PYERR {repr(e)}\n")
      except Exception:
        pass
      try:
        self._safeCloseRConn()
        self._refreshStatusLabels()
      except Exception:
        pass
      return False

  def _r_cli_pkg_selftest(self):
    """
    Run a *safe* package-load test in a separate Rscript process so a bad
    binary can’t crash Rserve. Returns (ok, info_dict).
    info_dict keys: geomorph, RRPP, r_home, libpaths(list), load_ok(dict), raw, returncode, rscript
    """
    rscript = self._r_getRscriptFromUI()
    if not (rscript and os.path.exists(rscript)):
      return (False, {"error": "Rscript not set or not found", "rscript": rscript})

    code = (
      "options(rgl.useNULL=TRUE); Sys.setenv(RGL_USE_NULL='TRUE'); "
      "okG <- FALSE; okR <- FALSE; vG <- ''; vR <- ''; "
      "s <- try(requireNamespace('geomorph', quietly=TRUE), silent=TRUE); "
      "if (isTRUE(s)) { okG <- TRUE; vG <- as.character(packageVersion('geomorph')); } "
      "s <- try(requireNamespace('RRPP', quietly=TRUE), silent=TRUE); "
      "if (isTRUE(s)) { okR <- TRUE; vR <- as.character(packageVersion('RRPP')); } "
      "cat('OK|', R.home('bin'), '|', paste(.libPaths(), collapse=';'), '|', "
      "    vG, '|', vR, '|', okG, '|', okR, sep='')"
    )

    try:
      p = subprocess.run([rscript, "-e", code], capture_output=True, text=True, timeout=60)
      out = ((p.stdout or "") + (p.stderr or "")).strip()

      # Be forgiving: find our marker anywhere in the combined output.
      idx = out.rfind("OK|")
      if idx >= 0:
        tail = out[idx + 3:]
        parts = tail.split("|")
        # OK| <rhome> | <libs> | <geomorph> | <RRPP> | <okG> | <okR>
        rhome = parts[0] if len(parts) > 0 else "?"
        libs = parts[1].split(";") if len(parts) > 1 and parts[1] else []
        vGeom = parts[2] if len(parts) > 2 else ""
        vRRPP = parts[3] if len(parts) > 3 else ""
        okGeom = (parts[4].strip() == "TRUE") if len(parts) > 4 else False
        okRRPP = (parts[5].strip() == "TRUE") if len(parts) > 5 else False
        return (True, {
          "r_home": rhome,
          "libpaths": libs,
          "geomorph": vGeom,
          "RRPP": vRRPP,
          "load_ok": {"geomorph": okGeom, "RRPP": okRRPP},
          "raw": out,
          "returncode": p.returncode,
          "rscript": rscript
        })

      # No marker found — return raw for diagnostics
      return (False, {"raw": out, "returncode": p.returncode, "rscript": rscript})

    except Exception as e:
      return (False, {"error": repr(e), "rscript": rscript})


#
# GPALogic
#

class GPALogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def loadLandmarks(self, filePathList, lmToRemove, extension):
    # initial data array
    lmToRemove = [x - 1 for x in lmToRemove]
    if 'json' in extension:
      import pandas
      tempTable = pandas.DataFrame.from_dict(pandas.read_json(filePathList[0])['markups'][0]['controlPoints'])
      landmarkNumber = len(tempTable)
      landmarkTypeArray=[]
      errorString = ""
      subjectErrorArray = []
      landmarkErrorArray = []
      for i in range(landmarkNumber):
        if tempTable['description'][i] =='Semi':
          landmarkTypeArray.append(str(i+1))
      landmarks=np.zeros(shape=(landmarkNumber-len(lmToRemove),3,len(filePathList)))
      for i in range(len(filePathList)):
        try:
          tmp1=pandas.DataFrame.from_dict(pandas.read_json(filePathList[i])['markups'][0]['controlPoints'])
        except:
          slicer.util.messageBox(f"Error: Load file {filePathList[i]} failed:.")
          logging.debug(f"Error: Load file {filePathList[i]} failed:.")
          self.ui.GPALogTextbox.insertPlainText(f"Error: Load file {filePathList[i]} failed:\n")
        if len(tmp1) == landmarkNumber:
          lmArray = tmp1['position'].to_numpy()
          landmarkIndex = 0
          for j in range(landmarkNumber):
            if j not in lmToRemove:
              if tmp1['positionStatus'][j] == 'defined':
                landmarks[landmarkIndex,:,i]=lmArray[j]
                landmarkIndex += 1
              else:
                subjectFileName = os.path.basename(filePathList[i])
                message = f"{subjectFileName}: Landmark {str(j+1)} \n"
                errorString += message
                if subjectFileName not in subjectErrorArray:
                  subjectErrorArray.append(subjectFileName)
                if j not in landmarkErrorArray:
                  landmarkErrorArray.append(j)
        else:
          warning = f"Error: Load file {filePathList[i]} failed. There are {len(tmp1)} landmarks instead of the expected {landmarkNumber}."
          slicer.util.messageBox(warning)
          return
      if (errorString != "") and not all(x in lmToRemove for x in landmarkErrorArray):
        landmarkErrorArrayString = ', '.join(map(str, [x+1 for x in landmarkErrorArray]))
        subjectErrorArrayString = ', '.join(subjectErrorArray)
        warning = "Error: The following undefined landmarks were found: \n" + errorString +\
                  "To resolve,  exclude the affected landmarks from all subjects using the 'Exclude landmarks' field: " +\
                  landmarkErrorArrayString +"\n" +\
                  "Alternatively,  remove the affected subjects from the landmark file selector: " + \
                  subjectErrorArrayString
        slicer.util.messageBox(warning)
        return
    else:
      landmarks, landmarkTypeArray = self.initDataArray(filePathList)
      landmarkNumber = landmarks.shape[0]
      for i in range(len(filePathList)):
        tmp1=self.importLandMarks(filePathList[i])
        if len(tmp1) == landmarkNumber:
          landmarks[:,:,i] = tmp1
        else:
          warning = f"Error: Load file {filePathList[i]} failed. There are {len(tmp1)} landmarks instead of the expected {landmarkNumber}."
          slicer.util.messageBox(warning)
          return
      landmarks = np.delete(landmarks, lmToRemove, axis=0)
    return landmarks, landmarkTypeArray

  def importLandMarks(self, filePath):
    """Imports the landmarks from file. Does not import sample if a  landmark is -1000
    Adjusts the resolution is log(nhrd) file is found returns kXd array of landmark data. k=# of landmarks d=dimension
    """
    # import data file
    datafile=open(filePath)
    data=[]
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):
        data.append(row.strip().split(','))
    # Make Landmark array
    dataArray=np.zeros(shape=(len(data),3))
    j=0
    sorter=[]
    for i in data:
      tmp=np.array(i)[1:4]
      dataArray[j,0:3]=tmp

      x=np.array(i).shape
      j=j+1
    slicer.app.processEvents()
    return dataArray

  def initDataArray(self, files):
    """
    returns an np array for the storage of the landmarks and an array of landmark types (Fixed, Semi)
    """
    dim=3
    subjectNumber = len(files)
    # import data file
    datafile=open(files[0])
    landmarkType = []
    rowNumber=0
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):
        rowNumber+=1
        tmp=(row.strip().split(','))
        if tmp[12] == 'Semi':
          landmarkType.append(str(rowNumber))
    i = rowNumber
    landmarks=np.zeros(shape=(rowNumber,dim,subjectNumber))
    return landmarks, landmarkType

  def dist(self, a):
    """
    Computes the euclidean distance matrix for nXK points in a 3D space. So the input matrix is nX3xk
    Returns a nXnXk matrix
    """
    id,jd,kd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1,kd))
    dx=fnx(a[:,0,:])
    dy=fnx(a[:,1,:])
    dz=fnx(a[:,2,:])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

  def dist2(self, a):
    """
    Computes the euclidean distance matrix for n points in a 3D space
    Returns a nXn matrix
     """
    id,jd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1))
    dx=fnx(a[:,0])
    dy=fnx(a[:,1])
    dz=fnx(a[:,2])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

  #plotting functions

  def makeScatterPlotWithFactors(self, data, files, factors,title,xAxis,yAxis,pcNumber):
    #create two tables for the first two factors and then check for a third
    #check if there is a table node has been created
    numPoints = len(data)
    uniqueFactors, factorCounts = np.unique(factors, return_counts=True)
    factorNumber = len(uniqueFactors)

    #Set up chart
    plotChartNode=slicer.mrmlScene.GetFirstNodeByName("Chart_PCA_cov" + xAxis + "v" +yAxis)
    if plotChartNode is None:
      plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode", "Chart_PCA_cov" + xAxis + "v" +yAxis)
      GPANodeCollection.AddItem(plotChartNode)
    else:
      plotChartNode.RemoveAllPlotSeriesNodeIDs()

    # Plot all series
    for factorIndex in range(len(uniqueFactors)):
      factor = uniqueFactors[factorIndex]
      tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table Factor ' + factor)
      if tableNode is None:
        tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table Factor ' + factor)
        GPANodeCollection.AddItem(tableNode)
      else:
        tableNode.RemoveAllColumns()    #clear previous data from columns

      # Set up columns for X,Y, and labels
      labels=tableNode.AddColumn()
      labels.SetName('Subject ID')
      tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

      for i in range(pcNumber):
        pc=tableNode.AddColumn()
        colName="PC" + str(i+1)
        pc.SetName(colName)
        tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

      factorCounter=0
      table = tableNode.GetTable()
      table.SetNumberOfRows(factorCounts[factorIndex])
      for i in range(numPoints):
        if (factors[i] == factor):
          table.SetValue(factorCounter, 0,files[i])
          for j in range(pcNumber):
            table.SetValue(factorCounter, j+1, data[i,j])
          factorCounter+=1

      plotSeriesNode=slicer.mrmlScene.GetFirstNodeByName("Series_PCA_" + factor + "_" + xAxis + "v" +yAxis)
      if plotSeriesNode is None:
        plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", factor)
        GPANodeCollection.AddItem(plotSeriesNode)
      # Create data series from table
      plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
      plotSeriesNode.SetXColumnName(xAxis)
      plotSeriesNode.SetYColumnName(yAxis)
      plotSeriesNode.SetLabelColumnName('Subject ID')
      plotSeriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
      plotSeriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
      plotSeriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
      # Set color determined by series index
      seriesColor=[0,0,0,0]
      if(factorIndex<8):
         randomColorTable = slicer.util.getFirstNodeByName('MediumChartColors')
         randomColorTable.GetColor(factorIndex,seriesColor)
      else:
        randomColorTable = slicer.util.getFirstNodeByName('Random')
        randomColorTable.GetColor(factorIndex-7,seriesColor)

      plotSeriesNode.SetColor(seriesColor[0:3])
      # Add data series to chart
      plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())

    # Set up view options for chart
    plotChartNode.SetTitle('PCA Scatter Plot with factors')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)
    layoutManager = slicer.app.layoutManager()

    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

  def makeScatterPlot(self, data, files, title,xAxis,yAxis,pcNumber):
    numPoints = len(data)
    #check if there is a table node has been created
    tableNode=slicer.mrmlScene.GetFirstNodeByName('PCA Scatter Plot Table')
    if tableNode is None:
      tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table')
      GPANodeCollection.AddItem(tableNode)

      #set up columns for X,Y, and labels
      labels=tableNode.AddColumn()
      labels.SetName('Subject ID')
      tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

      for i in range(pcNumber):
        pc=tableNode.AddColumn()
        colName="PC" + str(i+1)
        pc.SetName(colName)
        tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

      table = tableNode.GetTable()
      table.SetNumberOfRows(numPoints)
      for i in range(numPoints):
        table.SetValue(i, 0,files[i])
        for j in range(pcNumber):
            table.SetValue(i, j+1, data[i,j])

    plotSeriesNode1=slicer.mrmlScene.GetFirstNodeByName("Series_PCA" + xAxis + "v" +yAxis)
    if plotSeriesNode1 is None:
      plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Series_PCA" + xAxis + "v" +yAxis)
      GPANodeCollection.AddItem(plotSeriesNode1)

    plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode1.SetXColumnName(xAxis)
    plotSeriesNode1.SetYColumnName(yAxis)
    plotSeriesNode1.SetLabelColumnName('Subject ID')
    plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
    plotSeriesNode1.SetUniqueColor()

    plotChartNode=slicer.mrmlScene.GetFirstNodeByName("Chart_PCA" + xAxis + "v" +yAxis)
    if plotChartNode is None:
      plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode", "Chart_" + xAxis + "v" +yAxis)
      GPANodeCollection.AddItem(plotChartNode)

    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())
    plotChartNode.SetTitle('PCA Scatter Plot ')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)

    layoutManager = slicer.app.layoutManager()

    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

  def lollipopGraph(self, LMObj,LM, pc, scaleFactor, componentNumber, TwoDOption):
    print("lolli scale: ", scaleFactor)
    # set options for 3 vector displays
    if componentNumber == 1:
      color = [1,0,0]
      modelNodeName = 'Lollipop Vector Plot 1'
    elif componentNumber == 2:
      color = [0,1,0]
      modelNodeName = 'Lollipop Vector Plot 2'
    else:
      color = [0,0,1]
      modelNodeName = 'Lollipop Vector Plot 3'

    if pc != 0:
      pc=pc-1 # get current component
      endpoints=self.calcEndpoints(LMObj,LM,pc,scaleFactor)
      i,j=LM.shape

      # declare arrays for polydata
      points = vtk.vtkPoints()
      points.SetNumberOfPoints(i*2)
      lines = vtk.vtkCellArray()
      magnitude = vtk.vtkFloatArray()
      magnitude.SetName('Magnitude');
      magnitude.SetNumberOfComponents(1);
      magnitude.SetNumberOfValues(i);

      for x in range(i): #populate vtkPoints and vtkLines
        points.SetPoint(x,LM[x,:])
        points.SetPoint(x+i,endpoints[x,:])
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0,x)
        line.GetPointIds().SetId(1,x+i)
        lines.InsertNextCell(line)
        magnitude.InsertValue(x,abs(LM[x,0]-endpoints[x,0]) + abs(LM[x,1]-endpoints[x,1]) + abs(LM[x,2]-endpoints[x,2]))

      polydata=vtk.vtkPolyData()
      polydata.SetPoints(points)
      polydata.SetLines(lines)
      polydata.GetCellData().AddArray(magnitude)

      tubeFilter = vtk.vtkTubeFilter()
      tubeFilter.SetInputData(polydata)
      if scaleFactor != 1: #if using scaling for morphospace
        tubeFilter.SetRadius(scaleFactor/500)
      else:
        tubeFilter.SetRadius(scaleFactor/100)
      tubeFilter.SetNumberOfSides(20)
      tubeFilter.CappingOn()
      tubeFilter.Update()

      #check if there is a model node for lollipop plot
      modelNode=slicer.mrmlScene.GetFirstNodeByName(modelNodeName)
      if modelNode is None:
        modelNode = slicer.vtkMRMLModelNode()
        modelNode.SetName(modelNodeName)
        slicer.mrmlScene.AddNode(modelNode)
        GPANodeCollection.AddItem(modelNode)
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1") #name = "View"+ singletonTag
        modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
        GPANodeCollection.AddItem(modelDisplayNode)
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())

      modelDisplayNode = modelNode.GetDisplayNode()

      modelDisplayNode.SetColor(color)
      modelDisplayNode.SetVisibility2D(False)
      modelNode.SetDisplayVisibility(1)
      modelNode.SetAndObservePolyData(tubeFilter.GetOutput())
      if TwoDOption:
        modelDisplayNode.SetSliceDisplayModeToProjection()
        modelDisplayNode.SetVisibility2D(True)
        # Assign node to 2D views
        layoutManager = slicer.app.layoutManager()
        redNode = layoutManager.sliceWidget('Red').sliceView().mrmlSliceNode()
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1")
        modelDisplayNode.SetViewNodeIDs([viewNode1.GetID(),redNode.GetID()])
      else:
        viewNode1 = slicer.mrmlScene.GetFirstNodeByName("View1")
        modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
    else:
      modelNode=slicer.mrmlScene.GetFirstNodeByName(modelNodeName)
      if modelNode is not None:
        modelNode.SetDisplayVisibility(0)

  def calcEndpoints(self,LMObj,LM,pc, scaleFactor):
    i,j=LM.shape
    tmp=np.zeros((i,j))
    tmp[:,0]=LMObj.vec[0:i,pc]
    tmp[:,1]=LMObj.vec[i:2*i,pc]
    tmp[:,2]=LMObj.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3

  def convertFudicialToVTKPoint(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfControlPoints()
    lmData=np.zeros((numberOfLM,3))
    for i in range(numberOfLM):
      loc = fnode.GetNthControlPointPosition(i)
      lmData[i,:]=np.asarray(loc)
    points=vtk.vtkPoints()
    for i in range(numberOfLM):
      points.InsertNextPoint(lmData[i,0], lmData[i,1], lmData[i,2])
    return points

  def convertFudicialToNP(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfControlPoints()
    lmData=np.zeros((numberOfLM,3))

    for i in range(numberOfLM):
      loc = fnode.GetNthControlPointPosition(i)
      lmData[i,:]=np.asarray(loc)
    return lmData

  def convertNumpyToVTK(self, A):
    x,y=A.shape
    points=vtk.vtkPoints()
    for i in range(x):
      points.InsertNextPoint(A[i,0], A[i,1], A[i,2])
    return points

  def convertNumpyToVTKmatrix44(self, A):
    x,y=A.shape
    mat=vtk.vtkMatrix4x4()
    for i in range(x):
      for j in range(y):
        mat.SetElement(i,j,A[i,j])
    return mat

  def convertVTK44toNumpy(self, A):
    a=np.ones((4,4))
    for i in range(4):
      for j in range(4):
        a[i,j]=A.GetElement(i,j)
    return a

  def process(self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """

    if not inputVolume or not outputVolume:
      raise ValueError("Input or output volume is invalid")

    import time
    startTime = time.time()
    logging.info('Processing started')

    # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
    cliParams = {
      'InputVolume': inputVolume.GetID(),
      'OutputVolume': outputVolume.GetID(),
      'ThresholdValue' : imageThreshold,
      'ThresholdType' : 'Above' if invert else 'Below'
      }
    cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
    # We don't need the CLI module node anymore, remove it to not clutter the scene with it
    slicer.mrmlScene.RemoveNode(cliNode)

    stopTime = time.time()
    logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')


class GPATest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_GPA1()

  def test_GPA1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    # Get/create input data
    import SampleData
    registerSampleData()
    inputVolume = SampleData.downloadSample('TemplateKey1')
    self.delayDisplay('Loaded test data set')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 695)

    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    threshold = 100

    # Test the module logic

    logic = GPALogic()

    # Test algorithm with non-inverted threshold
    logic.process(inputVolume, outputVolume, threshold, True)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], threshold)

    # Test algorithm with inverted threshold
    logic.process(inputVolume, outputVolume, threshold, False)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')
