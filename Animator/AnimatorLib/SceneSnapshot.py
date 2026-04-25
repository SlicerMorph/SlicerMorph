"""
Helpers for SceneSnapshotAction: camera + volume-property snapshot
keyframes with linear interpolation and per-segment interpolate/hold
behavior.

A keyframe is::

    {
      'id': str,                       # uuid (stable across renames)
      'time': float,                   # absolute seconds in master timeline
      'label': str,                    # user-facing name
      'cameraState': {
          'position': [x, y, z],
          'focalPoint': [x, y, z],
          'viewUp': [x, y, z],
          'viewAngle': float,
          'parallelScale': float,
          'parallelProjection': int (0/1),
      } or None,
      'volumePropertyID': str or None, # MRML ID of a snapshot VP node
      'roiState': {                    # cropping ROI snapshot (or None)
          'xyz': [x, y, z],
          'radiusXYZ': [rx, ry, rz],
      } or None,
      'segmentMode': 'interpolate' | 'hold',  # mode of the segment
                                              # starting AT this keyframe
                                              # (ignored on the last keyframe)
      'thumbnailPath': str or None,   # path to a PNG on disk
    }
"""

import math
import os
import tempfile
import uuid

import vtk
import slicer

# Keep VP interpolation in one place.
from AnimatorLib.VolumePropertyKeyframes import (
    interpolate_volume_properties,
    snapshot_volume_property,
)


# ---------------------------------------------------------------------------
# Camera capture / restore / interpolation
# ---------------------------------------------------------------------------

def capture_camera_state(camera_node):
    """Return a dict snapshot of a vtkMRMLCameraNode."""
    cam = camera_node.GetCamera()
    return {
        'position': list(cam.GetPosition()),
        'focalPoint': list(cam.GetFocalPoint()),
        'viewUp': list(cam.GetViewUp()),
        'viewAngle': cam.GetViewAngle(),
        'parallelScale': cam.GetParallelScale(),
        'parallelProjection': int(cam.GetParallelProjection()),
    }


def apply_camera_state(camera_node, state):
    """Apply a previously captured state dict to a vtkMRMLCameraNode."""
    if state is None:
        return
    cam = camera_node.GetCamera()
    cam.SetPosition(*state['position'])
    cam.SetFocalPoint(*state['focalPoint'])
    cam.SetViewUp(*state['viewUp'])
    cam.SetViewAngle(state['viewAngle'])
    cam.SetParallelScale(state['parallelScale'])
    cam.SetParallelProjection(int(state['parallelProjection']))
    cam.OrthogonalizeViewUp()
    camera_node.Modified()
    # When the camera moves between snapshots VTK does not auto-update the
    # near/far clipping range, so volumes can get sliced off as the view
    # interpolates. Reset the clipping range on every 3D view whose active
    # camera matches this node.
    _reset_clipping_range_for_camera(cam)


def _reset_clipping_range_for_camera(vtk_camera):
    try:
        lm = slicer.app.layoutManager()
        if lm is None:
            return
        for i in range(lm.threeDViewCount):
            view = lm.threeDWidget(i).threeDView()
            renderer = view.renderWindow().GetRenderers().GetFirstRenderer()
            if renderer is None:
                continue
            if renderer.GetActiveCamera() is vtk_camera:
                renderer.ResetCameraClippingRange()
    except Exception:
        pass


def _lerp_vec(a, b, t):
    return [a[i] + t * (b[i] - a[i]) for i in range(len(a))]


def _normalize(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        return list(v)
    return [c / n for c in v]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(len(a)))


def _pick_perpendicular(u, hint=None):
    """Return a unit vector perpendicular to unit vector ``u``.

    If ``hint`` is provided and not parallel to ``u``, the result lies
    in the plane spanned by (u, hint) — useful as a tangent direction
    for great-circle interpolation when slerp endpoints are
    antiparallel (slerp itself is then undefined).
    """
    if hint is not None:
        h = hint
        # Project hint onto plane perpendicular to u: h - (h·u) u
        d = _dot(h, u)
        perp = [h[i] - d * u[i] for i in range(3)]
        n = math.sqrt(_dot(perp, perp))
        if n > 1e-6:
            return [perp[i] / n for i in range(3)]
    # Fall back to whichever world axis is least parallel to u.
    ax = min(range(3), key=lambda i: abs(u[i]))
    axis = [0.0, 0.0, 0.0]
    axis[ax] = 1.0
    d = _dot(axis, u)
    perp = [axis[i] - d * u[i] for i in range(3)]
    n = math.sqrt(_dot(perp, perp))
    return [perp[i] / n for i in range(3)]


