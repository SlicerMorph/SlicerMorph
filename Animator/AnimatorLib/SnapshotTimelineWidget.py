"""
Custom QWidget for editing a SceneSnapshotAction's keyframes.

Layout:

  [thumbnail strip — QListWidget in IconMode, horizontal scroll]
  [Time-scrub slider]               (live preview while dragging)
  [Selection details: time, label, segment mode]
  [Capture | Replace selected | Delete selected]
"""

import qt
import ctk
import slicer

from AnimatorLib.SceneSnapshot import (
    capture_current_scene,
    capture_thumbnail,
    sorted_keyframes,
    apply_camera_state,
    evaluate_at,
)


class SnapshotTimelineWidget(qt.QWidget):
    """Editor for one SceneSnapshotAction.

    Args:
      action: the action dict (mutated in place; caller persists via setAction)
      threeDView: the active threeDView (used for thumbnails and live preview)
      onChanged: callback invoked after every mutating edit; it receives no args
    """

    def __init__(self, action, threeDView, onChanged=lambda: None, parent=None):
        super().__init__(parent)
        self._action = action
        self._threeDView = threeDView
        self._onChanged = onChanged
        # remember pre-scrub state so we can restore on widget close
        self._preScrubCamState = None
        self._scrubbing = False
        self._buildUI()
        self._refreshTimeline()

    # ----- UI construction -----------------------------------------------

    def _buildUI(self):
        outerLayout = qt.QVBoxLayout(self)

        # Thumbnail strip
        self.thumbList = qt.QListWidget()
        self.thumbList.setViewMode(qt.QListWidget.IconMode)
        self.thumbList.setFlow(qt.QListView.LeftToRight)
        self.thumbList.setWrapping(False)
        self.thumbList.setIconSize(qt.QSize(120, 90))
        self.thumbList.setSpacing(8)
        self.thumbList.setMovement(qt.QListView.Static)
        self.thumbList.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self.thumbList.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAsNeeded)
        self.thumbList.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.thumbList.minimumHeight = 140
        self.thumbList.connect('currentRowChanged(int)', self._onSelectionChanged)
        outerLayout.addWidget(self.thumbList)

        # Live preview (scrubber)
        scrubRow = qt.QHBoxLayout()
        scrubRow.addWidget(qt.QLabel("Preview:"))
        self.scrubSlider = ctk.ctkSliderWidget()
        self.scrubSlider.singleStep = 0.01
        self.scrubSlider.decimals = 2
        self.scrubSlider.minimum = 0.0
        self.scrubSlider.maximum = 1.0
        self.scrubSlider.value = 0.0
        self.scrubSlider.setToolTip(
            "Drag to preview the animation in the 3D view. "
            "Releasing the slider restores the scene to the state captured "
            "before scrubbing started.")
        self.scrubSlider.connect('valueChanged(double)', self._onScrub)
        scrubRow.addWidget(self.scrubSlider, 1)
        self.restoreButton = qt.QPushButton("Restore live")
        self.restoreButton.setToolTip(
            "Restore the live camera/VP to whatever they were before you started "
            "scrubbing the preview slider above.")
        self.restoreButton.connect('clicked()', self._restoreLive)
        scrubRow.addWidget(self.restoreButton)
        outerLayout.addLayout(scrubRow)

        # Selection details
        detailGroup = qt.QGroupBox("Selected keyframe")
        detailForm = qt.QFormLayout(detailGroup)

        self.labelEdit = qt.QLineEdit()
        self.labelEdit.connect('editingFinished()', self._onLabelChanged)
        detailForm.addRow("Label", self.labelEdit)

        self.timeSpin = ctk.ctkDoubleSpinBox()
        self.timeSpin.suffix = " s"
        self.timeSpin.minimum = 0.0
        self.timeSpin.maximum = 9999.0
        self.timeSpin.singleStep = 0.1
        self.timeSpin.decimals = 2
        self.timeSpin.connect('editingFinished()', self._onTimeChanged)
        detailForm.addRow("Time", self.timeSpin)

        self.segmentModeCombo = qt.QComboBox()
        self.segmentModeCombo.addItem("Interpolate to next", "interpolate")
        self.segmentModeCombo.addItem("Hold until next", "hold")
        self.segmentModeCombo.setToolTip(
            "Behavior of the segment that STARTS at this keyframe. "
            "'Interpolate' tweens to the next keyframe; 'Hold' freezes "
            "this state until the next keyframe is reached.")
        self.segmentModeCombo.connect(
            'currentIndexChanged(int)', self._onSegmentModeChanged)
        detailForm.addRow("After this", self.segmentModeCombo)

        outerLayout.addWidget(detailGroup)

        # Action buttons
        buttonRow = qt.QHBoxLayout()
        self.captureButton = qt.QPushButton("Capture current state \u2192 new keyframe")
        self.captureButton.setToolTip(
            "Set up the 3D view exactly how you want this moment to look "
            "(camera angle, volume rendering colors, etc.) then click here. "
            "The new keyframe is appended at the current end-time + 1 second.")
        self.captureButton.connect('clicked()', self._onCapture)
        buttonRow.addWidget(self.captureButton)

        self.replaceButton = qt.QPushButton("Replace selected from current state")
        self.replaceButton.connect('clicked()', self._onReplace)
        buttonRow.addWidget(self.replaceButton)

        self.deleteButton = qt.QPushButton("Delete selected")
        self.deleteButton.connect('clicked()', self._onDelete)
        buttonRow.addWidget(self.deleteButton)

        outerLayout.addLayout(buttonRow)

    # ----- helpers --------------------------------------------------------

    def _keyframes(self):
        return self._action.setdefault('keyframes', [])

    def _normalizeAndSyncBounds(self):
        """Sort keyframes by time and set action.startTime / endTime to span them."""
        kfs = sorted_keyframes(self._keyframes())
        self._action['keyframes'] = kfs
        if kfs:
            self._action['startTime'] = kfs[0]['time']
            self._action['endTime'] = kfs[-1]['time']

    def _refreshTimeline(self, selectId=None):
        self._normalizeAndSyncBounds()
        kfs = self._keyframes()

        self.thumbList.blockSignals(True)
        self.thumbList.clear()
        for kf in kfs:
            item = qt.QListWidgetItem(f"{kf['label']}\n{kf['time']:.2f}s")
            item.setTextAlignment(qt.Qt.AlignHCenter | qt.Qt.AlignBottom)
            if kf.get('thumbnailPath'):
                item.setIcon(qt.QIcon(kf['thumbnailPath']))
            else:
                # fallback gray icon
                pix = qt.QPixmap(120, 90)
                pix.fill(qt.QColor(80, 80, 80))
                item.setIcon(qt.QIcon(pix))
            item.setData(qt.Qt.UserRole, kf['id'])
            self.thumbList.addItem(item)
        self.thumbList.blockSignals(False)

        # Update scrubber bounds
        if len(kfs) >= 2:
            self.scrubSlider.minimum = kfs[0]['time']
            self.scrubSlider.maximum = kfs[-1]['time']
            self.scrubSlider.singleStep = max(0.01, (kfs[-1]['time'] - kfs[0]['time']) / 200.0)
            self.scrubSlider.enabled = True
        else:
            self.scrubSlider.enabled = False
            self.scrubSlider.minimum = 0.0
            self.scrubSlider.maximum = 1.0

        # Restore selection
        target_row = -1
        if selectId is not None:
            for i, kf in enumerate(kfs):
                if kf['id'] == selectId:
                    target_row = i
                    break
        if target_row < 0 and kfs:
            target_row = self.thumbList.currentRow if self.thumbList.currentRow >= 0 else 0
            target_row = min(target_row, len(kfs) - 1)
        self.thumbList.setCurrentRow(target_row)
        self._loadSelectionIntoDetails()
        self._onChanged()

    def _selectedKeyframe(self):
        row = self.thumbList.currentRow
        kfs = self._keyframes()
        if 0 <= row < len(kfs):
            return kfs[row]
        return None

    def _loadSelectionIntoDetails(self):
        kf = self._selectedKeyframe()
        enabled = kf is not None
        self.labelEdit.enabled = enabled
        self.timeSpin.enabled = enabled
        self.segmentModeCombo.enabled = enabled
        self.replaceButton.enabled = enabled
        self.deleteButton.enabled = enabled
        if not kf:
            self.labelEdit.text = ""
            self.timeSpin.value = 0.0
            return
        self.labelEdit.blockSignals(True)
        self.timeSpin.blockSignals(True)
        self.segmentModeCombo.blockSignals(True)
        self.labelEdit.text = kf.get('label', '')
        self.timeSpin.value = kf.get('time', 0.0)
        mode = kf.get('segmentMode', 'interpolate')
        idx = self.segmentModeCombo.findData(mode)
        self.segmentModeCombo.currentIndex = idx if idx >= 0 else 0
        self.labelEdit.blockSignals(False)
        self.timeSpin.blockSignals(False)
        self.segmentModeCombo.blockSignals(False)

    # ----- callbacks ------------------------------------------------------

    def _onSelectionChanged(self, _row):
        self._loadSelectionIntoDetails()

    def _onLabelChanged(self):
        kf = self._selectedKeyframe()
        if kf is None:
            return
        kf['label'] = self.labelEdit.text
        self._refreshTimeline(selectId=kf['id'])

    def _onTimeChanged(self):
        kf = self._selectedKeyframe()
        if kf is None:
            return
        kf['time'] = float(self.timeSpin.value)
        self._refreshTimeline(selectId=kf['id'])

    def _onSegmentModeChanged(self, _idx):
        kf = self._selectedKeyframe()
        if kf is None:
            return
        kf['segmentMode'] = self.segmentModeCombo.itemData(
            self.segmentModeCombo.currentIndex)
        self._onChanged()

    def _onCapture(self):
        kfs = self._keyframes()
        if kfs:
            new_time = max(kf['time'] for kf in kfs) + 1.0
        else:
            new_time = 0.0
        new_label = f"Snapshot {len(kfs) + 1}"
        new_kf = capture_current_scene(
            animated_camera_id=self._action.get('animatedCameraID'),
            animated_vp_id=self._action.get('animatedVolumePropertyID'),
            action_id=self._action.get('id', ''),
            time_seconds=new_time,
            label=new_label,
        )
        new_kf['thumbnailPath'] = capture_thumbnail(self._threeDView, new_kf['id'])
        kfs.append(new_kf)
        self._refreshTimeline(selectId=new_kf['id'])

    def _onReplace(self):
        kf = self._selectedKeyframe()
        if kf is None:
            return
        # Capture fresh state but keep same id and time/label/segmentMode.
        replacement = capture_current_scene(
            animated_camera_id=self._action.get('animatedCameraID'),
            animated_vp_id=self._action.get('animatedVolumePropertyID'),
            action_id=self._action.get('id', ''),
            time_seconds=kf['time'],
            label=kf['label'],
        )
        # Drop the old VP snapshot node if any
        old_vp_id = kf.get('volumePropertyID')
        if old_vp_id:
            old_vp = slicer.mrmlScene.GetNodeByID(old_vp_id)
            if old_vp is not None:
                slicer.mrmlScene.RemoveNode(old_vp)
        kf['cameraState'] = replacement['cameraState']
        kf['volumePropertyID'] = replacement['volumePropertyID']
        kf['thumbnailPath'] = capture_thumbnail(self._threeDView, kf['id'])
        self._refreshTimeline(selectId=kf['id'])

    def _onDelete(self):
        kf = self._selectedKeyframe()
        if kf is None:
            return
        # Clean up VP snapshot node and thumbnail
        old_vp_id = kf.get('volumePropertyID')
        if old_vp_id:
            old_vp = slicer.mrmlScene.GetNodeByID(old_vp_id)
            if old_vp is not None:
                slicer.mrmlScene.RemoveNode(old_vp)
        kfs = self._keyframes()
        kfs.remove(kf)
        self._refreshTimeline()

    # ----- live scrubbing -------------------------------------------------

    def _onScrub(self, t):
        # Capture pre-scrub state once, on first move.
        if not self._scrubbing:
            cam_id = self._action.get('animatedCameraID')
            cam_node = slicer.mrmlScene.GetNodeByID(cam_id) if cam_id else None
            if cam_node is not None:
                from AnimatorLib.SceneSnapshot import capture_camera_state
                self._preScrubCamState = capture_camera_state(cam_node)
            self._scrubbing = True

        cam_state = evaluate_at(self._action, float(t))
        cam_id = self._action.get('animatedCameraID')
        cam_node = slicer.mrmlScene.GetNodeByID(cam_id) if cam_id else None
        if cam_state is not None and cam_node is not None:
            apply_camera_state(cam_node, cam_state)

    def _restoreLive(self):
        if not self._scrubbing or self._preScrubCamState is None:
            return
        cam_id = self._action.get('animatedCameraID')
        cam_node = slicer.mrmlScene.GetNodeByID(cam_id) if cam_id else None
        if cam_node is not None:
            apply_camera_state(cam_node, self._preScrubCamState)
        self._scrubbing = False
        self._preScrubCamState = None
