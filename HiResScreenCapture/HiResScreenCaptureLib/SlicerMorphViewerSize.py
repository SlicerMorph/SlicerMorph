"""
SlicerMorphViewerSize
=====================

Shared helper for SlicerMorph modules that need to undock a 3D viewer and
control its pixel dimensions (HiResScreenCapture, Animator, ...).

This file lives inside the HiResScreenCapture module folder. Slicer adds
each scripted-module folder to ``sys.path`` at startup, so other modules
can import it as::

    from SlicerMorphViewerSize import ViewerSizeController, snap_to_codec_size

Public API:

* ``ViewerSizeController`` - a ``QWidget`` providing viewer selection,
  undock/redock buttons, and width/height spinboxes with a lock/reset
  workflow. Emits signals when the tracked size changes or when the user
  pins/unpins a size.
* ``snap_to_codec_size(width, height, multiple=16)`` - pure function that
  returns the closest codec-friendly ``(w, h)`` preserving aspect ratio
  as well as possible. Used by Animator for H.264 output.
"""

import qt
import slicer


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def snap_to_codec_size(width, height, multiple=16):
    """Return a codec-friendly ``(w, h)`` close to the requested size.

    Strategy: snap *width* to the nearest multiple of ``multiple``, then
    derive height from the original aspect ratio and snap that to the
    nearest multiple of ``multiple``. This keeps the aspect ratio drift
    small while guaranteeing both dimensions satisfy the codec
    requirement (H.264 / libx264 prefers multiples of 16; ``yuv420p``
    requires at least multiples of 2).

    Returns
    -------
    (snapped_width, snapped_height, aspect_drift_percent)
        ``aspect_drift_percent`` is the absolute percentage change of
        ``w/h`` from the input to the snapped output.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if multiple < 1:
        raise ValueError("multiple must be >= 1")

    aspect = width / float(height)

    def _snap(v):
        # Round to the nearest multiple of ``multiple`` but never below it.
        snapped = int(round(v / float(multiple))) * multiple
        return max(multiple, snapped)

    snapped_w = _snap(width)
    snapped_h = _snap(snapped_w / aspect)

    new_aspect = snapped_w / float(snapped_h)
    drift_percent = abs(new_aspect - aspect) / aspect * 100.0
    return snapped_w, snapped_h, drift_percent


# ---------------------------------------------------------------------------
# Viewer size controller widget
# ---------------------------------------------------------------------------

class ViewerSizeController(qt.QWidget):
    """Reusable widget for undocking a 3D viewer and pinning its size.

    Signals
    -------
    sizeChanged(int width, int height)
        Emitted whenever the tracked viewer size changes (either because
        the user resized the undocked window or because the size was
        pinned programmatically).
    lockChanged(bool locked, int width, int height)
        Emitted when the size is pinned or released. ``width`` and
        ``height`` are the locked size when ``locked`` is True, otherwise
        the current dynamic size.
    undockChanged(bool undocked)
        Emitted when the viewer is undocked or redocked.
    """

    sizeChanged = qt.Signal(int, int)
    lockChanged = qt.Signal(bool, int, int)
    undockChanged = qt.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self._viewerSizeLocked = False
        self._pinnedWidth = None
        self._pinnedHeight = None
        self._viewerIsUndocked = False
        self._originalLayout = None
        self._threeDWidget = None
        self._timerUpdatingSize = False
        self._lastReportedSize = (0, 0)

        # Build the UI
        layout = qt.QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Viewer selector
        self.viewerComboBox = qt.QComboBox()
        self.viewerComboBox.toolTip = "Select which 3D viewer to undock"
        self.viewerComboBox.setMaximumWidth(200)
        layout.addRow("3D Viewer:", self.viewerComboBox)

        # Undock / Redock buttons stacked vertically
        buttonVBox = qt.QVBoxLayout()
        buttonVBox.setAlignment(qt.Qt.AlignLeft)

        self.undockViewerButton = qt.QPushButton("Undock 3D Viewer")
        self.undockViewerButton.toolTip = (
            "Undocks the 3D viewer so it can be resized for a custom output "
            "aspect ratio."
        )
        self.undockViewerButton.clicked.connect(self.onUndockViewer)
        self.undockViewerButton.setMaximumWidth(150)
        buttonVBox.addWidget(self.undockViewerButton)

        self.redockViewerButton = qt.QPushButton("Redock 3D Viewer")
        self.redockViewerButton.toolTip = "Redock the 3D viewer back to its original layout"
        self.redockViewerButton.clicked.connect(self.onRedockViewer)
        self.redockViewerButton.enabled = False
        self.redockViewerButton.setMaximumWidth(150)
        buttonVBox.addWidget(self.redockViewerButton)

        layout.addRow("", buttonVBox)

        # Size spinboxes
        self.widthSpinBox = qt.QSpinBox()
        self.widthSpinBox.setRange(100, 10000)
        self.widthSpinBox.setValue(800)
        self.widthSpinBox.setSuffix(" px")
        self.widthSpinBox.setMaximumWidth(90)
        self.widthSpinBox.setToolTip("Viewer width - press Enter to lock this value")

        self.heightSpinBox = qt.QSpinBox()
        self.heightSpinBox.setRange(100, 10000)
        self.heightSpinBox.setValue(600)
        self.heightSpinBox.setSuffix(" px")
        self.heightSpinBox.setMaximumWidth(90)
        self.heightSpinBox.setToolTip("Viewer height - press Enter to lock this value")

        self.resetSizeButton = qt.QPushButton("\u21ba")
        self.resetSizeButton.setMaximumWidth(28)
        self.resetSizeButton.setToolTip("Reset to dynamic (follow window size)")
        self.resetSizeButton.enabled = False
        self.resetSizeButton.clicked.connect(self.onViewerSizeReset)

        sizeHBox = qt.QHBoxLayout()
        sizeHBox.addWidget(self.widthSpinBox)
        sizeHBox.addWidget(qt.QLabel("\u00d7"))
        sizeHBox.addWidget(self.heightSpinBox)
        sizeHBox.addWidget(self.resetSizeButton)
        sizeHBox.addStretch()
        layout.addRow("Viewer Size:", sizeHBox)

        self.widthSpinBox.editingFinished.connect(self.onViewerSizePinned)
        self.heightSpinBox.editingFinished.connect(self.onViewerSizePinned)

        # Live size tracker
        self._updateTimer = qt.QTimer(self)
        self._updateTimer.timeout.connect(self._tickSizeUpdate)
        self._updateTimer.start(100)

        # Populate combo and watch for layout changes
        self._populateViewerComboBox()
        slicer.app.layoutManager().layoutChanged.connect(self._populateViewerComboBox)

    # -- lifecycle ----------------------------------------------------------

    def cleanup(self):
        """Stop the timer and disconnect Slicer signals.

        Safe to call multiple times; the parent widget should call this
        from its own ``cleanup``.
        """
        if self._updateTimer:
            self._updateTimer.stop()
        try:
            slicer.app.layoutManager().layoutChanged.disconnect(self._populateViewerComboBox)
        except Exception:
            pass

    # -- public state queries ----------------------------------------------

    def isLocked(self):
        return self._viewerSizeLocked

    def isUndocked(self):
        return self._viewerIsUndocked

    def threeDWidget(self):
        """Return the currently undocked 3D widget, or None."""
        return self._threeDWidget if self._viewerIsUndocked else None

    def lockedSize(self):
        """Return the pinned ``(width, height)`` or ``None`` if not locked."""
        if self._viewerSizeLocked and self._pinnedWidth and self._pinnedHeight:
            return (self._pinnedWidth, self._pinnedHeight)
        return None

    def currentSize(self):
        """Return the current tracked ``(width, height)``.

        If a size is pinned, return the pinned values; otherwise the
        live size of the (undocked or docked) 3D widget. Returns
        ``(0, 0)`` if no viewer is available yet.
        """
        if self._viewerSizeLocked and self._pinnedWidth and self._pinnedHeight:
            return (self._pinnedWidth, self._pinnedHeight)
        widget = self._currentTrackedWidget()
        if widget is None:
            return (0, 0)
        view = widget.threeDView()
        return (view.width, view.height)

    # -- public actions -----------------------------------------------------

    def pinSize(self, width, height):
        """Programmatically lock the viewer to ``(width, height)``.

        Updates the spinboxes, applies the size to the undocked widget
        if one is open, and emits ``lockChanged``.
        """
        self._viewerSizeLocked = True
        self._pinnedWidth = int(width)
        self._pinnedHeight = int(height)
        self._timerUpdatingSize = True
        self.widthSpinBox.setValue(self._pinnedWidth)
        self.heightSpinBox.setValue(self._pinnedHeight)
        self._timerUpdatingSize = False
        self.resetSizeButton.enabled = True
        if self._viewerIsUndocked and self._threeDWidget:
            self._applyUndockedSize(self._pinnedWidth, self._pinnedHeight)
        self.lockChanged.emit(True, self._pinnedWidth, self._pinnedHeight)
        self.sizeChanged.emit(self._pinnedWidth, self._pinnedHeight)

    def _applyUndockedSize(self, width, height):
        """Force the undocked top-level 3D widget to the requested size.

        ``QWidget.resize`` alone is unreliable on macOS for top-level
        windows once they have been shown - the window manager often
        clamps or ignores the request. We temporarily clear the
        min/max size constraints, use ``setGeometry`` to set the new
        size at the current position, restore the constraints, and
        also explicitly resize the inner ``threeDView`` so VTK rebuilds
        its render window at the new dimensions.
        """
        if not self._threeDWidget:
            return
        widget = self._threeDWidget
        old_min = widget.minimumSize
        old_max = widget.maximumSize
        # Allow any size temporarily.
        widget.setMinimumSize(qt.QSize(0, 0))
        widget.setMaximumSize(qt.QSize(16777215, 16777215))
        pos = widget.pos
        widget.setGeometry(pos.x(), pos.y(), int(width), int(height))
        widget.resize(qt.QSize(int(width), int(height)))
        # Resize the inner threeDView too, so VTK's render window picks
        # up the new dimensions immediately.
        try:
            view = widget.threeDView()
            if view is not None:
                view.resize(qt.QSize(int(width), int(height)))
                rw = view.renderWindow()
                if rw is not None:
                    rw.SetSize(int(width), int(height))
                    rw.Render()
        except Exception:
            pass
        slicer.app.processEvents()
        # Restore constraints.
        widget.setMinimumSize(old_min)
        widget.setMaximumSize(old_max)

    # -- internal slots -----------------------------------------------------

    def onUndockViewer(self):
        self._populateViewerComboBox()
        viewerIndex = self.viewerComboBox.currentIndex
        if viewerIndex < 0:
            viewerIndex = 0
        self._undock(viewerIndex)
        self.undockViewerButton.enabled = False
        self.redockViewerButton.enabled = True
        self.undockChanged.emit(True)

    def onRedockViewer(self):
        self._redock()
        self.onViewerSizeReset()
        # Defer button-state restore so the layout change can settle.
        qt.QTimer.singleShot(100, self._afterRedock)
        self.undockChanged.emit(False)

    def _afterRedock(self):
        self.undockViewerButton.enabled = True
        self.redockViewerButton.enabled = False

    def onViewerSizePinned(self):
        if self._timerUpdatingSize:
            return
        self.pinSize(self.widthSpinBox.value, self.heightSpinBox.value)

    def onViewerSizeReset(self):
        was_locked = self._viewerSizeLocked
        self._viewerSizeLocked = False
        self._pinnedWidth = None
        self._pinnedHeight = None
        self.resetSizeButton.enabled = False
        if was_locked:
            w, h = self.currentSize()
            self.lockChanged.emit(False, w, h)

    # -- internal helpers ---------------------------------------------------

    def _currentTrackedWidget(self):
        """Return the 3D widget whose live size we should track."""
        if self._viewerIsUndocked and self._threeDWidget:
            return self._threeDWidget
        layoutManager = slicer.app.layoutManager()
        if not layoutManager:
            return None
        viewerIndex = self.viewerComboBox.currentIndex
        if viewerIndex < 0 or viewerIndex >= layoutManager.threeDViewCount:
            viewerIndex = 0
        if layoutManager.threeDViewCount == 0:
            return None
        return layoutManager.threeDWidget(viewerIndex)

    def _tickSizeUpdate(self):
        """Periodic update of the spinboxes and emission of sizeChanged."""
        try:
            if self._viewerSizeLocked:
                w = self.widthSpinBox.value
                h = self.heightSpinBox.value
            else:
                widget = self._currentTrackedWidget()
                if widget is None:
                    return
                view = widget.threeDView()
                w = view.width
                h = view.height
                self._timerUpdatingSize = True
                if not self.widthSpinBox.hasFocus():
                    self.widthSpinBox.setValue(w)
                if not self.heightSpinBox.hasFocus():
                    self.heightSpinBox.setValue(h)
                self._timerUpdatingSize = False

            if w and h and (w, h) != self._lastReportedSize:
                self._lastReportedSize = (w, h)
                self.sizeChanged.emit(w, h)
        except Exception:
            pass

    def _populateViewerComboBox(self):
        layoutManager = slicer.app.layoutManager()
        if not layoutManager:
            return
        current = self.viewerComboBox.currentIndex
        self.viewerComboBox.clear()
        for i in range(layoutManager.threeDViewCount):
            node = layoutManager.threeDWidget(i).mrmlViewNode()
            name = node.GetName() if node and node.GetName() else f"3D View {i + 1}"
            self.viewerComboBox.addItem(name)
        if 0 <= current < self.viewerComboBox.count:
            self.viewerComboBox.currentIndex = current

    def _undock(self, viewerIndex):
        if self._viewerIsUndocked:
            return
        layoutManager = slicer.app.layoutManager()
        self._originalLayout = layoutManager.layout
        self._threeDWidget = layoutManager.threeDWidget(viewerIndex)
        self._threeDWidget.setParent(None)
        self._threeDWidget.show()
        # On macOS the VTK OpenGL surface needs a forced render after
        # reparenting or the window comes up blank.
        slicer.app.processEvents()
        self._threeDWidget.threeDView().renderWindow().Render()
        self._viewerIsUndocked = True

    def _redock(self):
        if not self._viewerIsUndocked:
            return
        if self._threeDWidget and self._originalLayout is not None:
            layoutManager = slicer.app.layoutManager()
            # Toggle the layout to force the widget to reparent.
            layoutManager.layout = slicer.vtkMRMLLayoutNode.SlicerLayoutCustomView
            layoutManager.layout = self._originalLayout
        self._viewerIsUndocked = False
        self._threeDWidget = None
