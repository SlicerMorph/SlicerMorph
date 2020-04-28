def addMenuShortcuts(targetCategory, newSubdirectory, modulesToMap):
  menu = mainWindow().moduleSelector().modulesMenuComboBox().menu()
  for action in menu.actions():
    if action.text == targetCategory:
      submenu = action.menu()   
  subsubmenu = submenu.addMenu(newSubdirectory)      

  for module in modulesToMap:
    action = qt.QAction(module, subsubmenu)
    action.connect("triggered()", lambda module=module : slicer.util.selectModule(module))
    subsubmenu.addAction(action)

#add links to community modules recommended for use with SlicerMorph
addMenuShortcuts("SlicerMorph", "Recommended Community Modules", ["CurvedPlanarReformat", "FiducialRegistrationWizard", "Lights", "RawImageGuess"])

#set the default volume storage to not compress by default
defaultVolumeStorageNode = slicer.vtkMRMLVolumeArchetypeStorageNode()
defaultVolumeStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultVolumeStorageNode)
logging.info("Volume nodes will be stored uncompressed by default")

#set the default volume storage to not compress by default
defaultVolumeStorageNode = slicer.vtkMRMLSegmentationStorageNode()
defaultVolumeStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultVolumeStorageNode)
logging.info("Segmentation nodes will be stored uncompressed")

#set the default model save format to ply (from vtk)
defaultModelStorageNode = slicer.vtkMRMLModelStorageNode()
defaultModelStorageNode.SetUseCompression(0)
defaultModelStorageNode.SetDefaultWriteFileExtension('ply')
slicer.mrmlScene.AddDefaultNode(defaultModelStorageNode)

#disable interpolation of the volumes by default
def NoInterpolate(caller,event):
  for node in slicer.util.getNodes('*').values():
    if node.IsA('vtkMRMLScalarVolumeDisplayNode'):
      node.SetInterpolate(0)
slicer.mrmlScene.AddObserver(slicer.mrmlScene.NodeAddedEvent, NoInterpolate)

#hide SLicer logo in module tab
slicer.util.findChild(slicer.util.mainWindow(), 'LogoLabel').visible = False

#collapse Data Probe tab by default to save space modules tab
slicer.util.findChild(slicer.util.mainWindow(), name='DataProbeCollapsibleWidget').collapsed = True

#customize keystrokes for segment editor to cycle through effects
# ` goes to previous and ~ skips to next effect

def cycleEffect(delta=1):
    try:
        orderedNames = list(slicer.modules.SegmentEditorWidget.editor.effectNameOrder())
        allNames = slicer.modules.SegmentEditorWidget.editor.availableEffectNames()
        for name in allNames:
            try:
                orderedNames.index(name)
            except ValueError:
                orderedNames.append(name)
        orderedNames.insert(0, None)
        activeEffect = slicer.modules.SegmentEditorWidget.editor.activeEffect()
        if activeEffect:
            activeName = slicer.modules.SegmentEditorWidget.editor.activeEffect().name
        else:
            activeName = None
        newIndex = (orderedNames.index(activeName) + delta) % len(orderedNames)
        slicer.modules.SegmentEditorWidget.editor.setActiveEffectByName(orderedNames[newIndex])
    except AttributeError:
        # module not active
        pass

shortcuts = [
    ('`', lambda: cycleEffect(1)),
    ('~', lambda: cycleEffect(-1)),
    ]

for (shortcutKey, callback) in shortcuts:
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence(shortcutKey))
    shortcut.connect( 'activated()', callback)
