import logging
import os
import vtk, qt, ctk, slicer
import warnings
from slicer.ScriptedLoadableModule import *

from SubjectHierarchyPlugins import AbstractScriptedSubjectHierarchyPlugin

class MorphPreferences(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "SlicerMorph MorphPreferences Plugin"
        parent.categories = [""]
        parent.contributors = ["Steve Pieper, Isomics, Inc."]
        parent.helpText = ""
        parent.hidden = not slicer.util.settingsValue('Developer/DeveloperMode', False, converter=slicer.util.toBool)

        #
        # register Settings panel and perform customizations
        #
        def onStartupCompleted():

            toBool = slicer.util.toBool
            key = "MorphPreferences/customize"
            customize = slicer.util.settingsValue(key, True, converter=toBool)
            if customize:
              moduleDir = os.path.dirname(self.parent.path)
              rcPath = os.path.join(moduleDir, 'Resources', 'SlicerMorphRC.py')
              try:
                exec(open(rcPath).read())
              except Exception as e:
                import traceback
                traceback.print_exc()
                errorMessage = "Error loading SlicerMorphRC.py\n\n" + str(e) + "\n\nSee Python Console for Stack Trace"
                slicer.util.errorDisplay(errorMessage)
              


            if not slicer.app.commandOptions().noMainWindow:
              # add the settings options
              self.settingsPanel = MorphPreferencesSettingsPanel()
              slicer.app.settingsDialog().addPanel("SlicerMorph", self.settingsPanel)

            loadMorphPreferences = int(slicer.util.settingsValue('MorphPreferences/loadMorphPreferences', qt.QMessageBox.InvalidRole))


        slicer.app.connect("startupCompleted()", onStartupCompleted)


class _ui_MorphPreferencesSettingsPanel(object):
  def __init__(self, parent):
    vBoxLayout = qt.QVBoxLayout(parent)
    # Add generic settings
    genericGroupBox = ctk.ctkCollapsibleGroupBox()
    genericGroupBox.title = "Generic SlicerMorph settings"
    genericGroupBoxFormLayout = qt.QFormLayout(genericGroupBox)

    self.loadMorphPreferencesCheckBox = qt.QCheckBox()
    self.loadMorphPreferencesCheckBox.toolTip = ("Customize SlicerMorph features such as hotkeys at startup"
      " (file can be customized in python for advanced users).",
      " Restart the app for changes to take effect.")
    toBool = slicer.util.toBool
    key = "MorphPreferences/customize"
    customize = slicer.util.settingsValue(key, True, converter=toBool)
    self.loadMorphPreferencesCheckBox.checked = customize

    genericGroupBoxFormLayout.addRow("Use SlicerMorph customizations:", self.loadMorphPreferencesCheckBox)

    self.loadMorphPreferencesCheckBox.connect("toggled(bool)", self.onLoadMorphPreferencesCheckBoxToggled)

    vBoxLayout.addWidget(genericGroupBox)
    vBoxLayout.addStretch(1)

  def onLoadMorphPreferencesCheckBoxToggled(self, checked):
    qt.QSettings().setValue("MorphPreferences/customize", checked)


class MorphPreferencesSettingsPanel(ctk.ctkSettingsPanel):
  def __init__(self, *args, **kwargs):
    ctk.ctkSettingsPanel.__init__(self, *args, **kwargs)
    self.ui = _ui_MorphPreferencesSettingsPanel(self)

