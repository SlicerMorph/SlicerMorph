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
    self.exportTfmAsAction = qt.QAction(f"Export Hardened as...", scriptedPlugin)
    self.menu = qt.QMenu("Plugin Menu")
    self.menu2 = qt.QMenu("Plugin Menu")
    self.exportAsAction.setMenu(self.menu)
    self.exportTfmAsAction.setMenu(self.menu2)

  #
  # item context menus are what happens when you right click on a selected line
  #
  def itemContextMenuActions(self):
    """the actions that could be shown for any of this plugins items"""
    return [self.exportAsAction]

  def showContextMenuActionsForItem(self, itemID):
    """Set actions visible that are valid for this itemID"""
    pluginHandlerSingleton = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
    subjectHierarchyNode = pluginHandlerSingleton.subjectHierarchyNode()
    self.exportAsAction.visible = True
    self.exportAsAction.enabled = False
    self.exportTfmAsAction.visible = True
    self.exportTfmAsAction.enabled = False
    self.menu.clear()
    self.menu2.clear()
    associatedNode = subjectHierarchyNode.GetItemDataNode(itemID)
    if associatedNode is not None and associatedNode.IsA("vtkMRMLStorableNode"):
        self.exportAsAction.enabled = True
        writerExtensions = slicer.app.coreIOManager().fileWriterExtensions(associatedNode)
        for writerFormat in writerExtensions:
          a = self.menu.addAction(writerFormat)
          a.connect("triggered()", lambda writerFormat=writerFormat : self.export(associatedNode, writerFormat)))  
    if associatedNode is not None and associatedNode.IsA("vtkMRMLStorableNode") and associatedNode.GetTransformNodeID():
        self.exportTfmAsAction.enabled = True
        writerExtensions = slicer.app.coreIOManager().fileWriterExtensions(associatedNode)
        for writerFormat in writerExtensions:
          b = self.menu2.addAction(writerFormat)
          b.connect("triggered()", lambda writerFormat=writerFormat : self.exportHardened(associatedNode, writerFormat))

  def export(self, node, writerFormat):
    fileName = qt.QFileDialog.getSaveFileName(slicer.util.mainWindow(),
                                            "Export As...", node.GetName(), writerFormat)
    extension = slicer.vtkDataFileFormatHelper.GetFileExtensionFromFormatString(writerFormat)
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
  
  def exportHardened(self, node, writerFormat):
    # Clone model node
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(node)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    print (clonedItemID)
    clonedNode = shNode.GetItemDataNode(clonedItemID)
    
    # Apply model node transform to cloned node
    trfNode = slicer.mrmlScene.GetNodeByID(node.GetTransformNodeID())
    clonedNode.SetAndObserveTransformNodeID(trfNode.GetID())

    # Harden cloned model transform
    transformLogic = slicer.vtkSlicerTransformLogic()
    transformLogic.hardenTransform(clonedNode)

    # Save cloned model to file
    fileName = qt.QFileDialog.getSaveFileName(slicer.util.mainWindow(),
                                            "Export As...", clonedNode.GetName(), writerFormat)
    extension = slicer.vtkDataFileFormatHelper.GetFileExtensionFromFormatString(writerFormat)
    if not fileName.endswith(extension):
        fileName = fileName + extension
    if fileName == "":
      return
    writerType = slicer.app.coreIOManager().fileWriterFileType(clonedNode)
    success = slicer.app.coreIOManager().saveNodes(writerType, {"nodeID": clonedNode.GetID(), "fileName": fileName})
    if success:
      logging.info(f"Exported {clonedNode.GetName()} to {fileName}")
    else:
      slicer.util.errorDisplay(f"Could not save {clonedNode.GetName()} to {fileName}")

    # Remove cloned model Node
    slicer.mrmlScene.RemoveNode(clonedNode)
