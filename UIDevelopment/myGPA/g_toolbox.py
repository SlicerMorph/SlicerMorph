import os
import re
import csv
import glob
import fnmatch
import gpa_lib
import load_landmarks
import vtk_lib
import  numpy as np
from __main__ import vtk, qt, ctk, slicer
# TODO
# update how to create volume nodes
# check resampling quality with differnent sizes

class g_toolbox:
    def __init__(self, parent):
        parent.title = "YAPP"
        parent.categories = ["Maga Lab"]
        parent.dependencies = []
        parent.contributors = ["Ryan E Young"] # replace with "Firstname Lastname (Org)"
        parent.helpText = """
         Many many things
        """
        parent.acknowledgementText = """ Seattle Children's Hospital  """ 
        self.parent = parent

class sliderGroup(qt.QGroupBox):

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

class LMData:
    def __init__(self):
        self.lm=0
        self.lmRaw=0
        self.val=0
        self.vec=0
        self.alignCoords=0
        self.mShape=0
        self.tangentCoord=0
        self.shift=0
        self.centriodSize=0

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
        # SampleScaleFactor=SampleScaleFactor*(1.0/self.val[0])
        # scale eigenvector

        for y in numVec:
            for s in scaleFactor:
                #print y,s
                if j==3 and y is not 0:
                    #print self.vec[0:i,y], tmp[:,0]
                    tmp[:,0]=tmp[:,0]+float(s)*self.vec[0:i,y]*SampleScaleFactor
                    tmp[:,1]=tmp[:,1]+float(s)*self.vec[i:2*i,y]*SampleScaleFactor
                    tmp[:,2]=tmp[:,2]+float(s)*self.vec[2*i:3*i,y]*SampleScaleFactor
        #print tmp.shape
        
        
        self.shift=tmp
        #print self.lmRaw

    def writeOutData(self,outputFolder,files):
        # np.save(outputFolder+os.sep+"RawLandmarks", self.lmRaw)
        # np.save(outputFolder+os.sep+"AlignedLM", self.lm)
        np.savetxt(outputFolder+os.sep+"MeanShape.csv", self.mShape, delimiter=",")
        np.savetxt(outputFolder+os.sep+"eigenvector.csv", self.vec, delimiter=",")
        np.savetxt(outputFolder+os.sep+"eigenvalues.csv", self.val, delimiter=",")

        percentVar=self.val/self.val.sum()
        #np.savetxt(outputFolder+os.sep+"percentVar.csv", percentVar, delimiter=",")

        # np.savetxt(outputFolder+os.sep+"centriodSize.csv", self.centriodSize, delimiter=",")

        self.procdist=gpa_lib.procDist(self.lm, self.mShape)
        # np.savetxt(outputFolder+os.sep+"procDist.csv", self.procdist, delimiter=",")

        files=np.array(files)
        i=files.shape
        files=files.reshape(i[0],1)
        k,j,i=self.lmRaw.shape

        coords=gpa_lib.makeTwoDim(self.lm)
        self.procdist=self.procdist.reshape(i,1)
        self.centriodSize=self.centriodSize.reshape(i,1)
        #print files.shape, self.procdist.shape, self.centriodSize.shape, coords.shape
        tmp=np.column_stack((files, self.procdist, self.centriodSize, np.transpose(coords)))
        #print tmp
        # # fmt = ",".join(["%s"] + ["%10.6e"] * (tmp.shape[1]-1))
        header=np.array(['Sample_name','proc_dist','centeroid'])
        # print header.shape
        i1,j=tmp.shape
        # l=[]
        # for q in range(j-4):
        #     l.append(" ")
        # l=np.array(l)
        # l=l.reshape(1,j-4)
        coodrsL=(j-3)/3.0
        l=np.zeros(3*coodrsL)
        # print "shape l" ,l.shape
        l=list(l)
        
        # print "num coords", coodrsL
        for x in range(int(coodrsL)):
            loc=x+1
            l[3*x]="x"+str(loc)
            l[3*x+1]="y"+str(loc)
            l[3*x+2]="z"+str(loc)
        l=np.array(l)
        header=np.column_stack((header.reshape(1,3),l.reshape(1,3*coodrsL)))
        # print "head shape", header.shape
        # print header

        # print header.shape, tmp.shape
        # print tmp
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
       # print tmp
        # normalize tmp

        # tmp=tmp*scaleFactor/4.0
        #transNode=slicer.util.getNode(MonsterObj.sourceTransID)
        #transMatrix=transNode.GetTransformToParent().GetMatrix()
        #i,j=tmp.shape

        # for x in range(i):
        #     tmpVTK=np.ones((4,1))
        #     tmpVTK[0]=tmp[x,0]
        #     tmpVTK[1]=tmp[x,1]
        #     tmpVTK[2]=tmp[x,2]
        #     l=transMatrix.MultiplyFloatPoint(tmpVTK)
        #     lArray=np.array(l)
        #     tmp[x,0]=lArray[0]
        #     tmp[x,1]=lArray[1]
        #     tmp[x,2]=lArray[2]
        #print tmp
        # rotate the shitf
        return LM+tmp*scaleFactor/3.0