def _slerp_unit(u, v, t, tangent_hint=None):
    """Spherical linear interpolation between two unit 3-vectors.

    For nearly-parallel vectors, falls back to a normalized lerp
    (slerp degenerates numerically). For nearly-antiparallel vectors
    slerp has no unique great circle, so a perpendicular tangent is
    chosen via ``tangent_hint`` (or an arbitrary world axis) and the
    arc is swept through it as a true 180° rotation.
    """
    if u is None or v is None:
        return u or v
    d = max(-1.0, min(1.0, _dot(u, v)))
    # Nearly parallel: lerp + renormalize is numerically fine.
    if d > 0.9995:
        return _normalize(_lerp_vec(u, v, t))
    # Nearly antiparallel: build a great-circle arc using a
    # perpendicular tangent direction so the swing is a true 180°
    # rotation rather than a (degenerate) straight line through
    # the origin.
    if d < -0.9995:
        axis = _pick_perpendicular(u, hint=tangent_hint)
        ang = math.pi * t
        c, s = math.cos(ang), math.sin(ang)
        return [c * u[i] + s * axis[i] for i in range(3)]
    theta = math.acos(d)
    sin_theta = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta
    return [a * u[i] + b * v[i] for i in range(3)]


def _orbit_camera_position(focal, pos_a, pos_b, t, view_up_hint=None):
    """Slerp the camera position around the focal point on a sphere whose
    radius linearly interpolates between |pos_a-focal| and |pos_b-focal|.

    This produces constant-angular-speed rotation with no chord-induced
    dolly toward the focal point (the artifact you get from a plain
    position lerp when two viewpoints sit on a common sphere).

    When the two camera-from-focal directions are nearly antiparallel
    (e.g. front view -> back view of the same object), ``view_up_hint``
    is used to pick the great-circle plane so the orbit sweeps through
    a sensible side view instead of degenerating.
    """
    va = [pos_a[i] - focal[i] for i in range(3)]
    vb = [pos_b[i] - focal[i] for i in range(3)]
    ra = math.sqrt(_dot(va, va))
    rb = math.sqrt(_dot(vb, vb))
    if ra < 1e-9 or rb < 1e-9:
        # Degenerate: camera at focal point. Fall back to plain lerp.
        return _lerp_vec(pos_a, pos_b, t)
    ua = [va[i] / ra for i in range(3)]
    ub = [vb[i] / rb for i in range(3)]
    # For an antiparallel front->back swing, slerping past viewUp gives
    # a top-down arc; slerping past (viewUp x ua) gives a side arc.
    # The side arc is the more visually expected "turntable" behavior,
    # so prefer the perpendicular-to-viewUp axis as the tangent hint.
    tangent = None
    if view_up_hint is not None:
        # cross(ua, viewUp) lies in the orbit plane perpendicular to
        # viewUp -- a horizontal swing if viewUp is world up.
        vx = [
            ua[1] * view_up_hint[2] - ua[2] * view_up_hint[1],
            ua[2] * view_up_hint[0] - ua[0] * view_up_hint[2],
            ua[0] * view_up_hint[1] - ua[1] * view_up_hint[0],
        ]
        n = math.sqrt(_dot(vx, vx))
        if n > 1e-6:
            tangent = [vx[i] / n for i in range(3)]
    u = _slerp_unit(ua, ub, t, tangent_hint=tangent)
    r = ra + t * (rb - ra)
    return [focal[i] + r * u[i] for i in range(3)]


