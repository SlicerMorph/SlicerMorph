import os
import glob
import fnmatch
import  numpy as np
from __main__ import vtk, qt, ctk, slicer
# TODO
# update how to create volume nodes
# check resampling quality with differnent sizes

class landmark_toolbox:
    def __init__(self, parent):
        parent.title = "Landmark Checker"
        parent.categories = ["Maga Lab"]
        parent.dependencies = []
        parent.contributors = ["Ryan E Young"] # replace with "Firstname Lastname (Org)"
        parent.helpText = """
        The module recursive searched a directory for fcsv files.  
        The files are then paired if the following convention is meet, name.fcsv, name*2.fcsv.
        The linear distance between landmarks is compared to the tolerance.
        Landmark with distances greater than the tolerance are output to the
        landmark_check.txt file in the output directory. 
        """
        parent.acknowledgementText = """ Seattle Children's Hospital  """ 
        self.parent = parent



class landmark_toolboxWidget:
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

    def textIn(self, label, dispText, toolTip):
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

    
        # select input directory
        self.inputDirline, inputDirLabel, self.inputDirButton=self.textIn('Input Directory','', 'No Spaces!')
        inputLayout.addWidget(self.inputDirline,1,2)
        inputLayout.addWidget(inputDirLabel,1,1)
        inputLayout.addWidget(self.inputDirButton,1,3)
        self.inputDirButton.connect('clicked(bool)', self.selectInputDir)
        self.layout.addWidget(inbutton)

         # select output directory
        self.outputDirline, outputDirLabel, self.outputDirButton=self.textIn('Output Directory','', 'No Spaces!')
        inputLayout.addWidget(self.outputDirline,2,2)
        inputLayout.addWidget(outputDirLabel,2,1)
        inputLayout.addWidget(self.outputDirButton,2,3)
        self.outputDirButton.connect('clicked(bool)', self.selectOutputDir)

        #tolerance 
        tolLabel=qt.QLabel()
        tolLabel.setText("Distance Tolerance")
        inputLayout.addWidget(tolLabel,3,1)
        self.toleranceBox=qt.QDoubleSpinBox()
        self.toleranceBox.setRange(0.0,100.0)
        self.toleranceBox.setValue(1.0)
        self.toleranceBox.setSingleStep(0.01)
        inputLayout.addWidget(self.toleranceBox,3,2,1,2)
     

        #apply buttion
        checkButton=qt.QPushButton("Check")
        checkButton.checkable = True
        checkButton.setStyleSheet(self.StyleSheet)
        checkButton.toolTip="Click to run program.  Must have choose a directory already "
        checkButton.connect("clicked(bool)", self.onCheck)
        inputLayout.addWidget(checkButton,4,1,1,3)

        self.layout.addStretch(1)  

#Gui function
    def selectInputDir(self):
        self.inputDir=qt.QFileDialog().getExistingDirectory()
        self.inputDirline.setText(self.inputDir)

    def selectOutputDir(self):
        self.outputDir=qt.QFileDialog().getExistingDirectory()
        self.outputDirline.setText(self.outputDir)    
       
    def onCheck(self):
      self.tol=self.toleranceBox.value
      logic=landmark_toolboxLogic()
      logic.qualityControl(self.inputDir, self.tol, self.outputDir)
      qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Done', 'The output file is names landmark_check.txt')
#import functions
class landmark_toolboxLogic:
  def __init__(self):
    pass
  def importLandMarks(self,filePath):
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
    for i in data:
      tmp=np.array(i)[1:4]
      # print type(tmp), tmp.shape
      dataArray[j,0:3]=tmp
      j=j+1

          # print i
      # if -1000 in tmp[1:4]:
      #   # print "-1000"
      #   return None
     # dataArray[i,0:3]=tmp[1:4]
        # print type(dataArray[i,2] )

      #read resolution 
    dirName=os.path.dirname(filePath)
    fileName=os.path.basename(filePath)
      # resolution=parseNHDR(dirName, fileName )

      # if resolution:
      #   dataArray=dataArray*resolution
    # print dataArray
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

  def initDataArray(self,dirs, file,k):  
    """
    returns an np array for the storage of the landmarks.
    """
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

  def importAllLandmarks(self,inputDirControl, outputFolder):
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

  def createMatchList(self,topDir,suffix):
    l=[]
    for root, dirs, files in os.walk(topDir):
        for name in files:
            if fnmatch.fnmatch(name,"*"+suffix):
                l.append(os.path.join(root, name[:-5]))
   # print "lenght l",len(l)
    matchList=[]
   # print l
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

  def qualityControl(self, topDir,tol,outDir,suffix=".fcsv"):
      # initial data array
      dirs, files=self.walk_dir(topDir)
      matchList, noMatch=self.createMatchList(topDir, suffix)
      landmarks=self.initDataArray(dirs,files[0],len(matchList))
      #open file
      myfile=open(outDir+os.sep+"landmark_check.txt",'w')
      myfile.write("Tolerance: "+str(tol)+"\n"+"\n")
      for i in range(len(matchList)):
          tmp1=self.importLandMarks(matchList[i][0]+suffix)
          tmp2=self.importLandMarks(matchList[i][1]+ suffix)
          tmp=(((tmp1-tmp2)**2).sum(axis=1))**0.5
          landmarkNumbers=np.where(tmp>tol)
          #convert to text
          num=landmarkNumbers[0].shape[0]
         # print "\n num", num, matchList[i][0]
        #convert to text
          if num != 0:
            t1=landmarkNumbers[0]
            l=[]
            j=t1.shape
            for x in range(j[0]):
                l.append(str(t1[x]+1))
            lands=", ".join(l)
            
            #print
            if j[0] is not 0:
                text="filename: "+matchList[i][0]+suffix+"\n"+"\t Landmarks Numbers: "+lands+"\n"+"\n"
                myfile.write(text)

      myfile.write("\n \nNo matching landmark file found for the following files: \n")
      for item in noMatch:
          myfile.write("\t"+str(item)+suffix+"\n")
      myfile.close()
    
    
