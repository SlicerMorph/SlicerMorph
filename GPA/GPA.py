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


class _PCAPlotMouseFilter(qt.QObject):
  """Qt event filter installed on every child widget of the qMRMLPlotView.
  We install on children because the qMRMLPlotView itself does not receive
  mouse events directly — they reach the inner QVTKOpenGLNativeWidget.
  """

  def __init__(self, owner):
    qt.QObject.__init__(self)
    self._owner = owner

  def eventFilter(self, obj, event):
    owner = self._owner
    if owner is None or not getattr(owner, "_plotDriveActive", False):
      return False
    et = event.type()
    if et == qt.QEvent.MouseButtonPress and event.button() == qt.Qt.LeftButton:
      owner._plotDriveDragging = True
      owner._handleQtMouseEvent(event, obj)
      return True
    if et == qt.QEvent.MouseMove and owner._plotDriveDragging:
      owner._handleQtMouseEvent(event, obj)
      return True
    if et == qt.QEvent.MouseButtonRelease and event.button() == qt.Qt.LeftButton:
      if owner._plotDriveDragging:
        owner._handleQtMouseEvent(event, obj)
        owner._plotDriveDragging = False
        return True
    return False

def _ensure_pyRserve_early() -> bool:
  """
  Ensure pyRserve is importable at module load time.
  - Applies NumPy 2.0 compatibility shim BEFORE importing pyRserve
  - Attempts import; if missing, installs via pip and imports again
  Returns True on success, False otherwise (non-fatal).
  """
  # ---- NumPy 2.x shim (must run before importing pyRserve) -------------------
  try:
    import numpy as _np
    from types import SimpleNamespace as _SS
    if not hasattr(_np, "string_"):  _np.string_ = _np.bytes_
    if not hasattr(_np, "unicode_"): _np.unicode_ = str
    if not hasattr(_np, "int"):      _np.int = int
    if not hasattr(_np, "bool"):     _np.bool = bool
    if not hasattr(_np, "float"):    _np.float = float
    if not hasattr(_np, "object"):   _np.object = object
    if not hasattr(_np, "compat"):
      _np.compat = _SS(long=int)
    elif not hasattr(_np.compat, "long"):
      _np.compat.long = int
  except Exception:
    pass

  # ---- Already imported? -----------------------------------------------------
  try:
    import sys
    if "pyRserve" in sys.modules:
      return True
  except Exception:
    pass

  # ---- Try normal import -----------------------------------------------------
  try:
    import pyRserve  # noqa: F401
    return True
  except Exception:
    pass

  # ---- Install and import ----------------------------------------------------
  progress = None
  try:
    progress = slicer.util.createProgressDialog(
      windowTitle="Installing...",
      labelText="Installing pyRserve...",
      maximum=0,
    )
    slicer.app.processEvents()
    slicer.util.pip_install(["pyRserve"])
    if progress:
      progress.close()
    import pyRserve  # noqa: F401
    return True
  except Exception:
    try:
      if progress:
        progress.close()
    except Exception:
      pass
    # Non-fatal: fitting will still fail gracefully later if Rserve is used without pyRserve.
    return False


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
        <layout type=\"horizontal\" split=\"true\">
         <item splitSize=\"400\">
          <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">
           <property name=\"orientation\" action=\"default\">Axial</property>
           <property name=\"viewlabel\" action=\"default\">R</property>
           <property name=\"viewcolor\" action=\"default\">#F34A33</property>
          </view>
         </item>
           <item splitSize=\"600\">
            <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
             <property name=\"viewlabel\" action=\"default\">1</property>
            </view>
           </item>
         <item splitSize=\"400\">
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
    i, j, k = self.lmOrig.shape
    # Vectorized: sum of squared per-axis deviations across subjects
    diff = self.lmOrig - self.mShape[:, :, None]
    varianceMat = np.sum(diff * diff, axis=2)
    # if GPA scaling has been skipped, don't apply image size scaling factor
    if(BoasOption):
      varianceMat = np.sqrt(varianceMat/(k-1))
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
    # SVD-based PCA on the centered (D x N) data matrix.
    # Avoids forming the D x D covariance entirely.
    # Eigenvectors of cov(X) == left singular vectors U;
    # eigenvalues of cov(X) == S**2 / N (matches original calcCov / N convention).
    i, j, k = self.lmOrig.shape
    twoDim = gpa_lib.makeTwoDim(self.lm)  # shape (D, N), already centered across subjects
    U, S, _ = np.linalg.svd(twoDim, full_matrices=False)
    self.val = (S * S) / float(k)
    self.vec = U
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

  def onReload(self):
    """Reload Support submodules before reloading the main module so that
    edits in Support/*.py take effect on 'Reload'."""
    # Tear down session state first so reloads don't accumulate event
    # filters, observers, or scene nodes (each accumulation has been
    # observed to cause repaint storms and 3D background hue flicker).
    try:
      self._gpaTeardown()
    except Exception as e:
      print(f"[GPA] teardown warning: {e}")
    import importlib, sys
    for name in list(sys.modules):
      if name == "Support" or name.startswith("Support."):
        try:
          importlib.reload(sys.modules[name])
        except Exception as e:
          print(f"[GPA] Could not reload {name}: {e}")
    ScriptedLoadableModuleWidget.onReload(self)

  def cleanup(self):
    """Called by Slicer when the module is unloaded (and on Reload)."""
    try:
      self._gpaTeardown()
    except Exception as e:
      print(f"[GPA] cleanup warning: {e}")
    try:
      ScriptedLoadableModuleWidget.cleanup(self)
    except Exception:
      pass

  def _gpaTeardown(self):
    """Idempotent teardown of all session-scoped state that survives Reload
    if not explicitly torn down (Qt event filters, mouse-tracking flags on
    plot view children, MRML observers, and engine-owned transform nodes)."""
    # Plot-drive event filter + mouseTracking on plot view children.
    try:
      if getattr(self, "_plotDriveFilteredWidgets", None):
        self._detachPlotMouseFilter()
    except Exception as e:
      print(f"[GPA teardown] plot mouse filter: {e}")
    # Remove the persistent status-bar PCA cursor label so reloads do not
    # leave stale widgets in Slicer's main status bar.
    try:
      self._removeStatusBarPCALabel()
    except Exception as e:
      print(f"[GPA teardown] status-bar label: {e}")
    # Reset mouseTracking on any plot view child we may have touched, even
    # if the filter list got out of sync (e.g. from a previous reload).
    try:
      pv = self._plotView() if hasattr(self, "_plotView") else None
      if pv is not None:
        try: pv.setMouseTracking(False)
        except Exception: pass
        for child in pv.findChildren(qt.QWidget):
          try: child.setMouseTracking(False)
          except Exception: pass
    except Exception:
      pass
    # LR controller: dispose the warp engine + drop the LR transform node
    # it owned, so the next instance does not contend with a stale node.
    try:
      lr = getattr(self, "lr", None) or getattr(self, "geomorphLR", None)
      if lr is not None:
        eng = getattr(lr, "_warp_engine", None)
        if eng is not None:
          try: eng.dispose()
          except Exception as e: print(f"[GPA teardown] engine.dispose: {e}")
          lr._warp_engine = None
    except Exception as e:
      print(f"[GPA teardown] LR engine: {e}")

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Initialize zoom factor for widget
    self.widgetZoomFactor = 0

    # Import pandas if needed (unchanged)
    try:
      import pandas  # noqa: F401
    except Exception:
      progressDialog = slicer.util.createProgressDialog(
        windowTitle="Installing...",
        labelText="Installing Pandas Python package...",
        maximum=0,
      )
      slicer.app.processEvents()
      try:
        slicer.util.pip_install(["pandas"])
        progressDialog.close()
      except Exception:
        slicer.util.infoDisplay("Issue while installing Pandas Python package. Please install manually.")
        progressDialog.close()

    # ---- Assemble split UI tabs into one QTabWidget ----
    tab = qt.QTabWidget()
    tab.setObjectName("tabWidget")  # keep old name for compatibility

    tabs = [
      ("Setup Analysis", "UI/GPA_SetupAnalysis.ui"),
      ("Results", "UI/GPA_ExploreDataResults.ui"),
      ("Interactive 3D", "UI/GPA_Interactive3D.ui"),
      ("Geomorph Linear Regression", "UI/GPA_GeomorphLR.ui"),
    ]

    for title, relpath in tabs:
      w = slicer.util.loadUI(self.resourcePath(relpath))
      tab.addTab(w, title)

    self.layout.addWidget(tab)
    # Collect all named children across tabs into self.ui (unchanged usage elsewhere)
    self.ui = slicer.util.childWidgetVariables(tab)

    # ---- LAZY LR INIT: do NOT import patsy or pyRserve here ----
    # We lazily attach the LR controller when the LR tab is first selected.
    self._tabWidget = tab
    self._lr_tab_index = None
    try:
      total = int(tab.count)
    except Exception:
      try:
        total = int(tab.count())
      except Exception:
        total = 0
    for i in range(total):
      try:
        w = tab.widget(i)
        if getattr(w, "objectName", None) == "geomorphLRTab":
          self._lr_tab_index = i
          break
      except Exception:
        pass

    # Connect tab change -> lazy LR initialization
    try:
      tab.currentChanged.connect(self._onTabChanged)
    except Exception:
      # PyQt4-style fallback
      tab.connect('currentChanged(int)', self._onTabChanged)

    # Gate non-Setup tabs until a GPA analysis is run / loaded. Setup
    # Analysis (index 0) is always enabled; Explore, Interactive 3D, and
    # LR depend on having self.LM and self.scatterDataAll populated.
    self._setAnalysisTabsEnabled(False)

    # If LR tab is already selected (unlikely), initialize immediately
    try:
      if self._lr_tab_index is not None and int(tab.currentIndex) == int(self._lr_tab_index):
        self._lazyInitLR()
    except Exception:
      pass

    # ---- Custom layout buttons (unchanged) ----
    self.addLayoutButton(500, 'GPA Module View', 'Custom layout for GPA module', 'LayoutSlicerMorphView.png',
                         slicer.customLayoutSM)
    self.addLayoutButton(501, 'Table Only View', 'Custom layout for GPA module', 'LayoutTableOnlyView.png',
                         slicer.customLayoutTableOnly)
    self.addLayoutButton(502, 'Plot Only View', 'Custom layout for GPA module', 'LayoutPlotOnlyView.png',
                         slicer.customLayoutPlotOnly)

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
    # Warp-source toggle (PCA vs Geomorph LR). The two radio buttons have
    # `autoExclusive=false` (set in the .ui) so they don't get pulled into
    # the same exclusive group as the mean-vs-model radios above. We manage
    # mutual exclusivity manually here.
    try:
      self.ui.warpModePCA.toggled.connect(
        lambda checked: self._setWarpMode("pca") if checked else None)
      self.ui.warpModeLR.toggled.connect(
        lambda checked: self._setWarpMode("lr") if checked else None)
    except Exception:
      pass
    self.ui.startRecordButton.connect('clicked(bool)', self.onStartRecording)
    self.ui.stopRecordButton.connect('clicked(bool)', self.onStopRecording)
    self.ui.resetButton.connect('clicked(bool)', self.reset)
    self.ui.updateMagnificationButton.connect("clicked()", self.onUpdateMagnificationClicked)
    # Plot-driven model warping (2D): toggled by user, takes X/Y PC from Explore tab.
    self.ui.drivePCAPlotCheckBox.connect('toggled(bool)', self.onTogglePlotDriving)
    self.PCList = []

    # PCA slider controller (unchanged)
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

    # Wrap PC-selection comboboxes with QSpinBox + variance QLabel.
    # The original combobox is hidden but kept alive so all existing
    # handlers (currentIndexChanged, currentIndex reads) keep working;
    # the spinbox writes through to combobox.setCurrentIndex().
    self._pcVariancePercent = []      # list[float], populated in updateList()
    self._pcSpinWidgets = {}          # combobox name -> {"spin": QSpinBox, "label": QLabel}
    self._wrapComboWithSpinBox(self.ui.pcComboBox,    allow_none=True,
                               prefix_text="Slider warps:")   # Interactive 3D
    self._wrapComboWithSpinBox(self.ui.XcomboBox,     allow_none=False)  # Results X
    self._wrapComboWithSpinBox(self.ui.YcomboBox,     allow_none=False)  # Results Y
    self._wrapComboWithSpinBox(self.ui.vectorOne,     allow_none=True)   # Lollipop 1
    self._wrapComboWithSpinBox(self.ui.vectorTwo,     allow_none=True)   # Lollipop 2
    self._wrapComboWithSpinBox(self.ui.vectorThree,   allow_none=True)   # Lollipop 3

    # Force tight vertical spacing on the Results-tab grids. The .ui file
    # sets verticalSpacing=2 but PythonQt's QUiLoader does not always honor
    # the property tag for QGridLayout, so we apply it explicitly here.
    # Layouts aren't exposed via childWidgetVariables, so we walk the widget
    # tree from the parent frame and pull the layout off each frame widget.
    for frame_name in ("plotFrame", "lolliFrame", "meanShapeFrame", "distributionFrame"):
      try:
        frame = getattr(self.ui, frame_name, None)
        if frame is None:
          continue
        grid = frame.layout()
        if grid is None:
          continue
        try: grid.setVerticalSpacing(2)
        except Exception: pass
        try: grid.setHorizontalSpacing(6)
        except Exception: pass
        try: grid.setContentsMargins(4, 2, 4, 2)
        except Exception: pass
        try:
          for r in range(int(grid.rowCount())):
            grid.setRowMinimumHeight(r, 0)
            grid.setRowStretch(r, 0)
        except Exception:
          pass
      except Exception:
        pass

    # Inject Drive-3D X/Y PC selector row right under the status label.
    self._injectDrivePlotPCRow()

    # Core state defaults (unchanged)
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
    # Active warp source for the shared Interactive-Visualization clones
    # (cloneLandmarkNode + cloneModelNode). "pca" parents them under
    # gridTransformNode; "lr" parents them under LRTPS_Transform.
    self.activeWarpMode = "pca"
    self._gridCache = {}
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
    # ---- Plot-driving (2-PC drag) state ----
    self._plotDriveActive = False
    self._plotDriveDragging = False
    self._plotDriveFilter = None
    self._plotDriveFilteredWidgets = []   # list of QWidget we installed on
    self._plotDrivePCs = (None, None)  # (xPC, yPC) currently bound to gridX, gridY
    self._plotDriveCursorSeries = None
    self._plotDriveCursorTable = None
    self._plotDriveDispCache = {}      # {(pc_index, magnification): np.ndarray (D,D,D,3)}
    self._plotDriveFusedImage = None   # vtkImageData reused across updates
    self._plotDriveFusedArray = None   # numpy view (flat) into the displacement scalars

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

  # ------------------------------------------------------------------
  # PC selection: spinbox + variance-label wrapper around each combobox
  # ------------------------------------------------------------------
  def _wrapComboWithSpinBox(self, combo, allow_none: bool, prefix_text: str = ""):
    """Hide `combo` and inject a QSpinBox + variance QLabel in its place.
    The spinbox writes through to combo.setCurrentIndex() so all existing
    handlers and reads continue to work unchanged.

    allow_none=True : spinbox 0..N where 0 maps to combo index 0 ('None')
                      and label shows '(none)' at 0.
    allow_none=False: spinbox 1..N where 1 maps to combo index 0
                      (i.e. PC1 is the first item in the combo).
    """
    parent = combo.parentWidget() if hasattr(combo, "parentWidget") else combo.parent()
    layout = parent.layout() if parent is not None else None
    if layout is None:
      return  # Cannot wrap — leave combo visible as-is.

    # The combobox may live inside a nested sub-layout (e.g. a QHBoxLayout
    # placed directly into a grid cell with no intermediate QWidget). Find
    # the actual layout that contains the combobox.
    def _find_owning_layout(root_layout, target):
      try:
        if root_layout.indexOf(target) >= 0:
          return root_layout
      except Exception:
        pass
      try:
        n = root_layout.count()
      except Exception:
        n = 0
      for i in range(n):
        try:
          item = root_layout.itemAt(i)
          if item is None:
            continue
          sub = item.layout()
          if sub is not None:
            found = _find_owning_layout(sub, target)
            if found is not None:
              return found
        except Exception:
          continue
      return None

    owning = _find_owning_layout(layout, combo)
    if owning is not None:
      layout = owning

    # Build the replacement: [QSpinBox][QLabel] inside a container widget.
    container = qt.QWidget(parent)
    h = qt.QHBoxLayout(container)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    try:
      container.setSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.Fixed)
    except Exception:
      pass
    spin = qt.QSpinBox(container)
    spin.setMinimum(0 if allow_none else 1)
    spin.setMaximum(1)  # placeholder; updated by _refreshPCSpinBoxes()
    if allow_none:
      spin.setSpecialValueText("None")
    spin.setFixedWidth(70)
    label = qt.QLabel("(no analysis)", container)
    label.setStyleSheet("color: gray;")
    if prefix_text:
      prefix = qt.QLabel(prefix_text, container)
      h.addWidget(prefix)
    h.addWidget(spin)
    h.addWidget(label, 1)

    # Insert container into the same slot the combobox occupies.
    # PythonQt's `isinstance(layout, qt.QGridLayout)` and `getItemPosition`
    # are unreliable. Use itemAtPosition() iteration for grids, which works.
    inserted = False

    # Try QGridLayout via row/col iteration
    if not inserted and hasattr(layout, "itemAtPosition") and hasattr(layout, "rowCount"):
      try:
        rc = int(layout.rowCount())
        cc = int(layout.columnCount())
        target_rc = None
        for r in range(rc):
          for c in range(cc):
            it = layout.itemAtPosition(r, c)
            if it is not None and it.widget() is combo:
              target_rc = (r, c)
              break
          if target_rc:
            break
        if target_rc is not None:
          r, c = target_rc
          # Span enough columns to consume the wasted space to the right.
          # Original combos use colspan=3 so we mirror that.
          try:
            layout.removeWidget(combo)
          except Exception:
            pass
          combo.setParent(parent)
          layout.addWidget(container, r, c, 1, 3)
          inserted = True
      except Exception:
        pass

    # Try QFormLayout
    if not inserted and hasattr(layout, "getWidgetPosition"):
      try:
        row, role = layout.getWidgetPosition(combo)
        if row >= 0:
          layout.setWidget(row, role, container)
          inserted = True
      except Exception:
        pass

    # Try QBoxLayout
    if not inserted and hasattr(layout, "insertWidget"):
      try:
        idx = layout.indexOf(combo)
        if idx >= 0:
          layout.removeWidget(combo)
          layout.insertWidget(idx, container)
          combo.setParent(parent)
          inserted = True
      except Exception:
        pass

    if not inserted:
      try:
        layout.addWidget(container)
      except Exception:
        pass
    combo.setVisible(False)

    # Wire spinbox -> combobox (mapped). When None is selected (allow_none
    # only), set combo index 0; else set combo index = spin.value - 1.
    offset = 0 if allow_none else 1
    def _on_spin_changed(v, _combo=combo, _label=label, _allow=allow_none, _off=offset):
      try:
        target_idx = (int(v) - _off) if not _allow else (0 if int(v) == 0 else int(v))
      except Exception:
        return
      try:
        if int(_combo.currentIndex) != target_idx:
          _combo.setCurrentIndex(target_idx)
      except Exception:
        try:
          _combo.setCurrentIndex(target_idx)
        except Exception:
          pass
      self._updatePCVarianceLabel(_label, int(v), _allow)
    spin.valueChanged.connect(_on_spin_changed)

    self._pcSpinWidgets[combo.objectName] = {
      "spin": spin, "label": label, "combo": combo, "allow_none": allow_none,
    }

  def _updatePCVarianceLabel(self, label, spin_value: int, allow_none: bool):
    pcs = getattr(self, "_pcVariancePercent", []) or []
    if not pcs:
      label.setText("(no analysis)")
      label.setStyleSheet("color: gray;")
      return
    if allow_none and spin_value == 0:
      label.setText("(none)")
      label.setStyleSheet("color: gray;")
      return
    pc_index_1based = spin_value if allow_none else spin_value
    if pc_index_1based < 1 or pc_index_1based > len(pcs):
      label.setText("")
      return
    pct = pcs[pc_index_1based - 1]
    label.setText(f"PC {pc_index_1based} \u2014 {pct:.2f}% var")
    label.setStyleSheet("")

  def _refreshPCSpinBoxes(self):
    """Update spinbox max + label after a new analysis populates _pcVariancePercent."""
    n = len(getattr(self, "_pcVariancePercent", []) or [])
    if n <= 0:
      return
    for name, w in (getattr(self, "_pcSpinWidgets", {}) or {}).items():
      spin = w["spin"]; label = w["label"]; allow = w["allow_none"]
      spin.blockSignals(True)
      try:
        spin.setMaximum(n if allow else n)
        # Ensure value is in range; preserve current value if possible.
        v = int(spin.value)
        if allow:
          if v < 0: v = 0
          if v > n: v = n
        else:
          if v < 1: v = 1
          if v > n: v = n
        spin.setValue(v)
      finally:
        spin.blockSignals(False)
      self._updatePCVarianceLabel(label, int(spin.value), allow)
    # Also update Drive-3D X/Y spinbox ranges + labels.
    if hasattr(self, "_driveSpinX") and self._driveSpinX is not None:
      for spin, lbl, default_v in (
        (self._driveSpinX, self._driveLabelX, 1),
        (self._driveSpinY, self._driveLabelY, 2),
      ):
        spin.blockSignals(True)
        try:
          spin.setMaximum(n)
          v = int(spin.value)
          if v < 1: v = default_v
          if v > n: v = n
          spin.setValue(v)
        finally:
          spin.blockSignals(False)
        pcs = getattr(self, "_pcVariancePercent", []) or []
        if pcs and 1 <= int(spin.value) <= len(pcs):
          lbl.setText(f"PC {int(spin.value)} \u2014 {pcs[int(spin.value)-1]:.2f}% var")
          lbl.setStyleSheet("")

  # ------------------------------------------------------------------
  # Drive 3D: X/Y PC selector row injected on Interactive 3D tab
  # ------------------------------------------------------------------
  def _injectDrivePlotPCRow(self):
    """Add 'X: [..] PC.. var   Y: [..] PC.. var' under the Status label so
    the user can change Drive-3D PC pair without leaving the tab."""
    status = getattr(self.ui, "drivePCAPlotStatus", None)
    if status is None:
      return
    parent = status.parentWidget()
    if parent is None:
      return
    layout = parent.layout()
    if layout is None or not hasattr(layout, "itemAtPosition"):
      return
    # Find row of status label.
    target_row = None
    try:
      rc = int(layout.rowCount()); cc = int(layout.columnCount())
      for r in range(rc):
        for c in range(cc):
          it = layout.itemAtPosition(r, c)
          if it is not None and it.widget() is status:
            target_row = r; break
        if target_row is not None: break
    except Exception:
      return
    if target_row is None:
      return

    # Build container row.
    container = qt.QWidget(parent)
    h = qt.QHBoxLayout(container)
    h.setContentsMargins(0, 4, 0, 0)
    h.setSpacing(6)

    self._driveSpinX = qt.QSpinBox(container)
    self._driveSpinX.setMinimum(1); self._driveSpinX.setMaximum(1); self._driveSpinX.setFixedWidth(70)
    self._driveLabelX = qt.QLabel("(no analysis)", container)
    self._driveLabelX.setStyleSheet("color: gray;")
    h.addWidget(qt.QLabel("X:", container))
    h.addWidget(self._driveSpinX)
    h.addWidget(self._driveLabelX, 1)

    self._driveSpinY = qt.QSpinBox(container)
    self._driveSpinY.setMinimum(1); self._driveSpinY.setMaximum(1); self._driveSpinY.setFixedWidth(70)
    self._driveLabelY = qt.QLabel("(no analysis)", container)
    self._driveLabelY.setStyleSheet("color: gray;")
    h.addWidget(qt.QLabel("Y:", container))
    h.addWidget(self._driveSpinY)
    h.addWidget(self._driveLabelY, 1)

    # Insert below the status label.
    new_row = target_row + 1
    # Push subsequent rows down by re-adding (Qt grids can have empty rows).
    layout.addWidget(container, new_row, 0, 1, 3)

    # Wire: spinbox change -> update Results combo (single source of truth) +
    # reset to mean shape + (only if toggle is ON) replot + rebind.
    self._driveSpinX.valueChanged.connect(lambda v: self._onDrivePCChanged("X", int(v)))
    self._driveSpinY.valueChanged.connect(lambda v: self._onDrivePCChanged("Y", int(v)))

    # Mirror the other direction: when the user changes XcomboBox/YcomboBox
    # on the Results tab, sync these spinboxes back.
    try:
      self.ui.XcomboBox.currentIndexChanged.connect(lambda _i: self._syncDriveSpinsFromCombos())
      self.ui.YcomboBox.currentIndexChanged.connect(lambda _i: self._syncDriveSpinsFromCombos())
    except Exception:
      pass

  def _onDrivePCChanged(self, axis: str, value: int):
    """Spinbox changed: write through to Results combobox, reset to mean,
    and (if Drive-3D is currently ON) trigger a replot + rebind."""
    combo = self.ui.XcomboBox if axis == "X" else self.ui.YcomboBox
    target_idx = max(0, value - 1)
    try:
      if int(combo.currentIndex) != target_idx:
        combo.setCurrentIndex(target_idx)  # also updates the Results spinbox via its own wiring
    except Exception:
      try: combo.setCurrentIndex(target_idx)
      except Exception: pass
    # Update variance label for this drive spinbox.
    pcs = getattr(self, "_pcVariancePercent", []) or []
    if pcs and 1 <= value <= len(pcs):
      lbl = self._driveLabelX if axis == "X" else self._driveLabelY
      lbl.setText(f"PC {value} \u2014 {pcs[value-1]:.2f}% var")
      lbl.setStyleSheet("")
    # Always reset visualization to mean shape so user starts clean.
    self._resetDrivePlotToMean()
    # Only rebuild the chart + rebind if the toggle is ON. Otherwise the
    # change is just a future-intent setting.
    if getattr(self, "_plotDriveActive", False):
      try:
        self.plot()  # rebuilds chart from XcomboBox/YcomboBox + factor
      except Exception:
        pass
      try:
        self._refreshPlotDriving(forceLog=True)
      except Exception:
        pass

  def _syncDriveSpinsFromCombos(self):
    """Mirror XcomboBox/YcomboBox -> drive spinboxes (no recursion: spinbox
    setValue is signal-blocked)."""
    if not hasattr(self, "_driveSpinX") or self._driveSpinX is None:
      return
    try:
      x_val = int(self.ui.XcomboBox.currentIndex) + 1
      y_val = int(self.ui.YcomboBox.currentIndex) + 1
    except Exception:
      return
    for spin, val, lbl in (
      (self._driveSpinX, x_val, self._driveLabelX),
      (self._driveSpinY, y_val, self._driveLabelY),
    ):
      if val < spin.minimum or val > spin.maximum:
        continue
      if int(spin.value) == val:
        continue
      spin.blockSignals(True)
      try: spin.setValue(val)
      finally: spin.blockSignals(False)
      pcs = getattr(self, "_pcVariancePercent", []) or []
      if pcs and 1 <= val <= len(pcs):
        lbl.setText(f"PC {val} \u2014 {pcs[val-1]:.2f}% var")
        lbl.setStyleSheet("")

  def _resetDrivePlotToMean(self):
    """Reset Drive-3D visualization to the mean shape (zero displacement)."""
    # Engine path / fused-array path:
    if getattr(self, "_plotDriveFusedArray", None) is not None:
      try:
        self._applyPlotScores(0.0, 0.0)
      except Exception:
        pass
    try:
      self._updatePCACursor(0.0, 0.0)
    except Exception:
      pass

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
    # Populate with ALL PCs (combos are hidden; spinboxes drive selection).
    self.pcNumber = int(len(percentVar))
    self._pcVariancePercent = [float(v) * 100.0 for v in percentVar]
    for x in range(self.pcNumber):
      tmp=f"{percentVar[x]*100:.1f}"
      string='PC '+str(x+1)+': '+str(tmp)+"%" +" var"
      self.PCList.append(string)
      self.ui.XcomboBox.addItem(string)
      self.ui.YcomboBox.addItem(string)
      self.ui.vectorOne.addItem(string)
      self.ui.vectorTwo.addItem(string)
      self.ui.vectorThree.addItem(string)
    # Refresh spinbox ranges and variance labels.
    self._refreshPCSpinBoxes()

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
    self.ui.grayscaleSelectorLabel.enabled = False
    self.ui.FudSelectLabel.enabled = False
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
    self._gridCache = {}
    self.gridTransformNode = None
    # Plot-drive cleanup
    try:
      if getattr(self, "ui", None) and hasattr(self.ui, "drivePCAPlotCheckBox"):
        self.ui.drivePCAPlotCheckBox.setChecked(False)
    except Exception:
      pass
    self._detachPlotMouseFilter()
    self._plotDriveActive = False
    self._plotDriveDragging = False
    self._plotDriveDispCache = {}
    self._plotDriveFusedImage = None
    self._plotDriveFusedArray = None
    self._plotDriveCursorSeries = None
    self._plotDriveCursorTable = None
    self._plotDrivePCs = (None, None)
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
    # Reserve index 0 of the factor selector for "no factor" so that the
    # first real covariate is at index 1 (the plot path checks currentIndex > 0).
    self.ui.selectFactor.clear()
    self.ui.selectFactor.addItem("")
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
        value = self.factorTableNode.GetTable().GetValue(j,i)
        if GPALogic.isNumericValue(value.ToString()):
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

    if hasattr(self, "lr"):
      self.lr.refreshFromCovariates()
      self.lr.refreshFitButton()

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
        value = self.factorTableNode.GetTable().GetValue(r, c)
        if GPALogic.isNumericValue(value.ToString()):
          has_numeric = True
          break
      if not has_numeric and name:
        self.ui.selectFactor.addItem(name)

    self.ui.GPALogTextbox.insertPlainText("Covariate table loaded for results session\n")

    if hasattr(self, "lr"):
      self.lr.refreshFromCovariates()
      self.lr.refreshFitButton()

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
    # Perf: see onLoad() for rationale. Wrap in StartModify/EndModify so we
    # don't trigger N synchronous renders during point creation.
    _wasMod = self.meanLandmarkNode.StartModify()
    try:
      for landmarkNumber in range (shape[0]):
        name = str(landmarkNumber+1) #start numbering at 1
        self.meanLandmarkNode.AddControlPoint(self.rawMeanLandmarks[landmarkNumber,:], name)
    finally:
      self.meanLandmarkNode.EndModify(_wasMod)
    self.meanLandmarkNode.SetDisplayVisibility(1)
    self.meanLandmarkNode.LockedOn() #lock position so when displayed they cannot be moved
    _showLabelsByDefault = (shape[0] <= 200)
    self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(1 if _showLabelsByDefault else 0)
    self.meanLandmarkNode.GetDisplayNode().SetTextScale(3)
    # On dense LM datasets the default glyph size of 3 is visually noisy and
    # eats fill rate. Drop to 1 when N>200; user can re-scale via the slider.
    if shape[0] > 200:
      try: self.ui.scaleMeanShapeSlider.value = 1
      except Exception: pass
    #initialize mean LM display
    self.scaleMeanGlyph()
    self.toggleMeanColor()
    # Set up cloned mean landmark node for pc warping
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.meanLandmarkNode)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.copyLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    GPANodeCollection.AddItem(self.copyLandmarkNode)
    self.copyLandmarkNode.SetName('Warped Landmarks')
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

    if hasattr(self, "lr"):
      self.lr.refreshFromCovariates()
      self.lr.refreshFitButton()

    self._setAnalysisTabsEnabled(True)

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
    # Perf: at high N, per-control-point Modified events trigger N renders
    # which can take seconds per render once labels are enabled. Wrap the
    # population loop in a single Modify block so the scene is rendered
    # exactly once after all points are added.
    _wasMod = self.meanLandmarkNode.StartModify()
    try:
      for landmarkNumber in range(shape[0]):
        name = str(landmarkNumber+1) #start numbering at 1
        self.meanLandmarkNode.AddControlPoint(vtk.vtkVector3d(self.rawMeanLandmarks[landmarkNumber,:]), name)
    finally:
      self.meanLandmarkNode.EndModify(_wasMod)
    self.meanLandmarkNode.SetDisplayVisibility(1)
    # Perf: per-point label rendering scales linearly with N (each text
    # actor re-rasterizes on every render). At N=1440 this drops the 3D
    # interactive frame rate from ~380fps to ~14fps. Default labels OFF
    # for high-N datasets; the user can re-enable via the "Show mean
    # landmark labels" button.
    _showLabelsByDefault = (shape[0] <= 200)
    self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(1 if _showLabelsByDefault else 0)
    self.meanLandmarkNode.GetDisplayNode().SetTextScale(3)
    # On dense LM datasets the default glyph size of 3 is visually noisy and
    # eats fill rate. Drop to 1 when N>200; user can re-scale via the slider.
    if shape[0] > 200:
      try: self.ui.scaleMeanShapeSlider.value = 1
      except Exception: pass
    if not _showLabelsByDefault:
      msg = (f"Note: point labels are off by default for {shape[0]} landmarks "
             f"(>200) to keep the 3D viewer responsive. Use the 'Show mean "
             f"landmark labels' button to toggle.\n")
      try: self.ui.GPALogTextbox.insertPlainText(msg)
      except Exception: pass
      print(msg, end="")
    self.meanLandmarkNode.LockedOn() #lock position so when displayed they cannot be moved

    # Set up cloned mean landmark node for pc warping
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.meanLandmarkNode)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.copyLandmarkNode = shNode.GetItemDataNode(clonedItemID)
    GPANodeCollection.AddItem(self.copyLandmarkNode)
    self.copyLandmarkNode.SetName('Warped Landmarks')
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

    if hasattr(self, "lr"):
      self.lr.refreshFromCovariates()
      self.lr.refreshFitButton()

    self._setAnalysisTabsEnabled(True)

  def initializeOnLoad(self):
    # clear rest of module when starting GPA analysis

    self._setAnalysisTabsEnabled(False)

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
    # Magnification changed: invalidate cached grids since they were built at the previous magnification.
    self._gridCache = {}
    self._plotDriveDispCache = {}
    self._plotDriveFusedImage = None
    self._plotDriveFusedArray = None
    self.setupPCTransform()
    if getattr(self, "_plotDriveActive", False):
      self._refreshPlotDriving()

  def _setWarpMode(self, mode):
    """Switch the active warp source for the shared Interactive-Visualization
    clones (cloneLandmarkNode + cloneModelNode). Reparents them under either
    `self.gridTransformNode` (PCA) or the LR module's `LRTPS_Transform`
    (Geomorph LR). Updates the radio-button UI signal-blocked."""
    mode = "lr" if str(mode).lower() == "lr" else "pca"
    self.activeWarpMode = mode

    # Pick parent transform.
    if mode == "pca":
      tnode = getattr(self, "gridTransformNode", None)
    else:
      lr = getattr(self, "lr", None)
      tnode = getattr(lr, "lrTPSTransformNode", None) if lr else None
      # Fall back to scene lookup by name (LR module instance may not be cached on widget).
      if tnode is None or not slicer.mrmlScene.IsNodePresent(tnode):
        tnode = slicer.mrmlScene.GetFirstNodeByName("LRTPS_Transform")

    tid = tnode.GetID() if (tnode is not None and slicer.mrmlScene.IsNodePresent(tnode)) else None

    lm = getattr(self, "cloneLandmarkNode", None) or getattr(self, "copyLandmarkNode", None)
    if lm is not None and slicer.mrmlScene.IsNodePresent(lm):
      try: lm.SetAndObserveTransformNodeID(tid)
      except Exception: pass

    try: modelChecked = bool(self.ui.modelVisualizationType.isChecked())
    except Exception: modelChecked = False
    cm = getattr(self, "cloneModelNode", None)
    if modelChecked and cm is not None and slicer.mrmlScene.IsNodePresent(cm):
      try: cm.SetAndObserveTransformNodeID(tid)
      except Exception: pass

    # Recolor the warped landmark glyphs to make the active source obvious.
    #   PCA  -> dark red    (rgb 0.55, 0.05, 0.05)
    #   LR   -> light pink  (rgb 1.00, 0.71, 0.76)
    if mode == "pca":
      glyph_rgb = (0.55, 0.05, 0.05)
      model_rgb = (0x7f / 255.0, 0xf4 / 255.0, 0xfd / 255.0)  # light blue (default)
    else:
      glyph_rgb = (1.00, 0.71, 0.76)
      model_rgb = (0.78, 0.65, 0.95)                          # light purple / lavender
    if lm is not None and slicer.mrmlScene.IsNodePresent(lm):
      try:
        d = lm.GetDisplayNode()
        if d is not None:
          try: d.SetSelectedColor(glyph_rgb)
          except Exception: pass
          try: d.SetColor(glyph_rgb)
          except Exception: pass
      except Exception:
        pass

    # Recolor the warped model surface so it pairs visually with the glyphs.
    cmd = getattr(self, "cloneModelDisplayNode", None)
    if cmd is None and cm is not None and slicer.mrmlScene.IsNodePresent(cm):
      try: cmd = cm.GetDisplayNode()
      except Exception: cmd = None
    if cmd is not None:
      try: cmd.SetColor(*model_rgb)
      except Exception: pass

    # Reflect in the radio buttons without re-emitting toggled signals.
    try:
      pca_btn = self.ui.warpModePCA
      lr_btn = self.ui.warpModeLR
      pca_was = pca_btn.blockSignals(True)
      lr_was = lr_btn.blockSignals(True)
      try:
        pca_btn.setChecked(mode == "pca")
        lr_btn.setChecked(mode == "lr")
      finally:
        pca_btn.blockSignals(pca_was)
        lr_btn.blockSignals(lr_was)
    except Exception:
      pass

    # Enable / disable the inactive driver's interactive widgets so the user
    # can't accidentally drive the wrong source. Radio buttons stay enabled
    # (so the user can switch back).
    pca_active = (mode == "pca")
    for name in ("pcSlider", "pcSpinBox", "pcComboBox"):
      try:
        w = getattr(self.ui, name, None)
        if w is not None:
          w.setEnabled(pca_active)
      except Exception:
        pass
    # The PC combobox is hidden behind a wrapper QSpinBox+label; disable that too.
    try:
      wrap = (self._pcSpinWidgets or {}).get("pcComboBox")
      if wrap:
        for k in ("spin", "label"):
          w = wrap.get(k)
          if w is not None:
            try: w.setEnabled(pca_active)
            except Exception: pass
    except Exception:
      pass
    for name in ("coefSlider", "coefSpinBox", "coefComboBox",
                 "coefMagnificationSpin", "coefUpdateMagnificationButton"):
      try:
        w = getattr(self.ui, name, None)
        if w is not None:
          w.setEnabled(not pca_active)
      except Exception:
        pass

    # Drive-3D from the PCA scatter plot is also a PCA driver. Disable the
    # toggle + the X/Y PC spinboxes when we leave PCA mode, and force the
    # toggle off so any active chart->warp binding stops firing.
    try:
      cb = getattr(self.ui, "drivePCAPlotCheckBox", None)
      if cb is not None:
        if not pca_active and cb.isChecked():
          # onTogglePlotDriving(False) cleans up the binding + resets to mean.
          try: cb.setChecked(False)
          except Exception: pass
        cb.setEnabled(pca_active)
    except Exception:
      pass
    for attr in ("_driveSpinX", "_driveSpinY", "_driveLabelX", "_driveLabelY"):
      try:
        w = getattr(self, attr, None)
        if w is not None:
          w.setEnabled(pca_active)
      except Exception:
        pass

    # Reset viewer 2 to the mean shape on every mode switch so the user
    # always starts from a known reference. For PCA: snap the PC slider to 0
    # (zero displacement scale). For LR: snap the coefficient slider back to
    # its neutral value (mean of numeric domain, ref level for categorical),
    # which produces an identity TPS at the next apply.
    try:
      if mode == "pca":
        if getattr(self, "pcController", None) is not None:
          self.pcController.setValue(0)
        # Force scale -> 0 even if the slider was already at 0 (no signal fires).
        gtn = getattr(self, "gridTransformNode", None)
        if gtn is not None:
          try:
            gtn.GetTransformFromParent().SetDisplacementScale(0.0)
            gtn.Modified()
          except Exception:
            pass
      else:
        lr = getattr(self, "lr", None)
        if lr is not None and getattr(lr, "coefController", None) is not None:
          # Re-apply the per-coefficient domain default (sets slider to neutral
          # AND triggers _coef_updateScaling -> _coef_applyTPS for the reset).
          try:
            lr._coef_set_slider_domain_for_current()
          except Exception:
            try: lr.coefController.setValue(0.0)
            except Exception: pass
          # Also force a TPS rebuild at neutral in case setValue was a no-op
          # (slider already at neutral -> no signal).
          try: lr._coef_applyTPS()
          except Exception: pass
    except Exception:
      pass

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

    # Build (or reuse cached) displacement grid for current PC.
    # Cache is keyed by (pc_index, current magnification). It is invalidated
    # whenever magnification changes (see onUpdateMagnificationClicked) or a new
    # analysis is loaded (initializeOnLoad / initializeOnSelect / reset).
    try:
      magnification = float(self.ui.spinMagnification.value)
    except Exception:
      magnification = 1.0
    if not hasattr(self, "_gridCache") or self._gridCache is None:
      self._gridCache = {}
    cache_key = (self.currentPC, magnification)
    cached = self._gridCache.get(cache_key)
    if cached is None:
      # Building the 50x50x50 displacement grid evaluates a TPS over all N
      # control points at every grid sample (~125k * N kernel evals). On
      # dense LM datasets this can take many seconds and runs synchronously
      # on the UI thread; show a progress dialog so the user knows the app
      # is working rather than hung. Cached after the first build per
      # (PC, magnification).
      progressDialog = None
      restoreCursor = False
      try:
        progressDialog = slicer.util.createProgressDialog(
          windowTitle="Caching deformation grid",
          labelText=f"Caching deformation grid for PC{self.currentPC} "
                    f"(magnification {magnification:g})...\n"
                    f"This is a one-time cost per PC; subsequent selections "
                    f"of this PC will be instant.",
          maximum=0,
        )
        # A freshly-created modal dialog needs the Qt event loop to spin
        # several times before it is actually painted to the screen.
        # Without forcing show + raise + repaint + a few processEvents()
        # ticks here, the long synchronous getGridTransform() call below
        # would start before the dialog is visible and the user would see
        # nothing during the wait. This pattern is portable across
        # platforms; macOS just happens to expose the bug most reliably.
        try:
          progressDialog.setModal(True)
          progressDialog.show()
          progressDialog.raise_()
          progressDialog.repaint()
        except Exception:
          pass
        slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
        restoreCursor = True
        for _ in range(5):
          slicer.app.processEvents()
        cached = self.getGridTransform(self.currentPC)
        self._gridCache[cache_key] = cached
      finally:
        if progressDialog is not None:
          try: progressDialog.close()
          except Exception: pass
        if restoreCursor:
          try: slicer.app.restoreOverrideCursor()
          except Exception: pass
    self.displacementGridData = cached

    needNewNode = (self._node('gridTransformNode') is None)
    if needNewNode:
      self.gridTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLGridTransformNode", "GridTransform")
      GPANodeCollection.AddItem(self.gridTransformNode)

    # Assign the displacement grid
    self.gridTransformNode.GetTransformFromParent().SetDisplacementGridData(self.displacementGridData)

    # Claim the shared Interactive-Visualization clones for PCA. This both
    # parents them under `gridTransformNode` and updates the warp-mode toggle.
    # Replaces an earlier unconditional `SetAndObserveTransformNodeID` block;
    # routing through `_setWarpMode` keeps the toggle UI in sync.
    try:
      self._setWarpMode("pca")
    except Exception:
      # Safety net: if `_setWarpMode` is unavailable (e.g. legacy path),
      # fall back to the original direct attachment.
      lm_node = getattr(self, "cloneLandmarkNode", None) or getattr(self, "copyLandmarkNode", None)
      if lm_node is not None:
        lm_node.SetAndObserveTransformNodeID(self.gridTransformNode.GetID())
      try: targetModelChecked = bool(self.ui.modelVisualizationType.isChecked())
      except Exception: targetModelChecked = False
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
    # User is interacting with a PC control → claim ownership of the shared
    # warped-landmark/model clones for the PCA pipeline. Auto-switches the
    # warp-mode toggle if the LR tab had previously claimed them.
    if getattr(self, "activeWarpMode", "pca") != "pca":
      try: self._setWarpMode("pca")
      except Exception: pass
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

    # If the user has the plot-drive mode enabled, (re)attach event filter and
    # rebuild the crosshair cursor series on the new chart.
    self._refreshPlotDriving()

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

  # --------------------------------------------------------------------------
  # Plot-driven 2-PC model warping
  # --------------------------------------------------------------------------

  def _plotWidget(self):
    """Return the qMRMLPlotWidget for plot view 0, or None."""
    try:
      lm = slicer.app.layoutManager()
      return lm.plotWidget(0) if lm else None
    except Exception:
      return None

  def _plotView(self):
    """Return the qMRMLPlotView showing the PCA scatter chart, or None."""
    pw = self._plotWidget()
    try:
      return pw.plotView() if pw else None
    except Exception:
      return None

  def _currentPlotChartNode(self):
    """Return the chart node currently attached to plot view 0, or None."""
    pw = self._plotWidget()
    if pw is None:
      return None
    try:
      pvn = pw.mrmlPlotViewNode()
    except Exception:
      pvn = None
    if pvn is None:
      return None
    chart_id = pvn.GetPlotChartNodeID() or ""
    return slicer.mrmlScene.GetNodeByID(chart_id) if chart_id else None

  def _currentChartXY(self):
    """Return the underlying vtkChartXY in the plot view's scene, or None."""
    pv = self._plotView()
    if pv is None:
      return None
    # qMRMLPlotView exposes chart() and scene() directly in Slicer 5.x.
    try:
      ch = pv.chart()
      if ch is not None:
        return ch
    except Exception:
      pass
    try:
      scene = pv.scene()
      if scene is not None:
        for i in range(scene.GetNumberOfItems()):
          item = scene.GetItem(i)
          if item and item.IsA("vtkChartXY"):
            return item
    except Exception:
      pass
    return None

  def onTogglePlotDriving(self, checked):
    self._plotDriveActive = bool(checked)
    if not self._plotDriveActive:
      try:
        self.ui.drivePCAPlotStatus.setText("Status: off")
      except Exception:
        pass
      self._setStatusBarPCACursor(None)
      self._detachPlotMouseFilter()
      return
    # Attach + ensure cursor + sanity check.
    # Auto-create a default PC1-vs-PC2 plot if the current plot view does
    # NOT show a PCA scatter (it may be empty, or showing an unrelated
    # chart like the Procrustes Distances plot from the Results tab).
    if not self._isPCAChartActive():
      if not self._autoCreateDefaultPCAPlot():
        # Failure path already set status + unchecked the box.
        return
    self._refreshPlotDriving(forceLog=True)

  def _isPCAChartActive(self):
    """True iff plot view 0 currently shows a PCA scatter chart created
    by self.plot() (makeScatterPlot / makeScatterPlotWithFactors). We
    identify by the chart title which both helpers set to a string
    starting with 'PCA Scatter Plot'."""
    chart = self._currentPlotChartNode()
    if chart is None:
      return False
    try:
      title = chart.GetTitle() or ""
    except Exception:
      return False
    return title.startswith("PCA Scatter Plot")

  def _autoCreateDefaultPCAPlot(self):
    """Convenience: when the user toggles 'Drive 3D from PCA scatter plot'
    without having clicked the Explore tab's 'Plot' button, build a default
    PC1-vs-PC2 scatter and bind it to plot view 0. Returns True on success."""
    # Prerequisite: GPA results must exist.
    if (getattr(self, "LM", None) is None
        or getattr(self, "scatterDataAll", None) is None
        or self.scatterDataAll.size == 0):
      self._setPlotDriveStatus("Status: load data and run GPA first")
      try: self.ui.drivePCAPlotCheckBox.setChecked(False)
      except Exception: pass
      self._plotDriveActive = False
      return False

    # If the current layout has no plot view, switch to the GPA custom
    # layout (id 500) which contains one. Avoids the surprise of clicking
    # 'on' and seeing nothing happen because plot view 0 doesn't exist.
    if self._plotWidget() is None:
      try:
        slicer.app.layoutManager().setLayout(500)
      except Exception as e:
        print(f"[GPA plot-drive] could not switch to layout 500: {e}",
              flush=True)
    if self._plotWidget() is None:
      self._setPlotDriveStatus("Status: no plot view available in current layout")
      try: self.ui.drivePCAPlotCheckBox.setChecked(False)
      except Exception: pass
      self._plotDriveActive = False
      return False

    # Force PC1 vs PC2 on the Explore-tab combos so that what the user sees
    # in the plot matches what drives the warp. Suppress signals to avoid
    # firing whatever index-changed handlers Explore may have wired up.
    try:
      for combo, idx in ((self.ui.XcomboBox, 0), (self.ui.YcomboBox, 1)):
        if combo.count > idx:
          blocked = combo.blockSignals(True)
          try: combo.setCurrentIndex(idx)
          finally: combo.blockSignals(blocked)
    except Exception as e:
      print(f"[GPA plot-drive] could not set PC1/PC2 combos: {e}",
            flush=True)

    # Build the chart via the same code path the 'Plot' button uses.
    try:
      self.plot()
    except Exception as e:
      self._setPlotDriveStatus(f"Status: auto-plot failed ({e})")
      try: self.ui.drivePCAPlotCheckBox.setChecked(False)
      except Exception: pass
      self._plotDriveActive = False
      return False

    if self._currentPlotChartNode() is None:
      self._setPlotDriveStatus("Status: plot creation failed")
      try: self.ui.drivePCAPlotCheckBox.setChecked(False)
      except Exception: pass
      self._plotDriveActive = False
      return False
    return True

  def _refreshPlotDriving(self, forceLog=False):
    """Wire the event filter and ensure a crosshair series exists.
    Safe to call multiple times (idempotent)."""
    if not getattr(self, "_plotDriveActive", False):
      return
    chart = self._currentPlotChartNode()
    if chart is None:
      msg = "Status: click 'Plot' on Explore Data tab first"
      self._setPlotDriveStatus(msg)
      return
    if not self._ensureTwoPCDisplacement():
      return
    self._attachPlotMouseFilter()
    self._ensurePCACursorSeries(chart)
    self._claimChartLeftButton()
    pcX, pcY = self._plotDrivePCs
    self._setPlotDriveStatus(f"Status: ON  (X=PC{pcX}, Y=PC{pcY}) — drag on plot; Shift=H-lock, Ctrl/Cmd=V-lock")
    if forceLog:
      print(f"[GPA] Plot-drive ON: X=PC{pcX}, Y=PC{pcY}", flush=True)

  def _claimChartLeftButton(self):
    """Disable the chart's built-in pan/zoom on left-mouse-button so our
    scene observers receive press/move/release events."""
    chart = self._currentChartXY()
    if chart is None:
      return
    try:
      # vtkChart action constants: PAN=0, ZOOM=1, SELECT=2, ZOOM_AXIS=3,
      # SELECT_POLYGON=4, CLICK_AND_DRAG=5, NOTIFY=6
      # Button constants (from vtkContextMouseEvent): NO_BUTTON=0,
      # LEFT_BUTTON=1, MIDDLE_BUTTON=2, RIGHT_BUTTON=4.
      LEFT_BUTTON = 1
      NO_BUTTON = 0
      # Move all left-button actions off so our observers see the events.
      for action in (vtk.vtkChart.PAN, vtk.vtkChart.ZOOM,
                     vtk.vtkChart.SELECT, vtk.vtkChart.CLICK_AND_DRAG):
        try:
          chart.SetActionToButton(action, NO_BUTTON)
        except Exception:
          pass
      # Re-bind pan to middle-button so users still have a pan affordance.
      try:
        chart.SetActionToButton(vtk.vtkChart.PAN, 2)
      except Exception:
        pass
    except Exception as e:
      print(f"[GPA plot-drive] could not reassign chart actions: {e}",
            flush=True)

  def _setPlotDriveStatus(self, text):
    try:
      self.ui.drivePCAPlotStatus.setText(text)
    except Exception:
      pass

  def _attachPlotMouseFilter(self):
    pv = self._plotView()
    if pv is None:
      return
    if self._plotDriveFilteredWidgets:
      return  # already installed
    if self._plotDriveFilter is None:
      self._plotDriveFilter = _PCAPlotMouseFilter(self)
    # qMRMLPlotView is a container; the child QVTKOpenGLNativeWidget is what
    # receives mouse events. Install on it (and on the view itself, harmless).
    targets = [pv]
    try:
      for child in pv.findChildren(qt.QWidget):
        targets.append(child)
    except Exception:
      pass
    for w in targets:
      try:
        w.installEventFilter(self._plotDriveFilter)
        w.setMouseTracking(True)
        self._plotDriveFilteredWidgets.append(w)
      except Exception:
        pass
    print(f"[GPA plot-drive] installed event filter on {len(self._plotDriveFilteredWidgets)} widgets",
          flush=True)
    # Force the plot view interaction mode to something that does NOT consume
    # left-click for pan/zoom: 'select points' (= 1).
    self._setPlotInteractionMode(1)

  def _detachPlotMouseFilter(self):
    if not getattr(self, "_plotDriveFilteredWidgets", None):
      return
    for w in self._plotDriveFilteredWidgets:
      try:
        w.removeEventFilter(self._plotDriveFilter)
      except Exception:
        pass
    self._plotDriveFilteredWidgets = []
    self._plotDriveDragging = False
    # Restore default 'pan view' (= 0) interaction.
    self._setPlotInteractionMode(0)

  def _setPlotInteractionMode(self, mode):
    """Set the qMRMLPlotView interaction mode by stamping the underlying
    vtkMRMLPlotViewNode. 0=pan, 1=select points, 2=freehand select, 3=move.
    """
    pw = self._plotWidget()
    if pw is None:
      return
    try:
      pvn = pw.mrmlPlotViewNode()
      if pvn is not None:
        pvn.SetInteractionMode(int(mode))
    except Exception as e:
      print(f"[GPA plot-drive] could not set interaction mode: {e}",
            flush=True)

  def _handleQtMouseEvent(self, event, widget):
    """Convert a Qt mouse event on `widget` to PC scores via current chart axes.
    """
    chart = self._currentChartXY()
    if chart is None or widget is None:
      print(f"[GPA plot-drive] no chart or widget (chart={chart})",
            flush=True)
      return
    bx = chart.GetAxis(vtk.vtkAxis.BOTTOM)
    ly = chart.GetAxis(vtk.vtkAxis.LEFT)
    if bx is None or ly is None:
      return
    bx_p1 = bx.GetPoint1(); bx_p2 = bx.GetPoint2()
    ly_p1 = ly.GetPoint1(); ly_p2 = ly.GetPoint2()
    if abs(bx_p2[0] - bx_p1[0]) < 1e-6 or abs(ly_p2[1] - ly_p1[1]) < 1e-6:
      return
    # Qt y is top-down, VTK chart axis points are bottom-up.
    # On HiDPI displays (Retina) Qt reports widget coordinates in logical
    # pixels but VTK's chart scene works in physical (render-window) pixels —
    # without scaling, the cursor lands at half the offset on macOS.
    try:
      dpr = float(widget.devicePixelRatioF())
    except Exception:
      try:
        dpr = float(widget.devicePixelRatio())
      except Exception:
        dpr = 1.0
    if dpr <= 0:
      dpr = 1.0
    h = float(widget.height) * dpr
    px = float(event.x()) * dpr
    py = h - float(event.y()) * dpr
    fx = (px - bx_p1[0]) / (bx_p2[0] - bx_p1[0])
    fy = (py - ly_p1[1]) / (ly_p2[1] - ly_p1[1])
    fx = max(0.0, min(1.0, fx))
    fy = max(0.0, min(1.0, fy))
    dx = bx.GetMinimum() + fx * (bx.GetMaximum() - bx.GetMinimum())
    dy = ly.GetMinimum() + fy * (ly.GetMaximum() - ly.GetMinimum())
    mods = event.modifiers()
    if (mods & qt.Qt.ShiftModifier) and self._plotDriveCursorTable is not None:
      dy = self._plotDriveCursorTable.GetTable().GetValue(0, 1).ToFloat()
    if (mods & qt.Qt.ControlModifier) and self._plotDriveCursorTable is not None:
      dx = self._plotDriveCursorTable.GetTable().GetValue(0, 0).ToFloat()
    self._applyPlotScores(dx, dy)
    self._updatePCACursor(dx, dy)

  def _detachPlotMouseFilter(self):
    for interactor, tag in getattr(self, "_plotDriveObserverIDs", []):
      try:
        interactor.RemoveObserver(tag)
      except Exception:
        pass
    self._plotDriveObserverIDs = []
    self._plotDriveDragging = False

  def _onVTKMousePress(self, caller, eventName):
    pass  # legacy no-op
  def _onVTKMouseMove(self, caller, eventName):
    pass
  def _onVTKMouseRelease(self, caller, eventName):
    pass
  def _onSceneMousePress(self, caller, eventName):
    pass
  def _onSceneMouseMove(self, caller, eventName):
    pass
  def _onSceneMouseRelease(self, caller, eventName):
    pass
  def _sceneMousePos(self, scene):
    return (0.0, 0.0)

  # ---- Geometry: build per-PC displacement arrays sharing one grid ----
  def _ensureTwoPCDisplacement(self):
    """Make sure both XcomboBox and YcomboBox PCs have cached displacement
    arrays sampled on a shared grid, and that a fused vtkImageData target
    exists for live updates. Returns True on success.
    """
    if self.LM is None or self.scatterDataAll is None or self.scatterDataAll.size == 0:
      self._setPlotDriveStatus("Status: load + run GPA first")
      return False
    try:
      pcX = int(self.ui.XcomboBox.currentIndex) + 1
      pcY = int(self.ui.YcomboBox.currentIndex) + 1
    except Exception:
      self._setPlotDriveStatus("Status: select X/Y PCs on Explore tab")
      return False
    # Need a model OR landmark target to compute grid bounds. Reuse setupPCTransform
    # path via a single getGridTransform call: pick X first to seed the geometry,
    # then convert any cached vtkImageData -> numpy displacement, and likewise for Y.
    try:
      magnification = float(self.ui.spinMagnification.value)
    except Exception:
      magnification = 1.0
    try:
      self._plotDrivePCmaxX = float(np.max(np.abs(self.scatterDataAll[:, pcX - 1])))
      self._plotDrivePCmaxY = float(np.max(np.abs(self.scatterDataAll[:, pcY - 1])))
    except Exception:
      self._plotDrivePCmaxX = 0.0
      self._plotDrivePCmaxY = 0.0
    if self._plotDrivePCmaxX < 1e-12 or self._plotDrivePCmaxY < 1e-12:
      self._setPlotDriveStatus("Status: PC range is degenerate")
      return False

    def _disp_for(pc_index):
      key = (pc_index, magnification)
      arr = self._plotDriveDispCache.get(key)
      if arr is not None:
        return arr
      # Reuse the slider's grid cache when possible: it stores a
      # vtkImageData built by the same getGridTransform(pc, magnification),
      # which is exactly what plot-drive needs as a numpy view. Avoids a
      # second 50^3 * N-control-point TPS evaluation that takes ~30s on
      # dense LM datasets.
      img = None
      shared = getattr(self, "_gridCache", None)
      if isinstance(shared, dict):
        cached_img = shared.get((pc_index, magnification))
        if cached_img is not None:
          img = cached_img
      if img is None:
        # Cache miss on BOTH caches: must compute the grid synchronously.
        # Show a progress dialog so the user knows the app is working.
        progressDialog = None
        restoreCursor = False
        try:
          try:
            progressDialog = slicer.util.createProgressDialog(
              windowTitle="Caching deformation grid",
              labelText=f"Caching deformation grid for PC{pc_index} "
                        f"(magnification {magnification:g})...\n"
                        f"This is a one-time cost per PC; subsequent uses "
                        f"of this PC will be instant.",
              maximum=0,
            )
            try:
              progressDialog.setModal(True)
              progressDialog.show()
              progressDialog.raise_()
              progressDialog.repaint()
            except Exception:
              pass
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            restoreCursor = True
            for _ in range(5):
              slicer.app.processEvents()
          except Exception:
            pass
          try:
            # getGridTransform reads self.pcScoreAbsMax to size the warp; set it
            # to the per-PC absolute score range so each PC's grid is built at
            # its own max-score deformation.
            prev_abs_max = getattr(self, "pcScoreAbsMax", None)
            prev_pc = getattr(self, "currentPC", None)
            self.pcScoreAbsMax = float(np.max(np.abs(self.scatterDataAll[:, pc_index - 1])))
            self.currentPC = pc_index
            try:
              img = self.getGridTransform(pc_index)
            finally:
              if prev_abs_max is not None:
                self.pcScoreAbsMax = prev_abs_max
              if prev_pc is not None:
                self.currentPC = prev_pc
          except Exception as e:
            print(f"[GPA] plot-drive: getGridTransform failed for PC{pc_index}: {e}", flush=True)
            return None
          # Populate the slider cache too so a later slider use is instant.
          if isinstance(shared, dict):
            shared[(pc_index, magnification)] = img
        finally:
          if progressDialog is not None:
            try: progressDialog.close()
            except Exception: pass
          if restoreCursor:
            try: slicer.app.restoreOverrideCursor()
            except Exception: pass
      dims = img.GetDimensions()
      vec = numpy_support.vtk_to_numpy(img.GetPointData().GetScalars()).copy()
      vec = vec.reshape((dims[2], dims[1], dims[0], 3))
      self._plotDriveDispCache[key] = vec
      # Capture geometry once so we can build a fused image with same lattice
      self._plotDriveGridDims = dims
      self._plotDriveGridOrigin = img.GetOrigin()
      self._plotDriveGridSpacing = img.GetSpacing()
      return vec

    dispX = _disp_for(pcX)
    dispY = _disp_for(pcY)
    if dispX is None or dispY is None:
      self._setPlotDriveStatus("Status: failed to build displacement grids")
      return False

    # Build (or reuse) a single fused vtkImageData attached to a single grid node.
    rebuilt = False
    if (self._plotDriveFusedImage is None
        or self._plotDriveFusedImage.GetDimensions() != self._plotDriveGridDims):
      img = vtk.vtkImageData()
      img.SetDimensions(self._plotDriveGridDims)
      img.SetOrigin(self._plotDriveGridOrigin)
      img.SetSpacing(self._plotDriveGridSpacing)
      n = (self._plotDriveGridDims[0]
           * self._plotDriveGridDims[1]
           * self._plotDriveGridDims[2])
      flat = np.zeros((n, 3), dtype=np.float64)
      vtk_arr = numpy_support.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_DOUBLE)
      vtk_arr.SetNumberOfComponents(3)
      vtk_arr.SetName("Displacement")
      img.GetPointData().SetScalars(vtk_arr)
      self._plotDriveFusedImage = img
      # Keep a numpy reshape view for fast in-place fills
      self._plotDriveFusedArray = numpy_support.vtk_to_numpy(vtk_arr).reshape(
        (self._plotDriveGridDims[2], self._plotDriveGridDims[1],
         self._plotDriveGridDims[0], 3))
      rebuilt = True
    # ALWAYS (re-)attach the fused image to the grid transform and wire
    # model + landmarks to it. Toggling off + using the regular visualization
    # path swaps the model's transform out from under us; re-bind on every
    # ON-toggle so the warp resumes.
    if self._node('gridTransformNode') is None:
      self.gridTransformNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLGridTransformNode", "GridTransform")
      GPANodeCollection.AddItem(self.gridTransformNode)
    self.gridTransformNode.GetTransformFromParent().SetDisplacementGridData(
      self._plotDriveFusedImage)
    self.gridTransformNode.GetTransformFromParent().SetDisplacementScale(1.0)
    lm_node = getattr(self, "cloneLandmarkNode", None) or getattr(self, "copyLandmarkNode", None)
    if lm_node is not None:
      lm_node.SetAndObserveTransformNodeID(self.gridTransformNode.GetID())
    try:
      modelChecked = bool(self.ui.modelVisualizationType.isChecked())
    except Exception:
      modelChecked = False
    if modelChecked and getattr(self, "cloneModelNode", None):
      self.cloneModelNode.SetAndObserveTransformNodeID(self.gridTransformNode.GetID())

    self._plotDrivePCs = (pcX, pcY)
    self._plotDriveDispX = dispX
    self._plotDriveDispY = dispY
    # Reset to origin (mean shape) on every toggle ON so the cursor and the
    # 3D model start in sync.
    self._applyPlotScores(0.0, 0.0)
    self._updatePCACursor(0.0, 0.0)
    return True

  def _applyPlotScores(self, scoreX, scoreY):
    """Set the fused displacement field to scoreX*dX_unit + scoreY*dY_unit
    where dX_unit / dY_unit are the per-PC max-score displacements scaled
    so that score == pcScoreAbsMax produces the maximum-shape grid we cached.
    """
    if self._plotDriveFusedArray is None:
      return
    if self._plotDrivePCmaxX < 1e-12 or self._plotDrivePCmaxY < 1e-12:
      return
    sx = float(scoreX) / self._plotDrivePCmaxX
    sy = float(scoreY) / self._plotDrivePCmaxY
    np.multiply(self._plotDriveDispX, sx, out=self._plotDriveFusedArray)
    self._plotDriveFusedArray += sy * self._plotDriveDispY
    self._plotDriveFusedImage.GetPointData().GetScalars().Modified()
    self._plotDriveFusedImage.Modified()
    if self._node('gridTransformNode') is not None:
      self.gridTransformNode.GetTransformFromParent().Modified()
      self.gridTransformNode.Modified()

  # ---- Crosshair series on the chart ----
  def _ensurePCACursorSeries(self, chartNode):
    """Add (once) a single '+' marker series tracking (scoreX, scoreY)."""
    if chartNode is None:
      return
    if self._plotDriveCursorTable is None:
      tableNode = slicer.mrmlScene.GetFirstNodeByName('PCA Cursor Table')
      if tableNode is None:
        tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Cursor Table')
        GPANodeCollection.AddItem(tableNode)
      tbl = tableNode.GetTable()
      tbl.RemoveAllColumns()
      colX = vtk.vtkFloatArray(); colX.SetName("X")
      colY = vtk.vtkFloatArray(); colY.SetName("Y")
      tbl.AddColumn(colX); tbl.AddColumn(colY)
      # VTK's chart scene logs 'Attempted to paint a line with <2 points'
      # for any series that has fewer than 2 rows, even when LineStyleNone is
      # set. Stamp two identical rows so VTK draws a zero-length line and
      # stays quiet; both rows render as the same crosshair marker.
      tbl.SetNumberOfRows(2)
      tbl.SetValue(0, 0, 0.0)
      tbl.SetValue(0, 1, 0.0)
      tbl.SetValue(1, 0, 0.0)
      tbl.SetValue(1, 1, 0.0)
      self._plotDriveCursorTable = tableNode
    if self._plotDriveCursorSeries is None:
      seriesNode = slicer.mrmlScene.GetFirstNodeByName('PCA Cursor')
      if seriesNode is None:
        seriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", 'PCA Cursor')
        GPANodeCollection.AddItem(seriesNode)
      seriesNode.SetAndObserveTableNodeID(self._plotDriveCursorTable.GetID())
      seriesNode.SetXColumnName("X")
      seriesNode.SetYColumnName("Y")
      seriesNode.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
      seriesNode.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
      try:
        seriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStylePlus)
      except Exception:
        seriesNode.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleCross)
      seriesNode.SetMarkerSize(28)
      seriesNode.SetColor(0.0, 0.0, 0.0)
      self._plotDriveCursorSeries = seriesNode
    if not chartNode.HasPlotSeriesNodeID(self._plotDriveCursorSeries.GetID()):
      chartNode.AddAndObservePlotSeriesNodeID(self._plotDriveCursorSeries.GetID())

  def _updatePCACursor(self, scoreX, scoreY):
    if self._plotDriveCursorTable is None:
      return
    tbl = self._plotDriveCursorTable.GetTable()
    tbl.SetValue(0, 0, float(scoreX))
    tbl.SetValue(0, 1, float(scoreY))
    # Mirror to the second row so the renderer has ≥2 points and stays quiet.
    if tbl.GetNumberOfRows() >= 2:
      tbl.SetValue(1, 0, float(scoreX))
      tbl.SetValue(1, 1, float(scoreY))
    self._plotDriveCursorTable.Modified()
    # Mirror to Slicer's main status bar (bottom-right) so the user can read
    # the cursor coordinate without squinting at the plot symbol.
    if getattr(self, "_plotDriveActive", False):
      self._setStatusBarPCACursor((float(scoreX), float(scoreY)))

  def _ensureStatusBarPCALabel(self):
    """Create (once) and return the persistent QLabel docked bottom-right of
    Slicer's main status bar, or None if no main window/status bar exists."""
    lbl = getattr(self, "_plotDriveStatusBarLabel", None)
    if lbl is not None:
      return lbl
    try:
      mw = slicer.util.mainWindow()
      sb = mw.statusBar() if mw is not None else None
    except Exception:
      sb = None
    if sb is None:
      return None
    lbl = qt.QLabel("")
    lbl.setObjectName("GPA_PCA_Cursor_StatusLabel")
    lbl.setStyleSheet("QLabel { padding: 0 8px; font-family: monospace; }")
    try:
      sb.addPermanentWidget(lbl)
    except Exception:
      return None
    self._plotDriveStatusBarLabel = lbl
    return lbl

  def _setStatusBarPCACursor(self, scores):
    """scores=None hides the label; (x, y) updates the text using current
    Drive-3D X/Y PC indices."""
    lbl = self._ensureStatusBarPCALabel()
    if lbl is None:
      return
    if scores is None:
      lbl.setText("")
      lbl.setVisible(False)
      return
    try:
      pcX = int(self.ui.XcomboBox.currentIndex) + 1
      pcY = int(self.ui.YcomboBox.currentIndex) + 1
    except Exception:
      pcX, pcY = 1, 2
    sx, sy = scores
    lbl.setText(f"X(PC{pcX})={sx:+.4f}  Y(PC{pcY})={sy:+.4f}")
    lbl.setVisible(True)

  def _removeStatusBarPCALabel(self):
    """Remove the status-bar label from Slicer's main window. Called from
    _gpaTeardown so reloads do not leave stale labels behind."""
    lbl = getattr(self, "_plotDriveStatusBarLabel", None)
    if lbl is None:
      return
    try:
      mw = slicer.util.mainWindow()
      sb = mw.statusBar() if mw is not None else None
      if sb is not None:
        sb.removeWidget(lbl)
    except Exception:
      pass
    try:
      lbl.deleteLater()
    except Exception:
      pass
    self._plotDriveStatusBarLabel = None

  # ---- Mouse → data coordinate conversion + dispatch ----
  def _handleVTKMouseEvent(self, interactor):
    pass  # legacy no-op

  def _handleScenePos(self, pos, shift=False, ctrl=False):
    pass  # legacy no-op

  def toggleMeanPlot(self):
    node = self._node('meanLandmarkNode')
    if not node:
      return
    vis = node.GetDisplayVisibility()
    if vis:
      node.SetDisplayVisibility(False)
    else:
      node.SetDisplayVisibility(True)
      disp = self._display(node)
      if disp:
        disp.SetGlyphScale(self.ui.scaleMeanShapeSlider.value)
        color = self.ui.meanShapeColor.color
        disp.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])
    # Note: do NOT propagate visibility to cloneLandmarkNode. The viewer-2
    # clone is owned by the active warp source (PCA/LR) and should remain
    # visible while the user toggles the viewer-1 mean shape independently.

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
    # Note: do NOT propagate to cloneLandmarkNode. The viewer-2 clone color is
    # owned by the active warp source (PCA = dark red, LR = light pink) via
    # _setWarpMode and overriding it here would break that visual convention.

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

    # Vectorized construction: flatten landmarks across all subjects to (i*k, 3).
    # Original ordering iterated subject-major, landmark-minor, so use transpose(2,0,1).
    flat = np.ascontiguousarray(
      self.LM.lmOrig.transpose(2, 0, 1).reshape(i * k, 3),
      dtype=np.float64,
    )
    vtkPointData = numpy_support.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_DOUBLE)
    points = vtk.vtkPoints()
    points.SetData(vtkPointData)

    # Per-point landmark index (1..i, repeated for each subject) for color mapping.
    indexArr = np.tile(np.arange(1, i + 1, dtype=np.float64), k)
    indexes = numpy_support.numpy_to_vtk(indexArr, deep=True, array_type=vtk.VTK_DOUBLE)
    indexes.SetName('LM Index')

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

      # Convert landmarks to numpy array first
      self.sourceLMnumpy=logic.convertFudicialToNP(self.sourceLMNode)
      loadedLMCount = self.sourceLMNode.GetNumberOfControlPoints()

      # Remove any excluded landmarks from the loaded landmarks
      j=len(self.LMExclusionList)
      if (j != 0):
        # Convert 1-based landmark indices to 0-based array indices
        indexToRemove = [x - 1 for x in self.LMExclusionList]
        self.sourceLMnumpy = np.delete(self.sourceLMnumpy, indexToRemove, axis=0)

      # Check if landmark number is valid after removing excluded landmarks
      expectedLMCount = self.LM.lmOrig.shape[0]
      actualLMCount = self.sourceLMnumpy.shape[0]

      if actualLMCount != expectedLMCount:
        # Provide meaningful error message based on whether exclusions were applied
        if j != 0:
          logging.debug(f"Number of landmarks for 3D visualization does not match after removing excluded landmarks\n")
          errorMsg = (f"Error: Dimension mismatch after removing excluded landmarks.\n\n"
                     f"Loaded file has {loadedLMCount} landmarks.\n"
                     f"After removing {j} excluded landmarks (indices: {self.LMExclusionList}), "
                     f"expected {expectedLMCount} landmarks but have {actualLMCount}.\n\n"
                     f"Please verify the landmark file corresponds to the analysis data.")
        else:
          logging.debug("Number of landmarks selected for 3D visualization does not match the analysis\n")
          errorMsg = (f"Error: Expected {expectedLMCount} landmarks but loaded file has {loadedLMCount}.\n\n"
                     f"Please verify the landmark file corresponds to the analysis data.")
        slicer.util.messageBox(errorMsg)
        slicer.mrmlScene.RemoveNode(self.sourceLMNode)
        return

      self.initializeOnSelect()
      GPANodeCollection.AddItem(self.sourceLMNode)

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
      self.cloneModelNode.SetName('Warped Model')
      self.cloneModelDisplayNode =  self.cloneModelNode.GetDisplayNode()
      # Light cyan (#7ff4fd) reads better than pure blue against the dark 3D background
      self.cloneModelDisplayNode.SetColor(0x7f/255.0, 0xf4/255.0, 0xfd/255.0)
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

    # Bind the existing PC grid transform (if any) to the newly created
    # cloneModelNode so the slider warps the model in addition to landmarks.
    # populateComboBox above resets the combobox to 'None', which would make
    # setupPCTransform() return early. Instead, attach the model directly to
    # whatever gridTransformNode is currently active. If no grid exists yet,
    # the user's first PC selection runs setupPCTransform() which already
    # handles the model attach.
    grid_node = getattr(self, "gridTransformNode", None)
    if (grid_node is not None
        and slicer.mrmlScene.IsNodePresent(grid_node)
        and getattr(self, "cloneModelNode", None) is not None
        and bool(self.ui.modelVisualizationType.isChecked())):
      try:
        self.cloneModelNode.SetAndObserveTransformNodeID(grid_node.GetID())
      except Exception:
        pass

    # Apply the active warp-mode color scheme to the freshly-created clones
    # so the user gets visual confirmation (dark red = PCA, light pink = LR)
    # immediately after Apply, not only after picking a PC / LR coefficient.
    try:
      self._setWarpMode(getattr(self, "activeWarpMode", "pca"))
    except Exception:
      pass

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

  def _setAnalysisTabsEnabled(self, enabled: bool):
    """Enable/disable the post-GPA tabs (everything except Setup Analysis).
    Setup Analysis (index 0) is always enabled. Called with False from
    setup() and True from the success path of onLoad / onLoadFromFile."""
    tab = getattr(self, "_tabWidget", None)
    if tab is None:
      return
    try:
      total = int(tab.count)
    except Exception:
      try:
        total = int(tab.count())
      except Exception:
        return
    for i in range(1, total):
      try:
        tab.setTabEnabled(i, bool(enabled))
      except Exception:
        pass

  def _onTabChanged(self, index: int):
    """Initialize the LR tab on first entry."""
    try:
      if self._lr_tab_index is not None and int(index) == int(self._lr_tab_index):
        self._lazyInitLR()
    except Exception:
      # Be robust if Qt int wrappers act up
      try:
        if self._lr_tab_index is not None and index == self._lr_tab_index:
          self._lazyInitLR()
      except Exception:
        pass

  def _lazyInitLR(self):
    """One-time initialization for the Geomorph LR tab (patsy + pyRserve + attach controller)."""
    # If already initialized, nothing to do
    if hasattr(self, "lr") and self.lr is not None:
      return

    # 1) Ensure patsy is available (install on-demand)
    try:
      import patsy  # noqa: F401
    except Exception:
      try:
        progressDialog = slicer.util.createProgressDialog(
          windowTitle="Installing...",
          labelText="Installing patsy (formula parser)...",
          maximum=0
        )
        slicer.app.processEvents()
        slicer.util.pip_install(["patsy"])
        progressDialog.close()
      except Exception:
        try:
          progressDialog.close()
        except Exception:
          pass
        # Continue; geomorph_lr will try again if needed.

    # 2) Ensure pyRserve importability (install on-demand)
    try:
      _ensure_pyRserve_early()
    except Exception:
      # Non-fatal; geomorph tab can still render, and connect will try again.
      pass

    # 3) Create and attach the LR controller now that the UI exists
    try:
      from Support.geomorph_lr import GeomorphLR
      self.lr = GeomorphLR(parent_widget=self, node_collection=GPANodeCollection)
      self.lr.attach()
      # Make sure fit gating & covariate list reflect current state (if any)
      try:
        self.lr.refreshFromCovariates()
      except Exception:
        pass
      try:
        self.lr.refreshFitButton()
      except Exception:
        pass
    except Exception as e:
      # Surface a short note in the module log; do not hard fail the module
      try:
        self.ui.GPALogTextbox.insertPlainText(f"[LR] Initialization error: {e}\n")
      except Exception:
        pass


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
    # Predictable, distinct color (deep blue) instead of SetUniqueColor()'s
    # randomly-picked palette entry — picks a color that contrasts with the
    # cursor crosshair (which is black).
    plotSeriesNode1.SetColor(0.12, 0.47, 0.71)

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

  @staticmethod
  def isNumericValue(s):
    """
    Check if a string can be converted to a numeric value.
    Returns True for strings that can be converted to float, False otherwise.
    This includes integers, floats, negative numbers, and scientific notation.
    """
    try:
      float(s)
      return True
    except (ValueError, TypeError):
      return False


