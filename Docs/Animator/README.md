## Animator

**Summary:** Animator makes keyframe animations of the 3D view and exports them as video (MP4) or animated GIF. You set up the scene at a few moments in time and capture each as a *snapshot*. Animator interpolates between the snapshots and records every frame. It uses the Sequences and Screen Capture modules, and the viewer-size controls of the HiResScreenCapture module (part of SlicerMorph).

A snapshot records:

- the camera (position, focal point, view-up, view angle or parallel scale);
- the volume rendering property (opacity and color transfer functions);
- the cropping ROI of the volume rendering;
- the visibility and opacity of models, segmentations, markups, volume renderings and folders.

### Requirements

Video export needs **ffmpeg**. On Windows, Slicer offers to download it on the first export. On macOS and Linux, install it (e.g. `brew install ffmpeg`, `sudo apt install ffmpeg`) and set its path in **Screen Capture → Advanced → ffmpeg executable**. See [Setting up ffmpeg](https://slicer.readthedocs.io/en/latest/user_guide/modules/screencapture.html#setting-up-ffmpeg).

### Panels

#### Output Viewer Setup

What is shown in the 3D viewer is what gets recorded, so the viewer is set to the output size before the animation is built.

- **3D Viewer**, **Undock 3D Viewer** / **Redock 3D Viewer:** move the chosen 3D view into its own window and back. Redocking releases the size lock.
- **Viewer Size:** typing a width or height locks the window at exactly that size (use even numbers). **↺** unlocks it.
- **Snap to codec-safe size:** after resizing the undocked window by dragging, proposes the nearest size with both dimensions a multiple of 16 (preferred by H.264), shows the aspect-ratio change, and locks the window on confirmation.

#### Animation Parameters

- **Animation Node:** create or select an animation. An animation and its snapshots are saved with the scene.
- **Create Snapshot Timeline:** adds the Scene Snapshot action to the animation and opens its editor. The editor is non-modal, so the 3D view and other modules stay usable. Reopen it with **Edit** under **Actions**.

#### Snapshot editor

- **Timeline span:** length of the animation in seconds (default 5 s).
- **Timeline:** one thumbnail per keyframe. Drag a thumbnail to change its time; right-click to copy, paste or delete a keyframe.
- **Time:** scrubs through the animation and shows the scene at that time.
- **Capture current state → new keyframe:** snapshots the scene. The first keyframe is placed at 0 s, the second at the end of the timeline, later ones halfway between the last keyframe and the end.
- **Replace selected from current state:** re-captures the selected keyframe and keeps its time, label and settings.
- For the selected keyframe:
  - **Label**, **Time**.
  - **After this:** what happens until the next keyframe. **Interpolate to next** (default) blends the camera, volume property, ROI and opacities. **Hold until next** keeps the state. **Explode models to next** / **Implode models to next** move the models in **Models folder** away from (or back to) their common center, by **Explode magnitude** times their distance from it, with ease-in/ease-out.
  - **Camera path:** **Orbit** rotates around the focal point (spherical interpolation); **Linear** moves the camera along a straight line.
- **Advanced (camera / volume property):** the camera and volume property node that are animated. They are selected automatically from the 3D view and the volume rendering.

To animate a crop, enable **Crop** in the Volume Rendering module and adjust its ROI before capturing. If the volume rendering has no ROI, Animator creates one sized to the volume on the first capture.

#### Export

- **Animation size:** the locked viewer size.
- **Video format:** H.264, H.264 (high-quality), MPEG-4, MPEG-4 (high-quality), Animated GIF, Animated GIF (grayscale).
- **Output file:** the file name; the extension is added from the format.
- **Export:** captures every frame (60 frames per second of animation) and encodes the video with ffmpeg.

### Tutorial

See the [Animator tutorial](https://github.com/SlicerMorph/Tutorials/tree/main/Animator).
