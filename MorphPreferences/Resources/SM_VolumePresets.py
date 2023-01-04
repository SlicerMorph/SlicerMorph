import logging

logging.info("Adding SlicerMorph Volume Rendering Presets")

# setting presets
moduleDir = os.path.dirname(slicer.util.modulePath("MorphPreferences"))
presetsScenePath = os.path.join(moduleDir, 'Resources/SM_presets.mrml')

# Read presets scene
customPresetsScene = slicer.vtkMRMLScene()
vrPropNode = slicer.vtkMRMLVolumePropertyNode()
customPresetsScene.RegisterNodeClass(vrPropNode)
customPresetsScene.SetURL(presetsScenePath)
customPresetsScene.Connect()

# Add presets to volume rendering logic
vrLogic = slicer.modules.volumerendering.logic()
presetsScene = vrLogic.GetPresetsScene()
vrNodes = customPresetsScene.GetNodesByClass("vtkMRMLVolumePropertyNode")
vrNodes.UnRegister(None)
for itemNum in range(vrNodes.GetNumberOfItems()):
  node = vrNodes.GetItemAsObject(itemNum)
  vrLogic.AddPreset(node)
