import os
import fnmatch
from __main__ import vtk, qt, ctk, slicer



class ExportImages:
  def __init__(self, parent):
    parent.title = "Export Images"
    parent.categories = ["Maga Lab"]
    parent.dependencies = []
    parent.contributors = ["Ryan Young"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    A scripted loadable extension for the export_images functions.
    """
    parent.acknowledgementText = """ Developed at Seattle Children's Hospital  """ 
    self.parent = parent


class ExportImagesWidget:
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
    

    # View buttons
    normalsButton = qt.QPushButton("Views")
    normalsButton.toolTip = "Select only one view"
    normalsButton.checkable = False
    self.layout.addWidget(normalsButton)
    normalsFrame = qt.QFrame(self.parent)
    self.layout.addWidget(normalsFrame)
    normalsFormLayout = qt.QFormLayout(normalsFrame)

    viewACheckBox = qt.QCheckBox("Anterior View")
    normalsFormLayout.addWidget(viewACheckBox)
    self.viewACheckBox=viewACheckBox

    viewLCheckBox = qt.QCheckBox("Left View")
    normalsFormLayout.addWidget(viewLCheckBox)
    self.viewLCheckBox=viewLCheckBox

    viewPCheckBox = qt.QCheckBox("Posterior View")
    normalsFormLayout.addWidget(viewPCheckBox)
    self.viewPCheckBox=viewPCheckBox

    viewRCheckBox = qt.QCheckBox("Right View")
    normalsFormLayout.addWidget(viewRCheckBox)
    self.viewRCheckBox=viewRCheckBox

    viewSCheckBox = qt.QCheckBox("Superoir View")
    normalsFormLayout.addWidget(viewSCheckBox)
    self.viewSCheckBox=viewSCheckBox

    viewICheckBox = qt.QCheckBox("Inferoir View")
    normalsFormLayout.addWidget(viewICheckBox)
    self.viewICheckBox=viewICheckBox



    # Rendering Mode buttons
    renderButton = qt.QPushButton("Render Mode")
    renderButton.toolTip = "Select only one render mode"
    renderButton.checkable = False
    self.layout.addWidget(renderButton)
    renderFrame = qt.QFrame(self.parent)
    self.layout.addWidget(renderFrame)
    renderFormLayout = qt.QFormLayout(renderFrame)

    per_CheckBox = qt.QCheckBox("Perspective Mode")
    renderFormLayout.addWidget(per_CheckBox)
    self.per_CheckBox = per_CheckBox

    ortho_CheckBox = qt.QCheckBox("Orthographic Mode")
    renderFormLayout.addWidget(ortho_CheckBox)
    self.ortho_CheckBox = ortho_CheckBox


    # Get Folder Name
    folderButton = qt.QPushButton(" Output Folder")
    folderButton.toolTip = "Set output folder name. No spaces is best"
    folderButton.checkable = False
    self.layout.addWidget(folderButton)
    folderFrame = qt.QFrame(self.parent)
    self.layout.addWidget(folderFrame)
    folderFormLayout = qt.QFormLayout(folderFrame)

    folderName=qt.QLineEdit("Enter Folder Name")
    folderFormLayout.addWidget(folderName)

    self.folderName=folderName

    # get input directory directory
    dirButton = qt.QPushButton(" Select Input Directory")
    dirButton.checkable = True
    dirButton.toolTip="Push button to select input directory"
    self.layout.addWidget(dirButton)
    dirFrame = qt.QFrame(self.parent)
    self.layout.addWidget(dirFrame)
    dirFormLayout = qt.QFormLayout(dirFrame)
    dirButton.connect('clicked(bool)', self.get_dir)
   
    self.dirButton=dirButton

    #display input directory name
    inDirNameText=qt.QLineEdit();
    dirFormLayout.addWidget(inDirNameText)
    inDirNameText.setText("Input directory will be displayed after it is selected")
    inDirNameText.toolTip = "Input directory will be displayed after it is selected"

    self.inDirNameText=inDirNameText
    # get output directory directory
    outDirButton = qt.QPushButton(" Select Output Directory")
    outDirButton.checkable = True
    outDirButton.toolTip="Push button to select output directory"
    self.layout.addWidget(outDirButton)
    outDirFrame = qt.QFrame(self.parent)
    self.layout.addWidget(outDirFrame)
    outDirFormLayout = qt.QFormLayout(outDirFrame)
    outDirButton.connect('clicked(bool)', self.get_out_dir)

    outDirNameText=qt.QLineEdit();
    outDirFormLayout.addWidget(outDirNameText)
    outDirNameText.setText("Output directory will be displayed after it is selected")
    outDirNameText.toolTip = "Output directory will be displayed after it is selected. Folder name must be entered frist"
    
    self.outDirNameText = outDirNameText
    # This will take you to a 
    # dirField=qt.QFileDialog().getExistingDirectory()

    # self.dirButton=dirButton
    # Apply button
    applyButton = qt.QPushButton("Apply")
    applyButton.checkable = True
    self.layout.addWidget(applyButton)
    applyButton.toolTip = "Push to export images. Make sure you have choosen an inpout and output director."
    applyFrame=qt.QFrame(self.parent)
    self.layout.addWidget(applyButton)
    applyButtonFormLayout=qt.QFormLayout(applyFrame)
    applyButton.connect('clicked(bool)', self.onApply)


    # Add vertical spacer
    self.layout.addStretch(1)
  
    
  def get_dir(self):
    dir_name=qt.QFileDialog().getExistingDirectory()
    self.dir_name=dir_name
    self.inDirNameText.setText(dir_name)

  def get_out_dir(self):
    dir_out_name=qt.QFileDialog().getExistingDirectory()
    self.dir_out_name=dir_out_name
    total_out_dir=dir_out_name+os.sep+self.folderName.text
    self.outDirNameText.setText(total_out_dir)

    
  def get_render_mode(self):
    if self.per_CheckBox.isChecked():
      self.render_mode=1
    else:
      self.render_mode=0
    return self.render_mode


  def get_view_axis(self):
    if self.viewICheckBox.isChecked():
      self.view_axis='I'
    elif self.viewSCheckBox.isChecked():
      self.view_axis='S'
    elif self.viewPCheckBox.isChecked():
      self.view_axis='P'
    elif self.viewRCheckBox.isChecked():
      self.view_axis='R'
    elif self.viewLCheckBox.isChecked():
      self.view_axis='L'
    else:
       self.view_axis='A'
    return self.view_axis
  

  def get_node(self):
    # make sure 3D view is rendered

    logic = slicer.modules.volumerendering.logic()
    vn=getNode('vtkMRMLViewNode1')
    a=logic.GetVolumeRenderingDisplayNodeForViewNode(vn)
    try:
        a.VisibilityOn()
    except:
        print "No node called VolumeRendering. Image may be ugly! "
        try:
            logic = slicer.modules.volumerendering.logic()
            volumeNode = slicer.mrmlScene.GetNodeByID('vtkMRMLScalarVolumeNode1')
            displayNode = logic.CreateVolumeRenderingDisplayNode()
            slicer.mrmlScene.AddNode(displayNode)
            displayNode.UnRegister(logic)
            logic.UpdateDisplayNodeFromVolumeNode(displayNode, volumeNode)
            volumeNode.AddAndObserveDisplayNodeID(displayNode.GetID())
            c=getNode('VolumeProperty')
            d=c.GetScalarOpacity()
            d.RemoveAllPoints()
            d.AddPoint(0,0)
            d.AddPoint(30,0)
            d.AddPoint(70,1)
        except:
            print "Could not render volume"


    # try:
    #     tempNode=getNode('VolumeRendering')
    #     tmp=tempNode.GetVisibility()
    #     if tmp==0:
    #         tempNode.VisibilityOn()
    # except AttributeError:
        # print "No node called VolumeRendering. Image may not render "
        # logic = slicer.modules.volumerendering.logic()
        # volumeNode = slicer.mrmlScene.GetNodeByID('vtkMRMLScalarVolumeNode1')
        # displayNode = logic.CreateVolumeRenderingDisplayNode()
        # slicer.mrmlScene.AddNode(displayNode)
        # displayNode.UnRegister(logic)
        # logic.UpdateDisplayNodeFromVolumeNode(displayNode, volumeNode)
        # volumeNode.AddAndObserveDisplayNodeID(displayNode.GetID())
        # c=getNode('VolumeProperty')
        # d=c.GetScalarOpacity()
        # d.RemoveAllPoints()
        # d.AddPoint(0,0)
        # d.AddPoint(30,0)
        # d.AddPoint(70,1)
    # # tempNode=getNode('VolumeRendering')
    # # tmp=tempNode.GetVisibility()
    # # if tmp==0:
    # #     tempNode.VisibilityOn()
    # # #set up node
    
    # try:
    #     tempNode=getNode('vtkMRMLVolumeRenderingDisplayNode1')
    #     tmp=tempNode.GetVisibility()
    #     if tmp==0:
    #         tempNode.VisibilityOn()
    # except AttributeError:
    #     print "No node called vtkMRMLVolumeRenderingDisplayNode1. Image my not render"

    node=slicer.mrmlScene.GetNodeByID('vtkMRMLViewNode1')
    return node

  def get_view(self):
    lm=slicer.app.layoutManager()
    lm.setLayout(4)
    view=lm.threeDWidget(0).threeDView()
    return view


  def adjust_node(self, node):
    #node=slicer.mrmlScene.GetNodeByID('vtkMRMLViewNode1')
    node.SetBoxVisible(0)
    node.SetAxisLabelsVisible(0)
    node.SetBackgroundColor([1,1,1])
    node.SetBackgroundColor2([1,1,1])


  def set_view(self, view,view_axis,render_mode, node):
    #global view
    view.resetFocalPoint()   
    if view_axis=='A':
         view.lookFromViewAxis(ctk.ctkAxesWidget.Anterior)
    elif view_axis=='L':
        view.lookFromViewAxis(ctk.ctkAxesWidget.Left)
    elif view_axis=='P':
        view.lookFromViewAxis(ctk.ctkAxesWidget.Posterior)
    elif view_axis=='R':
        view.lookFromViewAxis(ctk.ctkAxesWidget.Right)
    elif view_axis=='S':
        view.lookFromViewAxis(ctk.ctkAxesWidget.Superior)
    elif view_axis=='I':
        view.lookFromViewAxis(ctk.ctkAxesWidget.Inferior)
    view.resetFocalPoint()
    node.SetRenderMode(render_mode)


  def write_image(self, file_name,top,folder_name,view_axis,view, out_dir):
   
    img = qt.QPixmap.grabWidget(view).toImage()
    slicer.app.processEvents()
    file_name=file_name[0:len(file_name)-5]
    slicer.app.processEvents()
    im_name_and_path=out_dir+os.sep+folder_name+os.sep+file_name+"_"+view_axis+".png"
    img.scaled(2,2)
    slicer.app.processEvents()
    img.save(im_name_and_path)
    slicer.app.processEvents()


  def move_camera(self, view):
    view.setZoomFactor(.5)
    view.zoomOut()
    view.zoomOut()
    # view.zoomOut()
    slicer.app.processEvents()


  def adjust_image(self, view,node,view_axis, render_mode):
    self.adjust_node(node)
    slicer.app.processEvents()
    self.set_view(view,view_axis, render_mode,node)
    slicer.app.processEvents()
    self.move_camera(view)
    slicer.app.processEvents()


  def do_all(self, file_name,top,folder_name,view_axis,render_mode, out_dir):
    view=self.get_view()
    slicer.app.processEvents()
    node=self.get_node()
    slicer.app.processEvents()
    self.adjust_image(view,node,view_axis,render_mode)
    slicer.app.processEvents()
    self.write_image(file_name,top,folder_name,view_axis, view, out_dir)
    slicer.app.processEvents()

  def walk_dir(self, top_dir):
    dir_to_explore=[]
    file_to_open=[]
    for path, dir, files in os.walk(top_dir):
     for filename in files:
      if fnmatch.fnmatch(filename,"*.mrml"):
       #print filename
       dir_to_explore.append(path)
       file_to_open.append(filename)
    return dir_to_explore, file_to_open


  def check_inputs(self, view_axis,render_mode, top_dir, output_dir, folder_name):
    possible_views=['A','L','P','R','S','I']
    possible_render_modes=[0,1]
    if view_axis not in possible_views:
        print "Invalid view axis. Terminating"
        print "Valid views are: A,L,P,R,S,I"
        # sys.exit
    if render_mode not in possible_render_modes:
        print "Invalid render mode. Terminating"
        print "Valid render modes are: 0, or 1"
        print "0 for perspective, 1 for orthographic "
        # sys.exit
    if folder_name == "Enter Folder Name":
      print "Please choose folder Name"
  


  def export_images(self,top_dir,folder_name,per_mode,view_angle, out_dir):
    # check_inputs(view_axis,render_mode)
    dirs,files=self.walk_dir(top_dir)
    os.chdir(out_dir)
    if os.path.isdir(folder_name):
        print "Folder already exist.  Existing images may be overwritten."
    else:
        os.chdir(out_dir)
        os.mkdir(folder_name)

    for i in range(0,len(files)):
       os.chdir(dirs[i])
       slicer.app.processEvents()
       slicer.mrmlScene.Clear(0)
       slicer.app.processEvents()
       # print files[i]
       slicer.util.loadScene(files[i])
       slicer.app.processEvents()
       self.do_all(files[i],top_dir,folder_name,view_angle, per_mode, out_dir)
       slicer.app.processEvents()

    slicer.app.processEvents()
    # slicer.mrmlScene.Clear(0)
    # slicer.app.processEvents()
    
  def onApply(self):
    # node = self.get_node()
    # view =self.get_view()
    
    
    per_mode=self.get_render_mode()
    view_angle=self.get_view_axis()
    folder_name=self.folderName.text
    top_dir=self.dir_name
    out_dir=self.dir_out_name
    # print top_dir
    # print folder_name
    # print per_mode
    # print view_angle
    # self.check_inputs( top_dir, folder_name, per_mode, view_angle, out_dir)
    self.export_images( top_dir, folder_name, per_mode, view_angle, out_dir)  
  