import logging

logging.info("Customizing with SlicerMorphRC.py")

controlKey = "Ctrl" # this is the command key on mac osx

shortcuts = [
    (controlKey+'+b', lambda: slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)),
    (controlKey+'+n', lambda: slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)),
    (controlKey+'+m', lambda: slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)),
    (controlKey+'+,', lambda: slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)),
    ]

for (shortcutKey, callback) in shortcuts:
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence(shortcutKey))
    if not shortcut.connect( 'activated()', callback):
        print(f"Couldn't set up {shortcutKey}")

logging.info("Done customizing with SlicerMorphRC.py")
