import logging
import os
import vtk, qt, ctk, slicer
import warnings
from slicer.ScriptedLoadableModule import *

from SubjectHierarchyPlugins import AbstractScriptedSubjectHierarchyPlugin

class FormatMarkups(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "SlicerMorph Format Markups Plugin"
        parent.categories = [""]
        parent.contributors = [" Sara Rolfe (UW), Murat Maga (UW)"]
        parent.helpText = ""
        parent.hidden = not slicer.util.settingsValue('Developer/DeveloperMode', False, converter=slicer.util.toBool)

        #
        # register subject hierarchy plugin once app is initialized
        #
        def onStartupCompleted():
            import SubjectHierarchyPlugins
            from FormatMarkups import FormatMarkupsSubjectHierarchyPlugin
            scriptedPlugin = slicer.qSlicerSubjectHierarchyScriptedPlugin(None)
            scriptedPlugin.name = "FormatMarkups"
            scriptedPlugin.setPythonSource(FormatMarkupsSubjectHierarchyPlugin.filePath)
        slicer.app.connect("startupCompleted()", onStartupCompleted)


class FormatMarkupsSubjectHierarchyPlugin(AbstractScriptedSubjectHierarchyPlugin):
  """ Scripted subject hierarchy plugin for the formatMarkups extension.
  """

  # Necessary static member to be able to set python source to scripted subject hierarchy plugin
  filePath = __file__

  def __init__(self, scriptedPlugin):
    AbstractScriptedSubjectHierarchyPlugin.__init__(self, scriptedPlugin)

    pluginHandlerSingleton = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
    self.subjectHierarchyNode = pluginHandlerSingleton.subjectHierarchyNode()
    self.formatMarkupsAction = qt.QAction(f"Apply formatting to siblings", scriptedPlugin)
    self.menu = qt.QMenu("Plugin Menu")
    self.formatMarkupsAction.setMenu(self.menu)

  #
  # item context menus are what happens when you right click on a selected line
  #
  def itemContextMenuActions(self):
    """the actions that could be shown for any of this plugins items"""
    return [self.formatMarkupsAction]

  def showContextMenuActionsForItem(self, itemID):
    """Set actions visible that are valid for this itemID"""
    # reset all menus
    self.formatMarkupsAction.visible = False
    self.formatMarkupsAction.enabled = False
    self.menu.clear()
    # check if this is parent or leaf
    siblingIDList = vtk.vtkIdList()
    itemDataNode = self.subjectHierarchyNode.GetItemDataNode(itemID)
    parentID = self.subjectHierarchyNode.GetItemParent(itemID)
    parentIsScene = bool(self.subjectHierarchyNode.GetItemName(parentID) == "Scene")
    markupNodeTypes=["vtkMRMLMarkupsFiducialNode", "vtkMRMLMarkupsNode"]
    if itemDataNode is not None and itemDataNode.IsA("vtkMRMLMarkupsFiducialNode") and not parentIsScene:
      self.subjectHierarchyNode.GetItemChildren(parentID, siblingIDList)
      if siblingIDList.GetNumberOfIds()>0:
        copyDisplayAction = self.menu.addAction(f"Copy display properties to siblings")
        copyVisibilityAction = self.menu.addAction(f"Copy point visibility to siblings")
        uniqueColorAction = self.menu.addAction(f"Apply unique node color to siblings")
        copyDisplayAction.triggered.connect(lambda: self.copyDisplayProperties(itemDataNode, itemID, siblingIDList))
        copyVisibilityAction.triggered.connect(lambda: self.copyPointVisibility(itemDataNode, itemID, siblingIDList))
        uniqueColorAction.triggered.connect(lambda: self.applyUniqueColors(siblingIDList))
        # enable all menu options
        self.formatMarkupsAction.visible = True
        self.formatMarkupsAction.enabled = True
        copyDisplayAction.visible = True
        copyDisplayAction.enabled = True
        copyVisibilityAction.visible = True
        copyVisibilityAction.enabled = True

  def copyDisplayProperties(self, itemDataNode, itemID, siblingIDList):
    markupsLogic = slicer.modules.markups.logic()
    nodeLocked = itemDataNode.GetLocked()
    controlPointNumberLocked = itemDataNode.GetFixedNumberOfControlPoints()
    for i in range(siblingIDList.GetNumberOfIds()):
      siblingID = siblingIDList.GetId(i)
      if(itemID != siblingID):
        siblingNode = self.subjectHierarchyNode.GetItemDataNode(siblingID)
        markupsLogic.CopyBasicDisplayProperties(itemDataNode.GetDisplayNode(), siblingNode.GetDisplayNode())
        siblingNode.SetFixedNumberOfControlPoints(controlPointNumberLocked)
        siblingNode.SetLocked(nodeLocked)
        if(itemDataNode.GetNumberOfControlPoints() != siblingNode.GetNumberOfControlPoints()):
          logging.debug("Cannot apply control point lock flags to sibling with unequal point number: %s" % siblingNode.GetName())
        else:
          for j in range(itemDataNode.GetNumberOfControlPoints()):
            siblingNode.SetNthControlPointLocked(j, itemDataNode.GetNthControlPointLocked(j))


  def copyPointVisibility(self, itemDataNode, itemID, siblingIDList):
    for i in range(siblingIDList.GetNumberOfIds()):
      siblingID = siblingIDList.GetId(i)
      if(itemID == siblingID):
        next
      siblingNode = self.subjectHierarchyNode.GetItemDataNode(siblingID)
      if(itemDataNode.GetNumberOfControlPoints() != siblingNode.GetNumberOfControlPoints()):
        logging.debug("Cannot apply control point visibility to sibling with unequal point number: %s" % siblingNode.GetName())
      else:
        for j in range(itemDataNode.GetNumberOfControlPoints()):
          siblingNode.SetNthControlPointVisibility(j, itemDataNode.GetNthControlPointVisibility(j))

  def applyUniqueColors(self, siblingIDList):
    colorTableList = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLColorTableNode', 'GenericColors')
    colorTable = colorTableList.GetItemAsObject(0)
    color = [0,0,0,0]
    colorIndex = 1
    for i in range(siblingIDList.GetNumberOfIds()):
      siblingID = siblingIDList.GetId(i)
      siblingNode = self.subjectHierarchyNode.GetItemDataNode(siblingID)
      colorTable.GetColor(colorIndex,color)
      siblingNode.GetDisplayNode().SetSelectedColor(color[0:3])
      if colorIndex < 307:
        colorIndex+=1
      else:
        colorIndex=1