class Monsters:
    def __init__(self,volumeSelector,LMSelector, spacing):
        print spacing
        volumeLogic=slicer.modulelogic.vtkSlicerVolumesLogic()
        self.sourceVolume=volumeSelector.currentNode()
        self.sourceTransID=self.sourceVolume.GetTransformNodeID()
    
        self.tranformedVolume=slicer.util.getNode('Transformed_Volume')
        if self.tranformedVolume is None:
            self.tranformedVolume=slicer.vtkMRMLScalarVolumeNode()
            self.tranformedVolume.SetName("Transformed_Volume")
            colornode2=slicer.vtkMRMLColorTableNode()
            colornode2.SetTypeToGrey()
            slicer.mrmlScene.AddNode(colornode2)
            transDispNode=slicer.vtkMRMLScalarVolumeDisplayNode()
            slicer.mrmlScene.AddNode(transDispNode)
            transDispNode.SetAndObserveColorNodeID(colornode2.GetID())
            slicer.mrmlScene.AddNode(self.tranformedVolume)
            self.tranformedVolume.SetAndObserveDisplayNodeID(transDispNode.GetID())
            self.tranformedVolume.SetAndObserveTransformNodeID(self.sourceTransID)
            

        self.resampledSourceVolume=slicer.util.getNode('Resampled_Source')
        if self.resampledSourceVolume is None:
            self.resampledSourceVolume=slicer.vtkMRMLScalarVolumeNode()
            self.resampledSourceVolume.SetName("Resampled_Source")
            slicer.mrmlScene.AddNode(self.resampledSourceVolume)
            resampledDispNode=slicer.vtkMRMLScalarVolumeDisplayNode()
            slicer.mrmlScene.AddNode(resampledDispNode)
            colornode=slicer.vtkMRMLColorTableNode()
            colornode.SetTypeToGrey()
            slicer.mrmlScene.AddNode(colornode)
            resampledDispNode.SetAndObserveColorNodeID(colornode.GetID())
            self.resampledSourceVolume.SetAndObserveDisplayNodeID(resampledDispNode.GetID())
            if spacing[0] != 1:
                self.resampleVolume(self.sourceVolume, self.resampledSourceVolume, spacing)
            if spacing[0] ==1:
                self.resampledSourceVolume.SetAndObserveImageData(self.sourceVolume.GetImageData())
            self.resampledSourceVolume.SetAndObserveTransformNodeID(self.sourceTransID)
            self.resampledSourceVolume.SetOrigin(self.sourceVolume.GetOrigin())

        self.transformNode=slicer.util.getNode("TPS_transform")
        if self.transformNode is None:
            self.transformNode=slicer.vtkMRMLTransformNode()
            self.transformNode.SetName("TPS_transform")
            slicer.mrmlScene.AddNode(self.transformNode)

        self.tpsNode=0
        self.targetVolume=0
        self.tps=0
        self.sourceLMNode=LMSelector.currentNode()
        self.sourceLMnumpy=self.convertFudicialToNP(self.sourceLMNode)

    def warpVolumes(self, targetLMShift, sourceLM,tpsNode):
        # sourceLM=convertFudicialToVTKPoint(self.sourceLMNode)
        # sourceLMNP=convertFudicialToNP(self.sourceLMNode)
        target=sourceLM+targetLMShift
        # print "target", target
        # print "source", sourceLM
        targetLMVTK=self.convertNumpyToVTK(target)
        sourceLMVTK=self.convertNumpyToVTK(sourceLM)
        self.tps=self.createTPS(sourceLMVTK,targetLMVTK)
        self.tps.Update()
        # tpsNode.SetAndObserveTransformFromParent(self.tps.Inverse())
        # tpsNode.SetAndObserveTransformToParent(self.tps)
        self.resliceThroughTransform(  self.resampledSourceVolume,self.sourceVolume , self.tps ,  self.tranformedVolume)

    def returnLMNP(self):
        sourceLMNP=self.convertFudicialToNP(self.sourceLMNode)
        return sourceLMNP

    def matchVolumeProp(self):
        # pass
        # match origins
        #self.tranformedVolume.SetOrigin(self.sourceVolume.GetOrigin())
        # match display node
        #self.tranformedVolume.SetAndObserveDisplayNodeID(self.sourceVolume.GetDisplayNodeID())
        self.tranformedVolume.SetSpacing(self.sourceVolume.GetSpacing())
        # self.tranformedVolume.set
        # match spacing
        # sourceIMdata=self.sourceVolume.GetImageData()
        # spacing=sourceIMdata.GetSpacing()
        # tansformedIMData=self.tranformedVolume.GetImageData()
        # tansformedIMData.SetSpacing(spacing)
        # tranformedIMData.Modified()  
        # self.tranformedVolume.SetAndObserveImageData(tranformedIMdata)
        return

    def resampleVolume(self, inputVolume, outputVolume, spacing):

        inputIJKToRASMatrix = vtk.vtkMatrix4x4()
        inputVolume.GetIJKToRASMatrix(inputIJKToRASMatrix)
        resliceTransform = vtk.vtkTransform()
        resliceTransform.Identity()
     
        extent=inputVolume.GetImageData().GetWholeExtent()
        extent=list(extent)
        # print "e1", extent
        extent[1]=extent[1]/spacing[0]
        extent[3]=extent[3]/spacing[1]
        extent[5]=extent[5]/spacing[2]
        # print "e2", extent
     
        reslice = vtk.vtkImageReslice()
        reslice.SetInput(inputVolume.GetImageData())
        reslice.SetResliceTransform(resliceTransform)
        reslice.SetInterpolationModeToNearestNeighbor()
        reslice.AutoCropOutputOff()
        reslice.SetOutputExtent(extent)
        reslice.SetOutputSpacing(spacing)
        reslice.Update()
      
        outputIJKToRASMatrix = vtk.vtkMatrix4x4()
        inputVolume.GetIJKToRASMatrix(outputIJKToRASMatrix)
     
        # outputIJKToRASMatrix.DeepCopy(inputIJKToRASMatrix)
     
        changeInformation = vtk.vtkImageChangeInformation()
        changeInformation.SetInput(reslice.GetOutput())
        changeInformation.SetOutputOrigin(inputVolume.GetOrigin())
        changeInformation.SetOutputSpacing(spacing)
        changeInformation.Update()
        outputVolume.SetAndObserveImageData(changeInformation.GetOutput())
        outputVolume.SetIJKToRASMatrix(outputIJKToRASMatrix)
     
        inputSpacing=inputVolume.GetSpacing()
        # OutputSpacing=[1,1,1]
        # OutputSpacing[0]=inputSpacing[0]*spacing[0]
        # OutputSpacing[1]=inputSpacing[1]*spacing[1]
        # OutputSpacing[2]=inputSpacing[2]*spacing[2]
        # # print "inpout spacing", inputSpacing
        # # print "output spacing", OutputSpacing
        outputVolume.SetSpacing(inputSpacing)
        transID=inputVolume.GetTransformNodeID()
        outputVolume.SetAndObserveTransformNodeID(transID)
        outputVolume.Modified()
     
        return

    def resliceThroughTransform(self, sourceNode,refNode, transform, targetNode):
        """
        Fills the targetNode's vtkImageData with the source after
        applying the transform. Uses spacing from referenceNode. Ignores any vtkMRMLTransforms.
        sourceNode, referenceNode, targetNode: vtkMRMLScalarVolumeNodes
        transform: vtkAbstractTransform
        """

        # get the transform from RAS back to source pixel space
        sourceRASToIJK = vtk.vtkMatrix4x4()
        sourceNode.GetRASToIJKMatrix(sourceRASToIJK)

        # get the transform from target image space to RAS
        referenceIJKToRAS = vtk.vtkMatrix4x4()
        sourceNode.GetIJKToRASMatrix(referenceIJKToRAS)

        # this is the ijkToRAS concatenated with the passed in (abstract)transform
        resliceTransform = vtk.vtkGeneralTransform()
        resliceTransform.Concatenate(sourceRASToIJK)
        resliceTransform.Concatenate(transform)
        resliceTransform.Concatenate(referenceIJKToRAS)

        # use the matrix to extract the volume and convert it to an array
        reslice = vtk.vtkImageReslice()
        reslice.SetInterpolationModeToLinear()
        reslice.InterpolateOn()
        reslice.SetResliceTransform(resliceTransform)
        if vtk.VTK_MAJOR_VERSION <= 5:
          reslice.SetInput( sourceNode.GetImageData() )
        else:
          reslice.SetInputConnection( sourceNode.GetImageDataConnection() )

        dimensions = refNode.GetImageData().GetDimensions()
        reslice.SetOutputExtent(0, dimensions[0]-1, 0, dimensions[1]-1, 0, dimensions[2]-1)
        reslice.SetOutputOrigin((0,0,0))
        # sourceImData=sourceNode.GetImageData()
        reslice.SetOutputSpacing(1,1,1)

        reslice.UpdateWholeExtent()
        targetNode.SetAndObserveImageData(reslice.GetOutput())
        return
        #targetNode.setSpacing(sourceImData.GetSpacing())
        # print "reslicing"# targetNode

    def createTPS(self, sourceLM, targetLM):
        """Perform the thin plate transform using the vtkThinPlateSplineTransform class"""
     
        thinPlateTransform = vtk.vtkThinPlateSplineTransform()
        thinPlateTransform.SetBasisToR() # for 3D transform

        thinPlateTransform.SetSourceLandmarks(sourceLM)
        thinPlateTransform.SetTargetLandmarks(targetLM)
        thinPlateTransform.Update()
        # points=vtk.vtkPoints()
        # thinPlateTransform.TransformPoints(sourceLM,points)
        # print points
        self.transformNode.SetAndObserveTransformToParent(thinPlateTransform)

        return thinPlateTransform
        #resliceThroughTransform(moving, thinPlateTransform, fixed, transformed)

    def convertFudicialToVTKPoint(self, fnode):
        import numpy as np
        numberOfLM=fnode.GetNumberOfFiducials()
        x=y=z=0
        loc=[x,y,z]
        lmData=np.zeros((numberOfLM,3))
        # 
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
   
    # def meanShapeLMCalc(self, meanShape):
    #     # calculate centriod of volume
    #     size=np.linalg.norm(self.sourceLMnumpy-self.sourceLMnumpy.mean(axis=0))

    #     # calc center
    #     center=self.sourceLMnumpy.mean(axis=0)
    #     # print center
    #     # scale meanshape
    #     meanShape=meanShape*size

    #     # center meanshape
    #     # meanShape=(meanShape-meanShape.mean(axis=0))+center
    #     # mcenter=meanShape.mean(axis=0)
    #     # msize=np.linalg.norm(meanShape-meanShape.mean(axis=0))
    #     # print "center source, mshape \n", center, mcenter
    #     # print "size, source, mshape \n", size, msize
    #     # print "meanshape pre-align", meanShape
    #     # align the two shapes
    #     meanShape=gpa_lib.alignShape(self.sourceLMnumpy, meanShape)
    #     meanShape=(meanShape-meanShape.mean(axis=0))+center
    #     mcenter=meanShape.mean(axis=0)
    #     msize=np.linalg.norm(meanShape-meanShape.mean(axis=0))
    #     print "center source, mshape \n", center, mcenter
    #     print "size, source, mshape \n", size, msize
    #     for x in range(12):
    #             addruler(meanShape[x,:],self.sourceLMnumpy[x,:],2)
    #     # print "meanshape post-align", meanShape
    #     return meanShape

