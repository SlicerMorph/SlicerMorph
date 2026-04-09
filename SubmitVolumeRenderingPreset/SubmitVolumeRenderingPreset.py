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

        # ---- Collapsible: Preset Info ----
        infoBox = self._collapsible("Preset Information")
        formLayout = qt.QFormLayout(infoBox)

        self.nameEdit = qt.QLineEdit()
        self.nameEdit.placeholderText = "e.g. MouseSkull  (letters, digits, _ and - only)"
        self.nameEdit.toolTip = (
            "Short identifier for the preset. This becomes the filename prefix.\n"
            "Allowed characters: A-Z a-z 0-9 _ -"
        )
        formLayout.addRow("Preset name:", self.nameEdit)

        self.descEdit = qt.QLineEdit()
        self.descEdit.placeholderText = "One-line description (optional)"
        formLayout.addRow("Description:", self.descEdit)

        self.authorEdit = qt.QLineEdit()
        self.authorEdit.placeholderText = "Your name or GitHub @username (optional)"
        formLayout.addRow("Author:", self.authorEdit)

        # ---- Collapsible: Output folder ----
        outBox = self._collapsible("Output Folder")
        outLayout = qt.QFormLayout(outBox)

        self.outputDirButton = ctk_PathLineEdit()
        self.outputDirButton.filters = self.outputDirButton.Dirs
        self.outputDirButton.currentPath = os.path.expanduser("~/Desktop")
        self.outputDirButton.toolTip = (
            "Folder where the .vp.json and .png files will be saved before upload."
        )
        outLayout.addRow("Save to:", self.outputDirButton)

        # ---- Status label ----
        self.statusLabel = qt.QLabel("")
        self.statusLabel.wordWrap = True
        self.layout.addWidget(self.statusLabel)

        # ---- Buttons ----
        self.exportButton = qt.QPushButton("1 – Export preset files")
        self.exportButton.toolTip = (
            "Save <name>.vp.json and <name>.png to the output folder."
        )
        self.exportButton.enabled = False
        self.layout.addWidget(self.exportButton)

        self.submitButton = qt.QPushButton("2 – Open GitHub submission page")
        self.submitButton.toolTip = (
            "Opens a pre-filled GitHub issue in your browser.\n"
            "Drag the two exported files into the issue, then click Submit."
        )
        self.submitButton.enabled = False
        self.layout.addWidget(self.submitButton)

        # ---- Connections ----
        self.nameEdit.textChanged.connect(self._onNameChanged)
        self.exportButton.clicked.connect(self._onExport)
        self.submitButton.clicked.connect(self._onSubmit)

        self._exportedJson = None
        self._exportedPng = None

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

    def _onNameChanged(self, text):
        valid = bool(re.match(r'^[A-Za-z0-9_-]+$', text))
        self.exportButton.enabled = valid
        if text and not valid:
            self._setStatus(
                "⚠ Name may only contain letters, digits, _ and -.", "orange"
            )
        else:
            self._setStatus("")

    # --- export ----------------------------------------------------------

    def _onExport(self):
        name = self.nameEdit.text.strip()
        desc = self.descEdit.text.strip()
        author = self.authorEdit.text.strip()
        outDir = self.outputDirButton.currentPath

        if not os.path.isdir(outDir):
            try:
                os.makedirs(outDir)
            except OSError as e:
                self._setStatus(f"Cannot create output folder: {e}", "red")
                return

        try:
            jsonPath, pngPath = self.logic.exportPreset(
                name, outDir, description=desc, author=author
            )
        except Exception as e:
            self._setStatus(f"Export failed: {e}", "red")
            import traceback
            traceback.print_exc()
            return

        self._exportedJson = jsonPath
        self._exportedPng = pngPath
        self.submitButton.enabled = True
        self._setStatus(
            f"✓ Exported:\n  {os.path.basename(jsonPath)}\n  {os.path.basename(pngPath)}\n\n"
            f"Now click button 2 to open the GitHub submission page.",
            "darkgreen",
        )

        # Open the output folder in Finder so files are easy to drag
        qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(outDir))

    # --- submit (open browser) -------------------------------------------

    def _onSubmit(self):
        name = self.nameEdit.text.strip()
        desc = self.descEdit.text.strip()
        author = self.authorEdit.text.strip()

        body_lines = [
            "## Volume Rendering Preset Submission",
            "",
            f"**Preset name:** {name}",
        ]
        if desc:
            body_lines.append(f"**Description:** {desc}")
        if author:
            body_lines.append(f"**Author:** {author}")
        body_lines += [
            "",
            "### Files",
            f"Please attach the two files exported from Slicer:",
            f"- `{name}.vp.json`",
            f"- `{name}.png`",
            "",
            "Drag and drop both files into this text box, then click **Submit new issue**.",
            "",
            "---",
            "_Submitted via SlicerMorph SubmitVolumeRenderingPreset module_",
        ]
        body = "\n".join(body_lines)

        params = urllib.parse.urlencode({
            "title": f"New preset: {name}",
            "labels": "preset-submission",
            "body": body,
        })
        url = f"https://github.com/{self.REPO}/issues/new?{params}"
        qt.QDesktopServices.openUrl(qt.QUrl(url))

        self._setStatus(
            "✓ GitHub opened in your browser.\n"
            "Drag the two exported files from the Finder window into the issue, then submit.",
            "darkgreen",
        )


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

class SubmitVolumeRenderingPresetLogic(ScriptedLoadableModuleLogic):
    """Handles export of .vp.json and .png from the active volume rendering node."""

    def exportPreset(self, name, outputDir, description="", author=""):
        """
        Export the active volume-rendering preset.

        Returns (jsonPath, pngPath).
        Raises RuntimeError on failure.
        """
        vrLogic = slicer.modules.volumerendering.logic()
        volNode = self._getActiveVolumeNode()
        if volNode is None:
            raise RuntimeError("No active scalar volume node found. Load a volume first.")

        displayNode = vrLogic.GetFirstVolumeRenderingDisplayNode(volNode)
        if displayNode is None:
            raise RuntimeError(
                "Volume rendering is not enabled for the active volume. "
                "Enable it in the Volume Rendering module first."
            )

        vpNode = displayNode.GetVolumePropertyNode()
        if vpNode is None:
            raise RuntimeError("Could not find VolumePropertyNode.")

        jsonPath = os.path.join(outputDir, f"{name}.vp.json")
        pngPath = os.path.join(outputDir, f"{name}.png")

        self._exportVolumePropertyJson(vpNode, jsonPath, description=description, author=author)
        self._captureScreenshot(pngPath)

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

    def _captureScreenshot(self, path):
        """Capture the first 3-D view and save to PNG."""
        import vtk
        lm = slicer.app.layoutManager()
        threeDWidget = lm.threeDWidget(0)
        if threeDWidget is None:
            raise RuntimeError("No 3-D view is available.")

        threeDView = threeDWidget.threeDView()
        slicer.util.forceRenderAllViews()

        cap = vtk.vtkWindowToImageFilter()
        cap.SetInput(threeDView.renderWindow())
        cap.SetInputBufferTypeToRGBA()
        cap.ReadFrontBufferOff()
        cap.Update()

        writer = vtk.vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(cap.GetOutputPort())
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
