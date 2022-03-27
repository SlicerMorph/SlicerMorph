import os, glob
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np

#
# ExportMorphoJLandmarkFile
#

class ExportMorphoJLandmarkFile(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ExportMorphoJLandmarkFile"
    self.parent.categories = ["SlicerMorph.Input and Output"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steven Lewis (UB), Sara Rolfe (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module parses fcsv landmark files for landmark coordinates and compiles them into a new csv file where each sample name is followed by the x,y or x,y,& z coordinates
for all landmarks tied to the file.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This module was developed by Steven Lewis with the assistance of Sara Rolfe.
""" # replace with organization, grant and thanks.

class ExportMorphoJLandmarkFileWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Select landmark folder to import
    #

    self.inputDirectory = ctk.ctkDirectoryButton()
    self.inputDirectory.directory = qt.QDir.homePath()
    self.inputDirectory.setToolTip('Select Directory with fcsv lanmark files')
    parametersFormLayout.addRow("Input Directory:", self.inputDirectory)

    #
    # output directory selector
    #
    self.outputDirectory = ctk.ctkDirectoryButton()
    self.outputDirectory.directory = qt.QDir.homePath()
    parametersFormLayout.addRow("Output Directory:", self.outputDirectory)

    #
    # enter filename for output
    #
    self.outputFileName = qt.QLineEdit()
    self.outputFileName.text = "morphoJOutput"
    parametersFormLayout.addRow("Name of output file:", self.outputFileName)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the compiling."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputDirectory.connect('validInputChanged(bool)', self.onSelectInput)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelectInput()
    #self.onSelectOutput()

  def cleanup(self):
    pass

  def onSelectInput(self):
    self.applyButton.enabled = bool(self.inputDirectory.directory)


  def onApplyButton(self):
    logic = ExportMorphoJLandmarkFileLogic()
    outputFile = self.outputFileName.text + ".csv"
    outputPath = os.path.join(self.outputDirectory.directory, outputFile)
    logic.run(self.inputDirectory.directory, outputPath)

#
# ExportMorphoJLandmarkFileLogic
#

class ExportMorphoJLandmarkFileLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def run(self, inputDirectory, outputLandmarkFile):
    extensionInput = ".fcsv"
    fileList = glob.glob(inputDirectory + "/*.fcsv")
    if(fileList == []):
      logging.info("No landmark files found in: ", inputDirectory)
      return False
    success, currentLMNode = slicer.util.loadMarkupsFiducialList(fileList[0])
    subjectNumber = len(fileList)
    landmarkNumber = currentLMNode.GetNumberOfFiducials()
    LMArray=np.zeros(shape=(subjectNumber,landmarkNumber,3))
    fileIndex=0
    fileStems=[];
    headerLM = ["Subject"]
    for pointIndex in range(currentLMNode.GetNumberOfMarkups()):
      headerLM.append(currentLMNode.GetNthControlPointLabel(pointIndex)+'_X')
      headerLM.append(currentLMNode.GetNthControlPointLabel(pointIndex)+'_Y')
      headerLM.append(currentLMNode.GetNthControlPointLabel(pointIndex)+'_Z')

    LPS = [-1,-1,1]
    point = [0,0,0]
    for file in fileList:
      if fileIndex>0:
        success, currentLMNode = slicer.util.loadMarkupsFiducialList(file)
      fileStems.append(os.path.basename(file.split(extensionInput)[0]))
      for pointIndex in range(currentLMNode.GetNumberOfMarkups()):
        point=currentLMNode.GetNthControlPointPositionVector(pointIndex)
        point.Set(point[0]*LPS[0],point[1]*LPS[1],point[2]*LPS[2])
        LMArray[fileIndex, pointIndex,:]=point
      slicer.mrmlScene.RemoveNode(currentLMNode)
      fileIndex+=1

    temp = np.column_stack((np.array(fileStems), LMArray.reshape(subjectNumber, int(3 * landmarkNumber))))
    temp = np.vstack((np.array(headerLM), temp))
    np.savetxt(outputLandmarkFile, temp, fmt="%s", delimiter=",")
    logging.info("Processing complete")
    return True