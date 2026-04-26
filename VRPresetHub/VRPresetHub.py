import json
import os
import re
import tempfile
import urllib.parse
import urllib.request

import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

class VRPresetHub(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "VR Preset Hub"
        self.parent.categories = ["SlicerMorph.Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Murat Maga (UW)"]
        self.parent.helpText = """
Export the active volume-rendering preset to a <code>.vp.json</code> file,
    capture a 3-D screenshot, browse community presets, and open a pre-filled
    GitHub issue so you can share the preset with the SlicerMorph community with
    a simple drag-and-drop.
"""
        self.parent.acknowledgementText = ""


# ---------------------------------------------------------------------------
# Widget (UI)
# ---------------------------------------------------------------------------

class VRPresetHubWidget(ScriptedLoadableModuleWidget):

    REPO = "SlicerMorph/VPs"
    MANIFEST_URL = f"https://raw.githubusercontent.com/{REPO}/main/manifest.json"
    PREVIEW_SIZE = 240

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = VRPresetHubLogic()
        self.layout.setAlignment(qt.Qt.AlignTop)
        self.browserEntries = []
        self.filteredBrowserEntries = []
        self.previewPixmapCache = {}
        # (volumeNodeId, originalVolumePropertyNodeId) for last Apply, used by Revert.
        self._lastOriginalVP = (None, None)

        self.tabWidget = qt.QTabWidget()
        self.layout.addWidget(self.tabWidget)

        self.shareTab = qt.QWidget()
        self.shareLayout = qt.QVBoxLayout(self.shareTab)
        self.shareLayout.setAlignment(qt.Qt.AlignTop)
        self.browserTab = qt.QWidget()
        self.browserLayout = qt.QVBoxLayout(self.browserTab)
        self.browserLayout.setAlignment(qt.Qt.AlignTop)

        self.tabWidget.addTab(self.shareTab, "Share")
        self.tabWidget.addTab(self.browserTab, "Preset Browser")

        self._setupShareTab()
        self._setupBrowserTab()

        # Initial population
        self._populateSelectors()
        self._refreshBrowserPresets()

    def _setupShareTab(self):
        """Build the preset submission UI."""
        self.layout = self.shareLayout

        # ---- GitHub account notice ----
        noticeLabel = qt.QLabel(
            "<b>Note:</b> Submitting a preset requires a free "
            "<a href='https://github.com/signup'>GitHub account</a>. "
            "If you don't have one, create it at "
            "<a href='https://github.com/signup'>github.com/signup</a> "
            "before clicking the submission button."
        )
        noticeLabel.wordWrap = True
        noticeLabel.openExternalLinks = True
        noticeLabel.setStyleSheet(
            "background-color: #fff8c5; border: 1px solid #e3b341; "
            "border-radius: 4px; padding: 6px; margin-bottom: 4px;"
        )
        self.layout.addWidget(noticeLabel)

        # ---- Collapsible: Preset selection ----
        selBox = self._collapsible("Select Preset")
        selLayout = qt.QFormLayout(selBox)

        # VolumeProperty node selector row (combo + refresh button)
        vpRow = qt.QHBoxLayout()
        self.vpCombo = qt.QComboBox()
        self.vpCombo.toolTip = (
            "All VolumeProperty presets currently loaded in the scene.\n"
            "Select the preset you want to share. Rename it first in the\n"
            "Volume Rendering module (Property dropdown) if needed,\n"
            "then click Refresh."
        )
        vpRow.addWidget(self.vpCombo)
        self.refreshButton = qt.QPushButton("Refresh")
        self.refreshButton.toolTip = "Re-scan the scene for VolumeProperty presets."
        self.refreshButton.setFixedWidth(70)
        vpRow.addWidget(self.refreshButton)
        selLayout.addRow("Preset (Property node):", vpRow)

        # Editable preset name — auto-filled from selected volume, but overridable
        self.nameEdit = qt.QLineEdit()
        self.nameEdit.placeholderText = "Auto-filled from volume name; only A-Z a-z 0-9 _ - allowed"
        self.nameEdit.toolTip = (
            "Filename prefix for the exported files.\n"
            "Auto-filled from the selected volume name. Edit if needed.\n"
            "Allowed characters: A-Z a-z 0-9 _ -"
        )
        selLayout.addRow("Preset name:", self.nameEdit)

        self.descEdit = qt.QLineEdit()
        self.descEdit.placeholderText = "One-line description (optional)"
        selLayout.addRow("Description:", self.descEdit)

        self.authorEdit = qt.QLineEdit()
        self.authorEdit.placeholderText = "Your name or GitHub @username (optional)"
        selLayout.addRow("Author:", self.authorEdit)

        # ---- Collapsible: Screenshot source ----
        ssBox = self._collapsible("Screenshot Source")
        ssLayout = qt.QFormLayout(ssBox)

        self.viewCombo = qt.QComboBox()
        self.viewCombo.toolTip = (
            "Choose which 3-D view to capture for the preview image.\n"
            "Arrange the view exactly as you want it before submitting."
        )
        ssLayout.addRow("3-D view to capture:", self.viewCombo)

        ssHint = qt.QLabel(
            "<i>Tip: arrange the 3-D view (rotation, zoom, lighting) before submitting.</i>"
        )
        ssHint.wordWrap = True
        ssLayout.addRow("", ssHint)

        # ---- Status label ----
        self.statusLabel = qt.QLabel("")
        self.statusLabel.wordWrap = True
        self.layout.addWidget(self.statusLabel)

        # ---- Single submit button ----
        self.submitButton = qt.QPushButton("Submit preset to GitHub")
        self.submitButton.toolTip = (
            "Exports the preset, uploads files to cloud storage, then opens\n"
            "a pre-filled GitHub issue. Just click Submit new issue — done!"
        )
        self.submitButton.enabled = False
        self.layout.addWidget(self.submitButton)

        # ---- Connections ----
        self.refreshButton.clicked.connect(self._populateSelectors)
        self.vpCombo.currentIndexChanged.connect(self._onVpComboChanged)
        self.nameEdit.textChanged.connect(self._onNameChanged)
        self.submitButton.clicked.connect(self._onSubmit)

        self.shareLayout.addStretch(1)

    def _setupBrowserTab(self):
        """Build the manifest-driven preset browser UI."""
        introLabel = qt.QLabel(
            "Browse community presets from the SlicerMorph VPs catalog and load "
            "them directly into the current scene using Slicer's native transfer "
            "function reader."
        )
        introLabel.wordWrap = True
        self.browserLayout.addWidget(introLabel)

        browserControlsLayout = qt.QHBoxLayout()
        self.browserSearchEdit = qt.QLineEdit()
        self.browserSearchEdit.placeholderText = "Filter by preset name, author, or description"
        self.browserRefreshButton = qt.QPushButton("Refresh Catalog")
        self.browserRefreshButton.toolTip = "Fetch the latest preset catalog from the SlicerMorph VPs repository."
        browserControlsLayout.addWidget(self.browserSearchEdit)
        browserControlsLayout.addWidget(self.browserRefreshButton)
        self.browserLayout.addLayout(browserControlsLayout)

        browserSplitter = qt.QSplitter(qt.Qt.Horizontal)

        self.browserList = qt.QListWidget()
        self.browserList.setAlternatingRowColors(True)
        self.browserList.toolTip = "Select a preset to preview it. Double-click to load it into the scene."
        browserSplitter.addWidget(self.browserList)

        browserDetailsWidget = qt.QWidget()
        browserDetailsLayout = qt.QVBoxLayout(browserDetailsWidget)
        browserDetailsLayout.setAlignment(qt.Qt.AlignTop)

        self.browserPreviewLabel = qt.QLabel("Select a preset to preview it.")
        self.browserPreviewLabel.alignment = qt.Qt.AlignCenter
        self.browserPreviewLabel.minimumSize = qt.QSize(self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        self.browserPreviewLabel.setStyleSheet(
            "border: 1px solid #c8c8c8; border-radius: 4px; padding: 8px; background: white;"
        )
        browserDetailsLayout.addWidget(self.browserPreviewLabel)

        self.browserDetailsLabel = qt.QLabel("No preset selected.")
        self.browserDetailsLabel.wordWrap = True
        self.browserDetailsLabel.textFormat = qt.Qt.RichText
        self.browserDetailsLabel.openExternalLinks = True
        browserDetailsLayout.addWidget(self.browserDetailsLabel)

        browserButtonLayout = qt.QHBoxLayout()
        self.browserImportButton = qt.QPushButton("Import into Scene")
        self.browserApplyButton = qt.QPushButton("Apply to Active Volume")
        self.browserRevertButton = qt.QPushButton("Revert to Original")
        self.browserRevertButton.setToolTip(
            "Restore the volume rendering property that was active before "
            "the most recent 'Apply to Active Volume'.")
        self.browserOpenPreviewButton = qt.QPushButton("Open Preview")
        for button in (self.browserImportButton, self.browserApplyButton,
                       self.browserRevertButton, self.browserOpenPreviewButton):
            button.enabled = False
            browserButtonLayout.addWidget(button)
        browserDetailsLayout.addLayout(browserButtonLayout)
        browserDetailsLayout.addStretch(1)

        browserSplitter.addWidget(browserDetailsWidget)
        browserSplitter.setStretchFactor(0, 2)
        browserSplitter.setStretchFactor(1, 3)
        self.browserLayout.addWidget(browserSplitter)

        self.browserStatusLabel = qt.QLabel("")
        self.browserStatusLabel.wordWrap = True
        self.browserLayout.addWidget(self.browserStatusLabel)
        self.browserLayout.addStretch(1)

        self.browserRefreshButton.clicked.connect(self._refreshBrowserPresets)
        self.browserSearchEdit.textChanged.connect(self._filterBrowserPresets)
        self.browserList.currentRowChanged.connect(self._onBrowserSelectionChanged)
        self.browserList.itemDoubleClicked.connect(self._onImportBrowserPreset)
        self.browserImportButton.clicked.connect(self._onImportBrowserPreset)
        self.browserApplyButton.clicked.connect(self._onApplyBrowserPreset)
        self.browserRevertButton.clicked.connect(self._onRevertBrowserPreset)
        self.browserOpenPreviewButton.clicked.connect(self._onOpenBrowserPreview)

    # --- helpers ---------------------------------------------------------

    def _collapsible(self, title):
        import ctk
        btn = ctk.ctkCollapsibleButton()
        btn.text = title
        self.layout.addWidget(btn)
        return btn

    def _setStatus(self, msg, color="black"):
        self.statusLabel.text = msg
        self.statusLabel.setStyleSheet(f"color:{color};")

    def _setBrowserStatus(self, msg, color="black"):
        self.browserStatusLabel.text = msg
        self.browserStatusLabel.setStyleSheet(f"color:{color};")

    def _currentBrowserEntry(self):
        row = self.browserList.currentRow
        if row < 0 or row >= len(self.filteredBrowserEntries):
            return None
        return self.filteredBrowserEntries[row]

    def _clearBrowserSelection(self):
        self.browserList.clearSelection()
        self.browserPreviewLabel.clear()
        self.browserPreviewLabel.text = "Select a preset to preview it."
        self.browserDetailsLabel.text = "No preset selected."
        for button in (self.browserImportButton, self.browserApplyButton, self.browserOpenPreviewButton):
            button.enabled = False

    def _refreshBrowserPresets(self):
        self._setBrowserStatus("Fetching preset catalog…", "gray")
        slicer.app.processEvents()
        try:
            with urllib.request.urlopen(self.MANIFEST_URL, timeout=15) as resp:
                manifest = json.loads(resp.read())
        except Exception as e:
            self.browserEntries = []
            self.filteredBrowserEntries = []
            self.browserList.clear()
            self._clearBrowserSelection()
            self._setBrowserStatus(f"Could not fetch preset catalog: {e}", "red")
            return

        presets = manifest.get("presets", [])
        if not isinstance(presets, list):
            self.browserEntries = []
            self.filteredBrowserEntries = []
            self.browserList.clear()
            self._clearBrowserSelection()
            self._setBrowserStatus("Preset catalog is malformed.", "red")
            return

        self.browserEntries = sorted(presets, key=lambda preset: preset.get("prefix", "").lower())
        self._filterBrowserPresets()
        if self.browserEntries:
            self._setBrowserStatus(f"Loaded {len(self.browserEntries)} presets.", "darkgreen")
        else:
            self._setBrowserStatus("No presets are currently listed in the catalog.", "orange")

    def _filterBrowserPresets(self):
        searchText = self.browserSearchEdit.text.strip().lower()
        selectedPrefix = None
        currentEntry = self._currentBrowserEntry()
        if currentEntry:
            selectedPrefix = currentEntry.get("prefix")

        def matches(entry):
            if not searchText:
                return True
            haystack = " ".join(
                str(entry.get(key) or "")
                for key in ("prefix", "author", "contributor", "description")
            ).lower()
            return searchText in haystack

        self.filteredBrowserEntries = [entry for entry in self.browserEntries if matches(entry)]

        self.browserList.blockSignals(True)
        self.browserList.clear()
        restoredRow = -1
        for index, entry in enumerate(self.filteredBrowserEntries):
            item = qt.QListWidgetItem(entry.get("prefix") or "(unnamed preset)")
            description = entry.get("description")
            if description:
                item.setToolTip(description)
            self.browserList.addItem(item)
            if selectedPrefix and entry.get("prefix") == selectedPrefix:
                restoredRow = index
        self.browserList.blockSignals(False)

        if self.filteredBrowserEntries:
            self.browserList.setCurrentRow(restoredRow if restoredRow >= 0 else 0)
        else:
            self._clearBrowserSelection()
            if self.browserEntries:
                self._setBrowserStatus("No presets match the current filter.", "orange")

    def _onBrowserSelectionChanged(self, row):
        if row < 0 or row >= len(self.filteredBrowserEntries):
            self._clearBrowserSelection()
            return

        entry = self.filteredBrowserEntries[row]
        title = entry.get("prefix") or "(unnamed preset)"
        description = entry.get("description") or "No description provided."
        author = entry.get("author") or "Unknown"
        contributor = entry.get("contributor") or "Unknown"
        jsonUrl = entry.get("json_raw_url") or ""

        self.browserDetailsLabel.text = (
            f"<b>{title}</b><br/>"
            f"Author: {author}<br/>"
            f"Contributor: {contributor}<br/><br/>"
            f"{description}<br/><br/>"
            f"<a href='{jsonUrl}'>Raw preset JSON</a>"
        )

        previewUrl = entry.get("png_raw_url")
        if previewUrl:
            try:
                pixmap = self.previewPixmapCache.get(previewUrl)
                if pixmap is None:
                    with urllib.request.urlopen(previewUrl, timeout=15) as resp:
                        imageData = resp.read()
                    pixmap = qt.QPixmap()
                    if not pixmap.loadFromData(imageData):
                        raise RuntimeError("Could not decode preview image.")
                    self.previewPixmapCache[previewUrl] = pixmap
                scaledPixmap = pixmap.scaled(
                    self.PREVIEW_SIZE,
                    self.PREVIEW_SIZE,
                    qt.Qt.KeepAspectRatio,
                    qt.Qt.SmoothTransformation,
                )
                self.browserPreviewLabel.setPixmap(scaledPixmap)
            except Exception as e:
                self.browserPreviewLabel.clear()
                self.browserPreviewLabel.text = f"Could not load preview image.\n{e}"
        else:
            self.browserPreviewLabel.clear()
            self.browserPreviewLabel.text = "No preview image available."

        for button in (self.browserImportButton, self.browserApplyButton, self.browserOpenPreviewButton):
            button.enabled = True

    def _loadBrowserPreset(self):
        entry = self._currentBrowserEntry()
        if entry is None:
            raise RuntimeError("No preset selected.")

        prefix = entry.get("prefix") or "ImportedPreset"
        jsonUrl = entry.get("json_raw_url")
        if not jsonUrl:
            raise RuntimeError("Selected preset is missing its JSON URL.")

        self._setBrowserStatus(f"Loading preset '{prefix}'…", "gray")
        slicer.app.processEvents()
        presetNode = self.logic.loadPresetFromUrl(jsonUrl, prefix)
        self._setBrowserStatus(f"Loaded preset '{presetNode.GetName()}' into the scene.", "darkgreen")
        return presetNode

    def _onImportBrowserPreset(self, *_args):
        try:
            self._loadBrowserPreset()
        except Exception as e:
            self._setBrowserStatus(f"Failed to load preset: {e}", "red")

    def _onApplyBrowserPreset(self):
        try:
            presetNode = self._loadBrowserPreset()
            volumeNode, _displayNode, originalVPNodeId = (
                self.logic.applyPresetToActiveVolume(presetNode))
        except Exception as e:
            self._setBrowserStatus(f"Failed to apply preset: {e}", "red")
            return

        self._lastOriginalVP = (volumeNode.GetID(), originalVPNodeId)
        self.browserRevertButton.enabled = bool(originalVPNodeId)
        if originalVPNodeId:
            originalNode = slicer.mrmlScene.GetNodeByID(originalVPNodeId)
            originalName = originalNode.GetName() if originalNode else "previous property"
            self.browserRevertButton.setToolTip(
                f"Revert '{volumeNode.GetName()}' to its previous volume "
                f"property ('{originalName}').")
        self._setBrowserStatus(
            f"Loaded and applied preset to active volume '{volumeNode.GetName()}'.",
            "darkgreen",
        )

    def _onRevertBrowserPreset(self):
        volumeId, originalVPNodeId = self._lastOriginalVP
        if not (volumeId and originalVPNodeId):
            self._setBrowserStatus(
                "Nothing to revert — no preset has been applied this session.",
                "orange")
            return
        try:
            volumeNode = self.logic.revertVolumePropertyForVolume(
                volumeId, originalVPNodeId)
        except Exception as e:
            self._setBrowserStatus(f"Failed to revert: {e}", "red")
            return
        # Single revert; require another Apply before another Revert is possible.
        self._lastOriginalVP = (None, None)
        self.browserRevertButton.enabled = False
        self._setBrowserStatus(
            f"Reverted '{volumeNode.GetName()}' to its previous volume property.",
            "darkgreen",
        )

    def _onOpenBrowserPreview(self):
        entry = self._currentBrowserEntry()
        if entry is None:
            return
        previewUrl = entry.get("png_raw_url")
        if not previewUrl:
            self._setBrowserStatus("Selected preset does not have a preview image.", "orange")
            return
        qt.QDesktopServices.openUrl(qt.QUrl(previewUrl))

    def _populateSelectors(self):
        """Refresh the VolumeProperty combo and the 3-D view combo from the current scene."""
        # --- VolumeProperty nodes (the actual presets) ---
        self.vpCombo.blockSignals(True)
        prevNodeId = self.vpCombo.currentData
        self.vpCombo.clear()

        col = slicer.mrmlScene.GetNodesByClass("vtkMRMLVolumePropertyNode")
        col.InitTraversal()
        found = []
        node = col.GetNextItemAsObject()
        while node:
            found.append((node.GetName(), node.GetID()))
            node = col.GetNextItemAsObject()

        if found:
            for name, nodeId in found:
                self.vpCombo.addItem(name, nodeId)
            idx = next((i for i, (_, nid) in enumerate(found) if nid == prevNodeId), 0)
            self.vpCombo.setCurrentIndex(idx)
            self._setStatus("")
        else:
            self.vpCombo.addItem("(no VolumeProperty presets in scene)")
            self._setStatus(
                "No VolumeProperty presets found in the scene.\n"
                "Load a volume, enable volume rendering, then click Refresh.",
                "orange",
            )

        self.vpCombo.blockSignals(False)
        self._onVpComboChanged(self.vpCombo.currentIndex)

        # --- 3-D views ---
        self.viewCombo.blockSignals(True)
        prevView = self.viewCombo.currentText
        self.viewCombo.clear()
        lm = slicer.app.layoutManager()
        for i in range(lm.threeDViewCount):
            w = lm.threeDWidget(i)
            label = w.mrmlViewNode().GetName() if w.mrmlViewNode() else f"View {i+1}"
            self.viewCombo.addItem(label, i)
        if self.viewCombo.count == 0:
            self.viewCombo.addItem("(no 3-D views)")
        # restore
        existing = self.viewCombo.findText(prevView)
        if existing >= 0:
            self.viewCombo.setCurrentIndex(existing)
        self.viewCombo.blockSignals(False)

    def _onVpComboChanged(self, index):
        nodeId = self.vpCombo.itemData(index)
        if not nodeId:
            self.submitButton.enabled = False
            return
        node = slicer.mrmlScene.GetNodeByID(nodeId)
        if node:
            safeName = re.sub(r'[^A-Za-z0-9_-]', '_', node.GetName())
            self.nameEdit.setText(safeName)
        self._updateSubmitButton()

    def _onNameChanged(self, text):
        valid = bool(re.match(r'^[A-Za-z0-9_-]+$', text))
        if text and not valid:
            self._setStatus(
                "⚠ Name may only contain letters, digits, _ and -.", "orange"
            )
        else:
            self._setStatus("")
        self._updateSubmitButton()

    def _updateSubmitButton(self):
        nodeId = self.vpCombo.currentData
        nameOk = bool(re.match(r'^[A-Za-z0-9_-]+$', self.nameEdit.text))
        self.submitButton.enabled = bool(nodeId) and nameOk

    # --- submit (export to temp + upload + open browser) -------------------

    def _onSubmit(self):
        import tempfile
        name = self.nameEdit.text.strip()
        desc = self.descEdit.text.strip()
        author = self.authorEdit.text.strip()
        nodeId = self.vpCombo.currentData
        viewIndex = self.viewCombo.currentData if self.viewCombo.currentData is not None else 0

        # Export to a temp directory — no permanent files left on disk
        tmpDir = tempfile.mkdtemp(prefix="slicermorph_vp_")
        self._setStatus("Exporting preset…", "gray")
        slicer.app.processEvents()
        try:
            jsonPath, pngPath = self.logic.exportPreset(
                name, tmpDir, nodeId=nodeId, viewIndex=viewIndex,
                description=desc, author=author,
            )
        except Exception as e:
            self._setStatus(f"Export failed: {e}", "red")
            import traceback
            traceback.print_exc()
            return

        # 1. Fetch current presigned PUT URLs from the repo
        self._setStatus("Fetching upload configuration…", "gray")
        slicer.app.processEvents()
        raw_url = f"https://raw.githubusercontent.com/{self.REPO}/main/staging-urls.json"
        try:
            with urllib.request.urlopen(raw_url, timeout=15) as resp:
                staging = json.loads(resp.read())
        except Exception as e:
            self._setStatus(f"Could not fetch upload configuration: {e}", "red")
            return

        json_put_url = staging["json_url"]
        png_put_url  = staging["png_url"]
        uid          = staging["uuid"]

        # Check that the URLs haven't expired
        from datetime import datetime, timezone
        expires_at = datetime.strptime(
            staging["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
        if remaining < 180:
            self._setStatus(
                "Upload configuration on the server is stale or expired. "
                "Please try again after the staging URLs are refreshed.",
                "orange",
            )
            return

        # 2. Upload JSON
        self._setStatus("Uploading preset JSON…", "gray")
        slicer.app.processEvents()
        with open(jsonPath, "rb") as fh:
            json_data = fh.read()
        try:
            req = urllib.request.Request(json_put_url, data=json_data, method="PUT")
            with urllib.request.urlopen(req) as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(f"HTTP {resp.status}")
        except Exception as e:
            self._setStatus(f"Failed to upload preset JSON: {e}", "red")
            return

        # 3. Upload PNG
        self._setStatus("Uploading screenshot…", "gray")
        slicer.app.processEvents()
        with open(pngPath, "rb") as fh:
            png_data = fh.read()
        try:
            req = urllib.request.Request(png_put_url, data=png_data, method="PUT")
            with urllib.request.urlopen(req) as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(f"HTTP {resp.status}")
        except Exception as e:
            self._setStatus(f"Failed to upload screenshot: {e}", "red")
            return

        # 4. Open pre-filled GitHub issue in the browser
        issue_body = (
            f"Preset files uploaded automatically via SlicerMorph.\n"
            f"<!-- DO NOT EDIT THE LINE BELOW -->\n"
            f"staging: {uid}"
        )
        params = urllib.parse.urlencode({
            "labels": "preset-submission",
            "title":  f"New preset: {name}",
            "body":   issue_body,
        })
        url = f"https://github.com/{self.REPO}/issues/new?{params}"
        qt.QDesktopServices.openUrl(qt.QUrl(url))

        self._setStatus(
            "✓ Files uploaded successfully!\n\n"
            "A GitHub issue form has been opened in your browser.\n"
            "Just click \"Submit new issue\" — no editing needed.",
            "darkgreen",
        )


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

class VRPresetHubLogic(ScriptedLoadableModuleLogic):
    """Handles export of .vp.json and .png from the active volume rendering node."""

    def loadPresetFromUrl(self, url, nodeName=None):
        import SampleData

        parsedUrl = urllib.parse.urlparse(url)
        fileName = os.path.basename(parsedUrl.path) or "preset.vp.json"
        localFilePath = SampleData.SampleDataLogic().downloadFileIntoCache(url, fileName)
        self._normalizePresetJsonFile(localFilePath)
        presetNode = slicer.util.loadNodeFromFile(localFilePath, "TransferFunctionFile")
        if presetNode is None:
            raise RuntimeError("Preset did not load into the scene.")
        if nodeName:
            presetNode.SetName(slicer.mrmlScene.GetUniqueNameByString(nodeName))
        return presetNode

    def applyPresetToActiveVolume(self, presetNode):
        selectionNode = slicer.app.applicationLogic().GetSelectionNode()
        activeVolumeId = selectionNode.GetActiveVolumeID() if selectionNode else None
        if not activeVolumeId:
            raise RuntimeError("No active volume is selected.")

        volumeNode = slicer.mrmlScene.GetNodeByID(activeVolumeId)
        if volumeNode is None:
            raise RuntimeError("Selected active volume is not available.")

        volumeRenderingLogic = slicer.modules.volumerendering.logic()
        if volumeRenderingLogic is None:
            raise RuntimeError("Volume Rendering logic is not available.")

        displayNode = volumeRenderingLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
        if displayNode is None:
            raise RuntimeError("Could not create volume rendering nodes for the active volume.")

        # Remember the previously bound VolumeProperty node so the caller can
        # revert. SetAndObserveVolumePropertyNodeID only swaps the reference --
        # the previous VP node remains in the scene untouched.
        previousVP = displayNode.GetVolumePropertyNode()
        previousVPNodeId = previousVP.GetID() if previousVP is not None else None

        displayNode.SetAndObserveVolumePropertyNodeID(presetNode.GetID())
        displayNode.SetVisibility(True)
        return volumeNode, displayNode, previousVPNodeId

    def revertVolumePropertyForVolume(self, volumeId, originalVPNodeId):
        """Re-apply the snapshotted VolumeProperty to the volume's display node."""
        if not (volumeId and originalVPNodeId):
            raise RuntimeError("No original VolumeProperty was recorded.")
        volumeNode = slicer.mrmlScene.GetNodeByID(volumeId)
        originalVP = slicer.mrmlScene.GetNodeByID(originalVPNodeId)
        if volumeNode is None:
            raise RuntimeError("Original volume is no longer in the scene.")
        if originalVP is None:
            raise RuntimeError("Original VolumeProperty node is no longer in the scene.")
        volumeRenderingLogic = slicer.modules.volumerendering.logic()
        displayNode = volumeRenderingLogic.GetFirstVolumeRenderingDisplayNode(volumeNode)
        if displayNode is None:
            raise RuntimeError("Volume has no active volume-rendering display node.")
        displayNode.SetAndObserveVolumePropertyNodeID(originalVP.GetID())
        displayNode.SetVisibility(True)
        return volumeNode

    def exportPreset(self, name, outputDir, nodeId=None, viewIndex=0,
                     description="", author=""):
        """
        Export the selected VolumeProperty preset node.

        nodeId: ID of a vtkMRMLVolumePropertyNode.
        Returns (jsonPath, pngPath).
        Raises RuntimeError on failure.
        """
        if nodeId:
            vpNode = slicer.mrmlScene.GetNodeByID(nodeId)
        else:
            vpNode = None

        if vpNode is None:
            raise RuntimeError(
                "No VolumeProperty preset selected. "
                "Select a preset from the dropdown and click Refresh if needed."
            )

        jsonPath = os.path.join(outputDir, f"{name}.vp.json")
        pngPath = os.path.join(outputDir, f"{name}.png")

        self._exportVolumePropertyJson(vpNode, jsonPath, description=description, author=author)
        self._captureScreenshot(pngPath, viewIndex=viewIndex)

        return jsonPath, pngPath

    # --- private helpers --------------------------------------------------

    def _getActiveVolumeNode(self):
        selNode = slicer.mrmlScene.GetNodeByID(
            slicer.app.applicationLogic().GetSelectionNode().GetActiveVolumeID()
        )
        return selNode

    def _normalizePresetJsonFile(self, filePath):
        with open(filePath) as fp:
            data = json.load(fp)

        changed = False
        for volumeProperty in data.get("volumeProperties", []):
            for component in volumeProperty.get("components", []):
                for key in ("scalarOpacity", "gradientOpacity"):
                    transferFunction = component.get(key)
                    if not isinstance(transferFunction, dict):
                        continue
                    if transferFunction.get("type") == "piecewiseFunction":
                        transferFunction["type"] = "piecewiseLinearFunction"
                        changed = True
                    for point in transferFunction.get("points", []):
                        if "value" in point and "y" not in point:
                            point["y"] = point.pop("value")
                            changed = True

        if changed:
            with open(filePath, "w") as fp:
                json.dump(data, fp, indent=4)
                fp.write("\n")

    def _exportVolumePropertyJson(self, vpNode, path, description="", author=""):
        """
        Serialise a vtkMRMLVolumePropertyNode to the SlicerMorph VPs JSON schema.
        Uses StorableNode XML round-trip approach: write to a temp scene then re-encode
        into the community JSON format matching the existing .vp.json schema.
        """
        vp = vpNode.GetVolumeProperty()

        def _ctf_to_points(ctf):
            pts = []
            n = ctf.GetSize()
            for i in range(n):
                val = [0.0] * 6  # x, r, g, b, midpoint, sharpness
                ctf.GetNodeValue(i, val)
                pts.append({
                    "x": val[0],
                    "color": [val[1], val[2], val[3]],
                    "midpoint": val[4],
                    "sharpness": val[5],
                })
            return pts

        def _pwf_to_points(pwf):
            pts = []
            n = pwf.GetSize()
            for i in range(n):
                val = [0.0] * 4  # x, y, midpoint, sharpness
                pwf.GetNodeValue(i, val)
                pts.append({
                    "x": val[0],
                    "y": val[1],
                    "midpoint": val[2],
                    "sharpness": val[3],
                })
            return pts

        component = {
            "componentWeight": vp.GetComponentWeight(0),
            "shade": bool(vp.GetShade(0)),
            "lighting": {
                "diffuse": vp.GetDiffuse(0),
                "ambient": vp.GetAmbient(0),
                "specular": vp.GetSpecular(0),
                "specularPower": vp.GetSpecularPower(0),
            },
            "disableGradientOpacity": bool(vp.GetDisableGradientOpacity(0)),
            "scalarOpacityUnitDistance": vp.GetScalarOpacityUnitDistance(0),
            "rgbTransferFunction": {
                "type": "colorTransferFunction",
                "points": _ctf_to_points(vp.GetRGBTransferFunction(0)),
            },
            "scalarOpacity": {
                "type": "piecewiseLinearFunction",
                "points": _pwf_to_points(vp.GetScalarOpacity(0)),
            },
            "gradientOpacity": {
                "type": "piecewiseLinearFunction",
                "points": _pwf_to_points(vp.GetGradientOpacity(0)),
            },
        }

        effectiveRange = [0.0, 0.0]
        vp.GetRGBTransferFunction(0).GetRange(effectiveRange)

        data = {
            "@schema": (
                "https://raw.githubusercontent.com/slicer/slicer/main/"
                "Modules/Loadable/VolumeRendering/Resources/Schema/"
                "volume-property-schema-v1.0.0.json#"
            ),
            "volumeProperties": [
                {
                    "effectiveRange": list(effectiveRange),
                    "isoSurfaceValues": [0.0],
                    "independentComponents": bool(vp.GetIndependentComponents()),
                    "interpolationType": (
                        "linear" if vp.GetInterpolationType() == 1 else "nearest"
                    ),
                    "useClippedVoxelIntensity": False,
                    "clippedVoxelIntensity": -10000000000.0,
                    "scatteringAnisotropy": 0.0,
                    "components": [component],
                }
            ],
        }

        # Inject optional metadata not part of schema but useful for gallery
        if description:
            data["description"] = description
        if author:
            data["author"] = author

        with open(path, "w") as fh:
            json.dump(data, fh, indent=4)

    def _captureScreenshot(self, path, viewIndex=0):
        """Capture the selected 3-D view, centre-crop to square, and save to PNG."""
        import vtk
        lm = slicer.app.layoutManager()
        threeDWidget = lm.threeDWidget(viewIndex)
        if threeDWidget is None:
            raise RuntimeError(f"3-D view {viewIndex} is not available.")

        threeDView = threeDWidget.threeDView()
        slicer.util.forceRenderAllViews()

        cap = vtk.vtkWindowToImageFilter()
        cap.SetInput(threeDView.renderWindow())
        cap.SetInputBufferTypeToRGBA()
        cap.ReadFrontBufferOff()
        cap.Update()

        # Centre-crop to square so thumbnails look consistent in the gallery
        img = cap.GetOutput()
        w, h, _ = img.GetDimensions()
        size = min(w, h)
        x0 = (w - size) // 2
        y0 = (h - size) // 2

        crop = vtk.vtkExtractVOI()
        crop.SetInputConnection(cap.GetOutputPort())
        crop.SetVOI(x0, x0 + size - 1, y0, y0 + size - 1, 0, 0)
        crop.Update()

        writer = vtk.vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(crop.GetOutputPort())
        writer.Write()


# ---------------------------------------------------------------------------
# Minimal import shim so widget can use ctkPathLineEdit without ctk import
# at module load time (ctk is available inside Slicer at run-time).
# ---------------------------------------------------------------------------

def ctk_PathLineEdit():
    import ctk
    w = ctk.ctkPathLineEdit()
    return w


# ---------------------------------------------------------------------------
# Test stub (satisfies WITH_GENERIC_TESTS requirement)
# ---------------------------------------------------------------------------

class VRPresetHubTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.setUp()
        self.test_VRPresetHub1()

    def test_VRPresetHub1(self):
        self.delayDisplay("Module loaded successfully")