def interpolate_camera_state(state_a, state_b, fraction, mode='orbit'):
    """Interpolate two camera states.

    ``mode='orbit'`` (default): slerp the camera position around the
    focal point on a sphere, slerp viewUp on the unit sphere. Constant
    angular speed, no apparent dolly-in at the segment midpoint. Best
    for orbiting / turntable-style animations.

    ``mode='linear'``: legacy chord-lerp behavior — straight-line lerp
    of position and focalPoint in 3D space. Cheaper and gives a
    smoother fly-through when the viewpoints are *not* on a common
    sphere around the focal point, but introduces a midpoint dolly
    when two viewpoints share a focal point.
    """
    if state_a is None or state_b is None:
        return state_a or state_b
    focal = _lerp_vec(state_a['focalPoint'], state_b['focalPoint'], fraction)
    if mode == 'orbit':
        # Use the *interpolated* focal point as the orbit center. When
        # focalPoint is identical in both keyframes (the typical
        # turntable case) this is exactly the shared focal point; when
        # it varies, the orbit gradually shifts with it.
        # Pass viewUp as the antiparallel-tangent hint so a front<->back
        # swing orbits horizontally rather than degenerating.
        position = _orbit_camera_position(
            focal, state_a['position'], state_b['position'], fraction,
            view_up_hint=_normalize(state_a['viewUp']))
        view_up = _slerp_unit(
            _normalize(state_a['viewUp']),
            _normalize(state_b['viewUp']),
            fraction)
    else:  # 'linear'
        position = _lerp_vec(state_a['position'], state_b['position'], fraction)
        view_up = _normalize(_lerp_vec(
            state_a['viewUp'], state_b['viewUp'], fraction))
    return {
        'position': position,
        'focalPoint': focal,
        'viewUp': view_up,
        'viewAngle': state_a['viewAngle'] + fraction * (state_b['viewAngle'] - state_a['viewAngle']),
        'parallelScale': state_a['parallelScale']
            + fraction * (state_b['parallelScale'] - state_a['parallelScale']),
        'parallelProjection': state_a['parallelProjection'],
    }


# ---------------------------------------------------------------------------
# Cropping ROI capture / restore / interpolation
# ---------------------------------------------------------------------------

def capture_roi_state(roi_node):
    """Return a dict snapshot of a vtkMRMLMarkupsROINode (or annotation ROI)."""
    if roi_node is None:
        return None
    xyz = [0.0, 0.0, 0.0]
    radius = [0.0, 0.0, 0.0]
    roi_node.GetXYZ(xyz)
    roi_node.GetRadiusXYZ(radius)
    return {
        'xyz': list(xyz),
        'radiusXYZ': list(radius),
    }


def apply_roi_state(roi_node, state):
    """Apply a previously captured ROI state dict to an ROI node."""
    if state is None or roi_node is None:
        return
    roi_node.SetXYZ(*state['xyz'])
    roi_node.SetRadiusXYZ(*state['radiusXYZ'])


def interpolate_roi_state(state_a, state_b, fraction):
    """Linearly interpolate two ROI states (center + radii)."""
    if state_a is None or state_b is None:
        return state_a or state_b
    return {
        'xyz': _lerp_vec(state_a['xyz'], state_b['xyz'], fraction),
        'radiusXYZ': _lerp_vec(state_a['radiusXYZ'], state_b['radiusXYZ'], fraction),
    }


_AUTO_ROI_ATTR = 'Animator.autoCreatedFor'


def _find_volume_rendering_node():
    """Best-effort: return the first VolumeRendering display node in the scene."""
    node = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    if node is not None:
        return node
    # Fallback: any volume rendering display node.
    nodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLVolumeRenderingDisplayNode')
    if nodes and nodes.GetNumberOfItems() > 0:
        return nodes.GetItemAsObject(0)
    return None


def _volume_full_bounds_roi(volume_rendering_node):
    """Compute (center, radii) covering the rendered volume's RAS bounds.
    Returns None if no volume is associated."""
    if volume_rendering_node is None:
        return None
    try:
        volume_node = volume_rendering_node.GetVolumeNode()
    except Exception:
        volume_node = None
    if volume_node is None:
        return None
    bounds = [0.0] * 6
    volume_node.GetRASBounds(bounds)
    center = [(bounds[0] + bounds[1]) / 2.0,
              (bounds[2] + bounds[3]) / 2.0,
              (bounds[4] + bounds[5]) / 2.0]
    radii = [(bounds[1] - bounds[0]) / 2.0,
             (bounds[3] - bounds[2]) / 2.0,
             (bounds[5] - bounds[4]) / 2.0]
    # Guard against zero-size volumes.
    radii = [max(r, 0.5) for r in radii]
    return center, radii


