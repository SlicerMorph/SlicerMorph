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


def _lerp_vec(a, b, t):
    return [a[i] + t * (b[i] - a[i]) for i in range(len(a))]


def _normalize(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        return list(v)
    return [c / n for c in v]


def interpolate_camera_state(state_a, state_b, fraction):
    """Linearly interpolate two camera states. View-up is renormalized.
    Boolean projection mode is held from state_a within the segment.
    """
    if state_a is None or state_b is None:
        return state_a or state_b
    return {
        'position': _lerp_vec(state_a['position'], state_b['position'], fraction),
        'focalPoint': _lerp_vec(state_a['focalPoint'], state_b['focalPoint'], fraction),
        'viewUp': _normalize(_lerp_vec(state_a['viewUp'], state_b['viewUp'], fraction)),
        'viewAngle': state_a['viewAngle'] + fraction * (state_b['viewAngle'] - state_a['viewAngle']),
        'parallelScale': state_a['parallelScale']
            + fraction * (state_b['parallelScale'] - state_a['parallelScale']),
        'parallelProjection': state_a['parallelProjection'],
    }


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def _thumbnails_dir():
    base = os.path.join(tempfile.gettempdir(), 'SlicerAnimatorSnapshots')
    os.makedirs(base, exist_ok=True)
    return base


def capture_thumbnail(threeDView, keyframe_id, max_dim=160):
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
                  thumbnail_path=None, segment_mode='interpolate'):
    return {
        'id': str(uuid.uuid4()),
        'time': float(time_seconds),
        'label': label,
        'cameraState': camera_state,
        'volumePropertyID': volume_property_id,
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
    if kf_a is kf_b:
        cam_state = kf_a.get('cameraState')
    elif mode == 'hold':
        cam_state = kf_a.get('cameraState')
    else:
        cam_state = interpolate_camera_state(
            kf_a.get('cameraState'),
            kf_b.get('cameraState'),
            local,
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

    return cam_state


# ---------------------------------------------------------------------------
# Capture helper
# ---------------------------------------------------------------------------

def capture_current_scene(animated_camera_id, animated_vp_id, action_id,
                          time_seconds, label):
    """Snapshot the current camera + (optional) volume property state and
    return a new keyframe dict (without thumbnail; caller adds it).
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

    return make_keyframe(
        time_seconds=time_seconds,
        label=label,
        camera_state=cam_state,
        volume_property_id=vp_snapshot_id,
    )
