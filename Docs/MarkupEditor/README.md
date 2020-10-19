## MarkupEditor
**Summary:** This plugin enables selecting a number of fiducial points by drawing an arbitrary shaped closed curve. The selected points can be removed from the existing list or copy and pasted into a new fiducial list. It requires a 3D model and its associated set of fiducials. This module is useful for editing outputs from the PseudoLMGenerator or subsetting any dense landmark set into anatomical modules (for M&I analysis). 


### USAGE
Load a 3D model and a fiducial node containing the landmarks to be edited into an empty scene. Hover over one of the landmarks in 3D viewer (so that its color changes) and use the right mouse click to bring the pop-up menu. Choose **"Pick points with curve"** and for the first time choose **"Set Selection"**, and draw a closed curve on the model. Fiducials within the curve will be set to _Selected_ state, and everything else will _Unselected_. To add (or remove) more points to this selection subsequently, hover over another fiducial, again choose "Pick points with curve" and proceed with **"Add to (or remove from) selection"**. Only visible points on the model are selected. To choose points that are not visible, rotate the 3D model until they are visible, make a draw a curve and use the "Add to Selection" option. 

Once the selected set of fiducials finalized, hover over a fiducial, right mouse click to bring the popup menu and choose "Edit selected points". This will take the user to the Markups module, and highligted the rows of the selected points in the control points table. From there, user can delete the points from the existing list or copy, cut or paste them into a new MarkupsFiducialNode by using the available functions.  

Note that MarkupEditor uses the colors specified in the Display tab of the <a href="https://slicer.readthedocs.io/en/latest/user_guide/modules/markups.html"> Markups module </a> to designate selected and unselected states. We advise setting these to easily recognizable, distinct colors prior to operations. 


**Limitations:** There is no undo for actions (for example for deleted points). If necessary, we suggest cloning the fiducial node prior to editing so that original data can be restored. If you do so, also make sure to turn off the visibility of the cloned node.      


### TUTORIAL
Please see https://github.com/SlicerMorph/S_2020/blob/master/Day_3/MarkupEditor/MarkupEditor.md






