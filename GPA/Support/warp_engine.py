"""
Warp engine — grid-backed shape deformation visualization service.

Designed to replace the per-tab patchwork (PC tab grid + LR tab TPS rebuild +
duplicated landmark/transform nodes) with a single, fast, baseline-aware
shape-warp pipeline that any tab/backend can push into.

Key ideas
---------
- Baseline (p,3): the rest position of the shape. The displayed glyphs and
  model are snapped to baseline at neutral (slider==0). Default = Procrustes
  mean; LR uses model intercept-predicted shape; PC will use mean.
- Direction: a (p,3) displacement field at "full magnitude". A grid is built
  for each registered direction by sampling a TPS that maps baseline →
  baseline + vec*max_magnitude. Cached.
- Active direction + scale: the engine binds one direction at a time to its
  vtkMRMLGridTransformNode and uses SetDisplacementScale(scale/max_magnitude)
  for fast, per-tick updates (no TPS rebuild).

This prototype supports a single active direction. Multi-direction fusion
(e.g. 2-D PCA pad with PC1+PC2) can be added later by accumulating displacement
arrays from multiple grids — the public API leaves room for it.
"""

import numpy as np
import vtk
import slicer


__all__ = ["WarpEngine"]


def _np_to_vtk_points(arr):
  pts = vtk.vtkPoints()
  arr = np.asarray(arr, dtype=float)
  pts.SetNumberOfPoints(arr.shape[0])
  for i in range(arr.shape[0]):
    pts.SetPoint(i, float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2]))
  return pts


def _expanded_bounds(node, padding_factor=0.10):
  bounds = [0.0] * 6
  node.GetRASBounds(bounds)
  rx = bounds[1] - bounds[0]
  ry = bounds[3] - bounds[2]
  rz = bounds[5] - bounds[4]
  bounds[0] -= rx * padding_factor
  bounds[1] += rx * padding_factor
  bounds[2] -= ry * padding_factor
  bounds[3] += ry * padding_factor
  bounds[4] -= rz * padding_factor
  bounds[5] += rz * padding_factor
  eps = 1e-3
  if bounds[1] - bounds[0] < eps:
    bounds[1] = bounds[0] + eps
  if bounds[3] - bounds[2] < eps:
    bounds[3] = bounds[2] + eps
  if bounds[5] - bounds[4] < eps:
    bounds[5] = bounds[4] + eps
  return bounds


