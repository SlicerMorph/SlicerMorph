import os
import fnmatch
import csv
import glob
import re
import numpy as np
from __main__ import vtk, qt, ctk, slicer


class EdmaVis:
  def __init__(self, parent):
    parent.title = "EMDA Code"
    parent.categories = ["Maga Lab"]
    parent.dependencies = []
    parent.contributors = ["Ryan Young"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    This Slicer module performs the EMDA procedure as described by Julien Claude in
     his book Morphometrics with R.  The outputted rulers are colorer blue and red 
     relating to statistically significant longer or short distances respectively.  
     That is the numerator ( experiment) over the denominator (control) is greater
     than or less than one.   
    """
    parent.acknowledgementText = """ Developed at Seattle Children's Hospital  """ 
    self.parent = parent

class EdmaVisWidget:
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



  def setup(self):
    # Gui setup    
    self.input_file=[]
    self.StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
    normalsButton = qt.QPushButton("Options")
    normalsButton.toolTip = "  This button is not clickable!"
    normalsButton.setStyleSheet("font: 12px")
    normalsButton.checkable = False
    self.layout.addWidget(normalsButton)
    normalsFrame = qt.QFrame(self.parent)
    self.layout.addWidget(normalsFrame)
    normalsFormLayout = qt.QFormLayout(normalsFrame)

    adjImageCheckBox = qt.QCheckBox("Draw Lines")
    adjImageCheckBox.toolTip = "If selected significant distance lines will be drawn."
    normalsFormLayout.addWidget(adjImageCheckBox)
    self.adjImageCheckBox=adjImageCheckBox

    # interget spin box
    normalsButton1 = qt.QPushButton("Select Number of Sampling Events")
    normalsButton1.toolTip = "Select the P value.  This button is not clickable!"
    normalsButton1.setStyleSheet("font: 12px")
    normalsButton1.checkable = False
    self.layout.addWidget(normalsButton1)
    normalsFrame1 = qt.QFrame(self.parent)
    self.layout.addWidget(normalsFrame1)
    normalsFormLayout1 = qt.QFormLayout(normalsFrame1)

    repBox=qt.QSpinBox()
    normalsFormLayout1.addWidget(repBox)
    repBox.setValue(10000)
    repBox.setMinimum(1)
    repBox.setMaximum(100000)
    self.repBox=repBox

    # set P value
    normalsButton2 = qt.QPushButton("Select the P value")
    normalsButton2.toolTip = "Select the P value.  This button is not clickable!"
    normalsButton2.setStyleSheet("font: 12px")
    normalsButton2.checkable = False
    self.layout.addWidget(normalsButton2)
    normalsFrame2 = qt.QFrame(self.parent)
    self.layout.addWidget(normalsFrame2)
    normalsFormLayout1 = qt.QFormLayout(normalsFrame2)

    pBox=qt.QDoubleSpinBox()
    normalsFormLayout1.addWidget(pBox)
    pBox.setSingleStep(.01)
    pBox.setValue(.05)
    pBox.setMinimum(0)
    pBox.setMaximum(1)
    self.pBox=pBox

    # get Experimetnal Group directory 
    expDirButton1 = qt.QPushButton(" Select Experimetnal Group (Numerator)")
    expDirButton1.checkable = True
    expDirButton1.toolTip="Must be a directory containing .fcsv files."
    expDirButton1.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(expDirButton1)
    expDirFrame1 = qt.QFrame(self.parent)
    self.layout.addWidget(expDirFrame1)
    expDirFormLayout1 = qt.QFormLayout(expDirFrame1)
    expDirButton1.connect('clicked(bool)', self.get_input_file_1)
    self.expDirButton1=expDirButton1
    #display input directory name
    inexpDirNameText1=qt.QLineEdit();
    expDirFormLayout1.addWidget(inexpDirNameText1)
    inexpDirNameText1.setText("Experimental group directory will be displayed after it is selected")
    inexpDirNameText1.toolTip = "Experimental group directory will be displayed after it is selected"
    self.inexpDirNameText1=inexpDirNameText1

     # get Control Group Directory
    ctrlDirButton2 = qt.QPushButton(" Select Control Group Directory (Denominator)")
    ctrlDirButton2.checkable = True
    ctrlDirButton2.toolTip="Must be a directory containing .fcsv files."
    ctrlDirButton2.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(ctrlDirButton2)
    ctrlDirFrame2 = qt.QFrame(self.parent)
    self.layout.addWidget(ctrlDirFrame2)
    ctrlDirFormLayout2 = qt.QFormLayout(ctrlDirFrame2)
    ctrlDirButton2.connect('clicked(bool)', self.get_input_file_2)
    self.ctrlDirButton2=ctrlDirButton2
    #display input directory name
    inDirNameText2=qt.QLineEdit();
    ctrlDirFormLayout2.addWidget(inDirNameText2)
    inDirNameText2.setText("Experimental group directory will displayed after it is selected")
    inDirNameText2.toolTip = "Experimental group directory will be displayed after it is selected"
    self.inDirNameText2=inDirNameText2

     # get Output Directory
    outDirButton3 = qt.QPushButton(" Select Output Directory")
    outDirButton3.checkable = True
    outDirButton3.toolTip="You may wish to create a new folder.  To csv files will be written.  You must have write permission"
    self.layout.addWidget(outDirButton3)
    outDirButton3.setStyleSheet(self.StyleSheet)
    outDirFrame3 = qt.QFrame(self.parent)
    self.layout.addWidget(outDirFrame3)
    outDirFormLayout3 = qt.QFormLayout(outDirFrame3)
    outDirButton3.connect('clicked(bool)', self.get_input_file_3)
    self.outDirButton3=outDirButton3
    #display input directory name
    outDirNameText3=qt.QLineEdit();
    outDirFormLayout3.addWidget(outDirNameText3)
    outDirNameText3.setText("Select Output Directory")
    outDirNameText3.toolTip = " Select Output Directory"
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

  # linked functions
    # Button Functions
  def get_input_file_1(self):
    dir_name=qt.QFileDialog().getExistingDirectory()
    self.expDir=dir_name
    self.inexpDirNameText1.setText(dir_name)

  def get_input_file_2(self):
    dir_name=qt.QFileDialog().getExistingDirectory()
    self.ctrlDir=dir_name
    self.inDirNameText2.setText(dir_name)

  def get_input_file_3(self):
    dir_name=qt.QFileDialog().getExistingDirectory()
    self.outDir=dir_name
    self.outDirNameText3.setText(dir_name)

  def get_input_file_4(self):
    dir_name=qt.QFileDialog().getOpenFileName()
    self.refDir=dir_name
    self.refDirNameText4.setText(dir_name)

  def parseNHDR(self, inputPath, sampleName):
      os.chdir(inputPath)
      # print sampleName

      try:
      # get sample name before underscore
        l=re.search("([^_]*)", sampleName)
        logFiles=glob.glob('*.nhdr')
        to_open=[]
        if '_' in tmp:
          split=tmp.split('_')
        if '-' in tmp:
          split=tmp.split('-')
        l1=split[0]+'-'+split[1]
        l2=split[0]+'_'+split[1]
        lookFor=l1+'|'+l2
        for file in logFiles: 
          tmp=re.search(lookFor,file)
          if tmp:
            to_open.append(file)
        
        with open(inputPath+os.sep+to_open[0]) as f:
          f=f.readlines()
          keyPhrases=[]
          keyPhrases.append('# resolution =')
          keyPhrases.append('# unit =')

          parsedData=[]
          for lines in f:
              for phrase in keyPhrases:
                  if phrase in lines:
                      parsedData.append(lines)
      except:
          return None
          # print 'No log file found'
          # print sampleName, inputPath
          # print lookFor, logFiles


      resolution=None

      if len(parsedData) is 2:
        resolution=parsedData[0].split('=')[1].strip()
        unit=parsedData[1].split('=')[1].strip()       
        unitMatch=re.search('micron',unit)
        if unitMatch:
          resolution=float(resolution)/100.0
          
      return resolution

  # onApply
  def onApply(self):
    # check all inputs
    if not os.path.isdir(self.expDir) or not os.path.isdir(self.ctrlDir) or not os.path.isdir(self.outDir) or not os.path.isfile(self.refDir):
      qt.QMessageBox.critical(
          slicer.util.mainWindow(),
          'Error', 'Check Your Inputs!')

    if self.adjImageCheckBox.isChecked():
      vis=1
      slicer.mrmlScene.Clear(0)
      slicer.util.loadScene(self.refDir)
    else:
      vis=0

    self.reps=self.repBox.value
    self.pValue=self.pBox.value

    # print self.reps, self.pValue, vis

    # display warnings and break if needed

    # copmute
    self.computeAllFM(self.expDir, self.ctrlDir, self.outDir, self.refDir, self.reps , self.pValue, vis)

  # Import landmarks, walk-dir and init data array
  def importLandMarks(self,filePath):
    # import data file
    datafile=open(filePath,'r')
    data=[]
    for row in datafile:
      data.append(row.strip().split(','))
    # Make Landmark array
    dataArray=np.zeros(shape=(len(data)-3,3))
    for i in range(0, len(data)-3):
      tmp=data[i+3]
      if -1000 in tmp:
        return None

      dataArray[i,0:3]=tmp[1:4]

    #read resolution 
    dirName=os.path.dirname(filePath)
    fileName=os.path.basename(filePath)
    resolution=self.parseNHDR(dirName, fileName )

    if resolution:
      dataArray=dataArray*resolution
  
    return dataArray

  def walk_dir(self, top_dir):
    dir_to_explore=[]
    file_to_open=[]
    for path, dir, files in os.walk(top_dir):
      for filename in files:
        if fnmatch.fnmatch(filename,"*.fcsv"):
          dir_to_explore.append(path)
          file_to_open.append(filename)
    return dir_to_explore, file_to_open

  def initDataArray(self,dirs, file):
    k=len(dirs)
    j=3 
    # import data file
    datafile=open(dirs[0]+os.sep+file,'r')
    data=[]
    for row in datafile:
      data.append(row.strip().split(','))
    i= len(data)-3
    landmarks=np.zeros(shape=(i,j,k))
    return landmarks

  # Add Rulers
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
      ln.SetColor((.01,.1,1))
    ln.SetLabelVisibility(0)
    # rulerNode.setLocked(1)
    slicer.app.processEvents()

  # Edit Volume
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

  # Write Data
  def writeData(self, data, filepath):
    with open(filepath, 'wb') as f:
      csv.writer(f, delimiter=',').writerows(data)  

  # Format Output
  def formatOutput(self, probMatrix,Obs, conIntervalLower, condIntervalUpper,p,reps):
    i,j=probMatrix.shape
    formatData=[]
    formatData.append(['LM1','LM2','observed_ratio','permuted_ratio', 'lower_con','upper_con','length'])
    for x in range(0,i):
      for y in range(0,j):
        if x is not y:
          cp=probMatrix[x,y]
          if cp < p and cp is not 0 and not np.isnan(cp) :
            if x<y:
              lenght='-'
            else:
              lenght='+'
            formatData.append([x+1,y+1,Obs[x,y],cp,conIntervalLower[x,y],condIntervalUpper[x,y],lenght])
    
    formatData.append("")
    formatData.append("")
    import datetime
    formatData.append(['Time', str(datetime.datetime.now())])
    formatData.append(['Input files numerator',self.expDir ])
    formatData.append(['Input files denominator',self.ctrlDir] )
    formatData.append(['P-value', p ])
    formatData.append(['Number of permuations', reps])


    return formatData

  # Compute All
  def computeAllFM(self,inputDirExp, inputDirControl, saveFilePath, refpath, rep, p,vis):
    # import controls
    dirs, files=self.walk_dir(inputDirControl)
    landmarksControl=self.initDataArray(dirs,files[0])
    iD,jD,kD=landmarksControl.shape
    nControl=kD
    iD=iD.__int__();jD=jD.__int__();kD=kD.__int__()
   # fill landmarks
    for i in range(0,len(files)):
      tmp=self.importLandMarks(dirs[i]+os.sep+files[i])
      if type(tmp) is None:
        np.delete(landmarksControl,i,axis=2)
      else:
        # print tmp
        it,at=tmp.shape
        it=it.__int__(); at=at.__int__()
        if it == iD and at == jD:
          landmarksControl[:,:,i]=tmp
        else:
          np.delete(landmarksControl,i,axis=2)

    iD,jD,kD=landmarksControl.shape
    nControl=kD
    # import Experimetal
    dirs, files=self.walk_dir(inputDirExp)
    # print files
    landmarksExp=self.initDataArray(dirs,files[0])
    iD,jD,kD=landmarksExp.shape
    # print landmarksExp.shape
    nExp=kD
    iD=iD.__int__();jD=jD.__int__();kD=kD.__int__()
    # print iD
    # fill landmarks
    for i in range(0,len(files)):
      tmp=self.importLandMarks(dirs[i]+os.sep+files[i])
      if type(tmp) is None:
        np.delete(landmarksControl,i,axis=2)
      else:
        it,at=tmp.shape
        # print tmp.shape
        it=it.__int__(); at=at.__int__()
        if it == iD and at == jD:
          landmarksExp[:,:,i]=tmp
        else:
          np.delete(landmarksExp,i,axis=2)

    iD,jD,kD=landmarksExp.shape
    # print landmarksExp.shape
    nExp=kD
    # # merge landmark matrice together.
    landmarks=np.concatenate((landmarksControl,landmarksExp),axis=2)
    # Calculate permuation matric
    logic=EdmaVisLogic()
    probMatrix,Obs=logic.edmaPermuationTest(landmarks,nControl,nExp, rep)
    confLower, confUpper, boot=logic.edmaBootstrap(landmarks,nControl,nExp, rep,p)
    finalData=self.formatOutput(probMatrix,Obs,confLower, confUpper,p, rep)

    # write out data
    self.writeData(Obs,saveFilePath+os.sep+'observedRatios.csv')
    self.writeData(finalData,saveFilePath+os.sep+'formatData.csv')
    # edit 3D volume
    
    if vis:
      print refpath
      dirs, files=self.walk_dir(os.path.dirname(refpath))
      tmp=self.importLandMarks(dirs[0]+os.sep+files[0])
      for x in range(0,iD):
        for y in range(0,iD):
          if x is not y:
            cp=probMatrix[x,y]
            # print cp
            if cp <= p:
              p1=tmp[x,:]
              p2=tmp[y,:]
              if x < y : longer=1
              else: longer=0
              self.addruler(p1,p2,longer)
              slicer.app.processEvents()
      slicer.app.processEvents()
      self.editVolumeProp()
      slicer.app.processEvents()
    
    # print landmarks.shape
    # return landmarks

    # http://stackoverflow.com/questions/11631457/perform-a-for-loop-in-parallel-in-python-3-2
  
class EdmaVisLogic:
  def __init__(self):
    pass

       
  # Two Norm and Dist
  def TwoNorm(self, a):
      id,jd,kd=a.shape
      fnx = lambda q : q - np.reshape(q, (id, 1,kd))
      dx=fnx(a[:,0,:])
      dy=fnx(a[:,1,:])
      dz=fnx(a[:,2,:])
      return (dx**2.0+dy**2.0+dz**2.0)**0.5

  #  calculate the euclidean distance matrix for each sample.
  def dist(self, A):
      return self.TwoNorm(A)

  # edma
  def edma(self, A):
      # get dimension
      iDim,jDim,kDim=A.shape
      iDim=iDim.__int__(); jDim=jDim.__int__(); kDim=kDim.__int__();
      # get distance matrix
      distMatrix=self.dist(A)
      # Calculate Mean over the sample population (denoted by the 2. This is the thrid dimension of the matrix)
      distMeanMatrix=distMatrix.mean(axis=2)
      # Calculate the S matrix aka the varience of the squared distance matrix
      sMatrix=np.apply_along_axis(sum, 0, np.square(distMatrix.transpose()-distMeanMatrix))/kDim
      # Calculate final matrix thing
      if jDim == 2:
        omegaMatrix= (np.square(distMeanMatrix)-sMatrix)**(0.5)
      elif jDim==3:
        omegaMatrix=(np.square(distMeanMatrix)-1.5*sMatrix)**(0.5)
      # print omegaMatrix.shape
      return omegaMatrix 

  # Permuation Test
  def edmaPermuationTest(self, landmarks,nControl, nExp,rep):
      # constants
      nSample=nControl+nExp
      # set random number generator seed
      randomNumberGen=np.random.RandomState(1234567890)
      a=range(0,nSample)
      # iList=range(0,rep)
      # sample without replacement
      # np.random.shuffle(a)
      # return landmarks[:,:,range(0,nControl)]
      Obs=self.edma(landmarks[:,:,range(nControl,nSample)])/self.edma(landmarks[:,:,range(0,nControl)])
      iD,jD,kD=landmarks.shape; iD=iD.__int__()
      # print i,j,k
      permEDMA=np.zeros(shape=(iD,iD,rep))
      # print a
      # args=[]
      # for j in range(rep):
      #     tmp=(landmarks,nControl, nExp, j )
      #     args.append(tmp)

      # numProcessors=multiprocessing.cpu_count()
      # pool=multiprocessing.Pool(numProcessors-1)
      # i=0
      # for data in pool.map(edmaRatio_Perm, args):
      #   tmp=data
      #   permEDMA[:,:,i]=tmp
      #   i=i+1
      # pool.close()  
      # pool.join()
      for x in xrange(0,rep):
        np.random.shuffle(a)
        tmp=self.edma(landmarks[:,:,a[nControl:nSample]])/self.edma(landmarks[:,:,a[0:nControl]])
        permEDMA[:,:,x]=tmp
      # 
      probMatrix=np.zeros(shape=(iD,iD)) 
      #
      size=iD
      for i in range(0,size-1):
        for j in range(i+1,size):
          tmp=np.less_equal(permEDMA[i,j,:],Obs[i,j])
          probMatrix[i,j]=tmp.sum()/float(rep)
          probMatrix[j,i]=1-(tmp.sum()/float(rep))
      return probMatrix, Obs

  # Bootstrap
  def edmaBootstrap(self, landmarks,nControl, nExp,rep,p):
      # number of samples
      nSample=nControl+nExp
      iD,jD,kD=landmarks.shape; iD=iD.__int__()
      permEDMA=np.zeros(shape=(iD,iD,rep))

      # iList=range(0,rep)
      # args=[]
      # for j in range(0,rep):
      #   tmp=(landmarks,nControl,nExp,j)
      #   args.append(tmp)
      # i=0
      # numProcessors=multiprocessing.cpu_count()
      # pool=multiprocessing.Pool(numProcessors-1)
      # for data in pool.map(edmaRatio_Bootstrap ,args):
      #     permEDMA[:,:,i]=data
      #     i=i+1
      # pool.close()  
      # pool.join()
      for x in xrange(0,rep):
        nCtrl=np.random.randint(0,nControl,nControl)
        nEtoh=np.random.randint(nControl,nSample,nSample)
        tmp=self.edma(landmarks[:,:,nEtoh])/self.edma(landmarks[:,:,nCtrl])
        permEDMA[:,:,x]=tmp
      
      bootMatrix=np.sort(permEDMA,axis=2)
      toDrop=np.floor(rep*(p/2.0))
      conIntervalLower=bootMatrix[:,:,toDrop]
      condIntervalUpper=bootMatrix[:,:,(rep-toDrop)]
      # 
      return conIntervalLower, condIntervalUpper, bootMatrix