def ensure_animated_roi(action):
    """Guarantee that ``action`` has an animated cropping ROI.

    - If ``action['animatedROIID']`` already resolves, returns that node.
    - Otherwise, adopt the volume rendering's existing ROI if any.
    - Otherwise, create a hidden vtkMRMLMarkupsROINode sized to the
      volume's RAS bounds, assign it as the volume rendering's ROI,
      enable cropping, and tag it so we can clean it up later.
    - Backfills any keyframe whose ``roiState`` is None with the current
      ROI state so playback has a defined baseline.

    Returns the ROI node (or None if no volume rendering / volume found).
    """
    existing_id = action.get('animatedROIID')
    roi_node = slicer.mrmlScene.GetNodeByID(existing_id) if existing_id else None

    if roi_node is None:
        vr_node = _find_volume_rendering_node()
        if vr_node is None:
            return None
        # Adopt existing ROI on the volume rendering, if any.
        try:
            roi_node = vr_node.GetMarkupsROINode()
        except Exception:
            roi_node = None
        if roi_node is None:
            # Create a new hidden ROI sized to the volume's bounds.
            bounds = _volume_full_bounds_roi(vr_node)
            if bounds is None:
                return None
            center, radii = bounds
            roi_node = slicer.mrmlScene.AddNewNodeByClass(
                'vtkMRMLMarkupsROINode',
                'AnimatorSnapshotROI')
            roi_node.SetXYZ(*center)
            roi_node.SetRadiusXYZ(*radii)
            # Hide handles by default; do NOT touch visibility for
            # ROIs the user already had in the scene.
            for i in range(roi_node.GetNumberOfDisplayNodes()):
                disp = roi_node.GetNthDisplayNode(i)
                if disp is not None:
                    disp.SetVisibility(False)
            roi_node.SetAttribute(_AUTO_ROI_ATTR, action.get('id', ''))
            # Wire the new ROI to the volume rendering and turn cropping on.
            try:
                vr_node.SetAndObserveROINodeID(roi_node.GetID())
            except Exception:
                pass
        # Either way, make sure cropping is enabled so interpolation is visible.
        try:
            vr_node.SetCroppingEnabled(True)
        except Exception:
            pass
        action['animatedROIID'] = roi_node.GetID()

    # Backfill keyframes that have no roiState (e.g. legacy snapshots
    # captured before this action had an ROI). Using the current live
    # ROI ensures every keyframe has a baseline.
    seed = capture_roi_state(roi_node)
    if seed is not None:
        for kf in action.get('keyframes', []):
            if kf.get('roiState') is None:
                kf['roiState'] = {
                    'xyz': list(seed['xyz']),
                    'radiusXYZ': list(seed['radiusXYZ']),
                }
    return roi_node


def remove_auto_created_roi(action):
    """Remove the ROI node we auto-created for ``action`` (if any).
    Leaves user-supplied ROIs alone."""
    roi_id = action.get('animatedROIID')
    if not roi_id:
        return
    node = slicer.mrmlScene.GetNodeByID(roi_id)
    if node is None:
        return
    if node.GetAttribute(_AUTO_ROI_ATTR) == action.get('id', ''):
        slicer.mrmlScene.RemoveNode(node)


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def _thumbnails_dir():
    base = os.path.join(tempfile.gettempdir(), 'SlicerAnimatorSnapshots')
    os.makedirs(base, exist_ok=True)
    return base