class g_toolboxWidget:
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

    def ctkb(self, parent, text, buttonText):
    
        inbutton=ctk.ctkCollapsibleButton()
        inbutton.text=text
        Mylayout= qt.QGridLayout(inbutton)

        volumeIn, volumeInLabel, button1=textIn('Landmark Folder','', 'No Spaces!')
        Mylayout.addWidget(volumeIn,4,2)
        Mylayout.addWidget(volumeInLabel,4,1)
        Mylayout.addWidget(button1,4,3)

        # volumeIn2, volumeInLabel2, button2=textIn('Reference Volume MRML','', 'No Spaces!')
        # Mylayout.addWidget(volumeIn2,5,2)
        # Mylayout.addWidget(volumeInLabel2,5,1)
        # Mylayout.addWidget(button2,5,3)
   
        return inbutton, button1,volumeIn # button2, volumeIn2

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

    #Gui Setup
    def setup(self):
        self.input_file=[]
        self.StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
       
        inbutton=ctk.ctkCollapsibleButton()
        inbutton.text="Inputs"
        inputLayout= qt.QGridLayout(inbutton)

        self.LMText, volumeInLabel, self.LMbutton=self.textIn('Landmark Folder','', 'No Spaces!')
        inputLayout.addWidget(self.LMText,1,2)
        inputLayout.addWidget(volumeInLabel,1,1)
        inputLayout.addWidget(self.LMbutton,1,3)
        self.layout.addWidget(inbutton)
        self.LMbutton.connect('clicked(bool)', self.selectLandmarkFile)

        self.outText, outLabel, self.outbutton=self.textIn('Output Folder','', 'No Spaces!')
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
        # importMRMLButton.connect('clicked(bool)', self.selectMRMLFile)
        # self.grayscaleSelectorFrame = qt.QFrame(self.parent)
        # self.grayscaleSelectorFrame.setLayout(qt.QHBoxLayout())
        # self.parent.layout().addWidget(self.grayscaleSelectorFrame)
    
        # node selector tab
        volumeButton=ctk.ctkCollapsibleButton()
        volumeButton.text="Node Selector"
        volumeLayout= qt.QGridLayout(volumeButton)

        self.volumeRecText, VolumeRecLabel, voluemrecbutton=self.textIn('Recomended Volume','', 'No Spaces!')
        volumeLayout.addWidget(self.volumeRecText,1,2)
        volumeLayout.addWidget(VolumeRecLabel,1,1)
    

        self.grayscaleSelectorLabel = qt.QLabel("Volume Node: ")
        self.grayscaleSelectorLabel.setToolTip( "Select the grayscale volume (background grayscale scalar volume node) for statistics calculations")
        volumeLayout.addWidget(self.grayscaleSelectorLabel,2,1)

        self.grayscaleSelector = slicer.qMRMLNodeComboBox()
        self.grayscaleSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
        self.grayscaleSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
        self.grayscaleSelector.selectNodeUponCreation = False
        self.grayscaleSelector.addEnabled = False
        self.grayscaleSelector.removeEnabled = False
        self.grayscaleSelector.noneEnabled = True
        self.grayscaleSelector.showHidden = False
        self.grayscaleSelector.showChildNodeTypes = False
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

        resampleLabel=qt.QLabel()
        resampleLabel.setText('Resample Volume')
        resampleLabel.setToolTip("The warped volume created will be a resample version of the original violume.  Increase for faster performance")
        volumeLayout.addWidget(resampleLabel,4,1)

        self.resampleBox=qt.QSpinBox()
        self.resampleBox.setRange(1,10)
        self.resampleBox.setSingleStep(1)
        self.resampleBox.setValue(1)
        self.resampleBox.setToolTip("The warped volume created will be a resample version of the original violume.  Increase for faster performance")


        volumeLayout.addWidget(self.resampleBox,4,2)
        

        selectorButton = qt.QPushButton("Select")
        selectorButton.checkable = True
        selectorButton.setStyleSheet(self.StyleSheet)
        volumeLayout.addWidget(selectorButton,5,1,1,3)
        selectorButton.connect('clicked(bool)', self.SelectVolumes)

        self.layout.addWidget(volumeButton)

         #Apply Button 
        loadButton = qt.QPushButton("Load")
        loadButton.checkable = True
        loadButton.setStyleSheet(self.StyleSheet)
        inputLayout.addWidget(loadButton,5,1,1,3)
        loadButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
        #applyFrame=qt.QFrame(self.parent)
        #self.layout.addWidget(loadButton)
        #applyButtonFormLayout=qt.QFormLayout(applyFrame)
        loadButton.connect('clicked(bool)', self.onLoad)
        
        # adjust PC sectore
        vis=ctk.ctkCollapsibleButton()
        vis.text='Visualization Parameters'
        visLayout= qt.QGridLayout(vis)

        self.PCList=[]
        self.slider1=sliderGroup()
        self.slider1.connectList(self.PCList)
        #self.slider1.populateComboBox()
        visLayout.addWidget(self.slider1,3,1,1,2)

        self.slider2=sliderGroup()
        self.slider2.connectList(self.PCList)
        #self.slider2.populateComboBox()
        visLayout.addWidget(self.slider2,4,1,1,2)

        self.slider3=sliderGroup()
        self.slider3.connectList(self.PCList)
        #self.slider3.populateComboBox()
        visLayout.addWidget(self.slider3,5,1,1,2)

        self.slider4=sliderGroup()
        self.slider4.connectList(self.PCList)
        #self.slider4.populateComboBox()
        visLayout.addWidget(self.slider4,6,1,1,2)

        self.slider5=sliderGroup()
        self.slider5.connectList(self.PCList)
       # self.slider5.populateComboBox()
        visLayout.addWidget(self.slider5,7,1,1,2)

        self.layout.addWidget(vis)

        
        #Apply Button 
        applyButton = qt.QPushButton("Apply")
        applyButton.checkable = True
        applyButton.setStyleSheet(self.StyleSheet)
        self.layout.addWidget(applyButton)
        applyButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
        applyFrame=qt.QFrame(self.parent)
        visLayout.addWidget(applyButton,8,1,1,2)
        #applyButtonFormLayout=qt.QFormLayout(applyFrame)
        applyButton.connect('clicked(bool)', self.onApply)

        # # Reset Button
        # resetButton = qt.QPushButton("Reset")
        # resetButton.checkable = True
        # resetButton.setStyleSheet(self.StyleSheet)
        # self.layout.addWidget(resetButton)
        # resetButton.toolTip = "Push to reset all fields."
        # applyFrame=qt.QFrame(self.parent)
        # self.layout.addWidget(resetButton)
        # applyButtonFormLayout=qt.QFormLayout(applyFrame)
        # resetButton.connect('clicked(bool)', self.reset)

        #PC plot section
        plotFrame=ctk.ctkCollapsibleButton()
        plotFrame.text="PC Plot Options"
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

        plotButton = qt.QPushButton("Plot")
        plotButton.checkable = True
        plotButton.setStyleSheet(self.StyleSheet)
        plotButton.toolTip = "Push to make PC plot."
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

        lolliButton = qt.QPushButton("Plot")
        lolliButton.checkable = True
        lolliButton.setStyleSheet(self.StyleSheet)
        lolliButton.toolTip = "Push to make PC plot."
        lolliLayout.addWidget(lolliButton,4,1,1,4)
        lolliButton.connect('clicked(bool)', self.lolliPlot)


        resetButton = qt.QPushButton("Reset Scene")
        resetButton.checkable = True
        resetButton.setStyleSheet(self.StyleSheet)
        self.layout.addWidget(resetButton)
        resetButton.toolTip = "Push to reset all fields."
        #applyButtonFormLayout=qt.QFormLayout(applyFrame)
        resetButton.connect('clicked(bool)', self.reset)

        self.layout.addStretch(1)

    

