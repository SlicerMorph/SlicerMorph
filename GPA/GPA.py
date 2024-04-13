import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import math

import re
import csv
import glob
import fnmatch

import Support.vtk_lib as vtk_lib
import Support.gpa_lib as gpa_lib
import  numpy as np
from datetime import datetime
import scipy.linalg as sp

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
    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

#
# GPAWidget
#
class sliderGroup(qt.QGroupBox):
  def setValue(self, value):
        self.slider.setValue(value)

  def connectList(self,mylist):
    self.list=mylist

  def populateComboBox(self, boxlist):
    self.comboBox.clear()
    for i in boxlist:
        self.comboBox.addItem(i)

  def setLabelTest(self,i):
    j=str(i)
    self.label.setText(j)

  def boxValue(self):
    tmp=self.comboBox.currentIndex
    return tmp

  def sliderValue(self):
    tmp=self.spinBox.value
    return tmp

  def clear(self):
    self.spinBox.setValue(0)
    self.comboBox.clear()

  def __init__(self, parent=None, onChanged=None):
    super().__init__( parent)

    # slider
    self.slider = qt.QSlider(qt.Qt.Horizontal)
    self.slider.setTickPosition(qt.QSlider.TicksBothSides)
    self.slider.setTickInterval(10)
    self.slider.setSingleStep(1)
    self.slider.setMaximum(100)
    self.slider.setMinimum(-100)

    # combo box to be populated with list of PC values
    self.comboBox=qt.QComboBox()

    # spin box to display scaling
    self.spinBox=qt.QSpinBox()
    self.spinBox.setMaximum(100)
    self.spinBox.setMinimum(-100)

    # connect to each other
    self.slider.valueChanged.connect(self.spinBox.setValue)
    self.spinBox.valueChanged.connect(self.slider.setValue)
    if onChanged:
      self.slider.valueChanged.connect(onChanged)
      self.comboBox.currentIndexChanged.connect(onChanged)

    # layout
    slidersLayout = qt.QGridLayout()
    slidersLayout.addWidget(self.slider,1,2)
    slidersLayout.addWidget(self.comboBox,1,1)
    slidersLayout.addWidget(self.spinBox,1,3)
    self.setLayout(slidersLayout)

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
      self.centriodSize = outputData.centeroid.to_numpy()
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
    self.lm, self.mShape=gpa_lib.runGPA(self.lmOrig)
    self.procdist = gpa_lib.procDist(self.lm, self.mShape)
    if BoasOption:
      print("Calculating Boas coordinates")
      for lmNum in range(i):
        for dimNum in range(j):
          for subjectNum in range(k):
            self.lm[lmNum, dimNum, subjectNum] = self.centriodSize[subjectNum]*self.lm[lmNum, dimNum, subjectNum]
      self.mShape=self.lm.mean(axis=2)

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
    for currentRow in range(r):
      temp[currentRow+1,:] = self.vec[currentRow,:]
    #temp = np.vstack((np.array(headerPC), self.vec))
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
    np.savetxt(outputFolder + os.sep + "MeanShape.csv", temp, delimiter=",", fmt='%s')

    percentVar = self.val / self.val.sum()
    files = np.array(files)
    i = files.shape
    files = files.reshape(i[0], 1)
    k, j, i = self.lmOrig.shape

    coords = self.flattenArray(self.lm)
    self.procdist = self.procdist.reshape(i, 1)
    self.centriodSize = self.centriodSize.reshape(i, 1)
    tmp = np.column_stack((files, self.procdist, self.centriodSize, np.transpose(coords)))
    header = np.array(['Sample_name', 'proc_dist', 'centeroid'])
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
    np.savetxt(outputFolder + os.sep + "OutputData.csv", tmp1, fmt="%s", delimiter=",")

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

class GPAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at: https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Initialize zoom factor for widget
    self.widgetZoomFactor = 0

    # Set up tabs to split workflow
    tabsWidget = qt.QTabWidget()
    setupTab = qt.QWidget()
    setupTabLayout = qt.QFormLayout(setupTab)
    exploreTab = qt.QWidget()
    exploreTabLayout = qt.QFormLayout(exploreTab)
    visualizeTab = qt.QWidget()
    visualizeTabLayout = qt.QFormLayout(visualizeTab)

    tabsWidget.addTab(setupTab, "Setup Analysis")
    tabsWidget.addTab(exploreTab, "Explore Data/Results")
    tabsWidget.addTab(visualizeTab, "Interactive 3D Visualization")
    self.layout.addWidget(tabsWidget)

    ################################### Setup Tab ###################################
    inbutton=ctk.ctkCollapsibleButton()
    inbutton.text="Setup Analysis"
    inputLayout= qt.QGridLayout(inbutton)
    setupTabLayout.addRow(inbutton)

    self.LMbutton=qt.QPushButton("Select Landmark Files ...")
    self.LMbutton.setToolTip("Select one landmark file for each subject. Files must contain the identical number of landmark points.")
    inputLayout.addWidget(self.LMbutton,1,1,1,3)
    self.LMbutton.connect('clicked(bool)', self.onSelectLandmarkFiles)

    # File viewer box area
    fileViewerCollapsibleButton = ctk.ctkCollapsibleButton()
    fileViewerLayout = qt.QFormLayout(fileViewerCollapsibleButton)
    fileViewerCollapsibleButton.text = "View selected landmark files"
    fileViewerCollapsibleButton.collapsed = True
    inputLayout.addWidget(fileViewerCollapsibleButton,2,1,1,3)

    # File viewer box
    self.inputFileTable = qt.QTextEdit()
    fileViewerLayout.addRow(self.inputFileTable)

    # Clear Button
    #
    self.clearButton = qt.QPushButton("Clear landmark file selections")
    self.clearButton.toolTip = "Clear the landmark files selected in the viewer boxes"
    self.clearButton.enabled = False
    fileViewerLayout.addRow(self.clearButton)
    self.clearButton.connect('clicked(bool)', self.onClearButton)

    #Load covariates option
    loadCovariatesCollapsibleButton = ctk.ctkCollapsibleButton()
    loadCovariatesLayout = qt.QGridLayout(loadCovariatesCollapsibleButton)
    loadCovariatesCollapsibleButton.text = "Load optional covariates table"
    loadCovariatesCollapsibleButton.collapsed = True
    inputLayout.addWidget(loadCovariatesCollapsibleButton,3,1,1,3)

    #Select covariates table
    self.covariatesText, covariatesLabel, self.covariatesButton=self.textIn('Covariates Table','', '')
    loadCovariatesLayout.addWidget(self.covariatesText,2,2)
    loadCovariatesLayout.addWidget(covariatesLabel,2,1)
    loadCovariatesLayout.addWidget(self.covariatesButton,2,3)
    self.covariatesButton.connect('clicked(bool)', self.onSelectCovariatesTable)

    #Load covariates button
    self.loadCovariatesTableButton = qt.QPushButton("Load Covariates Table from File")
    self.loadCovariatesTableButton.checkable = True
    loadCovariatesLayout.addWidget(self.loadCovariatesTableButton,5,1,1,3)
    self.loadCovariatesTableButton.toolTip = "Select covariates table in CSV format from file."
    self.loadCovariatesTableButton.enabled = False
    self.loadCovariatesTableButton.connect('clicked(bool)', self.onLoadCovariatesTable)

    # Select output directory
    self.outText, outLabel, self.outbutton=self.textIn('Select output directory: ','', '')
    inputLayout.addWidget(self.outText,4,2)
    inputLayout.addWidget(outLabel,4,1)
    inputLayout.addWidget(self.outbutton,4,3)
    self.outbutton.connect('clicked(bool)', self.onSelectOutputDirectory)

    self.excludeLMLabel=qt.QLabel('Exclude landmarks')
    inputLayout.addWidget(self.excludeLMLabel,5,1)

    self.excludeLMText=qt.QLineEdit()
    self.excludeLMText.setToolTip("No spaces. Separate numbers by commas.  Example:  51,52")
    inputLayout.addWidget(self.excludeLMText,5,2,1,2)

    self.BoasOptionCheckBox = qt.QCheckBox()
    self.BoasOptionCheckBox.setText("Use Boas coordinates for GPA")
    self.BoasOptionCheckBox.checked = 0
    self.BoasOptionCheckBox.setToolTip("If checked, GPA will skip scaling.")
    inputLayout.addWidget(self.BoasOptionCheckBox, 6,2)

    #Load Button
    self.loadButton = qt.QPushButton("Execute GPA + PCA")
    self.loadButton.checkable = True
    inputLayout.addWidget(self.loadButton,7,1,1,3)
    self.loadButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    self.loadButton.enabled = False
    self.loadButton.connect('clicked(bool)', self.onLoad)

    #Open Results
    self.openResultsButton = qt.QPushButton("View output files")
    self.openResultsButton.checkable = True
    inputLayout.addWidget(self.openResultsButton,8,1,1,3)
    self.openResultsButton.toolTip = "Push to open the folder where the GPA + PCA results are stored"
    self.openResultsButton.enabled = False
    self.openResultsButton.connect('clicked(bool)', self.onOpenResults)

    #Load from file option
    loadFromFileCollapsibleButton = ctk.ctkCollapsibleButton()
    loadFromFileLayout = qt.QGridLayout(loadFromFileCollapsibleButton)
    loadFromFileCollapsibleButton.text = "Load previous analysis"
    loadFromFileCollapsibleButton.collapsed = True
    setupTabLayout.addRow(loadFromFileCollapsibleButton)

    #Select results folder
    self.resultsText, resultsLabel, self.resultsButton=self.textIn('Results Directory','', '')
    loadFromFileLayout.addWidget(self.resultsText,2,2)
    loadFromFileLayout.addWidget(resultsLabel,2,1)
    loadFromFileLayout.addWidget(self.resultsButton,2,3)
    self.resultsButton.connect('clicked(bool)', self.onSelectResultsDirectory)

    #Load Results Button
    self.loadResultsButton = qt.QPushButton("Load GPA + PCA Analysis from File")
    self.loadResultsButton.checkable = True
    loadFromFileLayout.addWidget(self.loadResultsButton,5,1,1,3)
    self.loadResultsButton.toolTip = "Select previous analysis from file and restore."
    self.loadResultsButton.enabled = False
    self.loadResultsButton.connect('clicked(bool)', self.onLoadFromFile)

    ################################### Explore Tab ###################################
    #Mean Shape display section
    meanShapeFrame = ctk.ctkCollapsibleButton()
    meanShapeFrame.text="Mean Shape Plot Options"
    meanShapeLayout= qt.QGridLayout(meanShapeFrame)
    exploreTabLayout.addRow(meanShapeFrame)

    meanButtonLable=qt.QLabel("Mean shape visibility: ")
    meanShapeLayout.addWidget(meanButtonLable,1,1)

    self.plotMeanButton3D = qt.QPushButton("Toggle mean shape visibility")
    self.plotMeanButton3D.checkable = True
    self.plotMeanButton3D.toolTip = "Toggle visibility of mean shape plot"
    meanShapeLayout.addWidget(self.plotMeanButton3D,1,2)
    self.plotMeanButton3D.enabled = False
    self.plotMeanButton3D.connect('clicked(bool)', self.toggleMeanPlot)

    meanButtonLable=qt.QLabel("Mean point label visibility: ")
    meanShapeLayout.addWidget(meanButtonLable,2,1)

    self.showMeanLabelsButton = qt.QPushButton("Toggle label visibility")
    self.showMeanLabelsButton.checkable = True
    self.showMeanLabelsButton.toolTip = "Toggle visibility of mean point labels"
    meanShapeLayout.addWidget(self.showMeanLabelsButton,2,2)
    self.showMeanLabelsButton.enabled = False
    self.showMeanLabelsButton.connect('clicked(bool)', self.toggleMeanLabels)

    meanColorLable=qt.QLabel("Mean shape color: ")
    meanShapeLayout.addWidget(meanColorLable,3,1)
    self.meanShapeColor = ctk.ctkColorPickerButton()
    self.meanShapeColor.displayColorName = False
    self.meanShapeColor.color = qt.QColor(250,128,114)
    meanShapeLayout.addWidget(self.meanShapeColor,3,2)
    self.meanShapeColor.connect('colorChanged(QColor)', self.toggleMeanColor)

    self.scaleMeanShapeSlider = ctk.ctkSliderWidget()
    self.scaleMeanShapeSlider.singleStep = .1
    self.scaleMeanShapeSlider.minimum = 0
    self.scaleMeanShapeSlider.maximum = 10
    self.scaleMeanShapeSlider.value = 3
    self.scaleMeanShapeSlider.setToolTip("Set scale for mean shape glyphs")
    meanShapeSliderLabel=qt.QLabel("Mean shape glyph scale")
    meanShapeLayout.addWidget(meanShapeSliderLabel,4,1)
    meanShapeLayout.addWidget(self.scaleMeanShapeSlider,4,2)
    self.scaleMeanShapeSlider.connect('valueChanged(double)', self.scaleMeanGlyph)

     # Landmark Variance Section
    distributionFrame=ctk.ctkCollapsibleButton()
    distributionFrame.text="Landmark Variance Plot Options"
    distributionLayout= qt.QGridLayout(distributionFrame)
    exploreTabLayout.addRow(distributionFrame)

    self.EllipseType=qt.QRadioButton()
    ellipseTypeLabel=qt.QLabel("Ellipse type")
    self.EllipseType.setChecked(True)
    distributionLayout.addWidget(ellipseTypeLabel,2,1)
    distributionLayout.addWidget(self.EllipseType,2,2,1,2)
    self.SphereType=qt.QRadioButton()
    sphereTypeLabel=qt.QLabel("Sphere type")
    distributionLayout.addWidget(sphereTypeLabel,3,1)
    distributionLayout.addWidget(self.SphereType,3,2,1,2)
    self.CloudType=qt.QRadioButton()
    cloudTypeLabel=qt.QLabel("Point cloud type")
    distributionLayout.addWidget(cloudTypeLabel,4,1)
    distributionLayout.addWidget(self.CloudType,4,2,1,2)
    self.NoneType=qt.QRadioButton()
    noneTypeLabel=qt.QLabel("None")
    distributionLayout.addWidget(noneTypeLabel,5,1)
    distributionLayout.addWidget(self.NoneType,5,2,1,2)

    self.scaleSlider = ctk.ctkSliderWidget()
    self.scaleSlider.singleStep = .1
    self.scaleSlider.minimum = 0
    self.scaleSlider.maximum = 10
    self.scaleSlider.value = 3
    self.scaleSlider.enabled = False
    self.scaleSlider.setToolTip("Set scale for variance visualization")
    sliderLabel=qt.QLabel("Scale Glyphs")
    distributionLayout.addWidget(sliderLabel,2,3)
    distributionLayout.addWidget(self.scaleSlider,3,3,1,2)
    self.scaleSlider.connect('valueChanged(double)', self.onPlotDistribution)

    self.plotDistributionButton = qt.QPushButton("Plot LM variance")
    self.plotDistributionButton.checkable = True
    self.plotDistributionButton.toolTip = "Visualize variance of landmarks from all subjects"
    distributionLayout.addWidget(self.plotDistributionButton,7,1,1,4)
    self.plotDistributionButton.enabled = False
    self.plotDistributionButton.connect('clicked(bool)', self.onPlotDistribution)

    #PC plot section
    plotFrame=ctk.ctkCollapsibleButton()
    plotFrame.text="PCA Scatter Plot Options"
    plotLayout= qt.QGridLayout(plotFrame)
    exploreTabLayout.addRow(plotFrame)

    self.XcomboBox=qt.QComboBox()
    Xlabel=qt.QLabel("X Axis")
    plotLayout.addWidget(Xlabel,1,1)
    plotLayout.addWidget(self.XcomboBox,1,2,1,3)

    self.YcomboBox=qt.QComboBox()
    Ylabel=qt.QLabel("Y Axis")
    plotLayout.addWidget(Ylabel,2,1)
    plotLayout.addWidget(self.YcomboBox,2,2,1,3)

    # self.factorNameLabel=qt.QLabel('Factor Name:')
    # plotLayout.addWidget(self.factorNameLabel,3,1)
    # self.factorName=qt.QLineEdit()
    # self.factorName.setToolTip("Enter factor name")
    # self.factorName.connect('textChanged(const QString &)', self.factorStringChanged)
    # plotLayout.addWidget(self.factorName,3,2)

    # self.inputFactorButton = qt.QPushButton("Add factor data")
    # self.inputFactorButton.checkable = True
    # self.inputFactorButton.toolTip = "Open table to input factor data"
    # plotLayout.addWidget(self.inputFactorButton,3,4)
    # self.inputFactorButton.enabled = False
    # self.inputFactorButton.connect('clicked(bool)', self.enterFactors)

    self.selectFactor=qt.QComboBox()
    self.selectFactor.addItem("No factor data")
    selectFactorLabel=qt.QLabel("Select factor: ")
    plotLayout.addWidget(selectFactorLabel,4,1)
    plotLayout.addWidget(self.selectFactor,4,2)

    self.plotButton = qt.QPushButton("Scatter Plot")
    self.plotButton.checkable = True
    self.plotButton.toolTip = "Plot PCs"
    plotLayout.addWidget(self.plotButton,5,1,1,5)
    self.plotButton.enabled = False
    self.plotButton.connect('clicked(bool)', self.plot)

    # Lollipop Plot Section

    lolliFrame=ctk.ctkCollapsibleButton()
    lolliFrame.text="Lollipop Plot Options"
    lolliLayout= qt.QGridLayout(lolliFrame)
    exploreTabLayout.addRow(lolliFrame)

    self.vectorOne=qt.QComboBox()
    vectorOneLabel=qt.QLabel("Vector One: Red")
    lolliLayout.addWidget(vectorOneLabel,1,1)
    lolliLayout.addWidget(self.vectorOne,1,2,1,3)

    self.vectorTwo=qt.QComboBox()
    vector2Label=qt.QLabel("Vector Two: Green")
    lolliLayout.addWidget(vector2Label,2,1)
    lolliLayout.addWidget(self.vectorTwo,2,2,1,3)

    self.vectorThree=qt.QComboBox()
    vector3Label=qt.QLabel("Vector Three: Blue")
    lolliLayout.addWidget(vector3Label,3,1)
    lolliLayout.addWidget(self.vectorThree,3,2,1,3)

    self.TwoDType=qt.QCheckBox()
    self.TwoDType.checked = False
    self.TwoDType.setText("Lollipop 2D Projection")
    lolliLayout.addWidget(self.TwoDType,4,2)

    self.lolliButton = qt.QPushButton("Lollipop Vector Plot")
    self.lolliButton.checkable = True
    self.lolliButton.toolTip = "Plot PC vectors"
    lolliLayout.addWidget(self.lolliButton,6,1,1,6)
    self.lolliButton.enabled = False
    self.lolliButton.connect('clicked(bool)', self.lolliPlot)

    ################################### Visualize Tab ###################################
    # Interactive view set up tab
    selectTemplatesButton=ctk.ctkCollapsibleButton()
    selectTemplatesButton.text="Setup Interactive Visualization"
    selectTemplatesLayout= qt.QGridLayout(selectTemplatesButton)
    visualizeTabLayout.addRow(selectTemplatesButton)

    self.landmarkVisualizationType=qt.QRadioButton()
    landmarkVisualizationTypeLabel=qt.QLabel("Mean shape visualization")
    self.landmarkVisualizationType.setChecked(True)
    self.landmarkVisualizationType.enabled = False
    selectTemplatesLayout.addWidget(landmarkVisualizationTypeLabel,2,1)
    selectTemplatesLayout.addWidget(self.landmarkVisualizationType,2,2,1,4)
    self.modelVisualizationType=qt.QRadioButton()
    self.modelVisualizationType.enabled = False
    modelVisualizationTypeLabel=qt.QLabel("3D model visualization")
    selectTemplatesLayout.addWidget(modelVisualizationTypeLabel,3,1)
    selectTemplatesLayout.addWidget(self.modelVisualizationType,3,2,1,4)
    self.landmarkVisualizationType.connect('toggled(bool)', self.onToggleVisualization)
    self.modelVisualizationType.connect('toggled(bool)', self.onToggleVisualization)

    self.grayscaleSelectorLabel = qt.QLabel("Specify reference model")
    self.grayscaleSelectorLabel.setToolTip( "Load the model for the interactive visualization")
    self.grayscaleSelectorLabel.enabled = False
    selectTemplatesLayout.addWidget(self.grayscaleSelectorLabel,4,2)

    self.grayscaleSelector = ctk.ctkPathLineEdit()
    self.grayscaleSelector.filters  = ctk.ctkPathLineEdit().Files
    self.grayscaleSelector.nameFilters= ["Model (*.ply *.stl *.obj *.vtk *.vtp *.orig *.g .byu )"]
    self.grayscaleSelector.enabled = False
    self.grayscaleSelector.connect('validInputChanged(bool)', self.onModelSelected)
    selectTemplatesLayout.addWidget(self.grayscaleSelector,4,3,1,3)

    self.FudSelectLabel = qt.QLabel("Specify LM set for the selected model: ")
    self.FudSelectLabel.setToolTip( "Select the landmark set that corresponds to the reference model")
    self.FudSelectLabel.enabled = False
    self.FudSelect = ctk.ctkPathLineEdit()
    self.FudSelect.filters  = ctk.ctkPathLineEdit().Files
    self.FudSelect.nameFilters=["Landmarks (*.json *.mrk.json *.fcsv )"]
    self.FudSelect.enabled = False
    self.FudSelect.connect('validInputChanged(bool)', self.onModelSelected)
    selectTemplatesLayout.addWidget(self.FudSelectLabel,5,2)
    selectTemplatesLayout.addWidget(self.FudSelect,5,3,1,3)

    self.selectorButton = qt.QPushButton("Apply")
    self.selectorButton.checkable = True
    selectTemplatesLayout.addWidget(self.selectorButton,6,1,1,5)
    self.selectorButton.enabled = False
    self.selectorButton.connect('clicked(bool)', self.onSelect)

    # PC warping
    vis=ctk.ctkCollapsibleButton()
    vis.text='PCA Visualization Parameters'
    visLayout= qt.QGridLayout(vis)
    visualizeTabLayout.addRow(vis)

    self.applyEnabled=False

    def warpOnChangePC1(value):
      if self.applyEnabled and self.slider1.boxValue() != 'None':
        self.onApply()

    def warpOnChangePC2(value):
      if self.applyEnabled and self.slider2.boxValue() != 'None':
        self.onApply()

    self.PCList=[]
    self.slider1=sliderGroup(onChanged = warpOnChangePC1)
    self.slider1.connectList(self.PCList)
    visLayout.addWidget(self.slider1,3,1,1,2)

    self.slider2=sliderGroup(onChanged = warpOnChangePC2)
    self.slider2.connectList(self.PCList)
    visLayout.addWidget(self.slider2,4,1,1,2)

    # Create Animations
    animate=ctk.ctkCollapsibleButton()
    animate.text='Create animation of PC Warping'
    animateLayout= qt.QGridLayout(animate)
    visualizeTabLayout.addRow(animate)

    self.startRecordButton = qt.QPushButton("Start Recording")
    self.startRecordButton.toolTip = "Start recording PCA warping applied manually using the slider bars."
    self.startRecordButton.enabled = False
    animateLayout.addWidget(self.startRecordButton,1,1,1,2)
    self.startRecordButton.connect('clicked(bool)', self.onStartRecording)
    self.stopRecordButton = qt.QPushButton("Stop Recording")
    self.stopRecordButton.toolTip = "Stop recording PC warping and review recording in the Sequences module."
    self.stopRecordButton.enabled = False
    animateLayout.addWidget(self.stopRecordButton,1,5,1,2)
    self.stopRecordButton.connect('clicked(bool)', self.onStopRecording)

    # Reset button
    resetButton = qt.QPushButton("Reset Scene")
    resetButton.checkable = True
    visualizeTabLayout.addRow(resetButton)
    resetButton.toolTip = "Push to reset all fields."
    resetButton.connect('clicked(bool)', self.reset)

    self.layout.addStretch(1)

    # Add menu buttons
    self.addLayoutButton(500, 'GPA Module View', 'Custom layout for GPA module', 'LayoutSlicerMorphView.png', slicer.customLayoutSM)
    self.addLayoutButton(501, 'Table Only View', 'Custom layout for GPA module', 'LayoutTableOnlyView.png', slicer.customLayoutTableOnly)
    self.addLayoutButton(502, 'Plot Only View', 'Custom layout for GPA module', 'LayoutPlotOnlyView.png', slicer.customLayoutPlotOnly)

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
    self.meanLandmarkNode.GetDisplayNode().SetViewNodeIDs([viewNode1.GetID(),redNode.GetID()])
    if hasattr(self, 'cloneLandmarkDisplayNode'):
      self.cloneLandmarkDisplayNode.SetViewNodeIDs([viewNode2.GetID()])

    # check for loaded reference model
    if hasattr(self, 'modelDisplayNode'):
      self.modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
    if hasattr(self, 'cloneModelDisplayNode'):
      self.cloneModelDisplayNode.SetViewNodeIDs([viewNode2.GetID()])

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

  def textIn(self,label, dispText, toolTip):
    """ a function to set up the appearance of a QlineEdit widget.
    """
    # set up text line
    textInLine=qt.QLineEdit();
    textInLine.setText(dispText)
    textInLine.toolTip = toolTip
    # set up label
    lineLabel=qt.QLabel()
    lineLabel.setText(label)

    # make clickable button
    button=qt.QPushButton("..")
    return textInLine, lineLabel, button

  def updateList(self):
    i,j,k=self.LM.lm.shape
    self.PCList=[]
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.PCList.append('None')
    self.LM.val=np.real(self.LM.val)
    percentVar=self.LM.val/self.LM.val.sum()
    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    self.vectorOne.addItem('None')
    self.vectorTwo.addItem('None')
    self.vectorThree.addItem('None')
    if len(percentVar)<self.pcNumber:
      self.pcNumber=len(percentVar)
    for x in range(self.pcNumber):
      tmp=f"{percentVar[x]*100:.1f}"
      string='PC '+str(x+1)+': '+str(tmp)+"%" +" var"
      self.PCList.append(string)
      self.XcomboBox.addItem(string)
      self.YcomboBox.addItem(string)
      self.vectorOne.addItem(string)
      self.vectorTwo.addItem(string)
      self.vectorThree.addItem(string)

  def factorStringChanged(self):
    if self.factorName.text != "":
      self.inputFactorButton.enabled = True
    else:
      self.inputFactorButton.enabled = False

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

  # def enterFactors(self):
    # sortedArray = np.zeros(len(self.files), dtype={'names':('filename', 'procdist'),'formats':('U50','f8')})
    # sortedArray['filename']=self.files

    ##check for an existing factor table, if so remove
    # if hasattr(self, 'factorTableNode'):
      # GPANodeCollection.RemoveItem(self.factorTableNode)
      # slicer.mrmlScene.RemoveNode(self.factorTableNode)

    # self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Factor Table')
    # GPANodeCollection.AddItem(self.factorTableNode)
    # col1=self.factorTableNode.AddColumn()
    # col1.SetName('ID')
    # for i in range(len(self.files)):
      # self.factorTableNode.AddEmptyRow()
      # self.factorTableNode.SetCellText(i,0,sortedArray['filename'][i])

    # col2=self.factorTableNode.AddColumn()
    # col2.SetName(self.factorName.text)
    # self.selectFactor.addItem(self.factorName.text)

    ##add table to new layout
    # slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(self.factorTableNode.GetID())
    # slicer.app.applicationLogic().PropagateTableSelection()
    # self.factorTableNode.GetTable().Modified()

    ##reset text field for names
    # self.factorName.setText("")
    # self.inputFactorButton.enabled = False

  def reset(self):
    # delete the two data objects

    # reset text fields
    self.outputDirectory=None
    self.outText.setText(" ")
    self.LM_dir_name=None
    self.openResultsButton.enabled = False

    self.grayscaleSelector.setCurrentPath("")
    self.FudSelect.setCurrentPath("")
    self.grayscaleSelector.enabled = False
    self.FudSelect.enabled = False

    self.slider1.clear()
    self.slider2.clear()

    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()
    self.selectFactor.clear()
    self.factorName.setText("")
    self.scaleSlider.value=3

    self.scaleMeanShapeSlider.value=3
    self.meanShapeColor.color=qt.QColor(250,128,114)

    self.scaleSlider.enabled = False

    # Disable buttons for workflow
    self.plotButton.enabled = False
    self.inputFactorButton.enabled = False
    self.lolliButton.enabled = False
    self.plotDistributionButton.enabled = False
    self.plotMeanButton3D.enabled = False
    self.showMeanLabelsButton.enabled = False
    self.loadButton.enabled = False
    self.landmarkVisualizationType.enabled = False
    self.modelVisualizationType.enabled = False
    self.selectorButton.enabled = False
    self.stopRecordButton.enabled = False
    self.startRecordButton.enabled = False

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
    self.inputFileTable.clear()
    self.inputFilePaths = []
    self.clearButton.enabled = False

  def onSelectLandmarkFiles(self):
    self.inputFileTable.clear()
    self.inputFilePaths = []
    filter = ["Landmarks (*.json *.mrk.json *.fcsv )"]
    self.inputFilePaths = qt.QFileDialog().getOpenFileNames(None, "Window name", "", filter)
    self.inputFileTable.plainText = '\n'.join(self.inputFilePaths)
    self.clearButton.enabled = True
    #enable load button if required fields are complete
    filePathsExist = bool(self.inputFilePaths is not [] )
    self.loadButton.enabled = bool (filePathsExist and hasattr(self, 'outputDirectory'))
    if filePathsExist:
      self.LM_dir_name = os.path.dirname(self.inputFilePaths[0])
      basename, self.extension = os.path.splitext(self.inputFilePaths[0])
      if self.extension == '.json':
        basename, secondExtension = os.path.splitext(basename)
        self.extension =  secondExtension + self.extension
      self.files=[]
      for path in self.inputFilePaths:
        basename =  os.path.basename(path).partition('.')[0]
        self.files.append(basename)

  def onSelectOutputDirectory(self):
    self.outputDirectory=qt.QFileDialog().getExistingDirectory()
    self.outText.setText(self.outputDirectory)
    try:
      filePathsExist = self.inputFilePaths is not []
      self.loadButton.enabled = bool (filePathsExist and self.outputDirectory)
    except AttributeError:
      self.loadButton.enabled = False

  def onSelectCovariatesTable(self):
    dialog = qt.QFileDialog()
    filter = "csv(*.csv)"
    self.covariateTableFile = qt.QFileDialog.getOpenFileName(dialog, "", "", filter)
    if self.covariateTableFile:
      self.covariatesText.setText(self.covariateTableFile)
      self.loadCovariatesTableButton.enabled = True
    else:
     self.covariatesText.setText("")
     self.loadCovariatesTableButton.enabled = False

  def onLoadCovariatesTable(self):
    numberOfInputFiles = len(self.inputFilePaths)
    if numberOfInputFiles<1:
      logging.debug('No input files are selected')
      return
    try:
      self.factorTableNode = slicer.util.loadTable(self.covariateTableFile)
    except AttributeError:
      logging.debug('Covariate table import failed')
      return
    #check for at least one covariate factor
    numberOfColumns = self.factorTableNode.GetTable().GetNumberOfColumns()
    if numberOfColumns<2:
      logging.debug('Covariate table import failed, covariate table must have at least one factor column')
      slicer.mrmlScene.RemoveNode(self.factorTableNode)
      return
    indexColumn = self.factorTableNode.GetTable().GetColumn(0)
    #check for same number of covariate rows and input filenames
    if indexColumn.GetNumberOfTuples() != numberOfInputFiles:
      logging.debug('Covariate table import failed, covariate table row number does not match number of input files')
      slicer.mrmlScene.RemoveNode(self.factorTableNode)
      return
    #check that input filenames match factor row names
    for i, inputFile in enumerate(self.inputFilePaths):
      if indexColumn.GetValue(i) != inputFile:
        logging.debug('Covariate table import failed, covariate filenames do not match input files')
        slicer.mrmlScene.RemoveNode(self.factorTableNode)
        return
    for i in range(1,numberOfColumns):
      self.selectFactor.addItem(self.factorTableNode.GetTable().GetColumnName(i))
    #GPANodeCollection.AddItem(self.factorTableNode)

  def onSelectResultsDirectory(self):
    self.resultsDirectory=qt.QFileDialog().getExistingDirectory()
    self.resultsText.setText(self.resultsDirectory)
    try:
      self.loadResultsButton.enabled = bool (self.resultsDirectory)
    except AttributeError:
      self.loadResultsButton.enabled = False

  def onOpenResults(self):
    qpath = qt.QUrl.fromLocalFile(os.path.dirname(self.outputFolder+os.path.sep))
    qt.QDesktopServices().openUrl(qpath)

  def onLoadFromFile(self):
    self.initializeOnLoad() #clean up module from previous runs
    logic = GPALogic()
    import pandas

    # Load data
    outputDataPath = os.path.join(self.resultsDirectory, 'OutputData.csv')
    meanShapePath = os.path.join(self.resultsDirectory, 'MeanShape.csv')
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
      return

    # Try to load skip scaling and skip LM options from log file, if present
    self.BoasOption = False
    self.LMExclusionList=[]
    logFilePath = os.path.join(self.resultsDirectory, 'analysis.log')
    try:
      with open(logFilePath) as f:
        for search in f:
          if 'Boas=False' in search:
            self.BoasOption = True
          if 'ExcludedLM' in search:
            line = search.rstrip()
            header, skippedText = line.split('=')
            if skippedText != '':
              self.LMExclusionList = [int(i) for i in skippedText.split(',')]
    except:
      logging.debug('Log import failed: Cannot read scaling option from log file')
      logging.debug('Log import failed: Cannot read skipped landmarks from log file')
    print("Boas option: ", self.BoasOption)
    print("Skipped Landmarks: ", self.LMExclusionList)

    # Initialize variables
    self.LM=LMData()
    success = self.LM.initializeFromDataFrame(outputData, meanShape, eigenVector, eigenValues)
    if not success:
      return

    self.files = outputData.Sample_name.tolist()
    shape = self.LM.lmOrig.shape
    print('Loaded ' + str(shape[2]) + ' subjects with ' + str(shape[0]) + ' landmark points.')

    # GPA parameters
    self.pcNumber=10
    self.updateList()

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
    self.sampleSizeScaleFactor = logic.dist2(self.rawMeanLandmarks).max()
    print("Scale Factor: " + str(self.sampleSizeScaleFactor))

    for landmarkNumber in range (shape[0]):
      name = str(landmarkNumber+1) #start numbering at 1
      self.meanLandmarkNode.AddControlPoint(self.rawMeanLandmarks[landmarkNumber,:], name)
    self.meanLandmarkNode.SetDisplayVisibility(1)
    self.meanLandmarkNode.LockedOn() #lock position so when displayed they cannot be moved
    self.meanLandmarkNode.EndModify(True)
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
    self.plotButton.enabled = True
    self.lolliButton.enabled = True
    self.plotDistributionButton.enabled = True
    self.plotMeanButton3D.enabled = True
    self.showMeanLabelsButton.enabled = True
    self.selectorButton.enabled = True
    self.landmarkVisualizationType.enabled = True
    self.modelVisualizationType.enabled = True

  def onLoad(self):
    self.initializeOnLoad() #clean up module from previous runs
    logic = GPALogic()

    # get landmarks
    self.LM=LMData()
    lmToExclude=self.excludeLMText.text
    if len(lmToExclude) != 0:
      self.LMExclusionList=lmToExclude.split(",")
      print("Excluded landmarks: ", self.LMExclusionList)
      self.LMExclusionList=[int(x) for x in self.LMExclusionList]
      lmNP=np.asarray(self.LMExclusionList)
    else:
      self.LMExclusionList=[]
    try:
      self.LM.lmOrig, self.landmarkTypeArray = logic.loadLandmarks(self.inputFilePaths, self.LMExclusionList, self.extension)
    except:
      logging.debug('Load landmark data failed: Could not create an array from landmark files')
      return
    shape = self.LM.lmOrig.shape
    print('Loaded ' + str(shape[2]) + ' subjects with ' + str(shape[0]) + ' landmark points.')

    # Do GPA
    self.BoasOption=self.BoasOptionCheckBox.checked
    self.LM.doGpa(self.BoasOption)
    self.LM.calcEigen()
    self.pcNumber=10
    self.updateList()

    #set scaling factor using mean of landmarks
    self.rawMeanLandmarks = self.LM.lmOrig.mean(2)
    logic = GPALogic()
    self.sampleSizeScaleFactor = logic.dist2(self.rawMeanLandmarks).max()
    print("Scale Factor: " + str(self.sampleSizeScaleFactor))

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
    self.meanLandmarkNode.StartModify()
    for landmarkNumber in range(shape[0]):
      name = str(landmarkNumber+1) #start numbering at 1
      self.meanLandmarkNode.AddControlPoint(vtk.vtkVector3d(self.rawMeanLandmarks[landmarkNumber,:]), name)
    self.meanLandmarkNode.EndModify(True)
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
      if hasattr(self, 'factorTableNode'):
        slicer.util.saveNode(self.factorTableNode, self.outputFolder + os.sep + "CovariateTable.csv")
      self.writeAnalysisLogFile(self.LM_dir_name, self.outputFolder, self.files)
      self.openResultsButton.enabled = True
    except:
      logging.debug('Result directory failed: Could not access output folder')
      print("Error creating result directory")

    # Get closest sample to mean
    filename=self.LM.closestSample(self.files)
    self.populateDistanceTable(self.files)
    print("Closest sample to mean:" + filename)

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
    self.plotButton.enabled = True
    self.lolliButton.enabled = True
    self.plotDistributionButton.enabled = True
    self.plotMeanButton3D.enabled = True
    self.showMeanLabelsButton.enabled = True
    self.selectorButton.enabled = True
    self.landmarkVisualizationType.enabled = True
    self.modelVisualizationType.enabled = True


  def initializeOnLoad(self):
    # clear rest of module when starting GPA analysis

    self.grayscaleSelector.setCurrentPath("")
    self.FudSelect.setCurrentPath("")

    self.landmarkVisualizationType.setChecked(True)

    self.slider1.clear()
    self.slider2.clear()

    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    self.scaleSlider.value=3
    self.scaleMeanShapeSlider.value=3
    self.meanShapeColor.color=qt.QColor(250,128,114)

    self.nodeCleanUp()

    # Reset zoom
    if self.widgetZoomFactor > 0:
      cameras=slicer.mrmlScene.GetNodesByClass('vtkMRMLCameraNode')
      for camera in cameras:
        camera.GetCamera().Zoom(1/self.widgetZoomFactor)
      self.widgetZoomFactor = 0

  def writeAnalysisLogFile(self, inputPath, outputPath, files):
    # generate log file
    logFile = open(outputPath+os.sep+"analysis.log","w")
    logFile.write("Date=" + datetime.now().strftime('%Y-%m-%d') + "\n")
    logFile.write("Time=" + datetime.now().strftime('%H:%M:%S') + "\n")
    logFile.write("InputPath=" + inputPath + "\n")
    logFile.write("OutputPath=" + outputPath.replace("\\","/") + "\n")
    logFile.write("Files=")
    for i in range(len(files)-1):
      logFile.write(files[i] + self.extension + ",")
    logFile.write(files[len(files)-1] + self.extension + "\n")
    logFile.write("LM_format="  + self.extension + "\n")
    [pointNumber, dim, subjectNumber] = self.LM.lmOrig.shape
    totalLandmarks = pointNumber + len(self.LMExclusionList)
    logFile.write("NumberLM=" + str(totalLandmarks) + "\n")
    logFile.write("ExcludedLM=")
    exclusions = ",".join(map(str, self.LMExclusionList))
    logFile.write(exclusions + "\n")
    logFile.write("Boas=" + str(not self.BoasOption) + "\n")
    logFile.write("MeanShape=MeanShape.csv"+ "\n")
    logFile.write("eigenvalues=eigenvalues.csv" + "\n")
    logFile.write("eigenvectors=eigenvectors.csv" + "\n")
    logFile.write("OutputData=OutputData.csv" + "\n")
    logFile.write("pcScores=pcScores.csv" + "\n")
    landmarkType_list = ",".join(self.landmarkTypeArray)
    logFile.write("SemiLandmarks= " + landmarkType_list)
    logFile.close()


  # Explore Data callbacks and helpers
  def plot(self):
    logic = GPALogic()
    # get values from box
    xValue=self.XcomboBox.currentIndex
    yValue=self.YcomboBox.currentIndex
    shape = self.LM.lm.shape

    factorIndex = self.selectFactor.currentIndex
    if (factorIndex > 0) and hasattr(self, 'factorTableNode'):
      factorCol = self.factorTableNode.GetTable().GetColumn(factorIndex)
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
    pb1=self.vectorOne.currentIndex
    pb2=self.vectorTwo.currentIndex
    pb3=self.vectorThree.currentIndex

    pcList=[pb1,pb2,pb3]
    logic = GPALogic()

    meanLandmarkNode=slicer.mrmlScene.GetFirstNodeByName('Mean Landmark Node')
    meanLandmarkNode.SetDisplayVisibility(1)
    componentNumber = 1
    for pc in pcList:
      logic.lollipopGraph(self.LM, self.rawMeanLandmarks, pc, self.sampleSizeScaleFactor, componentNumber, self.TwoDType.isChecked())
      componentNumber+=1

  def toggleMeanPlot(self):
    visibility = self.meanLandmarkNode.GetDisplayVisibility()
    if visibility:
      visibility = self.meanLandmarkNode.SetDisplayVisibility(False)
      if hasattr(self, 'cloneLandmarkNode'):
        self.cloneLandmarkNode.SetDisplayVisibility(False)
    else:
      visibility = self.meanLandmarkNode.SetDisplayVisibility(True)
      # refresh color and scale from GUI
      self.meanLandmarkNode.GetDisplayNode().SetGlyphScale(self.scaleMeanShapeSlider.value)
      color = self.meanShapeColor.color
      self.meanLandmarkNode.GetDisplayNode().SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])
      # refresh PC warped mean node
      if hasattr(self, 'cloneLandmarkNode'):
        self.cloneLandmarkNode.SetDisplayVisibility(True)
        self.cloneLandmarkDisplayNode.SetGlyphScale(self.scaleMeanShapeSlider.value)
        self.cloneLandmarkDisplayNode.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])

  def toggleMeanLabels(self):
    visibility = self.meanLandmarkNode.GetDisplayNode().GetPointLabelsVisibility()
    if visibility:
      self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(0)
      if hasattr(self, 'cloneLandmarkNode'):
        self.cloneLandmarkDisplayNode.SetPointLabelsVisibility(0)
    else:
      self.meanLandmarkNode.GetDisplayNode().SetPointLabelsVisibility(1)
      self.meanLandmarkNode.GetDisplayNode().SetTextScale(3)
      if hasattr(self, 'cloneLandmarkNode'):
        self.cloneLandmarkDisplayNode.SetPointLabelsVisibility(1)
        self.cloneLandmarkDisplayNode.SetTextScale(3)

  def toggleMeanColor(self):
    color = self.meanShapeColor.color
    self.meanLandmarkNode.GetDisplayNode().SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])
    if hasattr(self, 'cloneLandmarkNode'):
      self.cloneLandmarkDisplayNode.SetSelectedColor([color.red()/255,color.green()/255,color.blue()/255])

  def scaleMeanGlyph(self):
    scaleFactor = self.sampleSizeScaleFactor/10
    self.meanLandmarkNode.GetDisplayNode().SetGlyphScale(self.scaleMeanShapeSlider.value)
    if hasattr(self, 'cloneLandmarkNode'):
      self.cloneLandmarkDisplayNode.SetGlyphScale(self.scaleMeanShapeSlider.value)

  def onModelSelected(self):
    self.selectorButton.enabled = bool( self.grayscaleSelector.currentPath and self.FudSelect.currentPath)

  def onToggleVisualization(self):
    if self.landmarkVisualizationType.isChecked():
      self.selectorButton.enabled = True
    else:
      self.grayscaleSelector.enabled = True
      self.FudSelect.enabled = True
      print(self.grayscaleSelector.currentPath)
      print(self.FudSelect.currentPath )
      self.selectorButton.enabled = bool( self.grayscaleSelector.currentPath != "") and bool(self.FudSelect.currentPath != "")



  def onPlotDistribution(self):
    self.scaleSlider.enabled = True
    if self.NoneType.isChecked():
      self.unplotDistributions()
    elif self.CloudType.isChecked():
      self.plotDistributionCloud()
    else:
      self.plotDistributionGlyph(2*self.scaleSlider.value)

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

  def plotDistributionCloud(self):
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
    sphereSource.SetRadius(self.sampleSizeScaleFactor/300)
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
    self.scaleMeanShapeSlider.value=0
    for landmark in range(i):
      pt=self.rawMeanLandmarks[landmark,:]
      points.SetPoint(landmark,pt)
      scales.InsertNextValue(sliderScale*(varianceMat[landmark,0]+varianceMat[landmark,1]+varianceMat[landmark,2])/3)
      tensors.InsertTuple9(landmark,sliderScale*varianceMat[landmark,0],0,0,0,sliderScale*varianceMat[landmark,1],0,0,0,sliderScale*varianceMat[landmark,2])
      index.InsertNextValue(landmark+1)

    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().AddArray(index)

    if self.EllipseType.isChecked():
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
    self.initializeOnSelect()
    self.cloneLandmarkNode = self.copyLandmarkNode
    self.cloneLandmarkNode.CreateDefaultDisplayNodes()
    self.cloneLandmarkDisplayNode = self.cloneLandmarkNode.GetDisplayNode()
    if self.modelVisualizationType.isChecked():
      # get landmark node selected
      logic = GPALogic()
      self.sourceLMNode= slicer.util.loadMarkups(self.FudSelect.currentPath)
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
      self.modelNode=slicer.util.loadModel(self.grayscaleSelector.currentPath)
      GPANodeCollection.AddItem(self.modelNode)
      self.modelDisplayNode = self.modelNode.GetDisplayNode()
      self.modelNode.SetAndObserveTransformNodeID(self.transformMeanNode.GetID())
      slicer.vtkSlicerTransformLogic().hardenTransform(self.modelNode)

      # create a PC warped model as clone of the selected model node
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      itemIDToClone = shNode.GetItemByDataNode(self.modelNode)
      clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
      self.cloneModelNode = shNode.GetItemDataNode(clonedItemID)
      self.cloneModelNode.SetName('PCA Warped Volume')
      self.cloneModelDisplayNode =  self.cloneModelNode.GetDisplayNode()
      self.cloneModelDisplayNode.SetColor([0,0,1])
      GPANodeCollection.AddItem(self.cloneModelNode)
      visibility = self.meanLandmarkNode.GetDisplayVisibility()
      self.cloneLandmarkNode.SetDisplayVisibility(visibility)

      #Clean up
      GPANodeCollection.RemoveItem(self.sourceLMNode)
      slicer.mrmlScene.RemoveNode(self.sourceLMNode)

    else:
      self.cloneLandmarkNode.SetDisplayVisibility(1)
      self.meanLandmarkNode.SetDisplayVisibility(1)

    #set mean landmark color and scale from GUI
    self.scaleMeanGlyph()
    self.toggleMeanColor()
    visibility = self.meanLandmarkNode.GetDisplayNode().GetPointLabelsVisibility()
    self.cloneLandmarkDisplayNode.SetPointLabelsVisibility(visibility)
    self.cloneLandmarkDisplayNode.SetTextScale(3)

    if self.scaleMeanShapeSlider.value == 0:  # If the scale is set to 0, reset to default scale
      self.scaleMeanShapeSlider.value = 3

    self.cloneLandmarkDisplayNode.SetGlyphScale(self.scaleMeanShapeSlider.value)

    #apply custom layout
    self.assignLayoutDescription()

    # Set up transform for PCA warping
    self.transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'PC TPS Transform')
    GPANodeCollection.AddItem(self.transformNode)

    # Enable PCA warping and recording
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.applyEnabled = True
    self.startRecordButton.enabled = True

  def onApply(self):
    pc1=self.slider1.boxValue()
    pc2=self.slider2.boxValue()
    pcSelected=[pc1,pc2]

    # get scale values for each pc.
    sf1=self.slider1.sliderValue()
    sf2=self.slider2.sliderValue()
    scaleFactors=np.zeros(2)
    scaleFactors[0]=sf1/100.0
    scaleFactors[1]=sf2/100.0

    j=0
    for i in pcSelected:
      if i==0:
       scaleFactors[j]=0.0
      j=j+1

    logic = GPALogic()
    #get target landmarks
    self.LM.ExpandAlongPCs(pcSelected,scaleFactors, self.sampleSizeScaleFactor)
    target=self.rawMeanLandmarks+self.LM.shift

    if hasattr(self, 'cloneModelNode'):
      targetLMVTK=logic.convertNumpyToVTK(target)
      sourceLMVTK=logic.convertNumpyToVTK(self.rawMeanLandmarks)

      #Set up TPS
      VTKTPS = vtk.vtkThinPlateSplineTransform()
      VTKTPS.SetSourceLandmarks( sourceLMVTK )
      VTKTPS.SetTargetLandmarks( targetLMVTK )
      VTKTPS.SetBasisToR()  # for 3D transform

      #Connect transform to model
      self.transformNode.SetAndObserveTransformToParent( VTKTPS )
      self.cloneLandmarkNode.SetAndObserveTransformNodeID(self.transformNode.GetID())
      self.cloneModelNode.SetAndObserveTransformNodeID(self.transformNode.GetID())

    else:
      index = 0
      for targetLandmark in target:
        self.cloneLandmarkNode.SetNthControlPointPosition(index, targetLandmark)
        index+=1


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
    browserLogic.AddSynchronizedNode(self.modelSequence,self.cloneModelNode,browserNode)
    browserLogic.AddSynchronizedNode(self.modelSequence,self.cloneLandmarkNode,browserNode)
    browserLogic.AddSynchronizedNode(self.transformSequence,self.transformNode,browserNode)
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
    self.stopRecordButton.enabled = True
    self.startRecordButton.enabled = False

  def onStopRecording(self):
    browserWidget=slicer.modules.sequences.widgetRepresentation()
    recordWidget = browserWidget.findChild('qMRMLSequenceBrowserPlayWidget')
    recordWidget.setRecordingEnabled(0)
    slicer.util.selectModule(slicer.modules.sequences)
    self.stopRecordButton.enabled = False
    self.startRecordButton.enabled = True

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
      tubeFilter.SetRadius(scaleFactor/500)
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
    return LM+tmp*scaleFactor/3.0

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
