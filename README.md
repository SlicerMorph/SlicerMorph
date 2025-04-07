<img src="https://raw.githubusercontent.com/SlicerMorph/Images/main/husky_small.png" alt="SlicerMorph logo">

This is the official repository for SlicerMorph project.

Our project aims to enhance the open-source 3D Slicer platform with cutting-edge tools to assist biologists, anthropologists, and morphologists in analyzing 3D data from research imaging modalities. Our ultimate goal is to foster a collaborative community within the 3D Slicer ecosystem to facilitate seamless data exchange and promote the advancement of open science.

SlicerMorph streamlines digital morphology research by enabling effortless data import, visualization, measurement, annotation, and geometric morphometric analysis on 3D data, including volumetric scans (CTs and MRs) and 3D surface scans, all within the 3D Slicer application. Say goodbye to multiple programs, different file formats, and workflows!

[SlicerMorph: An open and extensible platform to retrieve, visualize and analyze 3D morphology](https://besjournals.onlinelibrary.wiley.com/doi/10.1111/2041-210X.13669) is now available in Methods in Ecology and Evolution as an open-access paper. A more detailed version of this manuscript that explains all digital anatomy workflows in Slicer is also [available as a preprint on Biorxiv](https://www.biorxiv.org/content/10.1101/2020.11.09.374926v1).

## Installation
Official method of obtaining SlicerMorph is through extension mechanism of 3D Slicer. To obtain SlicerMorph, please first install the latest **stable release** of [3D Slicer](https://download.slicer.org/) and use the [Extensions Manager module](https://www.slicer.org/wiki/Documentation/Nightly/SlicerApplication/ExtensionsManager) to search for and install the SlicerMorph extension. After restarting 3D Slicer, all SlicerMorph modules will be available in the application.

### Use SlicerMorph on the cloud:
Your data does not fit into your laptop, or do not have a powerful computer to run 3D Slicer and SlicerMorph, or your institution does not give you permission to install software on their devices? You can now run 3D Slicer and SlicerMorph inside a web browser without having to install anything through our **MorphoCloud On-Demand Instances**. All you need is GitHub account and a public ORCID profile. Please see http://instances.morpho.cloud for details and get started.

<img src="https://raw.githubusercontent.com/SlicerMorph/Spr_2021/main/TechCheckin/exten_manager.png">

## How to cite
If you use SlicerMorph in your research, please cite one or more of these publications.

* **SlicerMorph** as a general platform for digital morphology: Rolfe, S., Pieper, S., Porto, A., Diamond, K., Winchester, J., Shan, S., … Maga, A. M. (2021). _SlicerMorph: An open and extensible platform to retrieve, visualize and analyze 3D morphology._ Methods in Ecology and Evolution, 12:1816–1825. https://doi.org/10.1111/2041-210X.13669 (Open access)

* For **CreateSemiLMPatches, ProjectSemiLMs, PseudoLMGenerator**: Rolfe, S., Davis, C., & Maga, A. M. (2021). _Comparing semi-landmarking approaches for analyzing three-dimensional cranial morphology. American Journal of Physical Anthropology_. 175(1):227-237. https://doi.org/10.1002/ajpa.24214

* For **ALPACA**: Porto, A., Rolfe, S. M., & Maga, A. M. (2021). _ALPACA: A fast and accurate approach for automated landmarking of three-dimensional biological structures_. Methods in Ecology and Evolution. 12:2129–2144. http://doi.org/10.1111/2041-210X.13689 (Open access).

* For **MALPACA (Multi-Template ALPACA)**: Zhang, C., Porto, A., Rolfe, S., Kocatulum, A., & Maga, A. M. (2022). _Automated landmarking via multiple templates_. PLOS ONE. 17(12). e0278035. https://doi.org/10.1371/journal.pone.0278035 (Open access).

To cite 3D Slicer as a general purpose biomedical visualization platform, please use: Kikinis, R., Pieper, S. D., & Vosburgh, K. G. (2014). 3D Slicer: A Platform for Subject-Specific Image Analysis, Visualization, and Clinical Support. In Intraoperative Imaging and Image-Guided Therapy (pp. 277–289). Springer, New York, NY. https://doi.org/10.1007/978-1-4614-7657-3_19

[Follow this link to obtain a list of publications that cite the main SlicerMorph paper (Rolfe et al., 2021)](https://scholar.google.com/scholar?hl=en&as_sdt=5,48&sciodt=0,48&cites=13786917364486709604&scipsc=&q=&scisbd=1)

## Updating SlicerMorph

We continuously add new features and functionalities to SlicerMorph packages. To make sure you are using the latest version, go to Extension Manager, click Manage Extensions tab and then use the "Check for updates" function. Once updates are installed, please restart Slicer for changes to take effect. This feature is only available for stable releases. If you are using the preview version, you have to install a newer preview version to obtain the changes introduced to SlicerMorph.

<img src="https://raw.githubusercontent.com/SlicerMorph/Spr_2021/main/TechCheckin/Exten_manager_Update.png">

## Module Descriptions

Modules in SlicerMorph are organized in three broad categories:

### Input/Output Related Modules
- [**ImageStacks:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ImageStacks) A general purpose tool to import non-DICOM image sequences (png/jpg/bmp/tiff) into Slicer. Provides options to specify voxel size, select image quality (preview, half, full resolution), define an ROI for import, load every Nth slice (skip slice), or reverse stack order (to deal with mirroring of the specimen).
- [**SkyscanReconImport:** ](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/SkyscanReconImport) Imports an image stack from Bruker/Skyscan reconstruction software (Nrecon) with correct voxel spacing and orientation as a 3D volume. User just needs to point out to the *_Rec.log* file that is outputted by the Nrecon software. Also possible to process multiple scans through the batch conversion interface (requires all reconstructions to be under a single directory tree)
- [**GEVolImport:** ](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/GEVolImport) Utility to import the .VOL files generated by the GE/tome microCT scanners by parsing the associated reconstruction file (.PCR).
- [**MorphoSourceImport:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MorphoSourceImport) A utility to query and download open-access data from MorphoSource. An important distinction from the web based search of MorphoSource, queries primarily on keywords (e.g., Skull, femur or M2) which can be alternatively constrained by taxonomy. Requires an API key from MorphoSource to be able to download datasets.

### Geometric Morphometrics Related Modules
- [**GPA:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/GPA) Performs Generalized Procrustes Analysis (GPA) with conducts principle component analysis (PCA) of GPA aligned shape coordinates, provides graphical output of GPA results and real-time 3D visualization of PC warps either using the landmarks of mean shape, or using a reference model that is transformed into the mean shape. Visualization of 3D shape deformation of the reference model can be exported as video clips. The input into the module is a folder path containing a number of landmark files stored in Slicer’s fcsv format and optionally a 3D model and accompanying set of landmarks to be used as reference model in 3D visualization of PCA results.
- [**CreateSemiLMPatches:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/CreateSemiLMPatches) Provides triangular patches of semi-landmarks that are constrained by three fixed anatomical landmarks. The input into the module is a 3D model and its accompanying set of fixed landmarks, and users generate and visualize the patches by specifying triplets of fixed landmarks that form a triangle.
- [**PseudoLMGenerator:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PseudoLMGenerator) This module uses the 3D model’s geometry to create a dense template of pseudo-landmarks. The landmark placement is constrained to the external surface of the mesh. Points sampled on the template are projected to the mesh surface along the surface normals of the template and then filtered to remove those within the sample spacing distance, improving regularity of sampling. This module can be used to generate a large number of points on a 3D model that can serve as a landmark template for additional samples in the dataset.
- [**ALPACA:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ALPACA) Automated Landmarking through Pointcloud Alignment and Correspondence Analysis. ALPACA provides fast landmark transfer from a 3D model and its associated landmark set to target 3D model(s) through pointcloud alignment and deformable model registration. Unlike the two semi-landmarking methods above, it does not require presence of fixed landmarks. Optimal set of parameters that gives the best correspondence can be investigated (and outcome can be visualized) in single alignment mode, and then applied to a number of 3D models in batch mode. Invoked first time, ALPACA needs your permission to download necessary libraries. Depending on the internet speed, download may take sometime but it is a one-time event.
- [**MarkupEditor:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MarkupEditor) A plugin that enables to select and edit subsets of dense semi-landmarks by drawing an arbitrary closedcurve in the 3D viewer using right-click context menus in 3D viewer. Selected landmarks can be removed from the current node or copied into a new fiducial node. Useful to quickly identify and remove outliers from spherical sampling procedure, or group landmarks into anatomical regions for downstream analyses.
- [**PlaceLandmarkGrid:**]() Allows user to place a grid of semi landmarks that were constrained by 4 landmarks. Once placed, user can adjust the placement of the grid, and then resample semi-landmarks from them (WIP). Multiple grids can be created and then merged via the MergeMarkups module.


### Utility Modules

- [**ImportFromURL:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ImportFromURL) A simple utility that will download the data from the provided URL into the current Slicer scene.
- [**Animator:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/Animator) A basic keyframe-based animation of 3D volumes. Supports interpolation of regions of interests, rotations, and transfer functions for volume rendering. Output can be either as an image sequence of frames or can be compiled into mp4 format.
- [**PlaceSemiLMPatches:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/PlaceSemiLMPatches) A utility to apply the generated connectivity table from the **CreateSemiLMPatches** module to other 3D models with the same set of anatomical landmarks. A new set of semiLandmarks are sampled directly from the new models using the specified connectivity map. Inputs: The connectivity table from CreateSemiLMPatches, a directory with the list of 3D models that semi-landmarks will be placed on, and associated anatomical landmark files (in fcsv format). Both model and its corresponding fcsv file should have the same filename prefix.
- [**ProjectSemiLM:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/ProjectSemiLM) A utility to transfer a template of semilandmarks to new 3D models using Thin Plate Splines (TPS) warp. Requires existence a set of corresponding anatomical landmarks in the template and target models. Inputs: a base 3D model with its anatomical landmark and the semi-landmark template sets used as reference; a directory with the list of 3D models that semi-landmarks will be projected on and their associated anatomical landmark files (in fcsv format). Both model and its corresponding fcsv file should have the same filename prefix.
- [**MergeMarkups:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MergeMarkups). A utility to tag and consolidate fixed and semiLM files into a single merged file.
- [**MorphologikaLMConverter:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MorphologikaLMConverter) Imports a Morphologika formatted landmark file that may contain multiple subjects and exports a Slicer .FCSV landmark file for each individual to a directory specified by the user.
- [**IDAVLMConverter:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/IDAVLMConverter) Imports IDAV landmark editor files with header length specified by the user.
- **ImportSurfaceToSegment:** Imports a 3D surface model as a segmentation and prompts the user to edit it using the Segment Editor module.
- **SegmentEndoCranium:** Automatically segments the endocranial space in a 3D volume of a vertebrate skull. A detailed description of the module and how it works can be found [in this tutorial under the automated method](https://slicermorph.github.io/Endocast_creation.html).
- [**SlicerMorph Preferences:**](https://github.com/SlicerMorph/SlicerMorph/tree/master/Docs/MorphPreferences/) Users can choose to enable specific customizations that include keyboard shortcuts, and optimized settings for working with large 3D datasets using the Application Settings menu of 3D Slicer. See the documentation link for list of SlicerMorph specific keyboard shortcuts and modified settings.
- [**FastModelAlign:**](https://github.com/SlicerMorph/Tutorials/tree/main/FastModelAlign) Allows users to register a 3D model (source) to a target. Support scaling, rigid and affine transforms.
- [**QuickAlign:**](https://github.com/SlicerMorph/Tutorials/blob/main/QuickAlign/README.md) Allows users to approximately align two objects in two different 3D viewers, and then link the views. Useful to compare models, landmarks and volume that were scanned in different orientations.
- [**HiResScreenCapture:**](https://github.com/SlicerMorph/Tutorials/blob/main/HiResScreenCapture/readme.md) Allows the user to create high-resolution off-screen rendering of what's visible in the 3D viewer. Useful to create high-DPI rendering for posters and publications. (Only available for Slicer 5.7 or later).

## Dependencies
## Automatically installed extensions
The following extension is installed automatically with SlicerMorph. Although it is not directly relied on by the modules, it is necessary for many workflows supoorted by SlicerMorph:
- [**SegmentEditorExtraEffects:**](https://github.com/lassoan/SlicerSegmentEditorExtraEffects) Provides additional segmentation effects and utilities, such as our SplitSegment function that allows saving the 3D volume  into multiple smaller, individual volumes using the provided segmentation.
- [**Sandbox:**](https://github.com/lassoan/SlicerSandbox) Provides the `ColorizeVolume` module and other additional utilities that are functional, but not fully tested and not ready to be incorporated to Slicer's core.
- [**SurfaceMarkups:**](https://github.com/SlicerHeart/SlicerSurfaceMarkup) Provides the Surface Markup type needed by the 'PlaceLandmarkGrid' module.

## Manually installed extensions
The following extension is required for using the SegmentEndocranium. Installation is prompted on opening this module.
- [**SurfaceWrapSolidy:** A segment editor effect useful to extract endocasts of cranial and other spaces.](https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify)

## Related Extensions by the SlicerMorph team
<img src="https://github.com/SlicerMorph/SlicerMorph.github.io/blob/master/all_logos.png?raw=true">
<p></p>
SlicerMorph project also maintains other extensions that offer complementary functionality:

- [**ScriptEditor:**](https://github.com/SlicerMorph/SlicerScriptEditor) Provides the open-source Monaco programming editor inside the Slicer. Scripts can be saved as part of the scene and can be sent directly to the Slicer's integrated Python console for execution.
- [**Mouse Embryo Multi-Organ Segmentations (MEMOS):**](https://github.com/SlicerMorph/SlicerMEMOS)  An extension for automated segmentation 50 anatomical structures from diceCT scans of E15 fetal mice using deep-learning.
- [**Dense Correspondence Analysis (DeCA):**](https://github.com/SlicerMorph/SlicerDenseCorrespondenceAnalysis) is an extension for Dense Correspondence Analysis and to generate template-based semiLMs.
- [**Photogrammetry:**](https://github.com/SlicerMorph/SlicerPhotogrammetry) is an extension that integrates Segment Anything Model (SAM) and OpenDroneMap software to mask foreground in large collection of photographs with the purpose of building 3D textured models.
- [**MorphoDepot:**](https://github.com/MorphoCloud/SlicerMorphoDepot) is an extension that allows creating 3D specimen repositories on Github with focus on digital morphology classroom assignments or remote collaborative segmentation. It implements the `fork and pull` workflow for remote collaborations. (WIP)
- [**SlicerMorphR:**](https://github.com/SlicerMorph/SlicerMorphR) R library to read output from SlicerMorph's GPA module into R. It also supports reading/writing mrk.json files from Slicer.


## Other recommended extensions
Slicer extension catalog has over 100 extensions. We  recommend the following extensions that provide useful convenience functions:
- [**SlicerIGT:** Provides landmark driven registration (affine and deformable) of volumes and models.](https://github.com/SlicerIGT/SlicerIGT)
- [**RawImageGuess:** A module that enables the user to import proprietary imaging formats by specifying data type, image dimensions and endianness.](https://github.com/acetylsalicyl/SlicerRawImageGuess)
- [**Model To Model Distance:**]()This extension computes the distance between two 3D models. This is useful to generate heatmaps on models from PCA.


## SlicerMorph Tutorials
[We have step-by-step module specific tutorials that is useful for people starting with Slicer and SlicerMorph.](https://github.com/SlicerMorph/Tutorials)

## 3D Morphometrics and Image Analysis Short Course materials

We actively use SlicerMorph to teach a week-long intense [short course on 3D Morphometrics and Image analysis](http://workshop.SlicerMorph.org). The feedback of the attendees help us prioritize feature development and refinement. We are grateful for the feedback of over 200 participants. [Click for contents from the latest workshop, Spring 2022](https://github.com/SlicerMorph/Spr_2022)

## Important Websites
*	SlicerMorph project website: https://slicermorph.github.io (website list upcoming events, including monthly user group meeting. It also has pointers to some of the online specimen repositories).
*	SlicerMorph Step-by-Step Tutorials: https://github.com/SlicerMorph/Tutorials
*	Please sign up for the SlicerMorph announcement to receive notifications about SlicerMorph project, extension updates and upcoming demos and workshops http://mailman11.u.washington.edu/mailman/listinfo/slicermorph-announcements
* [Introduction to Slicer - Official Slicer Documentation](https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html)
* [SlicerMorph YouTube Channel](https://www.youtube.com/channel/UCy3Uz1ikRH1B7WSMfaldcjQ): provides visual tutorials for GPA, semilandmarks, and others.
*	Slicer Forum, https://discourse.slicer.org (alternatively you can use your github or google accounts to signup)

## Funding Acknowledgement
This project is supported by NSF Advances in Biological Informatics (1759883) and NSF/DBI Cyberinfrastructure (2301405) grants to A. Murat Maga.

<img src="./NSF_4-Color_bitmap_Logo.png" alt="NSF logo" width="256" height="256">

## License
See License.md