#Gui Function
    def onLoad(self):
        # try:
        #     self.LM=LMData()
        #     self.LM.lmRaw, files= importAllLandmarks(self.LM_dir_name, self.outputFolder)
        #     # print self.LM.lmRaw.shape
        #     self.LM.doGpa()
        #     self.LM.calcEigen()
        #     #slicer.util.loadScene(self.MRML_file_name)
        #     # m,ms=self.gpa()
        #     self.updateList()
        #     #write out GPA and PCA data
        #     self.LM.writeOutData(self.outputFolder, files)
        #     filename=self.LM.closestSample(files)
        #     self.volumeRecText.setText(filename)

        # except AttributeError:
        #     qt.QMessageBox.critical(
        #     slicer.util.mainWindow(),
        #   'Error', 'Please select input and output folders !')

        # except IndexError:
        #      qt.QMessageBox.critical(
        #     slicer.util.mainWindow(),
        #   'Error', 'No landmarks found.  Choose a different folder !')
        self.logic=g_toolboxLogic() 
        self.LM=LMData()
        lmToExclue=self.excludeLMText.text
        if len(lmToExclue) != 0:
            tmp=lmToExclue.split(",")
            print len(tmp)
            tmp=[np.int(x) for x in tmp]
            lmNP=np.asarray(tmp)
        else:
            tmp=[]
        # print tmp
        # print lmNP
        # print type(lmNP)
        # print np.asanyarray(tmp)
        # print np.random.randint(3,size=(3))
        self.LM.lmRaw, files= self.logic.mergeMatchs(self.LM_dir_name, tmp)
        #print self.LM.lmRaw.shape
        #print files
        print self.LM.lmRaw.shape
        self.LM.doGpa()
        self.LM.calcEigen()
            #slicer.util.loadScene(self.MRML_file_name)
            # m,ms=self.gpa()
        self.updateList()
            #write out GPA and PCA data
        self.LM.writeOutData(self.outputFolder, files)
        print files
        filename=self.LM.closestSample(files)
        self.volumeRecText.setText(filename)
          

    def SelectVolumes(self):
        # try:
        #     resampleAmount=self.resampleBox.value
        #     spacing=[resampleAmount,resampleAmount,resampleAmount]
        #     self.volumes=Monsters(self.grayscaleSelector,  self.FudSelect, spacing)
        #     fud=convertFudicialToNP(self.volumes.sourceLMNode) 
        #     self.sampleSizeScaleFactor=(dist2(fud)).max()
        #     print self.sampleSizeScaleFactor
        # except AttributeError:
        #     qt.QMessageBox.critical(
        #     slicer.util.mainWindow(),
        #   'Error', 'Please select and load  landmark and output folders !')
    
        resampleAmount=self.resampleBox.value
        spacing=[resampleAmount,resampleAmount,resampleAmount]
        self.volumes=Monsters(self.grayscaleSelector,  self.FudSelect, spacing)
        fud=self.logic.convertFudicialToNP(self.volumes.sourceLMNode) 
        self.sampleSizeScaleFactor=(self.logic.dist2(fud)).max()
        self.transformedRenderingNode=None
        self.sourceRenderingNode=None
        # CODE TO AUTOWARP TO THE MEAN SHAPE
        # meanShapeLM=self.volumes.meanShapeLMCalc(self.LM.mShape)
        # shiftToMeanShape=meanShapeLM-self.volumes.returnLMNP()
        # # print 'source_LM',tmp
        # # print 'meanshapoeLM', meanShapeLM
        # print "shift",shiftToMeanShape
        # self.volumes.warpVolumes(shiftToMeanShape/10.0, self.volumes.returnLMNP(),self.volumes.tpsNode )
        # self.volumes.matchVolumeProp()

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

        self.LM.ExpandAlongPCs(pcSelected,scaleFactors, self.sampleSizeScaleFactor)
        self.volumes.warpVolumes(self.LM.shift, self.volumes.returnLMNP(),self.volumes.tpsNode )
        self.volumes.matchVolumeProp()

        # set to correct setup
        # Dual 3D View
        # layoutManager = slicer.app.layoutManager()
        # layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDual3DView)
        # slicer.app.processEvents()

        # # # get display and view nodes
        # sourceDisplayNode=self.volumes.sourceVolume.GetDisplayNode()
        # transformedDisplayNodes=self.volumes.tranformedVolume.GetDisplayNode()
        # viewNode1=slicer.util.getNode('vtkMRMLViewNode1')
        # viewNode2=slicer.util.getNode('vtkMRMLViewNode2')

        # # # get volume rendering logic
        # mrml=slicer.mrmlScene
        # logic = slicer.modules.volumerendering.logic()
        # logic.SetAndObserveMRMLScene(mrml)

        # # Render transformed voluem on the left
        # if self.transformedRenderingNode is None:
        #     self.transformedRenderingNode=logic.CreateVolumeRenderingDisplayNode()
        #     self.transformedRenderingNode.AddViewNodeID(viewNode1.GetID())
        #     mrml.AddNode( self.transformedRenderingNode)
        #     self.transformedRenderingNode.SetName('Transformed_rendering')
        #     self.volumes.tranformedVolume.AddAndObserveDisplayNodeID( self.transformedRenderingNode.GetID())
        #     self.volumes.tranformedVolume.SetSpacing(self.volumes.resampledSourceVolume.GetSpacing())
        #     logic.UpdateDisplayNodeFromVolumeNode( self.transformedRenderingNode, self.volumes.tranformedVolume )
          

        # # Render source voluem on the right
        # if  self.sourceRenderingNode is None:
        #     self.sourceRenderingNode=logic.CreateVolumeRenderingDisplayNode()
        #     self.sourceRenderingNode.SetName('Source_rendering')
        #     self.sourceRenderingNode.AddViewNodeID(viewNode2.GetID())
        #     mrml.AddNode( self.sourceRenderingNode)
        #     logic.UpdateDisplayNodeFromVolumeNode( self.sourceRenderingNode, self.volumes.sourceVolume )
        #     self.volumes.sourceVolume.AddAndObserveDisplayNodeID( self.sourceRenderingNode.GetID())

        # slicer.app.processEvents()
        # # transfer properties from source to transformed volume
        # # get properites from source
        # tmp=logic.GetVolumeRenderingDisplayNodeForViewNode(viewNode2)
        # sourceVolumeProp=tmp.GetVolumePropertyNode()

        # # transformed node
        # vp=slicer.util.getNode('vtkMRMLVolumePropertyNode1')
        # self.TransformedRenderingNode=logic.GetVolumeRenderingDisplayNodeForViewNode(viewNode1)
        # self.TransformedRenderingNode.SetAndObserveVolumePropertyNodeID(vp.GetID())
       # TvolProp=self.TransformedRenderingNode.GetVolumeNode()
        # tScalarOpacity=TvolProp.GetScalarOpacity()
        # tScalarOpacity.RemoveAllPoints()
        # slicer.app.processEvents()

        # i=scalarNode.GetImageData()
        # tmp_matrix=vtk.util.numpy_support.vtk_to_numpy(i.GetPointData().GetScalars() )
        # mean=tmp_matrix.mean()
        # std=tmp_matrix.std()
        # slicer.app.processEvents()
        # tScalarOpacity.RemoveAllPoints()
        # tScalarOpacity.AddPoint(mean+1.5*std, 0)
        # tScalarOpacity.AddPoint(mean+2.5*std, 1)
        # tScalarOpacity.Modified()
        # slicer.app.processEvents()

        # set transformed volume to be yellow
        # transformedVolumeProp=self.volumes.tranformedVolume.GetVolumeDisplayNode()
        # colorNode=transformedVolumeProp.GetColorNode()
        # colorNode.SetTypeToYellow()
        # colorNode.Modified()

        # try:
        #     # get selected PCs
        #     pc1=self.slider1.boxValue()
        #     pc2=self.slider2.boxValue()
        #     pc3=self.slider3.boxValue()
        #     pc4=self.slider4.boxValue()
        #     pc5=self.slider5.boxValue()
        #     pcSelected=[pc1,pc2,pc3,pc4,pc5]

        #     # get scale values for each pc.
        #     sf1=self.slider1.sliderValue()
        #     sf2=self.slider2.sliderValue()
        #     sf3=self.slider3.sliderValue()
        #     sf4=self.slider4.sliderValue()
        #     sf5=self.slider5.sliderValue()
        #     scaleFactors=np.zeros((5))
        #     scaleFactors[0]=sf1/100.0
        #     scaleFactors[1]=sf2/100.0
        #     scaleFactors[2]=sf3/100.0
        #     scaleFactors[3]=sf4/100.0
        #     scaleFactors[4]=sf5/100.0

        #     j=0
        #     for i in pcSelected:
        #         if i==0:
        #             scaleFactors[j]=0.0
        #             j=j+1

        #     self.LM.ExpandAlongPCs(pcSelected,scaleFactors, self.sampleSizeScaleFactor)
        #     self.volumes.warpVolumes(self.LM.shift, self.volumes.returnLMNP(),self.volumes.tpsNode )
        #     self.volumes.matchVolumeProp()
        # except AttributeError: 
        #     qt.QMessageBox.critical(
        #     slicer.util.mainWindow(),
        #   'Error', 'Please select a volume node and landmark list !')
    
    def selectOutputFolder(self):
        self.outputFolder=qt.QFileDialog().getExistingDirectory()
        self.outText.setText(self.outputFolder)
        
    def selectLandmarkFile(self):
        self.LM_dir_name=qt.QFileDialog().getExistingDirectory()
        self.LMText.setText(self.LM_dir_name)

    def selectMRMLFile(self):
        self.MRML_file_name=qt.QFileDialog().getOpenFileName()
        self.MRMLText.setText(self.MRML_file_name)

    def gpa(self):
        monsters, mShape=gpa_lib.doGPA(self.landmarks)
        return monsters, mShape

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

        # slicer.mrmlScene.clear(0)
        
    def plot(self):
        try:
            # get values from boxs
            xValue=self.XcomboBox.currentIndex
            yValue=self.YcomboBox.currentIndex

            # get data to plot
            data=gpa_lib.plotTanProj(self.LM.lm,xValue,yValue)

            # plot it
            self.logic.makeScatterPlot(data,'PC Plot',"PC"+str(xValue+1),"PC"+str(yValue+1))

        except AttributeError:
            qt.QMessageBox.critical(
            slicer.util.mainWindow(),
          'Error', 'Please make sure a Landmark folder has been loaded  !')    

    def lolliPlot(self):
        # try:
        #     pb1=self.vectorOne.currentIndex
        #     pb2=self.vectorTwo.currentIndex
        #     pb3=self.vectorThree.currentIndex

        #     pcList=[pb1,pb2,pb3]
        #     self.logic.lollipopGraph(self.LM, self.volumes, pcList, self.sampleSizeScaleFactor)
        # except AttributeError:
        #     qt.QMessageBox.critical(
        #     slicer.util.mainWindow(),
        #     'Error', 'Please select a volume node and landmark list!')

        pb1=self.vectorOne.currentIndex
        pb2=self.vectorTwo.currentIndex
        pb3=self.vectorThree.currentIndex

        pcList=[pb1,pb2,pb3]
        self.logic.lollipopGraph(self.LM, self.volumes, pcList, self.sampleSizeScaleFactor)    
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


