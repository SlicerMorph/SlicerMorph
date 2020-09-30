import logging

logging.info("Customizing with SlicerMorphRC.py")


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

#
# Keyboard shortcuts
#

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


# change the main window layout

def setLayout(layoutID):
    slicer.app.layoutManager().setLayout(layoutID)

# operate on landmarks

def enterPlaceFiducial():
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)

def togglePlaceModePersistence():
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetPlaceModePersistence(not interactionNode.GetPlaceModePersistence())

def toggleMarkupLocks():
    selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    placeNode = slicer.mrmlScene.GetNodeByID(selectionNode.GetActivePlaceNodeID())
    if placeNode:
        placeNode.SetLocked(not placeNode.GetLocked())

# setup shortcut keys

shortcuts = [
    ('`', lambda: cycleEffect(1)),
    ('~', lambda: cycleEffect(-1)),
    ('Ctrl+b', lambda: setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)),
    ('Ctrl+n', lambda: setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)),
    ('Ctrl+m', lambda: setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)),
    ('Ctrl+,', lambda: setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)),
    ('p', enterPlaceFiducial),
    ('t', togglePlaceModePersistence),
    ('l', toggleMarkupLocks),
    ]

for (shortcutKey, callback) in shortcuts:
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence(shortcutKey))
    if not shortcut.connect( 'activated()', callback):
        print(f"Couldn't set up {shortcutKey}")


logging.info("Done customizing with SlicerMorphRC.py")
