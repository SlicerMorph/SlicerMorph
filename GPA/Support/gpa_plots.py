"""Matplotlib plots of the GPA module.

The figures are shown in a view of the GPA layouts (``<gpaplotview>``), provided
by the InteractiveMatplotlib module of the Sandbox extension. The figure is drawn
with Agg into a VTK render view, so it is pannable, zoomable and can be saved
(PNG/SVG/PDF) from its toolbar.

Matplotlib is imported only when a plot is made, so the GPA module (and ALPACA,
which loads GPA's logic from source) loads without it.
"""

import numpy as np
import slicer

MATPLOTLIB_REQUIREMENT = "matplotlib>=3.10"

#: Tag of the GPA plot view in layout descriptions.
VIEW_TAG = "gpaplotview"

#: Layout that GPA switches to when a plot is shown and the view is not in the layout.
GPA_LAYOUT_ID = 500

# The plot shown in the view. Matplotlib keeps only weak references to bound-method
# callbacks, so the plot object must be kept alive for hover and drag to work.
_currentPlot = None


def ensureMatplotlib():
    """Install matplotlib into Slicer's Python if it is missing or too old."""
    slicer.packaging.pip_ensure(MATPLOTLIB_REQUIREMENT, requester="GPA")


def layoutElement():
    """Return the layout description element of the GPA plot view."""
    return f"<{VIEW_TAG}></{VIEW_TAG}>"


def registerView():
    """Make the GPA plot view usable in layout descriptions.

    Must be called before switching to a layout that contains :func:`layoutElement`.
    """
    import InteractiveMatplotlibLib.view as view
    return view.registerLayoutView(VIEW_TAG)


def isViewInLayout():
    layoutNode = slicer.app.layoutManager().layoutLogic().GetLayoutNode()
    description = layoutNode.GetCurrentLayoutDescription() or ""
    return f"<{VIEW_TAG}" in description


def currentPlot():
    """Return the plot shown in the GPA plot view, or None."""
    return _currentPlot


def clear():
    """Remove the plot from the GPA plot view."""
    global _currentPlot
    if _currentPlot is not None:
        _currentPlot.disableDrive()
    _currentPlot = None
    import InteractiveMatplotlibLib.view as view
    widget = view.viewWidget(VIEW_TAG)
    if widget is not None:
        widget.setFigure(None)


def _show(plot):
    """Show ``plot.figure`` in the GPA plot view and return its canvas."""
    global _currentPlot
    import InteractiveMatplotlibLib.view as view
    if _currentPlot is not None:
        _currentPlot.disableDrive()
    registerView()
    if not isViewInLayout():
        slicer.app.layoutManager().setLayout(GPA_LAYOUT_ID)
    canvas = view.showFigure(plot.figure, VIEW_TAG)
    _currentPlot = plot
    return canvas


def _pcLabel(index, variancePercent):
    label = f"PC{index + 1}"
    if variancePercent is not None and index < len(variancePercent):
        label += f" ({variancePercent[index]:.1f}%)"
    return label


class _HoverLabel:
    """Annotation that names the specimen under the mouse."""

    def __init__(self, ax):
        self.ax = ax
        self.annotation = ax.annotate(
            "", xy=(0, 0), xytext=(8, 8), textcoords="offset points",
            fontsize="small", bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.9),
            zorder=10)
        self.annotation.set_visible(False)
        self.text = None

    def show(self, xy, text):
        if text == self.text:
            return False
        self.annotation.xy = xy
        self.annotation.set_text(text)
        self.annotation.set_visible(True)
        self.text = text
        return True

    def hide(self):
        if self.text is None:
            return False
        self.annotation.set_visible(False)
        self.text = None
        return True