class g_toolboxLogic():
    def __init__(self):
        pass
    # functions for landmark importation
    def mergeMatchs(self, topDir, lmToRemove, suffix=".fcsv"):
        # initial data array
        dirs, files=self.walk_dir(topDir)
        matchList, noMatch=self.createMatchList(topDir, "fcsv")
        #print matchList
        #print len(matchList)
        landmarks=self.initDataArray(dirs,files[0],len(noMatch))
        matchedfiles=[]
        for i in range(len(noMatch)):
            # print "test \n" ,matchList[i][0]+".fcsv"
            tmp1=self.importLandMarks(noMatch[i]+".fcsv")
            #tmp2=self.importLandMarks(matchList[i][1]+ ".fcsv")
           # print "shapes:", tmp1.shape, tmp2.shape, matchList[i][0]
            # print "tmp1.shape", tmp1.shape
            # print "tmp2", tmp2.shape
            # print "lm", landmarks.shape
            #landmarks[:,:,i]=(tmp1+tmp2)/2.0
            landmarks[:,:,i]=tmp1
            matchedfiles.append(os.path.basename(noMatch[i][0]))
      #  for i in range(len(noMatch)):
       #     tmp=importLandMarks(matchList[i]+suffix)
        #    landmarks[:,:,i+len(matchList)]=tmp
        j=len(lmToRemove)
        #print"j", j
        #print type(lmToRemove)
        for i in range(j):
            #print "num", lmToRemove[i]
            landmarks=np.delete(landmarks,(np.int(lmToRemove[i])-1),axis=0)

        #print "landmark Shapes", landmarks.shape
        return landmarks, noMatch
   
    def createMatchList(self, topDir,suffix):
        l=[]
        for root, dirs, files in os.walk(topDir):
            for name in files:
                if fnmatch.fnmatch(name,"*"+suffix):
                    l.append(os.path.join(root, name[:-5]))
       # print "lenght l",len(l)
        matchList=[]
        #print l
        from sets import Set
        noMatchList=Set()
        for name1 in l:
            for name2 in l:
                #print name1[:-1]+"*2"
                if fnmatch.fnmatch(name2,name1[:-1]+"*2"):
                   # print "match", name1, name2
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

        return matchList, noMatchs
    def importLandMarks(self, filePath):
      """
      Imports the landmarks from a .fcsv file.
      Does not import sample if a  landmark is -1000
      Adjusts the resolution is log(nhrd) file is found
      returns kXd array of landmark data.
      k=# of landmarks
      d=dimension
      """
      # import data file
      datafile=open(filePath,'r')
      data=[]
      for row in datafile:
        if not fnmatch.fnmatch(row[0],"#*"):
            # print row
            data.append(row.strip().split(','))
      # Make Landmark array
      dataArray=np.zeros(shape=(len(data),3))
      # print dataArray.shape
      #print data
      j=0
      # sorter=np.zeros((len(data)))
      sorter=[]
      for i in data:
        tmp=np.array(i)[1:4]
        # print type(tmp), tmp.shape
        dataArray[j,0:3]=tmp
        #sorter.append(i[11])
        #sorter[0,j]=(np.array(i)[11].split("-"))[1]
        # try:
        #     sorter[j]=i[11].split("-")[1]
        #     #print "type -"
        # except IndexError:
        #      sorter[j]=i[11].split("_")[1]
        #      #print "type __",filePath
        # except IndexError:
        #     sorter[j]=j
        #     print "error not sorted."
        x=np.array(i).shape
        #print x[0]
        #print (np.array(i)[11].split("-")), filePath
        j=j+1

      # print data
      # t=np.argsort(sorter)
      # t=t.astype(int)
      #print t
      #ind=[i[0] for i in sorted(enumerate(sorter), key=lambda x:x[1])]
      #Sort the data array
      # if not np.array_equal(ind,range(len(data))):
      #   print "t", ind, filePath, sorter
      # if not np.array_equal(dataArray,dataArray[ind,:]):
      #   print "dif", dataArray[ind,:]
      # #print dataArray[t,:].shape
      # tmp=dataArray[ind,:]
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
      #k=len(dirs) 
      # print k
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

    def addruler(self, p1,p2,color):
        #print "addruler"
        rulerNode = slicer.vtkMRMLAnnotationRulerNode()
        rulerNode.SetPosition1(p1)
        rulerNode.SetPosition2(p2)
        rulerNode.Initialize(slicer.mrmlScene)
        slicer.app.processEvents()
        ln=rulerNode.GetAnnotationLineDisplayNode()
        ln.SetLineThickness(10)
        if color==1:
          ln.SetColor((1,0,0))
        if color==2:
          ln.SetColor((0,1,0))
        if color==3:
            ln.SetColor((0.0, 0.0, 1.0))
        ln.SetLabelVisibility(0)
        rulerNode.SetLocked(1)
        slicer.app.processEvents()

    def lollipopGraph(self, LMObj,MonsterObj,pcList, scaleFactor):
        LM=MonsterObj.sourceLMnumpy
        ind=1
        for pc in pcList:
            if pc is not 0:
                pc=pc-1
                endpoints=LMObj.calcEndpoints(LM,pc,scaleFactor, MonsterObj)
                i,j=LM.shape
                for x in range(i):
                    self.addruler(LM[x,:],endpoints[x,:],ind)
            ind=ind+1

    def convertFudicialToVTKPoint(self, fnode):
        import numpy as np
        numberOfLM=fnode.GetNumberOfFiducials()
        x=y=z=0
        loc=[x,y,z]
        lmData=np.zeros((numberOfLM,3))
        # 
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



