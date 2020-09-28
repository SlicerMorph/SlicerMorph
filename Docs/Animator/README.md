## Animator
**Summary:** This module enables keyframe-based animation of 3D volumes. It supports interpolation of ROI, rotations, and transfer functions for volume rendering. Individual time-tracks can be set to each of these actions. While each volume rendering action support only a pair of transfer functions (Start and End), a number volume rendering tracks can be daisy-chained to create complex volume rendering animations. Output can be either as an image sequence of frames or can be compiled into mp4 format.

### USAGE
Start with loading the 3D volume to be rendered into Slicer, and [enable the Volume Rendering for it](https://raw.githubusercontent.com/SlicerMorph/S_2020/master/Day_1/ImageStacks/Data_Volume_Rendering.png).\

**ANIMATION PARAMETERS**\
**New Animation Duration:** Default is 5 sec, can be overwritten by user.\
**Animation Node:** Default blank, choose to create _New Animation_\


**ACTIONS**\
**Add Action:** There are three possibilities:\

  * **CameraRotationAction:** User needs to choose the rotation speed (degrees per second), and the axis of rotation (yaw, pitch or roll). 
  * **ROIAction:** User needs to define and starting and ending ROI and the Animator will interpolate shown region of interest. It is imported to set the ROI node of the volume to be rendered to the Value shown in in the "Animated ROI" prior to starting the animation.
  * **VolumePropertyAction:** User needs to define and starting and ending Volume Property fields and the Animator will interpolate volume property of the selected volume based on these. It is imported to set the Volume Property node of the volume to be rendered to the Value shown in in the "Animated Volume Property" prior to starting the animation.
  
Any number of these actions can be added as separate time-tracks. 
  
**EXPORT**\
**Animation Size:** Choose one of the rendering size presets, 160x120, 320x240, 640x480 or 1920x1024.\
**Animation Format:** Can be either mp4 or an animated GIF.\
**Output File:** Specify the location of the output file. 


### TUTORIAL
Please see https://github.com/SlicerMorph/S_2020/blob/master/Day_2/SlicerAnimator/SlicerAnimator.md





