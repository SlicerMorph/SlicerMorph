"""Mixin class that provides all Templates-tab widget handlers for ALPACAWidget.

Imported by ALPACA.py and mixed into ALPACAWidget via multiple inheritance:

    class ALPACAWidget(_ALPACATemplatesWidget, ScriptedLoadableModuleWidget):
        ...

All methods here operate on ``self.ui``, ``self.parameterDictionary``, etc.
exactly as they did when they lived directly inside ALPACAWidget.  No
behavioural changes — pure code move.
"""

import os
import logging
import numpy as np
from datetime import datetime
import time

import qt
import slicer


def _logic():
    """Lazy resolver for ALPACALogic (defined in ALPACA.py after this module
    is imported). Called only inside method bodies, by which time ALPACA is
    fully loaded so the import is safe."""
    from ALPACA import ALPACALogic
    return ALPACALogic()


class _ALPACATemplatesWidget:
    """Templates-tab widget handlers, extracted from ALPACAWidget."""

    ###Connecting function for kmeans templates selection
    def onUseExistingAtlasToggled(self, checked):
        """Show/hide the existing atlas selector and update button states."""
        self.ui.existingAtlasSelectorLabel.setVisible(checked)
        self.ui.existingAtlasSelector.setVisible(checked)
        # Collapse the consensus atlas build section when bypassing it.
        self.ui.consensusAtlasWidget.collapsed = checked
        self.onSelectKmeans()

    def onUseExistingPCDsToggled(self, checked):
        """Bypass Steps 1 and 2 by loading a previously generated PCDs folder."""
        self.ui.existingPCDsSelectorLabel.setVisible(checked)
        self.ui.existingPCDsSelector.setVisible(checked)
        self.onSelectKmeans()

    def _primeFromExistingPCDs(self):
        """Wire self.pcdOutputFolder to the user-chosen PCDs dir.

        Returns True if a valid folder with matched-point-cloud files
        (.mrk.json or .fcsv) was found.
        """
        path = self.ui.existingPCDsSelector.currentPath
        if not path or not os.path.isdir(path):
            return False
        valid = [
            f for f in os.listdir(path)
            if f.lower().endswith((".mrk.json", ".fcsv"))
        ]
        if not valid:
            return False
        self.pcdOutputFolder = path
        return True

    def onSelectKmeans(self):
        useExisting = self.ui.useExistingAtlasCheckBox.isChecked()
        existingPath = self.ui.existingAtlasSelector.currentPath if useExisting else ""
        useExistingPCDs = self.ui.useExistingPCDsCheckBox.isChecked()
        existingPCDsPath = (
            self.ui.existingPCDsSelector.currentPath if useExistingPCDs else ""
        )
        bypassPCDs = bool(existingPCDsPath and os.path.isdir(existingPCDsPath))
        logging.info(
            f"[ALPACA.onSelectKmeans] useExistingPCDs={useExistingPCDs} "
            f"path={existingPCDsPath!r} isdir={os.path.isdir(existingPCDsPath) if existingPCDsPath else None} "
            f"-> bypassPCDs={bypassPCDs}"
        )

        # downReferenceButton: needs a reference (existing atlas OR models dir) + output dir.
        hasReference = bool(
            existingPath
            or self.ui.modelsMultiSelector.currentPath
        )
        self.ui.downReferenceButton.enabled = bool(
            not bypassPCDs
            and hasReference
            and self.ui.kmeansOutputSelector.currentPath
        )
        self.ui.referenceSelector.enabled = (
            self.ui.selectRefCheckBox.isChecked() and not useExisting and not bypassPCDs
        )
        self.ui.buildConsensusAtlasButton.enabled = bool(
            not useExisting
            and not bypassPCDs
            and self.ui.modelsMultiSelector.currentPath
            and self.ui.kmeansOutputSelector.currentPath
        )
        self.ui.previewDensityButton.enabled = bool(
            not bypassPCDs
            and (existingPath or self.ui.modelsMultiSelector.currentPath)
        )
        # When bypassing PCD generation, prime the kmeans state and enable its buttons.
        if bypassPCDs and self._primeFromExistingPCDs():
            self.ui.matchingPointsButton.enabled = False
            self.ui.noGroupInput.enabled = True
            self.ui.multiGroupInput.enabled = True
            self.ui.kmeansTemplatesButton.enabled = True
            _n = len([
                f for f in os.listdir(self.pcdOutputFolder)
                if f.lower().endswith((".mrk.json", ".fcsv"))
            ])
            self.ui.subsampleInfo2.clear()
            self.ui.subsampleInfo2.insertPlainText(
                f"Using existing matched point clouds from:\n{self.pcdOutputFolder}\n"
                f"({_n} matched-PCD files)\n"
            )

    def onDownReferenceButton(self):
        logic = _logic()
        # Priority: existing atlas (user-selected bypass) > consensus atlas
        # (built this session) > user-selected reference > first model in dir.
        if self.ui.useExistingAtlasCheckBox.isChecked() and self.ui.existingAtlasSelector.currentPath:
            referencePath = self.ui.existingAtlasSelector.currentPath
        else:
            consensusPath = getattr(self, "consensusAtlasPath", None)
            if consensusPath and os.path.isfile(consensusPath):
                referencePath = consensusPath
            elif bool(self.ui.referenceSelector.currentPath):
                referencePath = self.ui.referenceSelector.currentPath
            else:
                referenceList = [
                    f
                    for f in os.listdir(self.ui.modelsMultiSelector.currentPath)
                    if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
                ]
                referenceFile = referenceList[0]
                referencePath = os.path.join(
                    self.ui.modelsMultiSelector.currentPath, referenceFile
                )
        self.sparseTemplate, template_density, self.referenceNode = logic.downReference(
            referencePath, self.ui.spacingFactorSlider.value
        )
        self.refName = os.path.basename(referencePath)
        self.refName = os.path.splitext(self.refName)[0]
        self.ui.subsampleInfo2.clear()
        self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
        self.ui.subsampleInfo2.insertPlainText(
            f"The number of points in the downsampled reference pointcloud is {template_density}"
        )
        self.ui.matchingPointsButton.enabled = True

    def onMatchingPointsButton(self):
        # Set up folders for matching point cloud output and kmeans selected templates under self.ui.kmeansOutputSelector.currentPath
        dateTimeStamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        self.kmeansOutputFolder = os.path.join(
            self.ui.kmeansOutputSelector.currentPath, dateTimeStamp
        )
        self.pcdOutputFolder = os.path.join(
            self.kmeansOutputFolder, "matching_point_clouds"
        )
        try:
            os.makedirs(self.kmeansOutputFolder)
            os.makedirs(self.pcdOutputFolder)
        except:
            logging.debug("Result directory failed: Could not access output folder")
            print("Error creating result directory")
        # Execute functions for generating point clouds matched to the reference
        logic = _logic()
        template_density, matchedPoints, indices, files = logic.matchingPCD(
            self.ui.modelsMultiSelector.currentPath,
            self.sparseTemplate,
            self.referenceNode,
            self.pcdOutputFolder,
            self.ui.spacingFactorSlider.value,
            self.ui.JSONFileFormatSelector.checked,
            self.parameterDictionary,
        )
        # Print results
        correspondent_threshold = 0.01
        self.ui.subsampleInfo2.clear()
        self.ui.subsampleInfo2.insertPlainText(f"The reference is {self.refName} \n")
        self.ui.subsampleInfo2.insertPlainText(
            "The number of points in the downsampled reference pointcloud is {}. The error threshold for finding correspondent points is {}% \n".format(
                template_density, correspondent_threshold * 100
            )
        )
        if len(indices) > 0:
            self.ui.subsampleInfo2.insertPlainText(
                f"There are {len(indices)} files have points repeatedly matched with the same point(s) template, these are: \n"
            )
            for i in indices:
                self.ui.subsampleInfo2.insertPlainText(
                    f"{files[i]}: {matchedPoints[i]} unique points are sampled to match the template pointcloud \n"
                )
            indices_error = [
                i
                for i in indices
                if (template_density - matchedPoints[i])
                > template_density * correspondent_threshold
            ]
            if len(indices_error) > 0:
                self.ui.subsampleInfo2.insertPlainText(
                    "The specimens with sampling error larger than the threshold are: \n"
                )
                for i in indices_error:
                    self.ui.subsampleInfo2.insertPlainText(
                        f"{files[i]}: {matchedPoints[i]} unique points are sampled. \n"
                    )
                    self.ui.subsampleInfo2.insertPlainText(
                        "It is recommended to check the alignment of these specimens with the template or experimenting with a higher spacing factor \n"
                    )
            else:
                self.ui.subsampleInfo2.insertPlainText(
                    "All error rates smaller than the threshold \n"
                )
        else:
            self.ui.subsampleInfo2.insertPlainText(
                "{} unique points are sampled from each model to match the template pointcloud \n"
            )
        # Save the reference/template's own point cloud so the output folder
        # contains all specimens including the reference itself.
        try:
            refFid = slicer.vtkMRMLMarkupsFiducialNode()
            nPts = self.sparseTemplate.GetNumberOfPoints()
            for i in range(nPts):
                pt = [0.0, 0.0, 0.0]
                self.sparseTemplate.GetPoint(i, pt)
                refFid.AddControlPoint(pt)
            slicer.mrmlScene.AddNode(refFid)
            refFid.SetFixedNumberOfControlPoints(True)
            refMrkPath = os.path.join(self.pcdOutputFolder, f"{self.refName}_atlas.mrk.json")
            slicer.util.saveNode(refFid, refMrkPath)
            slicer.mrmlScene.RemoveNode(refFid)
        except Exception as _e:
            logging.warning(f"Could not save reference point cloud: {_e}")

        # Enable buttons for kmeans
        self.ui.noGroupInput.enabled = True
        self.ui.multiGroupInput.enabled = True
        self.ui.kmeansTemplatesButton.enabled = True
        self.ui.matchingPointsButton.enabled = False

    # If select multiple group input radiobutton, execute enterFactors function
    def onToggleGroupInput(self):
        if self.ui.multiGroupInput.isChecked():
            self.enterFactors()
            self.ui.resetTableButton.enabled = True

    # Reset input button
    def onRestTableButton(self):
        self.resetFactors()

    # Add table for entering user-defined catalogs/groups for each specimen
    def enterFactors(self):
        # If has table node, remove table node and build a new one
        if hasattr(self, "factorTableNode") == False:
            files = [
                os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)
            ]
            sortedArray = np.zeros(
                len(files),
                dtype={"names": ("filename", "procdist"), "formats": ("U50", "f8")},
            )
            sortedArray["filename"] = files
            self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "Groups Table"
            )
            col1 = self.factorTableNode.AddColumn()
            col1.SetName("ID")
            for i in range(len(files)):
                self.factorTableNode.AddEmptyRow()
                self.factorTableNode.SetCellText(i, 0, sortedArray["filename"][i])
            col2 = self.factorTableNode.AddColumn()
            col2.SetName("Group")
            # add table to new layout
            slicer.app.layoutManager().setLayout(503)
            slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(
                self.factorTableNode.GetID()
            )
            slicer.app.applicationLogic().PropagateTableSelection()
            self.factorTableNode.GetTable().Modified()

    def resetFactors(self):
        if hasattr(self, "factorTableNode"):
            slicer.mrmlScene.RemoveNode(self.factorTableNode)
        files = [os.path.splitext(file)[0] for file in os.listdir(self.pcdOutputFolder)]
        sortedArray = np.zeros(
            len(files),
            dtype={"names": ("filename", "procdist"), "formats": ("U50", "f8")},
        )
        sortedArray["filename"] = files
        self.factorTableNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLTableNode", "Groups Table"
        )
        col1 = self.factorTableNode.AddColumn()
        col1.SetName("ID")
        for i in range(len(files)):
            self.factorTableNode.AddEmptyRow()
            self.factorTableNode.SetCellText(i, 0, sortedArray["filename"][i])
        col2 = self.factorTableNode.AddColumn()
        col2.SetName("Group")
        slicer.app.layoutManager().setLayout(503)
        slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(
            self.factorTableNode.GetID()
        )
        slicer.app.applicationLogic().PropagateTableSelection()
        self.factorTableNode.GetTable().Modified()

    # Generate templates based on kmeans and catalog
    def onkmeansTemplatesButton(self):
        start = time.time()
        logic = _logic()
        PCDFiles = os.listdir(self.pcdOutputFolder)
        if len(PCDFiles) < 1:
            logging.error(f"No point cloud files read from {self.pcdOutputFolder}\n")
            return

        # Optionally exclude atlas files (identified by the _atlas suffix) from analysis.
        # Use split(".")[0] to handle double extensions like .mrk.json correctly.
        if not self.ui.includeAtlasCheckBox.isChecked():
            PCDFiles = [
                f for f in PCDFiles
                if not f.split(".")[0].endswith("_atlas")
            ]

        pcdFilePaths = [os.path.join(self.pcdOutputFolder, file) for file in PCDFiles]
        # GPA for all specimens
        self.scores, self.LM = logic.pcdGPA(pcdFilePaths)
        files = [f.split(".")[0] for f in PCDFiles]
        # Set up a seed for numpy for random results
        if self.ui.setSeedCheckBox.isChecked():
            np.random.seed(1000)
        if self.ui.noGroupInput.isChecked():
            templates, clusterID, templatesIndices = logic.templatesSelection(
                None,
                self.scores,
                pcdFilePaths,
                None,
                self.ui.templatesNumber.value,
                self.ui.kmeansIterations.value,
            )
            clusterID = [str(x) for x in clusterID]
            print(f"kmeans cluster ID is: {clusterID}")
            print(f"templates indices are: {templatesIndices}")
            self.ui.templatesInfo.clear()
            self.ui.templatesInfo.insertPlainText(
                f"One pooled group for all specimens. The {int(self.ui.templatesNumber.value)} selected templates are: \n"
            )
            for file in templates:
                self.ui.templatesInfo.insertPlainText(file + "\n")
            # Add cluster ID from kmeans to the table
            self.plotClusters(files, templatesIndices)
            print(f"Time: {time.time() - start}")
        # multiClusterCheckbox is checked
        else:
            if hasattr(self, "factorTableNode"):
                self.ui.templatesInfo.clear()
                factorCol = self.factorTableNode.GetTable().GetColumn(1)
                groupFactorArray = []
                for i in range(factorCol.GetNumberOfTuples()):
                    temp = factorCol.GetValue(i).rstrip()
                    temp = str(temp).upper()
                    groupFactorArray.append(temp)
                print(groupFactorArray)
                # Count the number of non-null enties in the table
                countInput = 0
                for i in range(len(groupFactorArray)):
                    if groupFactorArray[i] != "":
                        countInput += 1
                if countInput == len(
                    PCDFiles
                ):  # check if group information is input for all specimens
                    uniqueFactors = list(set(groupFactorArray))
                    groupNumber = len(uniqueFactors)
                    self.ui.templatesInfo.insertPlainText(
                        f"The sample is divided into {groupNumber} groups. The templates for each group are: \n"
                    )
                    groupClusterIDs = [None] * len(files)
                    templatesIndices = []
                    for i in range(groupNumber):
                        factorName = uniqueFactors[i]
                        # Get indices for the ith cluster
                        indices = [
                            i for i, x in enumerate(groupFactorArray) if x == factorName
                        ]
                        print("indices for " + factorName + " is:")
                        print(indices)
                        key = factorName
                        paths = []
                        for i in range(len(indices)):
                            path = pcdFilePaths[indices[i]]
                            paths.append(path)
                        # PC scores of specimens belong to a specific group
                        tempScores = self.scores[indices, :]
                        #
                        templates, clusterID, tempIndices = logic.templatesSelection(
                            None,
                            tempScores,
                            paths,
                            None,
                            self.ui.templatesNumber.value,
                            self.ui.kmeansIterations.value,
                        )
                        print("Kmeans-cluster IDs for " + factorName + " are:")
                        print(clusterID)
                        templatesIndices = templatesIndices + [
                            indices[i] for i in tempIndices
                        ]
                        self.ui.templatesInfo.insertPlainText(
                            "Group " + factorName + "\n"
                        )
                        for file in templates:
                            self.ui.templatesInfo.insertPlainText(file + "\n")
                        # Prepare cluster ID for each group
                        uniqueClusterID = list(set(clusterID))
                        for i in range(len(uniqueClusterID)):
                            for j in range(len(clusterID)):
                                if clusterID[j] == uniqueClusterID[i]:
                                    index = indices[j]
                                    groupClusterIDs[index] = factorName + str(i + 1)
                                    print(groupClusterIDs[index])
                    # Plot PC1 and PC 2 based on kmeans clusters
                    print(f"group cluster ID are {groupClusterIDs}")
                    print(f"Templates indices are: {templatesIndices}")
                    self.plotClustersWithFactors(
                        files, groupFactorArray, templatesIndices
                    )
                    print(f"Time: {time.time() - start}")
                else:  # if the user input a factor requiring more than 3 groups, do not use factor
                    qt.QMessageBox.critical(
                        slicer.util.mainWindow(),
                        "Error",
                        "Please enter group information for every specimen",
                    )
            else:
                qt.QMessageBox.critical(
                    slicer.util.mainWindow(),
                    "Error",
                    "Please select Multiple groups within the sample option and enter group information for each specimen",
                )

    def plotClustersWithFactors(self, files, groupFactors, templatesIndices):
        logic = _logic()
        import Support.gpa_lib as gpa_lib

        # Set up scatter plot
        pcNumber = 2
        shape = self.LM.lm.shape
        scatterDataAll = np.zeros(shape=(shape[2], pcNumber))
        for i in range(pcNumber):
            data = gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig, i, 1)
            scatterDataAll[:, i] = data[:, 0]
        factorNP = np.array(groupFactors)
        # import GPA
        logic.makeScatterPlotWithFactors(
            scatterDataAll,
            files,
            factorNP,
            "PCA Scatter Plots",
            "PC1",
            "PC2",
            pcNumber,
            templatesIndices,
        )

    def plotClusters(self, files, templatesIndices):
        logic = _logic()
        import Support.gpa_lib as gpa_lib

        # Set up scatter plot
        pcNumber = 2
        shape = self.LM.lm.shape
        scatterDataAll = np.zeros(shape=(shape[2], pcNumber))
        for i in range(pcNumber):
            data = gpa_lib.plotTanProj(self.LM.lm, self.LM.sortedEig, i, 1)
            scatterDataAll[:, i] = data[:, 0]
        logic.makeScatterPlot(
            scatterDataAll,
            files,
            "PCA Scatter Plots",
            "PC1",
            "PC2",
            pcNumber,
            templatesIndices,
        )

    def onPreviewDensity(self):
        """Subsample the chosen reference at the current spacing factor and
        report the resulting sparse point count, without altering any state."""
        if self.ui.selectRefCheckBox.isChecked() and self.ui.referenceSelector.currentPath:
            refPath = self.ui.referenceSelector.currentPath
        else:
            modelsDir = self.ui.modelsMultiSelector.currentPath
            files = sorted(
                f for f in os.listdir(modelsDir)
                if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
            )
            if not files:
                slicer.util.errorDisplay("No mesh files found in input directory.")
                return
            refPath = os.path.join(modelsDir, files[0])

        node = slicer.util.loadModel(refPath)
        try:
            sparse = _logic().DownsampleTemplate(
                node.GetPolyData(), self.ui.spacingFactorSlider.value
            )
            count = sparse.GetNumberOfPoints()
            self.ui.consensusInfo.insertPlainText(
                f"Preview: spacing={self.ui.spacingFactorSlider.value:.3f} -> "
                f"{count} points (ref: {os.path.basename(refPath)})\n"
            )
        finally:
            slicer.mrmlScene.RemoveNode(node)

    def onBuildConsensusAtlasButton(self):
        """Build a bias-free consensus atlas from the input models folder."""
        modelsDir = self.ui.modelsMultiSelector.currentPath
        if not modelsDir:
            slicer.util.errorDisplay("Select a models directory first.")
            return
        outputRoot = self.ui.kmeansOutputSelector.currentPath
        if not outputRoot:
            slicer.util.errorDisplay("Select an output directory first.")
            return

        dateTimeStamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        outputDir = os.path.join(outputRoot, f"consensus_atlas_{dateTimeStamp}")
        os.makedirs(outputDir, exist_ok=True)

        self.ui.consensusInfo.clear()
        self.ui.consensusInfo.insertPlainText(
            f"Output: {outputDir}\nStarting consensus atlas construction...\n"
        )
        slicer.app.processEvents()

        def _progress(msg):
            self.ui.consensusInfo.insertPlainText(msg + "\n")
            slicer.app.processEvents()

        # Honor user-selected reference if the "Enable Reference Model"
        # checkbox is on and a path is set.
        userReferencePath = None
        if (self.ui.selectRefCheckBox.isChecked()
                and self.ui.referenceSelector.currentPath):
            userReferencePath = self.ui.referenceSelector.currentPath

        logic = _logic()
        try:
            finalPath = logic.buildConsensusAtlas(
                modelsDir=modelsDir,
                outputDir=outputDir,
                spacingFactor=self.ui.spacingFactorSlider.value,
                parameterDictionary=self.parameterDictionary,
                iterations=int(self.ui.consensusIterations.value),
                useJSONFormat=self.ui.JSONFileFormatSelector.checked,
                useScaling=self.ui.consensusScalingCheckBox.checked,
                userReferencePath=userReferencePath,
                smoothingIterations=int(self.ui.smoothingIterations.value),
                smoothReferenceIterations=int(self.ui.smoothReferenceIterations.value),
                progressCallback=_progress,
            )
        except Exception as e:
            slicer.util.errorDisplay(f"Consensus atlas construction failed: {e}")
            raise

        self.ui.consensusInfo.insertPlainText(f"\nDone. Final atlas: {finalPath}\n")
        # Remember the consensus atlas as the preferred reference for the
        # downstream "Generate Point Cloud" step.
        self.consensusAtlasPath = finalPath
        # Load the final atlas into the scene for visual inspection.
        try:
            slicer.util.loadModel(finalPath)
        except Exception:
            pass
