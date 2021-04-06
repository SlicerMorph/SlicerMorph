import logging
import os
import vtk, qt, ctk, slicer
import warnings
from slicer.ScriptedLoadableModule import *

from SubjectHierarchyPlugins import AbstractScriptedSubjectHierarchyPlugin

class ExportAs(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "SlicerMorph ExportAs Plugin"
        parent.categories = [""]
        parent.contributors = ["Steve Pieper, Isomics, Inc."]
        parent.helpText = ""
        parent.hidden = not slicer.util.settingsValue('Developer/DeveloperMode', False, converter=slicer.util.toBool)

        #
        # register subject hierarchy plugin once app is initialized
        #
        def onStartupCompleted():
            import SubjectHierarchyPlugins
            from ExportAs import ExportAsSubjectHierarchyPlugin
            scriptedPlugin = slicer.qSlicerSubjectHierarchyScriptedPlugin(None)
            scriptedPlugin.name = "ExportAs"
            scriptedPlugin.setPythonSource(ExportAsSubjectHierarchyPlugin.filePath)
        slicer.app.connect("startupCompleted()", onStartupCompleted)


class ExportAsSubjectHierarchyPlugin(AbstractScriptedSubjectHierarchyPlugin):
  """ Scripted subject hierarchy plugin for the ExportAs extension.
  """

  # Necessary static member to be able to set python source to scripted subject hierarchy plugin
  filePath = __file__

  def __init__(self, scriptedPlugin):
    AbstractScriptedSubjectHierarchyPlugin.__init__(self, scriptedPlugin)

    self.exportAsAction = qt.QAction(f"Export as...", scriptedPlugin)
    self.exportTransformedAsAction = qt.QAction(f"Export transformed as...", scriptedPlugin)
    self.menu = qt.QMenu("Plugin Menu")
    self.transformedMenu = qt.QMenu("Transformed Plugin Menu")
    self.exportAsAction.setMenu(self.menu)
    self.exportTransformedAsAction.setMenu(self.transformedMenu)

  #
  # item context menus are what happens when you right click on a selected line
  #
  def itemContextMenuActions(self):
    """the actions that could be shown for any of this plugins items"""
    return [self.exportAsAction, self.exportTransformedAsAction]

  def showContextMenuActionsForItem(self, itemID):
    """Set actions visible that are valid for this itemID"""
    pluginHandlerSingleton = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
    subjectHierarchyNode = pluginHandlerSingleton.subjectHierarchyNode()
    self.exportAsAction.visible = True
    self.exportAsAction.enabled = False
    self.exportTransformedAsAction.visible = False
    self.exportTransformedAsAction.enabled = False
    self.menu.clear()
    self.transformedMenu.clear()
    associatedNode = subjectHierarchyNode.GetItemDataNode(itemID)
    writeFormats = slicer.app.coreIOManager().fileWriterExtensions(associatedNode)

    # convert ('Markups JSON (.json)', 'Markups Fiducial CSV (.fcsv)')
    # to "Markups *.mrk.json *.json *.fcsv"
    # and {'.mrk.json': 'Markups JSON *.mrk.json', '.fcsv': 'Markups Fiducial CSV *.fcsv')
    allExtensionsFilter = ""
    filtersByExtension = {}
    formatsByExtension = {}
    for writerExtension in writeFormats:
      extension = writerExtension.split()[-1][1:-1]
      formatsByExtension[extension] = writerExtension
      allExtensionsFilter += " *" + extension
      filtersByExtension[extension] = f"{' '.join(writerExtension.split()[:-1])} *{extension}"

    menuAndFlags = [[self.menu, False]]
    if associatedNode is not None and associatedNode.IsA("vtkMRMLTransformableNode") and associatedNode.GetTransformNodeID():
      self.exportTransformedAsAction.visible = True
      self.exportTransformedAsAction.enabled = True
      menuAndFlags.append([self.exportTransformedAsAction, True])

    # export without transforming menu entries
    if associatedNode is not None and associatedNode.IsA("vtkMRMLStorableNode"):
        allExtensionsFilter = associatedNode.GetNodeTagName() + allExtensionsFilter
        self.exportAsAction.enabled = True
        for menu,transformedFlag in menuAndFlags:
          for extension in filtersByExtension.keys():
            a = menu.addAction(formatsByExtension[extension])
            a.connect("triggered()", lambda extension=extension, writerFilter=filtersByExtension[extension], allExtensionsFilter=allExtensionsFilter, transformedFlag=transformedFlag : self.export(associatedNode, extension, writerFilter, allExtensionsFilter, transformedFlag))


  def export(self, node, extension, writerFilter, allExtensionsFilter = "", transformedFlag = False):
    if transformedFlag:
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      itemIDToClone = shNode.GetItemByDataNode(node)
      clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
      clonedNode = shNode.GetItemDataNode(clonedItemID)

      transformNode = slicer.mrmlScene.GetNodeByID(node.GetTransformNodeID())
      clonedNode.SetAndObserveTransformNodeID(transformNode.GetID())

      transformLogic = slicer.vtkSlicerTransformLogic()
      transformLogic.hardenTransform(clonedNode)

      node = clonedNode

    fileFilter = allExtensionsFilter + ";;" + writerFilter + ";;All files *"
    fileName = qt.QFileDialog.getSaveFileName(slicer.util.mainWindow(),
                                            "Export As...", node.GetName()+extension, fileFilter, None, qt.QFileDialog.DontUseNativeDialog)
    if not fileName.endswith(extension):
        fileName = fileName + extension
    if fileName == "":
      return
    writerType = slicer.app.coreIOManager().fileWriterFileType(node)
    success = slicer.app.coreIOManager().saveNodes(writerType, {"nodeID": node.GetID(), "fileName": fileName})
    if success:
      logging.info(f"Exported {node.GetName()} to {fileName}")
    else:
      slicer.util.errorDisplay(f"Could not save {node.GetName()} to {fileName}")

    if transformedFlag:
      slicer.mrmlScene.RemoveNode(clonedNode.GetStorageNode())
      slicer.mrmlScene.RemoveNode(clonedNode.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(clonedNode)

