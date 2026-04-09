import json
import os
import re
import tempfile
import urllib.parse

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

class SubmitVolumeRenderingPreset(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Submit Volume Rendering Preset"
        self.parent.categories = ["SlicerMorph.SlicerMorph Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Murat Maga (UW)"]
        self.parent.helpText = """
Export the active volume-rendering preset to a <code>.vp.json</code> file,
capture a 3-D screenshot, and open a pre-filled GitHub issue so you can share
the preset with the SlicerMorph community with a simple drag-and-drop.
"""
        self.parent.acknowledgementText = ""


# ---------------------------------------------------------------------------
# Widget (UI)
# ---------------------------------------------------------------------------

class SubmitVolumeRenderingPresetWidget(ScriptedLoadableModuleWidget):

    REPO = "SlicerMorph/VPs"

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = SubmitVolumeRenderingPresetLogic()
        self.layout.setAlignment(qt.Qt.AlignTop)

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

        # Editable preset name — auto-filled from selected volume, but overrideable
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

        # Initial population
        self._populateSelectors()

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
                "Upload configuration has just expired. "
                "Please wait a moment for the hourly refresh and try again.",
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

class SubmitVolumeRenderingPresetLogic(ScriptedLoadableModuleLogic):
    """Handles export of .vp.json and .png from the active volume rendering node."""

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
                    "value": val[1],
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
                "type": "piecewiseFunction",
                "points": _pwf_to_points(vp.GetScalarOpacity(0)),
            },
            "gradientOpacity": {
                "type": "piecewiseFunction",
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

class SubmitVolumeRenderingPresetTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.setUp()
        self.test_SubmitVolumeRenderingPreset1()

    def test_SubmitVolumeRenderingPreset1(self):
        self.delayDisplay("Module loaded successfully")
