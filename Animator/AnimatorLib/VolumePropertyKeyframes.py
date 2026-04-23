"""
Helpers for the keyframe-based VolumePropertyAction.

A keyframe is a dict::

    {'time': float in [0.0, 1.0],   # fractional position in the action window
     'volumePropertyID': str}        # MRML node ID of a vtkMRMLVolumePropertyNode

A VolumePropertyAction stores an ordered list of keyframes. The first
keyframe must be at time 0.0 and the last at time 1.0; intermediate
keyframes are user-added.

Interpolation between any two adjacent keyframes resamples both
transfer functions onto the union of their control-point positions, so
the two source VolumeProperty nodes do NOT need to share the same
number of control points.
"""

import logging
import slicer


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------

def migrate_legacy_action(action):
    """If the action dict uses the old start/end VP schema, rewrite it
    in place to the keyframe schema. Idempotent.
    """
    if 'keyframes' in action:
        return action
    start_id = action.pop('startVolumePropertyID', None)
    end_id = action.pop('endVolumePropertyID', None)
    action.pop('clampAtStart', None)
    action.pop('clampAtEnd', None)
    keyframes = []
    if start_id:
        keyframes.append({'time': 0.0, 'volumePropertyID': start_id})
    if end_id:
        keyframes.append({'time': 1.0, 'volumePropertyID': end_id})
    action['keyframes'] = keyframes
    return action


# ---------------------------------------------------------------------------
# Keyframe lookup
# ---------------------------------------------------------------------------

def find_bracket(keyframes, fraction):
    """Return (kf_before, kf_after, local_fraction) for ``fraction`` in [0,1].

    If ``fraction`` is outside the range covered by the keyframes, the
    nearest endpoint keyframe is returned twice with local_fraction = 0.

    Returns (None, None, 0.0) if there are zero keyframes.
    """
    if not keyframes:
        return (None, None, 0.0)
    sorted_kfs = sorted(keyframes, key=lambda k: k['time'])
    if fraction <= sorted_kfs[0]['time']:
        return (sorted_kfs[0], sorted_kfs[0], 0.0)
    if fraction >= sorted_kfs[-1]['time']:
        return (sorted_kfs[-1], sorted_kfs[-1], 0.0)
    for i in range(len(sorted_kfs) - 1):
        a, b = sorted_kfs[i], sorted_kfs[i + 1]
        if a['time'] <= fraction <= b['time']:
            span = b['time'] - a['time']
            local = 0.0 if span <= 0 else (fraction - a['time']) / span
            return (a, b, local)
    return (sorted_kfs[-1], sorted_kfs[-1], 0.0)


# ---------------------------------------------------------------------------
# Resampling-based interpolation
# ---------------------------------------------------------------------------

def _node_positions(piecewise_or_color):
    """Return sorted list of x positions of the function's control points."""
    n = piecewise_or_color.GetSize()
    # opacity stores 4 floats per node (x, y, midpoint, sharpness)
    # color stores 6 floats per node (x, r, g, b, midpoint, sharpness)
    sample = [0.0] * 6
    positions = []
    for i in range(n):
        piecewise_or_color.GetNodeValue(i, sample)
        positions.append(sample[0])
    return sorted(positions)


def _union_positions(fn_a, fn_b):
    """Sorted union of control-point positions, deduplicated to ~1e-9."""
    merged = sorted(set(_node_positions(fn_a) + _node_positions(fn_b)))
    out = []
    for x in merged:
        if not out or abs(x - out[-1]) > 1e-9:
            out.append(x)
    return out


def _interpolate_opacity(opacity_a, opacity_b, opacity_out, fraction):
    """Resample opacity functions onto union of x positions, then interpolate."""
    xs = _union_positions(opacity_a, opacity_b)
    opacity_out.RemoveAllPoints()
    for x in xs:
        ya = opacity_a.GetValue(x)
        yb = opacity_b.GetValue(x)
        opacity_out.AddPoint(x, ya + fraction * (yb - ya))


def _interpolate_color(color_a, color_b, color_out, fraction):
    """Resample color transfer functions onto union of x positions."""
    xs = _union_positions(color_a, color_b)
    color_out.RemoveAllPoints()
    rgb_a = [0.0, 0.0, 0.0]
    rgb_b = [0.0, 0.0, 0.0]
    for x in xs:
        color_a.GetColor(x, rgb_a)
        color_b.GetColor(x, rgb_b)
        r = rgb_a[0] + fraction * (rgb_b[0] - rgb_a[0])
        g = rgb_a[1] + fraction * (rgb_b[1] - rgb_a[1])
        b = rgb_a[2] + fraction * (rgb_b[2] - rgb_a[2])
        color_out.AddRGBPoint(x, r, g, b)


def interpolate_volume_properties(vp_a, vp_b, fraction, animated_vp):
    """Write the interpolated state into ``animated_vp``.

    Safe to call when vp_a and vp_b have different numbers of control points
    or different x positions on their transfer functions.
    """
    disabled = animated_vp.StartModify()
    try:
        animated_vp.CopyParameterSet(vp_a)
        if fraction <= 0.0:
            return
        if fraction >= 1.0:
            animated_vp.CopyParameterSet(vp_b)
            return
        _interpolate_opacity(
            vp_a.GetScalarOpacity(),
            vp_b.GetScalarOpacity(),
            animated_vp.GetScalarOpacity(),
            fraction,
        )
        _interpolate_color(
            vp_a.GetColor(),
            vp_b.GetColor(),
            animated_vp.GetColor(),
            fraction,
        )
    finally:
        animated_vp.EndModify(disabled)


# ---------------------------------------------------------------------------
# Keyframe VolumeProperty node helpers
# ---------------------------------------------------------------------------

def snapshot_volume_property(source_vp, name):
    """Create a new vtkMRMLVolumePropertyNode that is a copy of ``source_vp``.

    Returns the new node.
    """
    new_vp = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVolumePropertyNode')
    new_vp.SetName(slicer.mrmlScene.GetUniqueNameByString(name))
    new_vp.CopyParameterSet(source_vp)
    return new_vp


def keyframe_node_name(action_id, fraction, label=None):
    """Return a human-readable name for a keyframe VP node."""
    short = action_id.split('-')[0] if action_id else 'anim'
    pct = int(round(fraction * 100))
    if label:
        return f"AnimKey_{short}_{pct:03d}_{label}"
    return f"AnimKey_{short}_{pct:03d}"
