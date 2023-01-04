import logging

logging.info("Customizing with SlicerMorphRC.py")

#set the default volume storage to not compress by default
#
defaultVolumeStorageNode = slicer.vtkMRMLVolumeArchetypeStorageNode()
defaultVolumeStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultVolumeStorageNode)
logging.info("  Volume nodes will be stored uncompressed by default")

#
#set the default volume storage to not compress by default
#
defaultVolumeStorageNode = slicer.vtkMRMLSegmentationStorageNode()
defaultVolumeStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultVolumeStorageNode)
logging.info("  Segmentation nodes will be stored uncompressed")

#
#set the default model save format to ply (from vtk)
#
defaultModelStorageNode = slicer.vtkMRMLModelStorageNode()
defaultModelStorageNode.SetUseCompression(0)
defaultModelStorageNode.SetDefaultWriteFileExtension('ply')
slicer.mrmlScene.AddDefaultNode(defaultModelStorageNode)

#
#disable interpolation of the volumes by default
#
def NoInterpolate(caller,event):
  for node in slicer.util.getNodes('*').values():
    if node.IsA('vtkMRMLScalarVolumeDisplayNode'):
      node.SetInterpolate(0)
slicer.mrmlScene.AddObserver(slicer.mrmlScene.NodeAddedEvent, NoInterpolate)

#
#hide SLicer logo in module tab
#
# slicer.util.findChild(slicer.util.mainWindow(), 'LogoLabel').visible = False

#
#collapse Data Probe tab by default to save space modules tab
#
# slicer.util.findChild(slicer.util.mainWindow(), name='DataProbeCollapsibleWidget').collapsed = True

#
#set the default module from Welcome to Data
#
qt.QSettings().setValue("Modules/HomeModule", "Data")


#
# set volume rendering modes
#
settings = slicer.app.settings()
settings.setValue("VolumeRendering/RenderingMethod", "vtkMRMLCPURayCastVolumeRenderingDisplayNode")
settings.setValue("VolumeRendering/DefaultQuality", "Normal")

#
# orthographic view mode and turn on rulers
#
settings = slicer.app.settings()
settings.setValue("Default3DView/UseOrthographicProjection", True)
settings.setValue("Default3DView/RulerType", "thin")
settings.setValue("DefaultSliceView/RulerType", "thin")

#
# units settings
#
revisionUserSettings = slicer.app.revisionUserSettings()
revisionUserSettings.setValue("length/precision", 10)

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

def cycleEffectForward():
    cycleEffect(1)

def cycleEffectBackward():
    cycleEffect(-1)


# change the main window layout

def setLayout(layoutID):
    slicer.app.layoutManager().setLayout(layoutID)

def setLayoutOneUpRedSliceView():
    setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)

def setLayoutOneUpYellowSliceView():
    setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)

def setLayoutOneUpGreenSliceView():
    setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)

def setLayoutFourUpView():
    setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)

# operate on landmarks

def placeFiducial():
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)
    cursorPosition = qt.QCursor.pos()
    widget = slicer.app.widgetAt(cursorPosition)
    mousePosition = widget.mapFromGlobal(cursorPosition)
    interactor = widget.parent().interactor()
    point = (mousePosition.x(), widget.height - mousePosition.y())
    interactor.SetEventPosition(*point)
    interactor.MouseMoveEvent()
    interactor.LeftButtonPressEvent()
    interactor.LeftButtonReleaseEvent()

def togglePlaceModePersistence():
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetPlaceModePersistence(not interactionNode.GetPlaceModePersistence())

def toggleMarkupLocks():
    selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    placeNode = slicer.mrmlScene.GetNodeByID(selectionNode.GetActivePlaceNodeID())
    if placeNode:
        wasLocked = placeNode.GetNthControlPointLocked(0)
        wasModifying = placeNode.StartModify()
        for index in range(placeNode.GetNumberOfControlPoints()):
            placeNode.SetNthControlPointLocked(index, not wasLocked)
        placeNode.EndModify(wasModifying)

# setup shortcut keys

shortcuts = [
    ('`', cycleEffectForward),
    ('~', cycleEffectBackward),
    ('p', placeFiducial),
    ('t', togglePlaceModePersistence),
    ('l', toggleMarkupLocks),
    ]

for (shortcutKey, callback) in shortcuts:
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence(shortcutKey))
    if not shortcut.connect( 'activated()', callback):
        print(f"Couldn't set up {shortcutKey}")
logging.info(f"  {len(shortcuts)} keyboard shortcuts installed")

logging.info("Done customizing with SlicerMorphRC.py")
logging.info("On first load of customization, restart Slicer to take effect.")