class ProcrustesDistancePlot:
    """Bar chart of the Procrustes distance of each specimen to the mean shape."""

    def __init__(self, ids, distances):
        from matplotlib.figure import Figure

        self.ids = list(ids)
        self.distances = np.asarray(distances, dtype=float)
        self.figure = Figure(constrained_layout=True)
        self.ax = self.figure.add_subplot()
        positions = np.arange(len(self.distances))
        self.ax.bar(positions, self.distances, width=0.8, color="tab:blue")
        self.ax.set_title("Procrustes Distances")
        self.ax.set_xlabel("Subjects")
        self.ax.set_ylabel("Distance")
        self.ax.set_xlim(-1, len(self.distances))
        if len(self.ids) <= 30:
            self.ax.set_xticks(positions, self.ids, rotation=60, ha="right", fontsize="small")
        self.ax.grid(True, axis="y", alpha=0.3)
        self.hover = _HoverLabel(self.ax)
        self.canvas = _show(self)
        self.canvas.mpl_connect("motion_notify_event", self._onMotion)

    def disableDrive(self):
        pass

    def _onMotion(self, event):
        changed = False
        if event.inaxes is self.ax and event.xdata is not None:
            index = int(round(event.xdata))
            if 0 <= index < len(self.distances) and 0 <= event.ydata <= self.distances[index]:
                changed = self.hover.show(
                    (index, self.distances[index]),
                    f"{self.ids[index]}\n{self.distances[index]:.4g}")
            else:
                changed = self.hover.hide()
        else:
            changed = self.hover.hide()
        if changed:
            self.canvas.draw_idle()


