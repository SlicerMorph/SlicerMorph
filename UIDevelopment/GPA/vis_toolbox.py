import os
import re
import csv
import glob
import numpy as np
from __main__ import vtk, qt, ctk, slicer

class vis_toolbox:
    def __init__(self, parent):
        parent.title = "Shape Difference Visualizer"
        parent.categories = ["Maga Lab"]
        parent.dependencies = []
        parent.contributors = ["Ryan E Young"] # replace with "Firstname Lastname (Org)"
        parent.helpText = """
        This module visualizes the statically significant landmark pairs from EDMA.  The data file to be read in must be from EDMA.py
        Longer is colored blue.
        Shorter is colored red.  The top N and bottom N landmarks will be displayed, where N is the numebr
        of landmark pairs selected.
        """
        parent.acknowledgementText = """ Seattle Children's Hospital  """ 
        self.parent = parent

class vis_toolboxWidget:
    def __init__(self, parent = None):
        if not parent:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
        else:
            self.parent = parent
            self.layout = self.parent.layout()
        if not parent:
            self.setup()
            self.parent.show()

    # Gui Setup
    def setup(self):
        self.input_file=[]
        self.StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
        
        normalsButton = qt.QPushButton("Inputs")
        normalsButton.toolTip = "  This button is not clickable!"
        normalsButton.setStyleSheet("font: 12px")
        normalsButton.checkable = False
        self.layout.addWidget(normalsButton)
        normalsFrame = qt.QFrame(self.parent)
        self.layout.addWidget(normalsFrame)
        normalsFormLayout = qt.QFormLayout(normalsFrame)

        # get Output Directory
        ipnutFile = qt.QPushButton(" Select CSV File")
        ipnutFile.checkable = True
        ipnutFile.toolTip="Selcect the output of an EDMA.py run.  It must be call SDM_Output.csv or FDM_Output.csv "
        self.layout.addWidget(ipnutFile)
        ipnutFile.setStyleSheet(self.StyleSheet)
        outDirFrame3 = qt.QFrame(self.parent)
        self.layout.addWidget(outDirFrame3)
        outDirFormLayout3 = qt.QFormLayout(outDirFrame3)
        ipnutFile.connect('clicked(bool)', self.get_input_file)
        self.ipnutFile=ipnutFile
        #display input directory name
        outDirNameText3=qt.QLineEdit();
        outDirFormLayout3.addWidget(outDirNameText3)
        outDirNameText3.setText("Select CSV File for Visualization")
        self.outDirNameText3=outDirNameText3

        # get reference directory
        refDirButton3 = qt.QPushButton(" Select MRML Scene for Visualization")
        refDirButton3.checkable = True
        refDirButton3.toolTip="Visualization lines will be drawn on this volume.  This must be a MRML file"
        self.layout.addWidget(refDirButton3)
        refDirButton3.setStyleSheet(self.StyleSheet)
        refDirFrame3 = qt.QFrame(self.parent)
        self.layout.addWidget(refDirFrame3)
        refDirFormLayout3 = qt.QFormLayout(refDirFrame3)
        refDirButton3.connect('clicked(bool)', self.get_input_file_4)
        self.refDirButton3=refDirButton3
        #display input directory name
        refDirNameText4=qt.QLineEdit();
        refDirFormLayout3.addWidget(refDirNameText4)
        refDirNameText4.setText("Select Reference Scene")
        refDirNameText4.toolTip = " Select Refernce Scene"
        self.refDirNameText4=refDirNameText4


        # set P value
        normalsButton2 = qt.QPushButton("Select Number of Landmark Pairs")
        normalsButton2.toolTip = "This half of the total number.  This many will be taken from the top and botton"
        normalsButton2.setStyleSheet("font: 12px")
        normalsButton2.checkable = False
        self.layout.addWidget(normalsButton2)
        normalsFrame2 = qt.QFrame(self.parent)
        self.layout.addWidget(normalsFrame2)
        normalsFormLayout1 = qt.QFormLayout(normalsFrame2)

        pBox=qt.QSpinBox()
        normalsFormLayout1.addWidget(pBox)
        pBox.setSingleStep(1)
        pBox.setValue(10)
        pBox.setMinimum(1)
        pBox.setMaximum(100)
        self.pBox=pBox


       # apply button
       # Apply button     
        applyButton = qt.QPushButton("Apply")
        applyButton.checkable = True
        applyButton.setStyleSheet(self.StyleSheet)
        self.layout.addWidget(applyButton)
        applyButton.toolTip = "Push to start the program. Make sure you have spefied all inputs."
        applyFrame=qt.QFrame(self.parent)
        self.layout.addWidget(applyButton)
        applyButtonFormLayout=qt.QFormLayout(applyFrame)
        applyButton.connect('clicked(bool)', self.onApply)
    
        # Add vertical spacer
        self.layout.addStretch(1)
  
    def get_input_file(self):
          dir_name=qt.QFileDialog().getOpenFileName()
          self.inputFileDirName=dir_name
          self.outDirNameText3.setText(dir_name)

    def get_input_file_4(self):
        dir_name=qt.QFileDialog().getOpenFileName()
        self.refDir=dir_name
        self.refDirNameText4.setText(dir_name)

    # onApply
    def onApply(self):
        # print self.inputFileDirName
        slicer.mrmlScene.Clear(0)
        slicer.util.loadScene(self.refDir)

        csvName=os.path.basename(self.inputFileDirName)

        numToDraw= self.pBox.value

        if csvName=="SDM_Output.csv":
          # For smd
          mat=np.zeros((2000,6))
          i=0
          with open(self.inputFileDirName , 'r') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=' ')
            for row in spamreader:
                tmp=row[0].split(',')
                if tmp[0].isdigit():
                  mat[i,0:5]=tmp[0:5]
                  mat[i,5]=tmp[6]
                  i=i+1
          mat=mat[~np.all(mat==0, axis=1)]
          #sort matrix
          data=mat[np.lexsort((mat[:,4], ))]       
          # get landmarks
          lmNode=slicer.util.getNode('vtkMRMLMarkupsFiducialNode1')
          landmarks=self.getLMPos(lmNode)
          # print landmarks 
          x,y=data.shape  
          x=x-1
          for i in range(numToDraw):
            # get top points
            i1=data[i,0]
            i2=data[i,1]
            # print i1, i2
            p1=landmarks[i1-1,:]
            p2=landmarks[i2-1,:]
           # print "frist",data[i,3], i1,i2, p1, p2
            if data[i,3]<0:
              longer=1
            else:
              longer=0
            self.addruler(p1,p2, longer)

            # repeat for smallest point
            # get top points
            i1=data[x-i,0]
            i2=data[x-i,1]
            p1=landmarks[i1-1,:]
            p2=landmarks[i2-1,:]
          #  print "last", data[x-i,3], i1,i2, p1, p2
           ## print "-i" data[-i,3]
            if data[x-i,3]<0:
              longer=1
            else:
              longer=0
            self.addruler(p1,p2, longer)

      # # FOR FDM
        if csvName=="FDM_Output.csv":
          # For smd
          mat=np.zeros((2000,6))
          i=0
          with open(self.inputFileDirName , 'r') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=' ')
            for row in spamreader:
                tmp=row[0].split(',')
                if tmp[0].isdigit():
                  mat[i,0:5]=tmp[0:5]
                  
                  i=i+1
          mat=mat[~np.all(mat==0, axis=1)]
          #sort matrix
          data=mat[np.lexsort((mat[:,5], ))]       
          # get landmarks
          lmNode=slicer.util.getNode('vtkMRMLMarkupsFiducialNode1')
          landmarks=self.getLMPos(lmNode)
          # print landmarks    
          x,y=data.shape  
          x=x-1
          for i in range(numToDraw):
            # get top points
            i1=data[i,0]
            i2=data[i,1]
            # print i1, i2
            p1=landmarks[i1-1,:]
            p2=landmarks[i2-1,:]
            if data[i,3]<1:
              longer=1
            else:
              longer=0
            self.addruler(p1,p2, longer)

            # repeat for smallest point
             # get top points
            i1=data[x-i,0]
            i2=data[x-i,1]
            p1=landmarks[i1-1,:]
            p2=landmarks[i2-1,:]
            if data[x-i,3]<1:
              longer=1
            else:
              longer=0
            self.addruler(p1,p2, longer)



      
    def getLMPos(self, markUpNode):
        numLM=markUpNode.GetNumberOfMarkups()
        pos=np.zeros((numLM,3))
        x1=x2=x3=0
        l=[x1,x2,x3]
        for i in range(numLM):
          markUpNode.GetNthFiducialPosition(i,l)
          pos[i,:]=l
        return pos  

    def addruler(self,p1,p2,longer):
        # print "addruler"
        rulerNode = slicer.vtkMRMLAnnotationRulerNode()
        rulerNode.SetPosition1(p1)
        rulerNode.SetPosition2(p2)
        rulerNode.Initialize(slicer.mrmlScene)
        slicer.app.processEvents()
        ln=rulerNode.GetAnnotationLineDisplayNode()
        ln.SetLineThickness(10)
        if longer:
          ln.SetColor((1,.01,.01))
        else:
          ln.SetColor((.01,.0,1))
        ln.SetLabelVisibility(0)
        rulerNode.SetLocked(1)
        # rulerNode.setLocked(1)
        slicer.app.processEvents()

    def editVolumeProp(self):
      # make histogram and get mean and std
      scalarNode=slicer.mrmlScene.GetNthNodeByClass(0,'vtkMRMLScalarVolumeNode')
      i=scalarNode.GetImageData()
      tmp_matrix=vtk.util.numpy_support.vtk_to_numpy(i.GetPointData().GetScalars() )
      mean=tmp_matrix.mean()
      std=tmp_matrix.std()
      slicer.app.processEvents()
      #get volume property node and edit transfer function
      vpClass=slicer.mrmlScene.GetNodesByClass('vtkMRMLVolumePropertyNode')
      vpNode=vpClass.GetItemAsObject(0)
      slicer.app.processEvents()
      scalarOpacityNode=vpNode.GetScalarOpacity()
      scalarOpacityNode.RemoveAllPoints()
      scalarOpacityNode.AddPoint(mean+1*std, 0)
      scalarOpacityNode.AddPoint(mean+2*std, .05)


# todo
# tie it all together
# check for fdm vs SDM