class GPATest(ScriptedLoadableModuleTest):
  """
  Self-test for the GPA module.

  Click "Reload and Test" in the Reload & Test section of the GPA module to:
  1) Download a known-good landmark dataset (494 specimens, 55 landmarks) and
     a reference 3D model (the specimen closest to the mean) from
     SlicerMorph/SampleData into Slicer's cache directory if not present.
  2) Run the full Load workflow (GPA + PCA + scene setup) on the landmarks.
  3) Sanity-check the results (file count, landmark shape, eigenvalue ordering).
  4) Print per-step timings plus the absolute paths of the extracted landmark
     folder and reference model so they can be plugged into the GPA UI for
     interactive 3D visualization. A timing JSON is also written into
     Slicer's cache under "GPA_selftest/results/".

  Override paths via env vars (optional):
    GPA_SELFTEST_LM_DIR   override input landmark folder
    GPA_SELFTEST_OUT_DIR  override timing JSON output folder
  """

  DATASET_URL = "https://github.com/SlicerMorph/SampleData/raw/master/converted_LMs.zip"
  DATASET_DIRNAME = "converted_LMs"
  MODEL_URL = "https://github.com/SlicerMorph/SampleData/raw/master/809-3.obj.zip"
  MODEL_FILENAME = "809-3.obj"
  METADATA_URL = "https://github.com/SlicerMorph/SampleData/raw/master/matched_metadata.csv"
  METADATA_FILENAME = "matched_metadata.csv"
  EXPECTED_NUM_FILES = 431
  EXPECTED_NUM_LANDMARKS = 55

  def setUp(self):
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    self.setUp()
    self.test_GPAWorkflow()

  def _ensureDataset(self):
    """Download + unzip the test dataset into Slicer's cache.
    Returns the absolute path to the folder containing *.fcsv files.

    If a previously cached dataset has a file count different from
    EXPECTED_NUM_FILES, the stale folder and zip are removed so the new
    dataset is re-downloaded.
    """
    import os, zipfile, shutil
    cache_root = slicer.app.cachePath
    target_dir = os.path.join(cache_root, "GPA_selftest", self.DATASET_DIRNAME)
    zip_path = os.path.join(cache_root, "GPA_selftest", "converted_LMs.zip")

    def _fcsv_count(d):
      return sum(1 for f in os.listdir(d) if f.endswith(".fcsv")) if os.path.isdir(d) else 0

    cached = _fcsv_count(target_dir)
    if cached and cached != self.EXPECTED_NUM_FILES:
      print(f"[GPA selftest] stale cache ({cached} files, expected {self.EXPECTED_NUM_FILES}); refreshing", flush=True)
      shutil.rmtree(target_dir, ignore_errors=True)
      if os.path.exists(zip_path):
        os.remove(zip_path)
    elif cached == self.EXPECTED_NUM_FILES:
      return target_dir

    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    if not os.path.exists(zip_path):
      print(f"[GPA selftest] downloading {self.DATASET_URL}", flush=True)
      slicer.util.downloadFile(self.DATASET_URL, zip_path)
    print(f"[GPA selftest] extracting -> {os.path.dirname(target_dir)}", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
      zf.extractall(os.path.dirname(target_dir))
    if not os.path.isdir(target_dir):
      # The zip may extract to a slightly different folder name; try to find it.
      for name in os.listdir(os.path.dirname(target_dir)):
        cand = os.path.join(os.path.dirname(target_dir), name)
        if os.path.isdir(cand) and any(f.endswith(".fcsv") for f in os.listdir(cand)):
          return cand
      raise RuntimeError(f"Extracted dataset folder not found under {os.path.dirname(target_dir)}")
    return target_dir

  def _ensureModel(self):
    """Download + unzip the reference 3D model into Slicer's cache.
    Returns the absolute path to the .obj file (or None if it cannot be located).
    """
    import os, zipfile
    cache_root = slicer.app.cachePath
    model_dir = os.path.join(cache_root, "GPA_selftest")
    model_path = os.path.join(model_dir, self.MODEL_FILENAME)
    if os.path.isfile(model_path):
      return model_path
    os.makedirs(model_dir, exist_ok=True)
    zip_path = os.path.join(model_dir, os.path.basename(self.MODEL_URL))
    if not os.path.exists(zip_path):
      print(f"[GPA selftest] downloading {self.MODEL_URL}", flush=True)
      slicer.util.downloadFile(self.MODEL_URL, zip_path)
    print(f"[GPA selftest] extracting -> {model_dir}", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
      zf.extractall(model_dir)
    if os.path.isfile(model_path):
      return model_path
    # Fallback: pick the first .obj that appeared.
    for name in os.listdir(model_dir):
      if name.lower().endswith(".obj"):
        return os.path.join(model_dir, name)
    return None

  def _ensureMetadata(self):
    """Download the matched-metadata covariate CSV into Slicer's cache.
    Returns the absolute path to the CSV (or None on failure).

    The downloaded CSV is always re-sorted by the first column (ID) using
    the same lexicographic order that ``sorted(glob('*.fcsv'))`` produces,
    so the row order matches the landmark file order GPA expects.
    """
    import os, csv as _csv
    cache_root = slicer.app.cachePath
    meta_dir = os.path.join(cache_root, "GPA_selftest")
    raw_path = os.path.join(meta_dir, "_raw_" + self.METADATA_FILENAME)
    meta_path = os.path.join(meta_dir, self.METADATA_FILENAME)
    os.makedirs(meta_dir, exist_ok=True)

    # Always re-download the raw CSV (small file) so we pick up upstream edits
    if os.path.isfile(raw_path):
      try:
        os.remove(raw_path)
      except OSError:
        pass
    print(f"[GPA selftest] downloading {self.METADATA_URL}", flush=True)
    try:
      slicer.util.downloadFile(self.METADATA_URL, raw_path)
    except Exception as e:
      print(f"[GPA selftest] metadata download failed: {e}", flush=True)
      return None
    if not os.path.isfile(raw_path):
      return None

    # Sort rows by first column (ID) to match sorted(glob('*.fcsv'))
    try:
      with open(raw_path, newline='') as f:
        reader = _csv.reader(f)
        header = next(reader)
        rows = sorted((r for r in reader if r), key=lambda r: r[0])
      with open(meta_path, 'w', newline='') as f:
        writer = _csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
      print(f"[GPA selftest] metadata sorted by ID -> {meta_path} ({len(rows)} rows)", flush=True)
    except Exception as e:
      print(f"[GPA selftest] metadata sort failed: {e}; using raw file", flush=True)
      meta_path = raw_path
    return meta_path

  def test_GPAWorkflow(self):
    import os, glob, time, json
    from datetime import datetime

    cache_root = slicer.app.cachePath
    default_out_dir = os.path.join(cache_root, "GPA_selftest", "results")

    lm_dir = os.environ.get("GPA_SELFTEST_LM_DIR")
    if not lm_dir:
      lm_dir = self._ensureDataset()
    model_path = self._ensureModel()
    metadata_path = self._ensureMetadata()
    out_dir = os.environ.get("GPA_SELFTEST_OUT_DIR", default_out_dir)

    self.assertTrue(os.path.isdir(lm_dir), f"Landmark dir not found: {lm_dir}")
    files = sorted(glob.glob(os.path.join(lm_dir, "*.fcsv")))
    if not files:
      files = sorted(glob.glob(os.path.join(lm_dir, "*.mrk.json")))
    self.assertTrue(files, f"No landmark files in {lm_dir}")
    extension = "fcsv" if files[0].endswith(".fcsv") else "json"
    os.makedirs(out_dir, exist_ok=True)
    print(f"[GPA selftest] LM dir : {lm_dir}", flush=True)
    print(f"[GPA selftest] results: {out_dir}", flush=True)

    # Switch to GPA module and grab the widget
    slicer.util.selectModule("GPA")
    widget = slicer.modules.GPAWidget
    widget.reset()
    slicer.app.processEvents()

    # Wire inputs as if the user had selected them
    widget.inputFilePaths = files
    widget.files = [os.path.basename(p) for p in files]
    widget.LM_dir_name = lm_dir
    widget.outputDirectory = out_dir
    widget.extension = extension
    try:
      widget.ui.outText.setText(out_dir)
    except Exception:
      pass

    # Wire covariate metadata (matched IDs in CSV must align with landmark filenames)
    if metadata_path and os.path.isfile(metadata_path):
      widget.covariateTableFile = metadata_path
      try:
        widget.ui.selectCovariatesText.setText(metadata_path)
      except Exception:
        pass
      print(f"[GPA selftest] covariates : {metadata_path}", flush=True)
    else:
      print("[GPA selftest] covariates : <not available>", flush=True)

    # --- Instrument the slow steps with thin wrappers ---
    timings = {}

    def _make_wrap(orig, name):
      def wrapped(*a, **kw):
        t0 = time.perf_counter()
        try:
          return orig(*a, **kw)
        finally:
          dt = time.perf_counter() - t0
          timings[name] = timings.get(name, 0.0) + dt
          print(f"[GPA selftest] {name:<32} {dt*1000:9.1f} ms", flush=True)
      wrapped._gpa_orig = orig
      return wrapped

    def _patch_class(cls, names):
      saved = {}
      for n in names:
        saved[n] = getattr(cls, n)
        setattr(cls, n, _make_wrap(saved[n], n))
      return saved

    def _patch_instance(obj, names):
      saved = {}
      for n in names:
        saved[n] = getattr(obj, n)
        setattr(obj, n, _make_wrap(saved[n], n))
      return saved

    # Patch classes (so freshly constructed instances inside onLoad are timed)
    saved_logic = _patch_class(GPALogic, ["loadLandmarks"])
    saved_lm = _patch_class(LMData, ["doGpa", "calcEigen", "writeOutData", "closestSample"])
    # Patch widget instance methods
    saved_widget = _patch_instance(widget, [
      "updateList",
      "setupPCTransform",
      "populateDistanceTable",
      "assignLayoutDescription",
      "scaleMeanGlyph",
      "toggleMeanColor",
      "writeAnalysisLogFile",
    ])

    print(f"\n[GPA selftest] running onLoad on {len(files)} files...\n", flush=True)
    t_total0 = time.perf_counter()
    try:
      widget.onLoad()
    finally:
      total = time.perf_counter() - t_total0
      for n, fn in saved_logic.items():
        setattr(GPALogic, n, fn)
      for n, fn in saved_lm.items():
        setattr(LMData, n, fn)
      for n, fn in saved_widget.items():
        setattr(widget, n, fn)

    print(f"\n[GPA selftest] TOTAL onLoad: {total*1000:.1f} ms\n", flush=True)

    # ---- Sanity checks on the output ----
    self.assertEqual(len(files), self.EXPECTED_NUM_FILES,
                     f"Expected {self.EXPECTED_NUM_FILES} landmark files, found {len(files)}")
    self.assertIsNotNone(getattr(widget, "LM", None), "widget.LM was not created")
    self.assertEqual(widget.LM.lmOrig.shape[0], self.EXPECTED_NUM_LANDMARKS,
                     f"Expected {self.EXPECTED_NUM_LANDMARKS} landmarks per specimen, got {widget.LM.lmOrig.shape[0]}")
    self.assertEqual(widget.LM.lmOrig.shape[2], self.EXPECTED_NUM_FILES,
                     f"Expected {self.EXPECTED_NUM_FILES} specimens in array, got {widget.LM.lmOrig.shape[2]}")
    eigvals = widget.LM.val
    self.assertTrue(eigvals[0] > 0, "Top eigenvalue is not positive")
    self.assertTrue((eigvals[:-1] >= eigvals[1:] - 1e-12).all(), "Eigenvalues are not sorted descending")

    # Write timing JSON
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_json = os.path.join(out_dir, f"selftest_{stamp}.json")
    payload = {
      "lm_dir": lm_dir,
      "model_path": model_path,
      "metadata_path": metadata_path,
      "n_files": len(files),
      "n_landmarks": int(widget.LM.lmOrig.shape[0]),
      "extension": extension,
      "total_onLoad_seconds": total,
      "step_seconds": timings,
      "top10_eigenvalues": [float(v) for v in eigvals[:10]],
    }
    with open(out_json, "w") as f:
      json.dump(payload, f, indent=2)
    print(f"[GPA selftest] wrote {out_json}", flush=True)

    # ---- User-visible summary: paths to plug into the GPA module UI ----
    selftest_root = os.path.join(cache_root, "GPA_selftest")
    summary_lines = [
      "=" * 72,
      "[GPA selftest] PASSED -- to try interactive 3D visualization, set:",
    ]
    if model_path and os.path.isfile(model_path):
      summary_lines.append(
        f"[GPA selftest] Reference model (paste into 3D Visualization): {model_path}")
      summary_lines.append(
        f"[GPA selftest] Mean specimen LM (paste into 3D Visualization): "
        f"{os.path.join(lm_dir, '809-3.fcsv')}")
    else:
      summary_lines.append("[GPA selftest] Reference model : <download failed>")
    summary_lines.append(
      f"[GPA selftest] All other inputs (landmark folder, output folder, "
      f"covariate CSV) are under {selftest_root}/")
    summary_lines.append("=" * 72)
    summary = "\n".join(summary_lines)
    print("\n" + summary + "\n", flush=True)
    # Also surface in the GPA module's own log textbox so the user sees it
    try:
      widget.ui.GPALogTextbox.insertPlainText("\n" + summary + "\n")
      widget.ui.GPALogTextbox.ensureCursorVisible()
    except Exception:
      pass

    # ---- Auto-populate 3D Visualization selectors and offer to launch ----
    try:
      mean_lm_path = os.path.join(lm_dir, "809-3.fcsv")
      have_inputs = bool(model_path and os.path.isfile(model_path)
                         and os.path.isfile(mean_lm_path))
      if have_inputs:
        try:
          widget.ui.modelVisualizationType.setChecked(True)
          widget.onToggleVisualization()
        except Exception:
          pass
        try: widget.ui.grayscaleSelector.setCurrentPath(model_path)
        except Exception: pass
        try: widget.ui.FudSelect.setCurrentPath(mean_lm_path)
        except Exception: pass
        try: widget.onModelSelected()
        except Exception: pass
        try:
          if slicer.util.confirmYesNoDisplay(
              "Selftest passed and 3D Visualization inputs are pre-filled.\n\n"
              "Click 'Apply' now to build the warped landmark + model display?",
              windowTitle="GPA selftest"):
            widget.onSelect()
        except Exception:
          pass
    except Exception:
      pass

    self.delayDisplay(f"GPA self-test PASSED: {total:.2f}s ({len(files)} files)")