class PCAScatterPlot:
    """Scatter plot of two PC scores, optionally colored by a factor.

    The axes have equal scale, so one unit of PC score spans the same length on
    both. With :meth:`enableDrive`, dragging with the left mouse button reports
    the PC scores under the mouse, which GPA uses to warp the 3D model.
    """

    def __init__(self, scores, ids, xIndex, yIndex, variancePercent=None,
                 groups=None, groupColors=None, groupTitle=None):
        from matplotlib.figure import Figure

        self.scores = np.asarray(scores, dtype=float)
        self.ids = list(ids)
        self.xIndex = xIndex
        self.yIndex = yIndex
        self.figure = Figure(constrained_layout=True)
        self.ax = self.figure.add_subplot()
        ax = self.ax

        xy = self.scores[:, [xIndex, yIndex]]
        # Symmetric, equal range on both axes so (0,0) is centered. This is also
        # the range that plot-drive scores are clamped to.
        self.limit = 1.05 * float(np.max(np.abs(xy))) if xy.size else 1.0
        if not np.isfinite(self.limit) or self.limit <= 0:
            self.limit = 1.0

        ax.axhline(0, color="0.8", linewidth=0.8, zorder=0)
        ax.axvline(0, color="0.8", linewidth=0.8, zorder=0)
        # (artist, row indices into scores) for hover lookup
        self._series = []
        if groups is None:
            artist = ax.scatter(xy[:, 0], xy[:, 1], s=20, color=(0.12, 0.47, 0.71))
            self._series.append((artist, np.arange(len(xy))))
            ax.set_title("PCA Scatter Plot")
        else:
            groups = np.asarray(groups)
            for groupIndex, group in enumerate(np.unique(groups)):
                rows = np.flatnonzero(groups == group)
                color = groupColors[groupIndex] if groupColors is not None else None
                artist = ax.scatter(xy[rows, 0], xy[rows, 1], s=20, color=color, label=str(group))
                self._series.append((artist, rows))
            ax.legend(title=groupTitle, fontsize="small", title_fontsize="small",
                      loc="best", framealpha=0.8)
            ax.set_title("PCA Scatter Plot with factors")
        ax.set_xlabel(_pcLabel(xIndex, variancePercent))
        ax.set_ylabel(_pcLabel(yIndex, variancePercent))
        ax.set_xlim(-self.limit, self.limit)
        ax.set_ylim(-self.limit, self.limit)
        # Square axes box: equal scale while keeping the symmetric limits above.
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.3)

        self.hover = _HoverLabel(ax)
        # Drive cursor: an animated artist, redrawn by blitting while dragging.
        self.cursor, = ax.plot([0.0], [0.0], marker="+", markersize=22, markeredgewidth=2,
                               color="black", animated=True, visible=False, zorder=11)
        self.cursorXY = (0.0, 0.0)
        self._background = None
        self._driveCallback = None
        self._dragging = False
        self._driveConnections = []

        self.canvas = _show(self)
        self.canvas.mpl_connect("draw_event", self._onDraw)
        self.canvas.mpl_connect("motion_notify_event", self._onHover)

    # -- hover ----------------------------------------------------------------
    def _onHover(self, event):
        if self._dragging:
            return
        changed = False
        found = None
        if event.inaxes is self.ax:
            for artist, rows in self._series:
                contains, info = artist.contains(event)
                if contains:
                    found = [rows[i] for i in info["ind"]]
                    break
        if found:
            names = [self.ids[i] for i in found[:5]]
            if len(found) > 5:
                names.append(f"(+{len(found) - 5} more)")
            first = found[0]
            changed = self.hover.show(
                (self.scores[first, self.xIndex], self.scores[first, self.yIndex]), "\n".join(names))
        else:
            changed = self.hover.hide()
        if changed:
            self.canvas.draw_idle()

    # -- drive ----------------------------------------------------------------
    def enableDrive(self, callback):
        """Report the PC scores under the mouse to ``callback(x, y)`` while dragging.

        Shift keeps the Y score and Ctrl (Cmd on macOS) keeps the X score of the
        cursor, to move along one PC only.
        """
        self.disableDrive()
        self._driveCallback = callback
        self._driveConnections = [
            self.canvas.mpl_connect("button_press_event", self._onPress),
            self.canvas.mpl_connect("motion_notify_event", self._onDrag),
            self.canvas.mpl_connect("button_release_event", self._onRelease),
        ]
        self.cursor.set_visible(True)
        self.canvas.draw_idle()

    def disableDrive(self):
        for cid in self._driveConnections:
            self.canvas.mpl_disconnect(cid)
        self._driveConnections = []
        self._driveCallback = None
        self._dragging = False
        if self.cursor.get_visible():
            self.cursor.set_visible(False)
            self.canvas.draw_idle()

    def isDriveEnabled(self):
        return self._driveCallback is not None

    def setCursor(self, x, y):
        """Move the drive cursor to the PC scores ``(x, y)``."""
        self.cursorXY = (float(x), float(y))
        self.cursor.set_data([self.cursorXY[0]], [self.cursorXY[1]])
        if not self.cursor.get_visible():
            return
        if self._background is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self._background)
        self.ax.draw_artist(self.cursor)
        self.canvas.blit(self.figure.bbox)

    def _onDraw(self, event):
        # Cache the figure without the cursor, then draw the cursor on top.
        self._background = self.canvas.copy_from_bbox(self.figure.bbox)
        if self.cursor.get_visible():
            self.ax.draw_artist(self.cursor)

    def _navigationActive(self):
        toolbar = getattr(self.canvas, "toolbar", None)
        return toolbar is not None and bool(toolbar.mode.value)

    def _onPress(self, event):
        if event.button != 1 or event.inaxes is not self.ax or self._navigationActive():
            return
        self._dragging = True
        if self.hover.hide():
            self.canvas.draw_idle()
        self._drive(event)

    def _onDrag(self, event):
        if self._dragging:
            self._drive(event)

    def _onRelease(self, event):
        if self._dragging and event.button == 1:
            self._drive(event)
            self._dragging = False

    def _drive(self, event):
        # Data coordinates also outside the axes, so dragging past the edge clamps.
        x, y = self.ax.transData.inverted().transform((event.x, event.y))
        x = min(max(float(x), -self.limit), self.limit)
        y = min(max(float(y), -self.limit), self.limit)
        modifiers = getattr(event, "modifiers", ()) or ()
        if "shift" in modifiers:
            y = self.cursorXY[1]
        if "ctrl" in modifiers:
            x = self.cursorXY[0]
        if self._driveCallback is not None:
            self._driveCallback(x, y)
