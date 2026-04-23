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


class _DraggableTimelineTrack(qt.QWidget):
    """Horizontal time track showing one marker per keyframe.

    Drag a marker left/right to change its time. Click a marker to select it.
    Emits a signal-equivalent via callbacks supplied by the parent widget.
    """

    MARKER_RADIUS = 9
    PAD_LEFT = 30
    PAD_RIGHT = 30
    TRACK_Y = 36

    def __init__(self, onTimeChanged, onSelect, onDragLive, parent=None):
        super().__init__(parent)
        self._keyframes = []
        self._selectedId = None
        self._draggingIndex = -1
        self._onTimeChanged = onTimeChanged   # (kf_id, new_time) -> None, called on release
        self._onSelect = onSelect             # (kf_id) -> None
        self._onDragLive = onDragLive         # (new_time) -> None, while dragging (for scrub)
        self._tMin = 0.0
        self._tMax = 1.0
        self.setMinimumHeight(70)
        self.setMouseTracking(True)
        self.setToolTip(
            "Drag a marker left/right to change its time. "
            "Click a marker to select it.")

    def setKeyframes(self, keyframes, selectedId=None):
        self._keyframes = list(keyframes)
        self._selectedId = selectedId
        if self._keyframes:
            self._tMin = min(0.0, min(k['time'] for k in self._keyframes))
            self._tMax = max(self._tMin + 1.0, max(k['time'] for k in self._keyframes))
            # Add 5% padding on the right so the last marker isn't on the edge.
            self._tMax = self._tMin + (self._tMax - self._tMin) * 1.05
        else:
            self._tMin, self._tMax = 0.0, 1.0
        self.update()

    # ----- coordinate mapping -----

    def _trackRect(self):
        w = self.width
        return self.PAD_LEFT, self.TRACK_Y, max(10, w - self.PAD_LEFT - self.PAD_RIGHT), 4

    def _timeToX(self, t):
        x0, _, w, _ = self._trackRect()
        if self._tMax <= self._tMin:
            return x0
        return x0 + (t - self._tMin) / (self._tMax - self._tMin) * w

    def _xToTime(self, x):
        x0, _, w, _ = self._trackRect()
        if w <= 0:
            return self._tMin
        frac = max(0.0, min(1.0, (x - x0) / float(w)))
        return self._tMin + frac * (self._tMax - self._tMin)

    def _markerAt(self, pos):
        for i, kf in enumerate(self._keyframes):
            cx = self._timeToX(kf['time'])
            cy = self.TRACK_Y + 2
            if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= (self.MARKER_RADIUS + 2) ** 2:
                return i
        return -1

    # ----- painting -----

    def paintEvent(self, _event):
        p = qt.QPainter(self)
        p.setRenderHint(qt.QPainter.Antialiasing, True)
        x0, y0, w, h = self._trackRect()

        # Track line
        p.setPen(qt.QPen(qt.QColor(120, 120, 120), 2))
        p.drawLine(x0, y0 + h // 2, x0 + w, y0 + h // 2)

        # Tick marks every ~1s if range small, else nice round step
        span = self._tMax - self._tMin
        step = 1.0
        if span > 30:
            step = 5.0
        elif span > 10:
            step = 2.0
        elif span < 2:
            step = 0.5
        p.setPen(qt.QPen(qt.QColor(140, 140, 140), 1))
        t = 0.0
        while t <= self._tMax + 1e-6:
            if t >= self._tMin - 1e-6:
                tx = self._timeToX(t)
                p.drawLine(int(tx), y0 + h // 2 - 4, int(tx), y0 + h // 2 + 4)
                p.drawText(int(tx) - 12, y0 + h // 2 + 18, f"{t:g}s")
            t += step

        # Markers
        for kf in self._keyframes:
            cx = self._timeToX(kf['time'])
            cy = y0 + 2
            selected = (kf['id'] == self._selectedId)
            color = qt.QColor(80, 160, 255) if selected else qt.QColor(220, 170, 60)
            p.setBrush(qt.QBrush(color))
            p.setPen(qt.QPen(qt.QColor(40, 40, 40), 1))
            p.drawEllipse(qt.QPoint(int(cx), int(cy)), self.MARKER_RADIUS, self.MARKER_RADIUS)
            # Time label above
            p.setPen(qt.QPen(qt.QColor(40, 40, 40), 1))
            p.drawText(int(cx) - 18, cy - self.MARKER_RADIUS - 4, f"{kf['time']:.2f}s")

    # ----- interaction -----

    def mousePressEvent(self, event):
        if event.button() != qt.Qt.LeftButton:
            return
        idx = self._markerAt(event.pos())
        if idx >= 0:
            self._draggingIndex = idx
            kf = self._keyframes[idx]
            self._selectedId = kf['id']
            self._onSelect(kf['id'])
            self.update()

    def mouseMoveEvent(self, event):
        if self._draggingIndex < 0:
            return
        kf = self._keyframes[self._draggingIndex]
        new_t = max(0.0, self._xToTime(event.pos().x()))
        kf['time'] = new_t
        self._onDragLive(new_t)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._draggingIndex < 0:
            return
        kf = self._keyframes[self._draggingIndex]
        self._draggingIndex = -1
        self._onTimeChanged(kf['id'], kf['time'])


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

        # Draggable timeline track
        self.timelineTrack = _DraggableTimelineTrack(
            onTimeChanged=self._onMarkerReleased,
            onSelect=self._onMarkerSelected,
            onDragLive=self._onMarkerDragLive,
        )
        outerLayout.addWidget(self.timelineTrack)

        # Live preview (scrubber)
        scrubRow = qt.QHBoxLayout()
        scrubRow.addWidget(qt.QLabel("Scrub time (s):"))
        self.scrubSlider = ctk.ctkSliderWidget()
        self.scrubSlider.singleStep = 0.01
        self.scrubSlider.decimals = 2
        self.scrubSlider.minimum = 0.0
        self.scrubSlider.maximum = 1.0
        self.scrubSlider.value = 0.0
        self.scrubSlider.setToolTip(
            "Drag to preview the animation in the 3D view at any moment. "
            "Use 'Play preview' for continuous playback. 'Restore live' "
            "puts the 3D view back to the state it was in before you "
            "started scrubbing.")
        self.scrubSlider.connect('valueChanged(double)', self._onScrub)
        scrubRow.addWidget(self.scrubSlider, 1)
        self.playButton = qt.QPushButton("\u25B6 Play preview")
        self.playButton.setCheckable(True)
        self.playButton.setToolTip(
            "Play the animation continuously in the 3D view, looping "
            "between the first and last keyframes.")
        self.playButton.connect('toggled(bool)', self._onPlayToggled)
        scrubRow.addWidget(self.playButton)
        self.restoreButton = qt.QPushButton("Restore live")
        self.restoreButton.setToolTip(
            "Restore the live camera/VP to whatever they were before you started "
            "scrubbing the preview slider above.")
        self.restoreButton.connect('clicked()', self._restoreLive)
        scrubRow.addWidget(self.restoreButton)
        outerLayout.addLayout(scrubRow)

        # Playback timer
        self._playTimer = qt.QTimer(self)
        self._playTimer.setInterval(33)  # ~30 fps preview
        self._playTimer.connect('timeout()', self._onPlayTick)

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
        # Push to draggable track too
        sel_id = None
        if 0 <= target_row < len(kfs):
            sel_id = kfs[target_row]['id']
        self.timelineTrack.setKeyframes(kfs, selectedId=sel_id)
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

    # ----- draggable timeline callbacks -----

    def _onMarkerSelected(self, kf_id):
        kfs = self._keyframes()
        for i, kf in enumerate(kfs):
            if kf['id'] == kf_id:
                self.thumbList.setCurrentRow(i)
                break

    def _onMarkerDragLive(self, _new_t):
        # Live-update the time spinbox so user sees the value changing.
        kf = self._selectedKeyframe()
        if kf is not None:
            self.timeSpin.blockSignals(True)
            self.timeSpin.value = kf['time']
            self.timeSpin.blockSignals(False)

    def _onMarkerReleased(self, kf_id, _new_time):
        # Persist + re-sort + update everything.
        self._refreshTimeline(selectId=kf_id)

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

    # ----- preview playback ----------------------------------------------

    def _onPlayToggled(self, checked):
        if checked:
            kfs = self._keyframes()
            if len(kfs) < 2:
                self.playButton.setChecked(False)
                slicer.util.messageBox(
                    "Add at least 2 keyframes before playing the preview.")
                return
            self.playButton.setText("\u25A0 Stop preview")
            # Reset to start of timeline
            self.scrubSlider.value = self.scrubSlider.minimum
            self._playTimer.start()
        else:
            self.playButton.setText("\u25B6 Play preview")
            self._playTimer.stop()

    def _onPlayTick(self):
        # Advance the scrub slider; when we reach the end, loop.
        step = float(self._playTimer.interval) / 1000.0  # seconds of real time
        new_t = self.scrubSlider.value + step
        if new_t > self.scrubSlider.maximum:
            new_t = self.scrubSlider.minimum
        # _onScrub will be called via valueChanged signal
        self.scrubSlider.value = new_t

    def stopPlayback(self):
        """Public hook so the parent dialog can stop our timer on close."""
        if self._playTimer.isActive():
            self._playTimer.stop()
        if self.playButton.isChecked():
            self.playButton.setChecked(False)
