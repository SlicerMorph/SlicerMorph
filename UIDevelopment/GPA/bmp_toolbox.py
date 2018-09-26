import os
import re
import csv
import glob
from __main__ import vtk, qt, ctk, slicer

class bmp_toolbox:
  def __init__(self, parent):
    parent.title = "BMP_Toolbox"
    parent.categories = ["Maga Lab"]
    parent.dependencies = []
    parent.contributors = ["Ryan Young"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    This toolbox automates the process of importing a bmp images sequence and creating a scalar volume. In additon 
    the entered metadata is stored both in a csv file and as attributes on the scalar volume nodes.
    Basic adjustments to the window level, scalar opacity mapping, and scalar color
     mapping are made.
    """
    parent.acknowledgementText = """ Developed at Seattle Children's Hospital  """ 
    self.parent = parent

def ctkb(parent, text, buttonText):
    # inputFrame = qt.QFrame(parent)
    # inputFrame.setLayout(qt.QHBoxLayout())
    inbutton=ctk.ctkCollapsibleButton()
    inbutton.text=text
    Mylayout= qt.QGridLayout(inbutton)
    # 
    fileInButton, fileInDisp = fileIn(buttonText)
    Mylayout.addWidget(fileInButton,2,1,1,15)
    Mylayout.addWidget(fileInDisp,3,1,1,15)
   # fileInButton.connect('clicked(bool)', test)

    # general discription.  Whatever you would like to say
    dtextIn, dtextLabel= textIn('Description (Suffix)','Extra Information. One word','Baseline, Day 5, ...')
    Mylayout.addWidget(dtextIn, 1,2)
    Mylayout.addWidget(dtextLabel, 1,1)

    volumeIn, volumeInLabel=textIn('Volume Name','Enter volume name', 'No Spaces!')
    Mylayout.addWidget(volumeIn,4,2)
    Mylayout.addWidget(volumeInLabel,4,1)
   
    return inbutton, fileInButton, volumeIn, fileInDisp, dtextIn

def textIn(label, dispText, toolTip):
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
    return textInLine, lineLabel

def intSpinBox(label, min_int, max_int, inc, dispText):
    """ a function to set up the appearnce of a QSpinBox widget.
        the widget is returned.
        """
     # spinBox
    spinBox=qt.QSpinBox()
    spinBox.setSingleStep(inc)
    spinBox.setMinimum(min_int)
    spinBox.setMaximum(max_int)
    spinBox.setSpecialValueText(dispText)
    #  Label
    boxLabel=qt.QLabel()
    boxLabel.setText(label)
    return spinBox, boxLabel
    
def doubleSpinBox(label, min, max, inc, dispText):
    """ a function to set up the appearnce of a QSpinBox widget.
        the widget is returned.
        """
     # spinBox
    spinBox=qt.QDoubleSpinBox()
    spinBox.setSingleStep(inc)
    spinBox.setMinimum(min)
    spinBox.setMaximum(max)
    spinBox.setSpecialValueText(dispText)
    #  Label
    boxLabel=qt.QLabel()
    boxLabel.setText(label)
    return spinBox, boxLabel

def comboBox(label, choices=[]):
    """ Defines a cobox with a label. Both returned.
        The argument for the combox comboBox are passed in as a list
        """
    cBox=qt.QComboBox()
    for item in choices:
        cBox.addItem(item)
    # label
    cBoxLabel=qt.QLabel()
    cBoxLabel.setText(label)
    return cBox, cBoxLabel

def fileIn(buttonText):
    fileInButton = qt.QPushButton(buttonText)
    fileInButton.checkable = True
    fileInButton.toolTip="Must select bmp image sequance"
    StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
    fileInButton.setStyleSheet(StyleSheet)
    #display input directory name
    fileNameDisp=qt.QLineEdit();
    fileNameDisp.setText("Input directory  will be displayed after it is selected")
    fileNameDisp.toolTip = "Input directory  will be displayed after it is selected"
    return fileInButton, fileNameDisp

def parseName(inputFile):
    splitPath=inputFile.split('/')
    # try:
    node_name=splitPath[-1]
    # print "in parseName: splitinputfile, node_name", inputFile, node_name
    # except IndexError:
    try:
        tmp=re.search('__rec',node_name)
        if tmp.group():
            node_name=node_name[0:tmp.start()]
    except:
        pass
    return node_name


class bmp_toolboxWidget:
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
    # View buttons
    normalsButton = qt.QPushButton("Information")
    normalsButton.toolTip = "Select if you want the images adjusted.  This button is not clickable!"
    normalsButton.setStyleSheet("font: 12px")
    normalsButton.checkable = False
    self.layout.addWidget(normalsButton)
    normalsFrame = qt.QFrame(self.parent)
    self.layout.addWidget(normalsFrame)
    normalsFormLayout = qt.QGridLayout(normalsFrame)

    self.dadIn, dadLabel=textIn("Father's Name","", 'No Spaces!')
    normalsFormLayout.addWidget(self.dadIn,5,2)
    normalsFormLayout.addWidget(dadLabel,5,1)
 
    self.momIn, momLabel=textIn("Mother's Name","", 'No Spaces!')
    normalsFormLayout.addWidget(self.momIn,6,2)
    normalsFormLayout.addWidget(momLabel,6,1)
 
    self.strainIn, strainLabel=textIn("Strain's Name","C57BL_6J", 'Do not change')
    normalsFormLayout.addWidget(self.strainIn,7,2)
    normalsFormLayout.addWidget(strainLabel,7,1)
 
    self.litterBox, litterLabel =intSpinBox('Litter (# pups)', 1, 100, 1, '')
    normalsFormLayout.addWidget(self.litterBox,8,2)
    normalsFormLayout.addWidget(litterLabel, 8,1)
 
    self.wieghtBox, wieghtLabel = doubleSpinBox('Weight (g)', 1, 10000, 0.1, '')
    normalsFormLayout.addWidget(self.wieghtBox,9,2)
    normalsFormLayout.addWidget(wieghtLabel,9 ,1)

    self.ageBox, agaLabel = doubleSpinBox('Age (days)', 10, 100, 0.5, '')
    normalsFormLayout.addWidget(self.ageBox,10,2)
    normalsFormLayout.addWidget(agaLabel,10 ,1)
 
    self.expBox, expLabel= comboBox('Experiment',['Pre-Gestational', 'Gestational', 'Postnatal','Paternal' ])
    normalsFormLayout.addWidget(self.expBox,11,2)
    normalsFormLayout.addWidget(expLabel,11,1)
 
    self.treatmentBox, treatmentLabel= comboBox('Treatment',['Control', 'Ethanol', 'Sucrose' ])
    normalsFormLayout.addWidget(self.treatmentBox,12,2)
    normalsFormLayout.addWidget (treatmentLabel,12,1)

    self.stageBox, stageLabel= comboBox('Stage',['Fetal', 'Postnatal' ])
    normalsFormLayout.addWidget(self.stageBox,13,2)
    normalsFormLayout.addWidget(stageLabel,13,1)

    myctkButton1, inFile1, self.inName1, self.inDisp1, self.dscirpIn =ctkb(self.parent,'Scan One','Select Frist Image Sequance ')
    self.layout.addWidget(myctkButton1)
    inFile1.connect('clicked(bool)', self.get_input_file_1)

   

    sampleButton = qt.QPushButton("Sample Information")
    sampleButton.toolTip = "Select if you want the images adjusted.  This button is not clickable!"
    sampleButton.setStyleSheet("font: 12px")
    sampleButton.checkable = False
    self.layout.addWidget(sampleButton)
    sampleFrame = qt.QFrame(self.parent)
    self.layout.addWidget(sampleFrame)
    sampleLayout = qt.QGridLayout(sampleFrame)

    # getSaveDir=qt.QPushButton("Select Output Directory")
    # getSaveDir.setStyleSheet(self.StyleSheet)
    # getSaveDir.connect('clicked(bool)', self.getSaveDirFunc)
    # sampleLayout.addWidget(getSaveDir,1,1,1,2)

    self.sampleName=qt.QLineEdit()
    sampleNameLabel=qt.QLabel()
    sampleNameLabel.setText('Sample Name')
    sampleEnty=qt.QFrame()
    sampleLayout.addWidget(self.sampleName,3,2)
    sampleLayout.addWidget(sampleNameLabel,3,1)

    # self.saveDirTextLine=qt.QLineEdit()
    # saveDirLabel=qt.QLabel()
    # saveDirLabel.setText('Output Directory')
    # sampleEnty=qt.QFrame()
    # sampleLayout.addWidget(self.saveDirTextLine,2,2)
    # sampleLayout.addWidget(saveDirLabel,2,1)



    myctkButton2, inFile2, self.inName2, self.inDisp2, self.dscirpIn2 =ctkb(self.parent,'Scan Two','Select Second Image Sequance')
    self.layout.addWidget(myctkButton2)
    inFile2.connect('clicked(bool)', self.get_input_file_2)

    applyButton = qt.QPushButton("Apply")
    applyButton.checkable = True
    applyButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(applyButton)
    applyButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    applyFrame=qt.QFrame(self.parent)
    self.layout.addWidget(applyButton)
    applyButtonFormLayout=qt.QFormLayout(applyFrame)
    applyButton.connect('clicked(bool)', self.onApply)

    resetButton = qt.QPushButton("Reset")
    resetButton.checkable = True
    resetButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(resetButton)
    resetButton.toolTip = "Push to reset all fields."
    applyFrame=qt.QFrame(self.parent)
    self.layout.addWidget(resetButton)
    applyButtonFormLayout=qt.QFormLayout(applyFrame)
    resetButton.connect('clicked(bool)', self.reset)

    # self.pBar=qt.QProgressBar()
    # self.pBar.setFormat('Working')
    # self.layout.addWidget(self.pBar)


    self.metaData={'sample_name':None, 'dad':None, 'mom':None, 'strain':None, 
                    'litter':None, 'weight':None, 'experiment':None, 'treatment':None, 
                    'stage':None, 'age':None, 'volOneName': None, 'volOnePath': None, 'VolTwoName': None,
                    'volTwoPath': None, 'username':None}

    # self.writeAttributes()
    self.layout.addStretch(1)   

    input_file=[]
    
# Reset
  def reset(self):
    # reset metaData
     self.metaData={'sample_name':None, 'dad':None, 'mom':None, 'strain':None, 
                    'litter':None, 'weight':None, 'experiment':None, 'treatment':None, 
                    'stage':None, 'age':None, 'volOneName': None, 'volOnePath': None, 'VolTwoName': None,
                    'volTwoPath': None,  'username':None}
    
    # reset information fields
     self.dadIn.setText('')
     self.momIn.setText('')
     self.strainIn.setText('C57BL_6J')
     self.litterBox.setSpecialValueText('')
     self.wieghtBox.setSpecialValueText('')
     self.ageBox.setSpecialValueText('')

    # reset Scan one fields
     self.inName1.setText('Enter volume name')
     self.inDisp1.setText('Input directory  will be displayed after it is selected')
     self.dscirpIn.setText('Extra Information. One word')
     # self.saveDir.setText('')

    # reset Scan two fields
     self.inName2.setText('Enter volume name')
     self.inDisp2.setText('Input directory  will be displayed after it is selected')
     self.dscirpIn2.setText('Extra Information. One word')
     self.sampleName.setText('')

     # reset dave location
     # self.saveDirTextLine.setText('')
     # reset local varibales
     self.input_file=[]

# Functions linked to buttons Get input files
  def get_input_file_1(self):
    dir_name=qt.QFileDialog().getOpenFileName()
    self.input_file.append(dir_name)
    fileName=parseName(dir_name) 
    # print fileName
    self.dirName=dir_name

    if self.dscirpIn.modified:
        name=fileName+"_"+self.dscirpIn.text
        self.inName1.setText(name)
        self.setName1=name
    else:
        self.inName1.setText(fileName)
    self.inDisp1.setText(dir_name)
    self.sampleName.setText(fileName)
    

  def get_input_file_2(self):
    dir_name=qt.QFileDialog().getOpenFileName()
    self.input_file.append(dir_name)
    fileName=parseName(dir_name)
    if self.dscirpIn2.modified:
        name=fileName+"_"+self.dscirpIn2.text
        self.inName2.setText(name)
        self.setName=name
    else:
        self.inName2.setText(fileName)
    self.inDisp2.setText(dir_name)
    self.metaData['name']=fileName
  
  def getSaveDirFunc(self):
      self.saveDir=qt.QFileDialog().getExistingDirectory()
      self.saveDirTextLine.setText(self.saveDir)

# Get metadata
  def getMetaData(self):
    # self.metaData['name']=self.inName1.text
    self.metaData['dad']=self.dadIn.text
    self.metaData['mom']=self.momIn.text
    self.metaData['strain']=self.strainIn.text
    self.metaData['litter']=self.litterBox.value
    self.metaData['weight']=self.wieghtBox.value
    self.metaData['treatment']=self.treatmentBox.currentText
    self.metaData['stage']=self.stageBox.currentText 
    self.metaData['experiment']=self.expBox.currentText
    self.metaData['sample_name']=self.sampleName.text
    self.metaData['age']=self.ageBox.value
    self.metaData['volOneName']=self.inName1.text
    self.metaData['volOnePath']=self.inDisp1.text
    self.metaData['volTwoName']=self.inName2.text
    self.metaData['volTwoPath']=self.inDisp2.text
    self.metaData['username']=os.environ['USERNAME']

# Convert vector to scalar
  def convert_to_scalar_volume(self, vectorVolume, node_name ):
    #set input cvolume
    # inputClass=slicer.mrmlScene.GetNodesByClass('vtkMRMLVectorVolumeNode')
    inputVolume=vectorVolume

    # create new scalar node and add to mrml scene
    scalarNode=slicer.vtkMRMLScalarVolumeNode()
    scene=slicer.mrmlScene
    scene.AddNode(scalarNode)

    # check that input is good
    # check for input data
    if not (inputVolume and scalarNode):
      qt.QMessageBox.critical(
          slicer.util.mainWindow(),
          'Error', 'Input and output volumes are required for conversion')
      return
    # check that data has enough components
    inputImage = inputVolume.GetImageData()
    if not inputImage or inputImage.GetNumberOfScalarComponents() < 3:
      qt.QMessageBox.critical(
          slicer.util.mainWindow(),
          'Vector to Scalar Volume', 'Input does not have enough components for conversion')
      return

    # run the filter
    # code barrowed from Steve Piper's Vector to Scalar Volume Module
    # - extract the RGB portions 
    extract = vtk.vtkImageExtractComponents()
    extract.SetComponents(0,1,2)
    extract.SetInput(inputVolume.GetImageData())
    luminance = vtk.vtkImageLuminance()
    luminance.SetInput(extract.GetOutput())
    luminance.GetOutput().Update()
    ijkToRAS = vtk.vtkMatrix4x4()
    inputVolume.GetIJKToRASMatrix(ijkToRAS)
    scalarNode.SetIJKToRASMatrix(ijkToRAS)
    scalarNode.SetAndObserveImageData(luminance.GetOutput())
    # set node name
    scalarNode.SetName(node_name)
    # make the output volume appear in all the slice view
    
    # do not bother to render if adjustments will be made later.
    # if self.adjImageCheckBox.isChecked()==0:
    #     # make the output volume appear in all the slice view
    #     selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    #     selectionNode.SetReferenceActiveVolumeID(scalarNode.GetID())
    #     slicer.app.applicationLogic().PropagateVolumeSelection(0)
    #     slicer.app.processEvents()
    #     mrml=slicer.mrmlScene
    #     vn=slicer.mrmlScene.GetNthNodeByClass(0,'vtkMRMLViewNode')
    #     logic = slicer.modules.volumerendering.logic()
    #     logic.SetAndObserveMRMLScene(mrml)
    #     b=logic.CreateVolumeRenderingDisplayNode()
    #     mrml.AddNode(b)
    #     logic.UpdateDisplayNodeFromVolumeNode(b, scalarNode )
    #     scalarNode.AddAndObserveDisplayNodeID(b.GetID())
    #     lm=slicer.app.layoutManager()
    #     view=lm.threeDWidget(0).threeDView()
    #     view.resetFocalPoint()
    #     self.view=view
    #     slicer.app.processEvents()

    # delete vector volume
    slicer.mrmlScene.RemoveNode(inputVolume)

    return scalarNode

# Adjust node 
  def adjust_node(self,scalarNode,volumeNumber):
   
    #propagate new scalar node to all views 
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID(scalarNode.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection(0)
    slicer.app.processEvents()

    # make sure new node is rendered
    mrml=slicer.mrmlScene
    vn=slicer.mrmlScene.GetNthNodeByClass(0,'vtkMRMLViewNode')
    logic = slicer.modules.volumerendering.logic()
    logic.SetAndObserveMRMLScene(mrml)
    b=logic.CreateVolumeRenderingDisplayNode()
    mrml.AddNode(b)
    logic.UpdateDisplayNodeFromVolumeNode(b, scalarNode )
    scalarNode.AddAndObserveDisplayNodeID(b.GetID())


    # set window level
    dispNode=scalarNode.GetDisplayNode()
    dispNode.SetAutoWindowLevel(0)
    dispNode.SetWindowLevelMinMax(0,256)
    slicer.app.processEvents()
    dispNode.GetWindowLevelMax()
    
    # make histogram and get mean and std
    i=scalarNode.GetImageData()
    tmp_matrix=vtk.util.numpy_support.vtk_to_numpy(i.GetPointData().GetScalars() )
    mean=tmp_matrix.mean()
    std=tmp_matrix.std()
    slicer.app.processEvents()

    #get volume property node and edit transfer function
    vpClass=slicer.mrmlScene.GetNodesByClass('vtkMRMLVolumePropertyNode')
    vpNode=vpClass.GetItemAsObject(volumeNumber)
    slicer.app.processEvents()
    scalarOpacityNode=vpNode.GetScalarOpacity()
    scalarOpacityNode.RemoveAllPoints()
    scalarOpacityNode.AddPoint(mean+1.5*std, 0)
    scalarOpacityNode.AddPoint(mean+2.5*std, 1)

    # adjust scalar color mapping
    colorTransFunc=vtk.vtkColorTransferFunction()
    colorTransFunc.AddRGBPoint(.01,0,0,0)
    colorTransFunc.AddRGBPoint(mean+2.5*std,1,1,1)
    colorTransFunc.AddRGBPoint(254,1,1,1)
    # add color transfer function to volume property node
    vpNode.SetColor(colorTransFunc)

    # edit view
    lm=slicer.app.layoutManager()
    view=lm.threeDWidget(0).threeDView()
    view.resetFocalPoint()
    self.view=view
    slicer.app.processEvents()

# set resolution
  def setResolution(self,scalarNode,resolution):
     # set resolution
    resolution=resolution*(10**(-3))
    scalarNode.SetSpacing((resolution,resolution,resolution))
   
# Create Template
  def createLMnode(self, name,scene):
    LMnode=slicer.vtkMRMLMarkupsFiducialNode()
    LMnode.SetName(name)
    scene.AddNode(LMnode)


  def createLTnode(self, name,scene):
    LTnode=slicer.vtkMRMLLinearTransformNode()
    LTnode.SetName(name)
    scene.AddNode(LTnode)


  def createTemplate(self, filename):
    # get mrml scene
    scene=slicer.mrmlScene
    # add Skull Landmarks
    self.createLMnode(filename+'_Skull_1',scene)
    self.createLMnode(filename+'_Skull_2',scene)
    # add Madi Landmarks
    self.createLMnode(filename+'_Mandible_1',scene)
    self.createLMnode(filename+'_Mandible_2',scene)
    # add linear transform 
    self.createLTnode(filename+'_Transform',scene)

# write Attributes
  def writeAttributes(self, scalarNode):
    for keys in self.metaData:
        scalarNode.SetAttribute(keys, str(self.metaData[keys]))

# adjust view
  def adjustView(self,scalarNode):
    x=x1=y=y1=z=z1=0
    q=[x,x1,y,y1,z,z1]
    scalarNode.GetRASBounds(q)
    lm=slicer.app.layoutManager()
    # lm.setLayout(4)
    view=lm.threeDWidget(0).threeDView()
    view.lookFromViewAxis(ctk.ctkAxesWidget.Anterior)
    view.setFocalPoint((x1-x)/2.0, (y1-y)/2.0,(z1-z/2.0) )
    view.zoomIn()
    view.zoomIn()
    slicer.app.processEvents()

# Task
  def longTask(self):
    volumeNumber=0
    slicer.app.processEvents()
    for inputFile in self.input_file:
        # check got input file error
        # print "inputFile",inputFile
        if (inputFile[(len(inputFile)-3):len(inputFile)] != 'bmp') or (len(inputFile)==0) :
            print inputFile
            qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Error', 'You must select an bmp image sequance!  Try Select Input Image Sequance again!')
            break

        # load scene
        vl=slicer.vtkSlicerVolumesLogic()
        mrml=slicer.mrmlScene
        vl.SetAndObserveMRMLScene(mrml)
        vectorVolumeNode=vl.AddArchetypeVolume(inputFile ,'vectorVolume')
        filename=os.path.basename(inputFile)

        #set node_name
        if volumeNumber==0:
            node_name=self.inName1.text
        else:
            node_name=self.inName2.text

        resolution=parseLogFile(self.dirName)
        # print resolution
        scalarNode = self.convert_to_scalar_volume(vectorVolumeNode,node_name) 
        self.createTemplate(node_name)
        self.getMetaData()
        self.writeAttributes(scalarNode)
        self.adjust_node(scalarNode, volumeNumber)
        slicer.app.processEvents()
        # if possible, set resolution
        if resolution:
            self.setResolution(scalarNode, resolution)

        self.adjustView(scalarNode)
        volumeNumber +=1

    # after looping over volumes write sample info to log. 
    try:
        writeLog(self.metaData)
    except:
         qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Error', 'Metadata not written to database.')
    # saveScene(self.metaData['sample_name'], self.saveDir)
    slicer.app.processEvents()
    # noCompression(scalarNode)
    slicer.app.processEvents()
    self.reset()
   
# onApply
  def onApply(self):
    self.longTask()
    # slicer.app.processEvents()
    # noCompression()
    slicer.app.processEvents()


# ------------------------- end of BMP Widget -----------------------------------------

def writeLog(metaData):
    path=os.environ['USERPROFILE']
    compName=os.environ['COMPUTERNAME']
    data=list(metaData.values())
    with open(path+os.sep+"Dropbox (Maga Lab)"+os.sep+compName+'_SlicerDataLog.csv', 'a') as f:
      csv.writer(f, dialect='excel').writerow(data)  

    # # # path=os.environ['DB']
    # path='/home/magalab/Dropbox (Maga Lab)'
    # # order=[6,2,4,5,8,1,0,3,9,7]
    # order=[6,2,4,5,8,9,1,0,3,7]
    # tmp=list(metaData.keys())
    # data=[tmp[i] for i in order]
    # print data
    # with open(path+os.sep+'SlicerDataLog.csv', 'a') as f:
    #   csv.writer(f, dialect='excel').writerow(data)  
       
def parseLogFile(dirName):
    path=os.path.dirname(dirName)
    os.chdir(path)
    logFiles=glob.glob('*_rec.log')
    if len(logFiles)==0:
         logFiles=glob.glob('*rec_voi_.log')
       
    if len(logFiles)==0:
        print "log file not found"
        return None
    
    with open(path+os.sep+logFiles[0]) as f:
        f=f.readlines()

    keyPhrases=[]
    keyPhrases.append('Image Pixel Size (um)=')

    parsedData=[]
    for lines in f:
        for phrase in keyPhrases:
            if phrase in lines:
                parsedData.append(lines)

    if len(parsedData) is not 1:
        print "Too many fields found"
    # print parsedData
    resolution=None

    try:
        tmp=parsedData[0].split('=')
        resolution=float(tmp[1].strip())
    except IndexError:
        qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Error', 'Log file not found. Resolution will not be written')

    return resolution

def saveScene( sceneName, path):
    if not path:
        qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Error', 'Choose scene saving directory')

    saveLocation=path+os.sep+sceneName
    print saveLocation
    if not os.path.isdir(saveLocation):
        os.mkdir(saveLocation)
    # print saveLocation
    logic=slicer.app.applicationLogic()
    saved=logic.SaveSceneToSlicerDataBundleDirectory(saveLocation, None)
    slicer.app.processEvents()

    if not saved:
         qt.QMessageBox.critical(
            slicer.util.mainWindow(),
            'Error', 'Scene did not save')

def noCompression(scalarNode):
    nodeList=slicer.util.getNodes('*StorageNode*')
    for key in nodeList.keys():
        tmpNode=nodeList[key]
        tmpNode.SetUseCompression(0)
        print "Compression dissabled on: ", key
        slicer.app.processEvents()