def capture_thumbnail(threeDView, keyframe_id, max_dim=80):
    """Grab the current 3D view as a small PNG and return its path."""
    try:
        pixmap = threeDView.grab()
        w = pixmap.width()
        h = pixmap.height()
        if w <= 0 or h <= 0:
            return None
        scale = float(max_dim) / max(w, h)
        if scale < 1.0:
            from qt import Qt
            pixmap = pixmap.scaled(int(w * scale), int(h * scale),
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
        path = os.path.join(_thumbnails_dir(), f"{keyframe_id}.png")
        if not pixmap.save(path, "PNG"):
            return None
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Keyframe construction / lookup
# ---------------------------------------------------------------------------

def make_keyframe(time_seconds, label, camera_state, volume_property_id=None,
                  thumbnail_path=None, segment_mode='interpolate',
                  roi_state=None):
    return {
        'id': str(uuid.uuid4()),
        'time': float(time_seconds),
        'label': label,
        'cameraState': camera_state,
        'volumePropertyID': volume_property_id,
        'roiState': roi_state,
        'segmentMode': segment_mode,
        'thumbnailPath': thumbnail_path,
    }


def sorted_keyframes(keyframes):
    return sorted(keyframes, key=lambda k: k['time'])


def find_segment(keyframes, t):
    """Given absolute master-time t, return (kf_before, kf_after, local_fraction).

    If t is outside the keyframe range, return the nearest endpoint twice
    with local_fraction = 0. Returns (None, None, 0.0) if no keyframes.
    """
    if not keyframes:
        return (None, None, 0.0)
    kfs = sorted_keyframes(keyframes)
    if t <= kfs[0]['time']:
        return (kfs[0], kfs[0], 0.0)
    if t >= kfs[-1]['time']:
        return (kfs[-1], kfs[-1], 0.0)
    for i in range(len(kfs) - 1):
        a, b = kfs[i], kfs[i + 1]
        if a['time'] <= t <= b['time']:
            span = b['time'] - a['time']
            local = 0.0 if span <= 0 else (t - a['time']) / span
            return (a, b, local)
    return (kfs[-1], kfs[-1], 0.0)


# ---------------------------------------------------------------------------
# Per-frame evaluation
# ---------------------------------------------------------------------------

def evaluate_at(action, script_time):
    """Compute the camera state and (optionally) push the volume property
    update for ``action`` at ``script_time``. Returns the camera state to
    apply (or None) so the caller can write it to the animated camera.
    """
    keyframes = action.get('keyframes', [])
    if not keyframes:
        return None

    kf_a, kf_b, local = find_segment(keyframes, script_time)
    if kf_a is None:
        return None

    # Segment mode: 'hold' freezes at kf_a until kf_b is reached.
    mode = kf_a.get('segmentMode', 'interpolate')
    # Rotation mode: 'orbit' (slerp around focal, default) or 'linear'
    # (legacy chord-lerp). Stored on kf_a so it describes the segment
    # that *starts* at kf_a, matching segmentMode semantics.
    rot_mode = kf_a.get('rotationMode', 'orbit')
    if kf_a is kf_b:
        cam_state = kf_a.get('cameraState')
    elif mode == 'hold':
        cam_state = kf_a.get('cameraState')
    else:
        cam_state = interpolate_camera_state(
            kf_a.get('cameraState'),
            kf_b.get('cameraState'),
            local,
            mode=rot_mode,
        )

    # Volume property: only act if the action has an animated VP target
    animated_vp_id = action.get('animatedVolumePropertyID')
    if animated_vp_id:
        animated_vp = slicer.mrmlScene.GetNodeByID(animated_vp_id)
        if animated_vp is not None:
            vp_a_id = kf_a.get('volumePropertyID')
            vp_b_id = kf_b.get('volumePropertyID')
            vp_a = slicer.mrmlScene.GetNodeByID(vp_a_id) if vp_a_id else None
            vp_b = slicer.mrmlScene.GetNodeByID(vp_b_id) if vp_b_id else None
            if vp_a is not None and vp_b is not None:
                if kf_a is kf_b or mode == 'hold':
                    animated_vp.CopyParameterSet(vp_a)
                else:
                    interpolate_volume_properties(vp_a, vp_b, local, animated_vp)

    # Cropping ROI: only act if the action has an animated ROI target
    animated_roi_id = action.get('animatedROIID')
    if animated_roi_id:
        animated_roi = slicer.mrmlScene.GetNodeByID(animated_roi_id)
        if animated_roi is not None:
            roi_a = kf_a.get('roiState')
            roi_b = kf_b.get('roiState')
            if roi_a is not None and roi_b is not None:
                if kf_a is kf_b or mode == 'hold':
                    apply_roi_state(animated_roi, roi_a)
                else:
                    apply_roi_state(
                        animated_roi,
                        interpolate_roi_state(roi_a, roi_b, local),
                    )
            elif roi_a is not None:
                apply_roi_state(animated_roi, roi_a)

    return cam_state


# ---------------------------------------------------------------------------
# Capture helper
# ---------------------------------------------------------------------------

def capture_current_scene(animated_camera_id, animated_vp_id, action_id,
                          time_seconds, label, animated_roi_id=None):
    """Snapshot the current camera + (optional) volume property + (optional)
    cropping ROI state and return a new keyframe dict (without thumbnail;
    caller adds it).
    """
    cam_state = None
    if animated_camera_id:
        cam_node = slicer.mrmlScene.GetNodeByID(animated_camera_id)
        if cam_node is not None:
            cam_state = capture_camera_state(cam_node)

    vp_snapshot_id = None
    if animated_vp_id:
        vp_node = slicer.mrmlScene.GetNodeByID(animated_vp_id)
        if vp_node is not None:
            short = action_id.split('-')[0] if action_id else 'snap'
            name = f"AnimSnap_{short}_{int(round(time_seconds * 1000))}ms"
            vp_snapshot = snapshot_volume_property(vp_node, name)
            vp_snapshot_id = vp_snapshot.GetID()

    roi_state = None
    if animated_roi_id:
        roi_node = slicer.mrmlScene.GetNodeByID(animated_roi_id)
        if roi_node is not None:
            roi_state = capture_roi_state(roi_node)

    return make_keyframe(
        time_seconds=time_seconds,
        label=label,
        camera_state=cam_state,
        volume_property_id=vp_snapshot_id,
        roi_state=roi_state,
    )
