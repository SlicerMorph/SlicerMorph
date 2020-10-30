<img src="https://raw.githubusercontent.com/SlicerMorph/SlicerMorph/master/GPA/Resources/Icons/GPA.png" alt="SlicerMorph logo" width="256" height="256">

This is the development repository for [SlicerMorph project](http://SlicerMorph.org). 

SlicerMorph enable biologists to retrieve, visualize, measure and annotate high-resolution specimen data both from volumetric scans (CTs and MRs) as well as from 3D surface scanners more effectively within 3D Slicer. It has a number of modules that facilitate Geometric Morphometrics analysis on these 3D specimens. 

## Installation
Official method of obtaining SlicerMorph is through extension mechanism of 3D Slicer. To install, please first install the Preview Release (v4.11 or higher) of [3D Slicer](https://download.slicer.org/), as SlicerMorph is not available for older versions. Open the application and use the [Extensions Manager module](https://www.slicer.org/wiki/Documentation/Nightly/SlicerApplication/ExtensionsManager) to search for and install the SlicerMorph extension. After restarting 3D Slicer, all SlicerMorph modules will be available in the application.

Alternatively, Mac and Windows users looking for a pre-packaged portable installation (e.g., running from a flash drive) of SlicerMorph, can [download our customized versions from](http://download.SlicerMorph.org). Our prepackaged versions are approximately updated quarterly with a newer base version of 3D Slicer, and with its latest extensions.  

## Module Descriptions

Modules in SlicerMorph are organized in three broad categories:

### Input/Output Related Modules
  - [**ImageStacks:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ImageStacks) A general purpose tool to import non-DICOM image sequences (png/jpg/bmp/tiff) into Slicer. Provides options to specify voxel size, select partial range, downsample (50%) along all three axes, load every Nth slice (skip a slice), or reverse stack order (to deal with mirroring of the specimen). Resultant volume is always a scalar volume (single channel image) that can be immediately processed in Slicer. If new Volume is not created, default file prefix in the image stack is used. 
  - [**SkyscanReconImport:** ](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/SkyscanReconImport) Imports an image stack from Bruker/Skyscan reconstruction software (Nrecon) with correct voxel spacing and orientation as a 3D volume. Use just needs to point out to the *_Rec.log* file that is outputed by the Nrecon software.
  - **ExportAs:** A generic export utility that can be used to save selected nodes in specific formats. It can also be used to save open and closedcurve Markup types in the older fcsv format (instead of default mrk.json) which makes easier to export semi-landmarks derived from them. 
  - [**MorphoSourceImport:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MorphoSourceImport) A utility to query and download open-access 3D models (ply/stl/object) from MorphoSource. The complete list of 3D models released under free access model can be found at [here](https://docs.google.com/spreadsheets/d/1fhdVv2JwvUJAC4dvSgKZi2pwSl7dPGaB-ksYsB64k4U/edit#gid=0).

### Geometric Morphometrics Related Modules
  - [**GPA:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/GPA) Performs Generalized Procrustes Analysis (GPA) with or without scaling shape configurations to unit size, conducts principle component analysis (PCA) of GPA aligned shape coordinates, provides graphical output of GPA results and real-time 3D visualization of PC warps either using the landmarks of mean shape, or using a reference model that is transformed into the mean shape. Visualization of 3D shape deformation of the reference model can be exported as video clips. The input into the module is a folder path containing a number of landmark files stored in Slicer’s fcsv format and optionally a 3D model and accompanying set of landmarks to be used as reference model in 3D visualization of PCA results.
  - [**CreateSemiLMPatches:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/CreateSemiLMPatches) Provides triangular patches of semi-landmarks that are constrained by three fixed anatomical landmarks. The input into the module is a 3D model and its accompanying set of fixed landmarks, and users generate and visualize the patches by specifying triplets of fixed landmarks that form a triangle. 
  - [**PseudoLMGenerator:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PseudoLMGenerator) This module uses the 3D model’s geometry to create a dense template of pseudo-landmarks. The landmark placement is constrained to the external surface of the mesh. Points sampled on the template are projected to the mesh surface along the surface normals of the template and then filtered to remove those within the sample spacing distance, improving regularity of sampling. This module can be used to generate a large number of points on a 3D model that can serve as a landmark template for additional samples in the dataset. 
  - [**ALPACA:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ALPACA) Automated Landmarking through Pointcloud Alignment and Correspondence Analysis. ALPACA provides fast landmark transfer from a 3D model and its associated landmark set to target 3D model(s) through pointcloud alignment and deformable mesh registration. Unlike the two semi-landmarking methods above, it does not require presence of fixed landmarks. Optimal set of parameters that gives the best correspondence can be investigated (and outcome can be visualized) in single alignment mode, and then applied to a number of 3D models in batch mode. Invoked first time, ALPACA needs your permission to download open3D library. Depending on the internet speed, download may take sometime but it is a one-time event. [A preprint explaining the method is available on Biorxiv](https://www.biorxiv.org/content/10.1101/2020.09.18.303891v1).     
  - [**MarkupEditor:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MarkupEditor) A plugin that enables to select and edit subsets of dense semi-landmarks by drawing an arbitrary closedcurve in the 3D viewer using right-click context menus in 3D viewer. Selected landmarks can be removed from the current node or copied into a new fiducial node. Useful to quickly identify and remove outliers from spherical sampling procedure, or group landmarks into anatomical regions for downstream analyses. 
  - **Auto3Dgm:** Auto3dgm, an existing method that allows for comparative analysis of 3D digital models representing biological surfaces, is also part of the SlicerMorph project, but packaged as a separate extension, which is automatically downloaded and installed by SlicerMorph.  Pseudo-landmark output from Auto3Dgm can be directly analyzed with the **GPA module**. Auto3Dgm requires a license for the proprietory optimization library mosek. [See auto3Dgm website for more information about the module and specific post-install instructions](https://toothandclaw.github.io/) 

### Utility Modules 

  - [**ImportFromURL:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ImportFromURL) A simple utility that will download the data from the provided URL into the current Slicer scene. 
  - [**Animator:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/Animator) A basic keyframe-based animation of 3D volumes. Supports interpolation of regions of interests, rotations, and transfer functions for volume rendering. Output can be either as an image sequence of frames or can be compiled into mp4 format.   
  - [**PlaceSemiLMPatches:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PlaceSemiLMPatches) A utility to apply the generated connectivity table from the **CreateSemiLMPatches** module to other 3D models with the same set of anatomical landmarks. A new set of semiLandmarks are sampled directly from the new models using the specified connectivity map. Inputs: The connectivity table from CreateSemiLMPatches, a directory with the list of 3D models that semi-landmarks will be placed on, and associated anatomical landmark files (in fcsv format). Both model and its corresponding fcsv file should have the same filename prefix. 
  - [**ProjectSemiLM:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ProjectSemiLM) A utility to transfer a template of semilandmarks to new 3D models using Thin Plate Splines (TPS) warp. Requires existence a set of corresponding anatomical landmarks in the template and target models. Inputs: a base 3D model with its anatomical landmark and the semi-landmark template sets used as reference; a directory with the list of 3D models that semi-landmarks will be projected on and their associated anatomical landmark files (in fcsv format). Both model and its corresponding fcsv file should have the same filename prefix. 
  - [**MorphologikaLMConverter:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MorphologikaLMConverter) Imports a Morphologika formatted landmark file that may contain multiple subjects and exports a Slicer .FCSV landmark file for each individual to a directory specified by the user.
  - [**IDAVLMConverter:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/IDAVLMConverter) Imports IDAV landmark editor files with header length specified by the user.
  - **ImportSurfaceToSegment:** Imports a 3D surface model as a segmentation and prompts the user to edit it using the Segment Editor module.
  - **SegmentEndoCranium:** Automatically segments the endocranial space in a 3D volume of a vertebrate skull. A detailed description of the module and how it works can be found [in this tutorial under the automated method](https://slicermorph.github.io/Endocast_creation.html). 

## Dependencies
SlicerMorph automatically installs these additional extensions as dependencies. It should be noted that none of the SlicerMorph specific functionality directly relies on these modules. Functionality in these extensions complements modules in SlicerMorph. Click on the links to get more information about these extensions.

- [**SegmentEditorExtraEffects:** Provides additional segmentation effects and utilities, such as our SplitSegment function that allows saving the 3D volume  into multiple smaller, individual volumes using the provided segmentation.](https://github.com/lassoan/SlicerSegmentEditorExtraEffects)
- [**SlicerIGT:** Provides landmark driven registration (affine and deformable) of volumes and models.](https://github.com/SlicerIGT/SlicerIGT)
- [**Sandbox:** Provides utilities like Cross-sectional Area from segments, Lights module for more in-depth lighting control and CurvePlanarReformat module for straightening of curved structures (e.g., coiled snake scans.](https://github.com/PerkLab/SlicerSandbox/)
- [**DCM2NIIX:** Provides a user-interface for the DICOM to NIFTI converter DCM2NIIX. Ideal for stripping metadata from DICOM datasets.](https://github.com/rordenlab/dcm2niix)
- [**SurfaceWrapSolidy:** A segment editor effect useful to extract endocasts of cranial and other spaces.](https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify)
- [**RawImageGuess:** A module that enables the user to import proprietory imaging formats by specifying data type, image dimensions and endiness.](https://github.com/acetylsalicyl/SlicerRawImageGuess)


## 3D Morphometrics and Image Analysis Short Course materials

We actively use SlicerMorph to teach a week-long intense [short course on 3D Morphometrics and Image analysis](http://workshop.SlicerMorph.org). The feedback of the attendees help us prioritize feature development and refinement. We are grateful for the feedback of over 100 participants. Contents from previous workshops are available on github. 
- [Summer 2020](https://github.com/SlicerMorph/S_2020)
- [Winter 2020](https://github.com/SlicerMorph/W_2020)
- [Summer 2019](https://github.com/SlicerMorph/S_2019)


## Important Websites	
*	SlicerMorph project website: https://www.SlicerMorph.org (website has additional tutorial, pointers to specimen repositories, and list of upcoming events).
*	Please sign up for the SlicerMorph announcement to keep up-to-date with SlicerMorph project and extension updates http://mailman11.u.washington.edu/mailman/listinfo/slicermorph-announcements
* [Introduction to Slicer - Official Slicer Documentation](https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html)
* [Difference between Slicer and SlicerMorph](https://docs.google.com/document/d/1VdsYQzhjEh9tT5WQQjb1GUdn5Hmnq8cK3yLzjYeVv5M/edit)
* [SlicerMorph YouTube Channel](https://www.youtube.com/channel/UCy3Uz1ikRH1B7WSMfaldcjQ): provides visual tutorials for GPA, semilandmarks, and others.
*	Slicer Forum, https://discourse.slicer.org (alternatively you can use your github or google accounts to signup)

## Funding Acknowledgement
This project is supported by a NSF Advances in Biological Informatics Collaborative grant to Murat Maga (ABI-1759883), Adam Summers (ABI-1759637) and Doug Boyer (ABI-1759839).

<img src="./NSF_4-Color_bitmap_Logo.png" alt="NSF logo" width="256" height="256">

## License
See License.md