class WarpEngine:
  """Grid-backed shape warp engine. See module docstring."""

  def __init__(self, scene=None, name="WarpEngine", grid_dimension=50,
               padding_factor=0.10, log_fn=None):
    self.scene = scene if scene is not None else slicer.mrmlScene
    self.name = str(name)
    self.grid_dimension = int(grid_dimension)
    self.padding_factor = float(padding_factor)
    self._log_fn = log_fn

    self.baseline = None              # (p, 3) ndarray — rest positions
    self.baseline_label = "(none)"

    # name -> {"vec": (p,3), "max": float, "grid": vtkImageData|None}
    self.directions = {}
    self.active = None                # active direction name

    self.target_landmark_node = None
    self.target_model_node = None
    self.bounds_node = None           # used to size the grid
    self.transform_node = None        # vtkMRMLGridTransformNode

  # ---- logging shim --------------------------------------------------------

  def _log(self, msg):
    if self._log_fn is not None:
      try:
        self._log_fn(f"[WarpEngine/{self.name}] {msg}")
        return
      except Exception:
        pass
    print(f"[WarpEngine/{self.name}] {msg}")

  # ---- lifecycle -----------------------------------------------------------

  def _ensure_transform_node(self):
    n = self.transform_node
    if n is not None:
      try:
        if self.scene.IsNodePresent(n):
          return n
      except Exception:
        pass
    self.transform_node = self.scene.AddNewNodeByClass(
      "vtkMRMLGridTransformNode", f"{self.name}_GridTransform"
    )
    return self.transform_node

  def attach_targets(self, landmark_node=None, model_node=None, bounds_node=None):
    """Bind landmark + (optional) model node so they follow this engine's
    transform. `bounds_node` overrides the grid-bounds source; otherwise
    model_node is preferred, then landmark_node."""
    if landmark_node is not None:
      self.target_landmark_node = landmark_node
    if model_node is not None:
      self.target_model_node = model_node
    self.bounds_node = bounds_node or self.target_model_node or self.target_landmark_node
    node = self._ensure_transform_node()
    if self.target_landmark_node is not None:
      try:
        self.target_landmark_node.SetAndObserveTransformNodeID(node.GetID())
      except Exception as e:
        self._log(f"attach landmark: {e}")
    if self.target_model_node is not None:
      try:
        self.target_model_node.SetAndObserveTransformNodeID(node.GetID())
      except Exception as e:
        self._log(f"attach model: {e}")

  def detach_model(self):
    if self.target_model_node is not None:
      try:
        self.target_model_node.SetAndObserveTransformNodeID(None)
      except Exception:
        pass
    self.target_model_node = None

  def detach_targets(self):
    for n in (self.target_landmark_node, self.target_model_node):
      if n is None:
        continue
      try:
        n.SetAndObserveTransformNodeID(None)
      except Exception:
        pass
    self.target_landmark_node = None
    self.target_model_node = None

  def dispose(self):
    self.detach_targets()
    if self.transform_node is not None:
      try:
        if self.scene.IsNodePresent(self.transform_node):
          self.scene.RemoveNode(self.transform_node)
      except Exception:
        pass
    self.transform_node = None
    self.directions = {}
    self.active = None
    self.baseline = None

  # ---- baseline ------------------------------------------------------------

  def set_baseline(self, p3_array, label=None):
    """Set the rest-position landmarks. Invalidates all cached grids if shape
    or values changed. Caller is responsible for repopulating the bound
    landmark glyph node to match (the engine does not move control points)."""
    new = np.asarray(p3_array, dtype=float)
    if new.ndim != 2 or new.shape[1] != 3:
      raise ValueError(f"baseline must be (p,3), got {new.shape}")
    invalidate = (
      self.baseline is None
      or self.baseline.shape != new.shape
      or not np.allclose(self.baseline, new)
    )
    if invalidate:
      for d in self.directions.values():
        d["grid"] = None
    self.baseline = new
    if label is not None:
      self.baseline_label = str(label)

  def current_baseline_label(self):
    return self.baseline_label

  # ---- direction registry --------------------------------------------------

  def register_direction(self, name, vec_p3, max_magnitude=1.0):
    """Register a named displacement direction. `vec_p3` (p,3) is the
    displacement at full magnitude. Cached grids for the prior name (if any)
    are dropped."""
    v = np.asarray(vec_p3, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3:
      raise ValueError(f"vec must be (p,3), got {v.shape}")
    self.directions[str(name)] = {
      "vec": v,
      "max": float(max_magnitude) if max_magnitude else 1.0,
      "grid": None,
    }

  def clear_directions(self):
    self.directions = {}
    self.active = None

  def has_direction(self, name):
    return str(name) in self.directions

  # ---- active direction + scaling -----------------------------------------

  def set_active_direction(self, name):
    """Select which registered direction the slider drives. Builds the grid
    for that direction (cached) and binds it to the transform node. Resets
    scale to 0."""
    if name is None:
      self.active = None
      return
    name = str(name)
    if name not in self.directions:
      raise KeyError(f"Direction not registered: {name}")
    self.active = name
    self._ensure_grid_for(name)
    node = self._ensure_transform_node()
    grid = self.directions[name]["grid"]
    try:
      node.GetTransformFromParent().SetDisplacementGridData(grid)
    except Exception as e:
      self._log(f"set grid data: {e}")
    self.set_scale(0.0)

  def set_scale(self, value):
    """Apply scalar magnitude on the active direction. `value` is in the
    user-facing units assumed by `register_direction`'s max_magnitude."""
    if self.transform_node is None:
      return
    if self.active is None:
      try:
        self.transform_node.GetTransformFromParent().SetDisplacementScale(0.0)
        self.transform_node.Modified()
      except Exception:
        pass
      return
    d = self.directions[self.active]
    max_mag = d["max"] if d["max"] != 0 else 1.0
    sf = float(value) / max_mag
    try:
      self.transform_node.GetTransformFromParent().SetDisplacementScale(sf)
      self.transform_node.Modified()
    except Exception as e:
      self._log(f"set scale: {e}")

  def reset_scale(self):
    self.set_scale(0.0)

  # ---- grid construction ---------------------------------------------------

  def invalidate_grids(self):
    for d in self.directions.values():
      d["grid"] = None

  def _ensure_grid_for(self, name):
    d = self.directions[name]
    if d["grid"] is not None:
      return
    if self.baseline is None:
      raise RuntimeError("Cannot build grid: baseline not set")
    if self.bounds_node is None:
      raise RuntimeError("Cannot build grid: no bounds node attached")

    # Build TPS at full magnitude. Convention follows GPA.py:getGridTransform —
    # source/target are swapped because vtkTransformToGrid samples the inverse
    # of the supplied transform; the net effect of a forward warp.
    target = self.baseline + d["vec"] * d["max"]

    bounds = _expanded_bounds(self.bounds_node, self.padding_factor)
    origin = (bounds[0], bounds[2], bounds[4])
    size = (bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
    N = self.grid_dimension
    extent = [0, N - 1, 0, N - 1, 0, N - 1]
    spacing = (size[0] / N, size[1] / N, size[2] / N)

    # Parallel TPS->grid sampler (Z-slab thread pool, releases the GIL).
    from Support import vtk_lib as _vtk_lib
    d["grid"] = _vtk_lib.sampleTPSToDisplacementGrid(
      sourceLM=target,
      targetLM=self.baseline,
      origin=origin,
      spacing=spacing,
      extent=extent,
      basis="R",
    )
