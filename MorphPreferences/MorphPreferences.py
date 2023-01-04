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
            MorphPreferences.loadPresetFile(self.vrPresetPath())
            toBool = slicer.util.toBool
            key = "MorphPreferences/customize"
            customize = slicer.util.settingsValue(key, False, converter=toBool)
            if customize:
                MorphPreferences.loadRCFile(self.rcPath())

            if not slicer.app.commandOptions().noMainWindow:
              # add the settings options
              self.settingsPanel = MorphPreferencesSettingsPanel(self.rcPath())
              slicer.app.settingsDialog().addPanel("SlicerMorph", self.settingsPanel)

            loadMorphPreferences = int(slicer.util.settingsValue('MorphPreferences/loadMorphPreferences', qt.QMessageBox.InvalidRole))


        slicer.app.connect("startupCompleted()", onStartupCompleted)

    def rcPath(self):
        moduleDir = os.path.dirname(self.parent.path)
        return os.path.join(moduleDir, 'Resources', 'SlicerMorphRC.py')

    @staticmethod
    def loadRCFile(rcPath):
      try:
        exec(open(rcPath).read(), globals())
      except Exception as e:
        import traceback
        traceback.print_exc()
        errorMessage = "Error loading SlicerMorphRC.py\n\n" + str(e) + "\n\nSee Python Console for Stack Trace"
        slicer.util.errorDisplay(errorMessage)
        
### path to the volume rendering customization file.
    def vrPresetPath(self):
        moduleDir = os.path.dirname(self.parent.path)
        return os.path.join(moduleDir, 'Resources', 'SM_VolumePresets.py')

    @staticmethod
    def loadPresetFile(vrPresetPath):
      try:
        exec(open(vrPresetPath).read(), globals())
      except Exception as e:
        import traceback
        traceback.print_exc()
        errorMessage = "Error loading SlicerMorphRC.py\n\n" + str(e) + "\n\nSee Python Console for Stack Trace"
        slicer.util.errorDisplay(errorMessage)

class _ui_MorphPreferencesSettingsPanel:
  def __init__(self, parent, rcPath):
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
    customize = slicer.util.settingsValue(key, False, converter=toBool)
    self.loadMorphPreferencesCheckBox.checked = customize
    genericGroupBoxFormLayout.addRow("Use SlicerMorph customizations:", self.loadMorphPreferencesCheckBox)

    hbox = qt.QHBoxLayout()
    label = qt.QLineEdit(rcPath)
    label.readOnly = True
    genericGroupBoxFormLayout.addRow("Customization file:", label)

    loadNowButton = qt.QPushButton("Load now")
    loadNowButton.toolTip = "Load the customization file now"
    hbox.addWidget(label)
    hbox.addWidget(loadNowButton)
    genericGroupBoxFormLayout.addRow("Customization file:", hbox)

    loadNowButton.connect("clicked()", lambda rcPath=rcPath: MorphPreferences.loadRCFile(rcPath))
    self.loadMorphPreferencesCheckBox.connect("toggled(bool)", self.onLoadMorphPreferencesCheckBoxToggled)

    addDownloadDirectory = False
    if addDownloadDirectory:
        hbox = qt.QHBoxLayout()
        self.downloadDirectory = qt.QLineEdit()
        self.downloadDirectory.readOnly = True
        key = "MorphPreferences/downloadDirectory"
        downloadDirectory = slicer.util.settingsValue(key, "", converter=str)
        if downloadDirectory == "":
            self.downloadDirectory.setText("Defaults")
        else:
            self.downloadDirectory.setText(downloadDirectory)
            self.setDownloadDirectories(downloadDirectory)
        self.setDownloadDirectoryButton = qt.QPushButton("Set")
        self.setDownloadDirectoryButton.connect("clicked()", self.onSetDownloadDirectory)
        hbox.addWidget(self.downloadDirectory)
        hbox.addWidget(self.setDownloadDirectoryButton)
        genericGroupBoxFormLayout.addRow("Download directory:", hbox)

    vBoxLayout.addWidget(genericGroupBox)
    vBoxLayout.addStretch(1)

  def onLoadMorphPreferencesCheckBoxToggled(self, checked):
    slicer.app.settings().setValue("MorphPreferences/customize", checked)

  def onSetDownloadDirectory(self):
    directory = qt.QFileDialog.getExistingDirectory()
    if directory != "":
        self.downloadDirectory.setText(directory)
        slicer.app.settings().setValue("MorphPreferences/downloadDirectory", directory)
        self.setDownloadDirectories(directory)

  def setDownloadDirectories(self, directory):
    slicer.app.settings().setValue("Cache/Path", directory)
    slicer.app.settings().setValue("Modules/TemporaryDirectory", directory)


class MorphPreferencesSettingsPanel(ctk.ctkSettingsPanel):
  def __init__(self, rcPath, *args, **kwargs):
    ctk.ctkSettingsPanel.__init__(self, *args, **kwargs)
    self.ui = _ui_MorphPreferencesSettingsPanel(self, rcPath)
