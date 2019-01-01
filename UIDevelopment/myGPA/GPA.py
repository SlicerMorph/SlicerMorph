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

import support.vtk_lib as vtk_lib
import support.gpa_lib as gpa_lib
import  numpy as np

#
# GPA
#

class GPA(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "GPA" # TODO make this more human readable by adding spaces
    self.parent.categories = ["GPA Toolbox"]
    self.parent.dependencies = []
    self.parent.contributors = ["Ryan Young, Sara Rolfe, Murat Maga"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module preforms standard Generalized Procrustes Analysis (GPA) based on (citation)
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

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
    
  def __init__(self, parent=None):
    super(sliderGroup, self).__init__( parent)

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

    # connect to eachother
    self.slider.valueChanged.connect(self.spinBox.setValue)
    self.spinBox.valueChanged.connect(self.slider.setValue)
    # self.label.connect(self.comboBox ,self.comboBox.currentIndexChanged, self.label.setText('test1'))

    # layout
    slidersLayout = qt.QGridLayout()
    slidersLayout.addWidget(self.slider,1,2)
    slidersLayout.addWidget(self.comboBox,1,1)
    slidersLayout.addWidget(self.spinBox,1,3)
    self.setLayout(slidersLayout) 

class LMData:
  def __init__(self):
    self.lm=0
    self.lmRaw=0
    self.lmOrig=0
    self.val=0
    self.vec=0
    self.alignCoords=0
    self.mShape=0
    self.tangentCoord=0
    self.shift=0
    self.centriodSize=0

  def calcLMVariation(self):
    i,j,k=self.lmRaw.shape
    varianceMat=np.zeros((i,j))
    for subject in range(k):
      tmp=pow((self.lmRaw[:,:,subject]-self.mShape),2)
      varianceMat=varianceMat+tmp
    varianceMat = np.sqrt(varianceMat/(k-1))
    return varianceMat
    
  def doGpa(self):
    i,j,k=self.lmRaw.shape
    self.centriodSize=np.zeros(k)
    for i in range(k):
      self.centriodSize[i]=np.linalg.norm(self.lmRaw[:,:,i]-self.lmRaw[:,:,i].mean(axis=0))
    self.lm, self.mShape=gpa_lib.doGPA(self.lmRaw)

  def calcEigen(self):
    twoDim=gpa_lib.makeTwoDim(self.lm)
    mShape=gpa_lib.calcMean(twoDim)
    covMatrix=gpa_lib.calcCov(twoDim)
    self.val, self.vec=np.linalg.eig(covMatrix)
    self.vec=np.real(self.vec) 
    # scale eigen Vectors
    i,j =self.vec.shape
    # for q in range(j):
    #     self.vec[:,q]=self.vec[:,q]/np.linalg.norm(self.vec[:,q])

  def ExpandAlongPCs(self, numVec,scaleFactor,SampleScaleFactor):
    b=0
    i,j,k=self.lm.shape 
    tmp=np.zeros((i,j)) 
    points=np.zeros((i,j))   
    self.vec=np.real(self.vec)  
    # scale eigenvector
    for y in numVec:
      for s in scaleFactor:
          #print y,s
        if j==3 and y is not 0:
            #print self.vec[0:i,y], tmp[:,0]
          tmp[:,0]=tmp[:,0]+float(s)*self.vec[0:i,y]*SampleScaleFactor
          tmp[:,1]=tmp[:,1]+float(s)*self.vec[i:2*i,y]*SampleScaleFactor
          tmp[:,2]=tmp[:,2]+float(s)*self.vec[2*i:3*i,y]*SampleScaleFactor
    
    self.shift=tmp

  def writeOutData(self,outputFolder,files):
    np.savetxt(outputFolder+os.sep+"MeanShape.csv", self.mShape, delimiter=",")
    np.savetxt(outputFolder+os.sep+"eigenvector.csv", self.vec, delimiter=",")
    np.savetxt(outputFolder+os.sep+"eigenvalues.csv", self.val, delimiter=",")

    percentVar=self.val/self.val.sum()
    self.procdist=gpa_lib.procDist(self.lm, self.mShape)
    files=np.array(files)
    i=files.shape
    files=files.reshape(i[0],1)
    k,j,i=self.lmRaw.shape

    coords=gpa_lib.makeTwoDim(self.lm)
    self.procdist=self.procdist.reshape(i,1)
    self.centriodSize=self.centriodSize.reshape(i,1)
    tmp=np.column_stack((files, self.procdist, self.centriodSize, np.transpose(coords)))
    header=np.array(['Sample_name','proc_dist','centeroid'])
    i1,j=tmp.shape
    coodrsL=(j-3)/3.0
    l=np.zeros(int(3*coodrsL))

    l=list(l)

    for x in range(int(coodrsL)):
      loc=x+1
      l[3*x]="x"+str(loc)
      l[3*x+1]="y"+str(loc)
      l[3*x+2]="z"+str(loc)
    l=np.array(l)
    header=np.column_stack((header.reshape(1,3),l.reshape(1,int(3*coodrsL))))
    tmp1=np.vstack((header,tmp))
    np.savetxt(outputFolder+os.sep+"OutputData.csv", tmp1, fmt="%s" , delimiter=",")

    # calc PC scores
    twoDcoors=gpa_lib.makeTwoDim(self.lm)
    scores=np.dot(np.transpose(twoDcoors),self.vec)
    scores=np.transpose(np.real(scores))
    
    scores=np.vstack((files.reshape(1,i),scores))
    np.savetxt(outputFolder+os.sep+"pcScores.csv", scores, fmt="%s", delimiter=",")

  def closestSample(self,files):
    import operator
    min_index, min_value = min(enumerate(self.procdist), key=operator.itemgetter(1))
    tmp=files[min_index]
   # print "The closest sample to the mean shape is:", tmp[:-5]
    return tmp[:-5]

  def calcEndpoints(self,LM,pc, scaleFactor, MonsterObj):
    i,j=LM.shape
    tmp=np.zeros((i,j))
    tmp[:,0]=self.vec[0:i,pc]
    tmp[:,1]=self.vec[i:2*i,pc]
    tmp[:,2]=self.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3.0

class GPAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def textIn(self,label, dispText, toolTip):
    """ a function to set up the appearnce of a QlineEdit widget.
    the widget is returned.
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
    
  def selectLandmarkFile(self):
    self.LM_dir_name=qt.QFileDialog().getExistingDirectory()
    self.LMText.setText(self.LM_dir_name)
      
  def selectOutputFolder(self):
    self.outputFolder=qt.QFileDialog().getExistingDirectory()
    self.outText.setText(self.outputFolder)

  def updateList(self):
    i,j,k=self.LM.lm.shape
    self.PCList=[]
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.slider3.populateComboBox(self.PCList)
    self.slider4.populateComboBox(self.PCList)
    self.slider5.populateComboBox(self.PCList)
    self.PCList.append('None')
    self.LM.val=np.real(self.LM.val)
    percentVar=self.LM.val/self.LM.val.sum()
    #percentVar=np.real(percentVar)
    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    self.vectorOne.addItem('None')
    self.vectorTwo.addItem('None')
    self.vectorThree.addItem('None')
    for x in range(10):
      tmp="{:.1f}".format(percentVar[x]*100) 
      string='PC '+str(x+1)+': '+str(tmp)+"%" +" var"
      self.PCList.append(string)
      self.XcomboBox.addItem(string)
      self.YcomboBox.addItem(string)
      self.vectorOne.addItem(string)
      self.vectorTwo.addItem(string)
      self.vectorThree.addItem(string)
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.slider3.populateComboBox(self.PCList)
    self.slider4.populateComboBox(self.PCList)
    self.slider5.populateComboBox(self.PCList)

  def onLoad(self):
    logic = GPALogic()
    #logic.run(self.inputSelector.currentNode(), self.outputSelector.currentNode(), imageThreshold, enableScreenshotsFlag)
    self.LM=LMData()
    lmToExclude=self.excludeLMText.text
    if len(lmToExclude) != 0:
      tmp=lmToExclude.split(",")
      print len(tmp)
      tmp=[np.int(x) for x in tmp]
      lmNP=np.asarray(tmp)
    else:
      tmp=[]
    self.LM.lmOrig, files = logic.mergeMatchs(self.LM_dir_name, tmp)
    self.LM.lmRaw, files = logic.mergeMatchs(self.LM_dir_name, tmp)
    self.LM.doGpa()
    self.LM.calcEigen()
    self.updateList()
    self.LM.writeOutData(self.outputFolder, files)
    #print files
    filename=self.LM.closestSample(files)
    self.volumeRecText.setText(filename)
    print("Closest to mean:")
    print(filename)
    
  def plot(self):
    logic = GPALogic()
    try:
      # get values from boxs
      xValue=self.XcomboBox.currentIndex
      yValue=self.YcomboBox.currentIndex

      # get data to plot
      data=gpa_lib.plotTanProj(self.LM.lm,xValue,yValue)
      #print(data)

      # plot it
      logic.makeScatterPlot(data,'PCA Scatter Plots',"PC"+str(xValue+1),"PC"+str(yValue+1))

    except AttributeError:
      qt.QMessageBox.critical(
      slicer.util.mainWindow(),
    'Error', 'Please make sure a Landmark folder has been loaded  !')
    
  def lolliPlot(self):
    pb1=self.vectorOne.currentIndex
    pb2=self.vectorTwo.currentIndex
    pb3=self.vectorThree.currentIndex

    pcList=[pb1,pb2,pb3]
    logic = GPALogic()
    logic.lollipopGraph(self.LM, self.sourceLMNode, pcList, self.sampleSizeScaleFactor)    
  def reset(self):
    # delete the two data objects

    # reset text fields
    self.outputFolder=None
    self.outText.setText(" ")
    self.LM_dir_name=None
    self.LMText.setText(" ")

    self.volumeRecText.setText(" ")

    self.slider1.clear()
    self.slider2.clear()
    self.slider3.clear()
    self.slider4.clear()
    self.slider5.clear()

    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    try:
      if self.LM is not None:
        del self.LM
    except:
      pass
    try:
      if self.volumes is not None:
        del self.volumes
    except:
      pass
    slicer.mrmlScene.Clear(0)
    # could delete created volumes and chart nodes  
    
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # self.input_file=[]
    self.StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
       
    inbutton=ctk.ctkCollapsibleButton()
    inbutton.text="Setup Analysis"
    inputLayout= qt.QGridLayout(inbutton)

    self.LMText, volumeInLabel, self.LMbutton=self.textIn('Landmark Folder')
    inputLayout.addWidget(self.LMText,1,2)
    inputLayout.addWidget(volumeInLabel,1,1)
    inputLayout.addWidget(self.LMbutton,1,3)
    self.layout.addWidget(inbutton)
    self.LMbutton.connect('clicked(bool)', self.selectLandmarkFile)

    self.outText, outLabel, self.outbutton=self.textIn('Output folder prefix')
    inputLayout.addWidget(self.outText,2,2)
    inputLayout.addWidget(outLabel,2,1)
    inputLayout.addWidget(self.outbutton,2,3)
    self.layout.addWidget(inbutton)
    self.outbutton.connect('clicked(bool)', self.selectOutputFolder)

    self.excludeLMLabel=qt.QLabel('Exclude landmarks')
    inputLayout.addWidget(self.excludeLMLabel,3,1)

    self.excludeLMText=qt.QLineEdit()
    self.excludeLMText.setToolTip("No spaces. Seperate numbers by commas.  Exsampe:  51,52")
    inputLayout.addWidget(self.excludeLMText,3,2,1,2)

    # node selector tab
    volumeButton=ctk.ctkCollapsibleButton()
    volumeButton.text="Setup 3D Visualization"
    volumeLayout= qt.QGridLayout(volumeButton)

    self.volumeRecText, VolumeRecLabel, voluemrecbutton=self.textIn('Sample Closest to the mean')
    volumeLayout.addWidget(self.volumeRecText,1,2)
    volumeLayout.addWidget(VolumeRecLabel,1,1)


    self.grayscaleSelectorLabel = qt.QLabel("Specify Reference Model for 3D Vis.")
    self.grayscaleSelectorLabel.setToolTip( "Select the model node for display")
    volumeLayout.addWidget(self.grayscaleSelectorLabel,2,1)

    self.grayscaleSelector = slicer.qMRMLNodeComboBox()
    self.grayscaleSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    #self.grayscaleSelector.addAttribute( "vtkMRMLModelNode", "LabelMap", 0 )
    self.grayscaleSelector.selectNodeUponCreation = False
    self.grayscaleSelector.addEnabled = False
    self.grayscaleSelector.removeEnabled = False
    self.grayscaleSelector.noneEnabled = True
    self.grayscaleSelector.showHidden = False
    #self.grayscaleSelector.showChildNodeTypes = False
    self.grayscaleSelector.setMRMLScene( slicer.mrmlScene )
    volumeLayout.addWidget(self.grayscaleSelector,2,2,1,3)


    self.FudSelectLabel = qt.QLabel("Landmark List: ")
    self.FudSelectLabel.setToolTip( "Select the glandmark list")
    self.FudSelect = slicer.qMRMLNodeComboBox()
    self.FudSelect.nodeTypes = ( ('vtkMRMLMarkupsFiducialNode'), "" )
    #self.FudSelect.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.FudSelect.selectNodeUponCreation = False
    self.FudSelect.addEnabled = False
    self.FudSelect.removeEnabled = False
    self.FudSelect.noneEnabled = True
    self.FudSelect.showHidden = False
    self.FudSelect.showChildNodeTypes = False
    self.FudSelect.setMRMLScene( slicer.mrmlScene )
    volumeLayout.addWidget(self.FudSelectLabel,3,1)
    volumeLayout.addWidget(self.FudSelect,3,2,1,3)

    
    selectorButton = qt.QPushButton("Select")
    selectorButton.checkable = True
    selectorButton.setStyleSheet(self.StyleSheet)
    volumeLayout.addWidget(selectorButton,5,1,1,3)
    selectorButton.connect('clicked(bool)', self.onSelect)

    self.layout.addWidget(volumeButton)

    #Apply Button 
    loadButton = qt.QPushButton("Execute GPA + PCA")
    loadButton.checkable = True
    loadButton.setStyleSheet(self.StyleSheet)
    inputLayout.addWidget(loadButton,5,1,1,3)
    loadButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    loadButton.connect('clicked(bool)', self.onLoad)
    
    # adjust PC sectore
    vis=ctk.ctkCollapsibleButton()
    vis.text='PCA Visualization Parameters'
    visLayout= qt.QGridLayout(vis)

    self.PCList=[]
    self.slider1=sliderGroup()
    self.slider1.connectList(self.PCList)
    visLayout.addWidget(self.slider1,3,1,1,2)

    self.slider2=sliderGroup()
    self.slider2.connectList(self.PCList)
    visLayout.addWidget(self.slider2,4,1,1,2)

    self.slider3=sliderGroup()
    self.slider3.connectList(self.PCList)
    visLayout.addWidget(self.slider3,5,1,1,2)

    self.slider4=sliderGroup()
    self.slider4.connectList(self.PCList)
    visLayout.addWidget(self.slider4,6,1,1,2)

    self.slider5=sliderGroup()
    self.slider5.connectList(self.PCList)
    visLayout.addWidget(self.slider5,7,1,1,2)

    self.layout.addWidget(vis)

        
    #Apply Button 
    applyButton = qt.QPushButton("Apply")
    applyButton.checkable = True
    applyButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(applyButton)
    applyButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    applyFrame=qt.QFrame(self.parent)
    applyButton.connect('clicked(bool)', self.onApply)
    visLayout.addWidget(applyButton,8,1,1,2)

    #PC plot section
    plotFrame=ctk.ctkCollapsibleButton()
    plotFrame.text="PCA Scatter Plot Options"
    plotLayout= qt.QGridLayout(plotFrame)
    self.layout.addWidget(plotFrame)

    self.XcomboBox=qt.QComboBox()
    Xlabel=qt.QLabel("X Axis")
    plotLayout.addWidget(Xlabel,1,1)
    plotLayout.addWidget(self.XcomboBox,1,2,1,3)

    self.YcomboBox=qt.QComboBox()
    Ylabel=qt.QLabel("Y Axis")
    plotLayout.addWidget(Ylabel,2,1)
    plotLayout.addWidget(self.YcomboBox,2,2,1,3)

    plotButton = qt.QPushButton("Scatter Plot")
    plotButton.checkable = True
    plotButton.setStyleSheet(self.StyleSheet)
    plotButton.toolTip = "Plot PCs"
    plotLayout.addWidget(plotButton,3,1,1,4)
    plotButton.connect('clicked(bool)', self.plot)

    # Lollipop Plot Section

    lolliFrame=ctk.ctkCollapsibleButton()
    lolliFrame.text="Lollipop Plot Options"
    lolliLayout= qt.QGridLayout(lolliFrame)
    self.layout.addWidget(lolliFrame)

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

    lolliButton = qt.QPushButton("Lollipop Plot")
    lolliButton.checkable = True
    lolliButton.setStyleSheet(self.StyleSheet)
    lolliButton.toolTip = "Plot PC vectors"
    lolliLayout.addWidget(lolliButton,4,1,1,4)
    lolliButton.connect('clicked(bool)', self.lolliPlot)
 
 # Landmark Distribution Section
    distributionFrame=ctk.ctkCollapsibleButton()
    distributionFrame.text="Landmark Distribution Plot Options"
    distributionLayout= qt.QGridLayout(distributionFrame)
    self.layout.addWidget(distributionFrame)

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
    
    plotDistributionButton = qt.QPushButton("Plot LM Distribution")
    plotDistributionButton.checkable = True
    plotDistributionButton.setStyleSheet(self.StyleSheet)
    plotDistributionButton.toolTip = "Visualize distribution of landmarks from all subjects"
    distributionLayout.addWidget(plotDistributionButton,5,1,1,4)
    plotDistributionButton.connect('clicked(bool)', self.onPlotDistribution)
    
    resetButton = qt.QPushButton("Reset Scene")
    resetButton.checkable = True
    resetButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(resetButton)
    resetButton.toolTip = "Push to reset all fields."
    resetButton.connect('clicked(bool)', self.reset)

    self.layout.addStretch(1)

    
  def cleanup(self):
    pass

  def onSelect(self):
    self.modelNode=self.grayscaleSelector.currentNode()
    self.modelDisplayNode = self.modelNode.GetDisplayNode()
    logic = GPALogic()
    self.sourceLMNode=self.FudSelect.currentNode()
    self.sourceLMnumpy=logic.convertFudicialToNP(self.sourceLMNode)
    self.sampleSizeScaleFactor = logic.dist2(self.sourceLMnumpy).max()

    self.transformNode=slicer.vtkMRMLTransformNode()
    self.transformNode.SetName("TPSTransformNode")
    slicer.mrmlScene.AddNode(self.transformNode)
    print("completed selections")

  def onApply(self):
    pc1=self.slider1.boxValue()
    pc2=self.slider2.boxValue()
    pc3=self.slider3.boxValue()
    pc4=self.slider4.boxValue()
    pc5=self.slider5.boxValue()
    pcSelected=[pc1,pc2,pc3,pc4,pc5]

    # get scale values for each pc.
    sf1=self.slider1.sliderValue()
    sf2=self.slider2.sliderValue()
    sf3=self.slider3.sliderValue()
    sf4=self.slider4.sliderValue()
    sf5=self.slider5.sliderValue()
    scaleFactors=np.zeros((5))
    scaleFactors[0]=sf1/100.0
    scaleFactors[1]=sf2/100.0
    scaleFactors[2]=sf3/100.0
    scaleFactors[3]=sf4/100.0
    scaleFactors[4]=sf5/100.0

    j=0
    for i in pcSelected:
      if i==0:
       scaleFactors[j]=0.0
      j=j+1

    logic = GPALogic()
    #get target landmarks
    self.LM.ExpandAlongPCs(pcSelected,scaleFactors, self.sampleSizeScaleFactor)
    sourceLMNP=logic.convertFudicialToNP(self.sourceLMNode)
    target=sourceLMNP+self.LM.shift
    targetLMVTK=logic.convertNumpyToVTK(target)
    sourceLMVTK=logic.convertNumpyToVTK(sourceLMNP)
    
    #Set up TPS
    VTKTPS = vtk.vtkThinPlateSplineTransform()
    VTKTPS.SetSourceLandmarks( sourceLMVTK )
    VTKTPS.SetTargetLandmarks( targetLMVTK )
    VTKTPS.SetBasisToR()  # for 3D transform

    #Connect transform to model
    self.transformNode.SetAndObserveTransformToParent( VTKTPS )
    self.modelNode.SetAndObserveTransformNodeID(self.transformNode.GetID())
    
  def onPlotDistribution(self):
    if self.CloudType.isChecked():
      self.plotDistributionCloud()
    else: 
      self.plotDistributionGlyph()
      
  def plotDistributionCloud(self):
    i,j,k=self.LM.lmRaw.shape
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
        indexes.InsertNextValue(landmark)
        pointCounter+=1
    
    #add points to polydata
    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().SetScalars(indexes)
    
    #set up glyph for visualizing point cloud
    sphereSource = vtk.vtkSphereSource()
    glyph = vtk.vtkGlyph3D()
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)   
    glyph.ScalingOff()    
    glyph.Update()
  
    #display
    modelNode = slicer.vtkMRMLModelNode()
    modelNode.SetName('Landmark Variance')
    slicer.mrmlScene.AddNode(modelNode)
    modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
    
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('LM Index')
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    slicer.mrmlScene.AddNode(modelDisplayNode)
    modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
    modelNode.SetAndObservePolyData(glyph.GetOutput())
    
  def plotDistributionGlyph(self):
    varianceMat = self.LM.calcLMVariation()
    i,j,k=self.LM.lmRaw.shape
    pt=[0,0,0]
    #set up vtk point array for each landmark point
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(i)
    scales = vtk.vtkDoubleArray()
    scales.SetName("Scales")

    #set up tensor array to scale ellipses
    tensors = vtk.vtkDoubleArray()
    tensors.SetNumberOfTuples(i)
    tensors.SetNumberOfComponents(9)
    tensors.SetName("Tensors")

    for landmark in range(i):
      pt=self.sourceLMnumpy[landmark,:]
      points.SetPoint(landmark,pt)
      scales.InsertNextValue(self.sampleSizeScaleFactor*(varianceMat[landmark,0]+varianceMat[landmark,1]+varianceMat[landmark,2])/3)
      tensors.InsertTuple9(landmark,self.sampleSizeScaleFactor*varianceMat[landmark,0],0,0,0,self.sampleSizeScaleFactor*varianceMat[landmark,1],0,0,0,self.sampleSizeScaleFactor*varianceMat[landmark,2])

    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().SetScalars(scales)
    polydata.GetPointData().SetTensors(tensors)

    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(64)
    sphereSource.SetPhiResolution(64)

    if self.EllipseType.isChecked():
      glyph = vtk.vtkTensorGlyph()
      glyph.ExtractEigenvaluesOff()
    else:
      glyph = vtk.vtkGlyph3D()
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)
    glyph.Update()

    modelNode = slicer.vtkMRMLModelNode()
    modelNode.SetName('Landmark Variance')
    slicer.mrmlScene.AddNode(modelNode)
    modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('Scales')
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    slicer.mrmlScene.AddNode(modelDisplayNode)
    modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
    modelNode.SetAndObservePolyData(glyph.GetOutput())


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

  def hasImageData(self,volumeNode):
    """This is an example logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      logging.debug('hasImageData failed: no volume node')
      return False
    if volumeNode.GetImageData() is None:
      logging.debug('hasImageData failed: no image data in volume node')
      return False
    return True

  def isValidInputOutputData(self, inputVolumeNode, outputVolumeNode):
    """Validates if the output is not the same as input
    """
    if not inputVolumeNode:
      logging.debug('isValidInputOutputData failed: no input volume node defined')
      return False
    if not outputVolumeNode:
      logging.debug('isValidInputOutputData failed: no output volume node defined')
      return False
    if inputVolumeNode.GetID()==outputVolumeNode.GetID():
      logging.debug('isValidInputOutputData failed: input and output volume is the same. Create a new volume for output to avoid this error.')
      return False
    return True

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

  def mergeMatchs(self, topDir, lmToRemove, suffix=".fcsv"):
    # initial data array
    dirs, files=self.walk_dir(topDir)
    matchList, noMatch=self.createMatchList(topDir, "fcsv")
    landmarks=self.initDataArray(dirs,files[0],len(matchList))
    matchedfiles=[]
    for i in range(len(matchList)):
      tmp1=self.importLandMarks(matchList[i]+".fcsv")
      landmarks[:,:,i]=tmp1
      matchedfiles.append(os.path.basename(matchList[i]))
    j=len(lmToRemove)
    for i in range(j):
      landmarks=np.delete(landmarks,(np.int(lmToRemove[i])-1),axis=0)    
    return landmarks, matchedfiles
   
  def createMatchList(self, topDir,suffix):
    l=[]
    for root, dirs, files in os.walk(topDir):
      for name in files:
        if fnmatch.fnmatch(name,"*"+suffix):
          l.append(os.path.join(root, name[:-5]))
    matchList=[]
    from sets import Set
    noMatchList=Set()
    for name1 in l:
      for name2 in l:
        if fnmatch.fnmatch(name2,name1[:-1]+"*2"):
          if not fnmatch.fnmatch(name2,name1):
            tmp=[name1,name2]
            matchList.append(tmp)
    #create list of no matchs
    #flatten matchlist
    matches=[item for sublist in matchList for item in sublist]
    noMatchs=[]
    #print "lenght l",len(l)
    for items in l:
     if items not in matches:
       noMatchs.append(items)

    return matches, noMatchs
  def importLandMarks(self, filePath):
    """Imports the landmarks from a .fcsv file. Does not import sample if a  landmark is -1000
    Adjusts the resolution is log(nhrd) file is found returns kXd array of landmark data. k=# of landmarks d=dimension
    """
    # import data file
    datafile=open(filePath,'r')
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

  def walk_dir(self, top_dir):
    """
    Returns a list of all fcsv files in a diriectory, including sub-directories.
    """
    dir_to_explore=[]
    file_to_open=[]
    for path, dir, files in os.walk(top_dir):
      for filename in files:
        if fnmatch.fnmatch(filename,"*.fcsv"):
          #print filename
          dir_to_explore.append(path)
          file_to_open.append(filename)
    return dir_to_explore, file_to_open

  def initDataArray(self, dirs, file,k):  
    """
    returns an np array for the storage of the landmarks.
    """
    j=3 
    # import data file
    datafile=open(dirs[0]+os.sep+file,'r')
    data=[]
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):
        # print row
        data.append(row.strip().split(','))
    i= len(data)
    landmarks=np.zeros(shape=(i,j,k))
    return landmarks

  def importAllLandmarks(self, inputDirControl, outputFolder):
    """
    Import all of the landmarks.
    Controls are stored frist, then experimental landmarks, in a np array
    Returns the landmark array and the number of experimetnal and control samples repectively.
    """
    # get files and directories
    dirs, files=self.walk_dir(inputDirControl)
    # print dirs, files
    with open(outputFolder+os.sep+"filenames.txt",'w') as f:
      for i in range(len(files)):
        tmp=files[i]
        f.write(tmp[:-5]+"\n")
    # initilize and fill control landmakrs
    landmarksControl=self.initDataArray(dirs,files[0])
    iD,jD,kD=landmarksControl.shape
    nControl=kD
    iD=iD.__int__();jD=jD.__int__();kD=kD.__int__()
    # fill landmarks
    for i in range(0,len(files)):
      tmp=self.importLandMarks(dirs[i]+os.sep+files[i])
      #  check that landmarks where imported, if not delete zeros matrix
      if type(tmp) is not 'NoneType':
        it,at=tmp.shape
        it=it.__int__(); at=at.__int__()
        if it == iD and at == jD:
          landmarksControl[:,:,i]=tmp
        else:
          np.delete(landmarksControl,i,axis=2)
      else:
          np.delete(landmarksControl,i,axis=2)

    return landmarksControl, files

    # function with vtk and tps
    # Random Function
  def dist(self, a):
    """
    Computes the ecuideain distance matrix for nXK points in a 3D space. So the input matrix is nX3xk
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
    Computes the ecuideain distance matrix for n points in a 3D space
    Returns a nXn matrix 
     """
    id,jd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1))
    dx=fnx(a[:,0])
    dy=fnx(a[:,1])
    dz=fnx(a[:,2])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

  #plotting functions
  def makeScatterPlot(self, data,title,xAxis,yAxis):
    numPoints = len(data)
    print(data.shape)
    
    tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode")
    table = tableNode.GetTable()

    arrX = vtk.vtkFloatArray()
    arrX.SetName(xAxis)
    table.AddColumn(arrX)

    arrY1 = vtk.vtkFloatArray()
    arrY1.SetName(yAxis)
    table.AddColumn(arrY1)
    
    table.SetNumberOfRows(numPoints)
    for i in range(numPoints):
      print(data[i,0])    
      table.SetValue(i, 0, data[i,0])
      table.SetValue(i, 1, data[i,1])
      
    plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Scatter Plot")
    plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode1.SetXColumnName(xAxis)
    plotSeriesNode1.SetYColumnName(yAxis)
    plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
    plotSeriesNode1.SetUniqueColor()
     
    plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode")
    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())
    plotChartNode.SetTitle('A simple scatter plot ')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)
     
    layoutManager = slicer.app.layoutManager()
    layoutWithPlot = slicer.modules.plots.logic().GetLayoutWithPlot(layoutManager.layout)
    layoutManager.setLayout(layoutWithPlot)

    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())
      
  def makeScatterPlotOld(self, data,title,xAxis,yAxis):
    lns = slicer.mrmlScene.GetNodesByClass('vtkMRMLLayoutNode')
    lns.InitTraversal()
    ln = lns.GetNextItemAsObject()
    ln.SetViewArrangement(24)
    cvns = slicer.mrmlScene.GetNodesByClass('vtkMRMLChartViewNode')
    cvns.InitTraversal()
    cvn = cvns.GetNextItemAsObject()
    #
    dn = slicer.mrmlScene.AddNode(slicer.vtkMRMLDoubleArrayNode())
    dn.SetName(xAxis+"_"+yAxis+"_data")
    a = dn.GetArray()
    i,j=data.shape
    a.SetNumberOfTuples(i)
    x = range(0, i)
    for j in range(len(x)):
      a.SetComponent(j, 0, data[j,0])
      a.SetComponent(j, 1, data[j,1])
      a.SetComponent(j, 2, 0)

    cn = slicer.mrmlScene.AddNode(slicer.vtkMRMLChartNode())
    state=cn.StartModify()
    # Add the Array Nodes to the Chart. The first argument is a string used for the legend and to refer to the Array when setting properties.
    cn.AddArray('A double array', dn.GetID())
    #
    # Set a few properties on the Chart. The first argument is a string identifying which Array to assign the property. 
    # 'default' is used to assign a property to the Chart itself (as opposed to an Array Node).
    cn.SetProperty('default', 'type', 'scatter')
    cn.SetProperty('default', 'title', title)
    cn.SetProperty('default', 'xAxisLabel', xAxis)
    cn.SetProperty('default', 'yAxisLabel', yAxis)
    cn.SetProperty('default', 'showLegend', '')
    cn.SetName(xAxis+"_"+yAxis)
    cn.EndModify(state)
    cvn.SetChartNodeID(cn.GetID())
    cvn.Modified()

  def lollipopGraph(self, LMObj,LMNode, pcList, scaleFactor):
    LM = self.convertFudicialToNP(LMNode)
    ind=1
    for pc in pcList:
      if pc is not 0:
        pc=pc-1
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
      ind=ind+1
    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetLines(lines)
    polydata.GetCellData().AddArray(magnitude)

    tubeFilter = vtk.vtkTubeFilter()
    tubeFilter.SetInputData(polydata)
    tubeFilter.SetRadius(0.7)
    tubeFilter.SetNumberOfSides(20)
    tubeFilter.CappingOn()
    tubeFilter.Update()
    
    modelNode = slicer.vtkMRMLModelNode()
    slicer.mrmlScene.AddNode(modelNode)
    modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('Magnitude')
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    modelDisplayNode.SetSliceIntersectionVisibility(True)
    modelDisplayNode.SetSliceDisplayModeToProjection()
    slicer.mrmlScene.AddNode(modelDisplayNode)
    modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
    modelNode.SetAndObservePolyData(tubeFilter.GetOutput())
    
  def calcEndpoints(self,LMObj,LM,pc, scaleFactor):
    i,j=LM.shape
    tmp=np.zeros((i,j))
    tmp[:,0]=LMObj.vec[0:i,pc]
    tmp[:,1]=LMObj.vec[i:2*i,pc]
    tmp[:,2]=LMObj.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3.0
    
  def convertFudicialToVTKPoint(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfFiducials()
    x=y=z=0
    loc=[x,y,z]
    lmData=np.zeros((numberOfLM,3))
    for i in range(numberOfLM):
      fnode.GetNthFiducialPosition(i,loc)
      lmData[i,:]=np.asarray(loc)
    #return lmData
    # print lmData
    points=vtk.vtkPoints()
    for i in range(numberOfLM):
      points.InsertNextPoint(lmData[i,0], lmData[i,1], lmData[i,2]) 
    return points

  def convertFudicialToNP(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfFiducials()
    x=y=z=0
    loc=[x,y,z]
    lmData=np.zeros((numberOfLM,3))
    # 
    for i in range(numberOfLM):
      fnode.GetNthFiducialPosition(i,loc)
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
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = GPALogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')