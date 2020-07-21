<img src="https://raw.githubusercontent.com/SlicerMorph/SlicerMorph/master/GPA/Resources/Icons/GPA.png" alt="SlicerMorph logo" width="256" height="256">

This is the development repository for our NSF ABI grant

SlicerMorph enable biologists to retrieve, visualize, measure and annotate high-resolution specimen data both from volumetric scans (CTs and MRs) as well as from 3D surface scanners effectively within 3D-Slicer. It also provides a Generalized Procrustes Analysis (GPA) module as well as tools to visualize PCA decomposition of the GPA results.

## Installation
To install SlicerMorph, please first install the Preview Release of [3D-Slicer](https://download.slicer.org/). Open the application and use the [Extensions Manager module](https://www.slicer.org/wiki/Documentation/Nightly/SlicerApplication/ExtensionsManager) to install the SlicerMorph extension. After restarting 3D-Slicer, all SlicerMorph modules will be available in the application.

## Module Descriptions
- **GPA:** Performs generalized Procrustes analysis (GPA) with or without scaling and principle component analysis (PCA) of shape from landmark data and provides visualizations of statistical output (identification of outliers, PC score plots, real-time 3D visualization of PC warps either through mean shape coordinates, or using a reference model).
- **SemiLandmarks:** Provides patch-based resampling of semi-landmarks from a 3D model with associated landmarks. 
- **Transfer SemiLandmarks:** A utility to apply the generated connectivity table from the semiLandmarks module to other 3D models with the same set of landmarks. A new set of semiLandmarks are sampled directly from the new models using the specified connectivity map. Inputs: a directory with 3D models and fcsv (same filename prefix). 
- **Transfer SemiLandmarks Warp:** A utility to transfer a template of semiLandmarks to new 3D models using Thin Plate Splines (TPS) warp. Requires existence identical set of landmarks in the template and new models. 
- **SegmentEndoCranium:** Automatically segments the endocranial space in a 3D volume of a vertebrate skull. 
- **ImageStacks:** A general purpose tool to import non-DICOM image sequences (png/jpg/bmp/tiff) into Slicer. Provides options to specify voxel size, select partial range, downsample (50%) along all three axes, load every Nth slice (skip a slice), or reverse stack order (to deal with mirroring of the specimen). Resultant volume is always a scalar volume (single channel image) that can be immediately processed in Slicer. If new Volume is not created, default file prefix in the image stack is used. 
- **SkyscanReconImport:** Imports an image stack from Bruker/Skyscan reconstruction software (Nrecon) with correct voxel spacing and orientation as a 3D volume.
- **SlicerAnimator:** A prototype of keyframe-based animation of 3D volumes. Supports interpolation of VOIs, transfer functions and rotations. 
- **MorphoSource Browser:** A built-in web browser that provides convenient access to MorphoSource website directly within Slicer (deprecated). 
- **MorphoSourceImport:** A utility to query and download open-access 3D models (ply/stl/object) from MorphoSource. The complete list of 3D models released under free access model can be found at [here](https://docs.google.com/spreadsheets/d/1fhdVv2JwvUJAC4dvSgKZi2pwSl7dPGaB-ksYsB64k4U/edit#gid=0).
- **ConvertMorphologikaLandmarks:** Imports a Morphologika formatted landmark file that may contain multiple subjects and exports a Slicer .FCSV landmark file for each individual to a directory specified by the user.
- **ImportSurfaceToSegment:** Imports a 3D surface model as a segmentation and prompts the user to edit it using the Segment Editor module.
- **ReadLandmarkFile:** Imports IDAV landmark editor files with header length specified by the user.
- **ExportAs:** A generic export utility that can be used to save selected nodes in specific formats. It can also be used to save open and closedcurve Markup types in the older fcsv format (instead of default mrk.json) which makes easier to export semi-landmarks derived from them. 
- **LandmarkEditor:** A module that enables to select and edit subsets of dense semi-landmarks by drawing an arbitrary closedcurve in the 3D viewer. Selected landmarks can be removed from the current node or copied into a new fiducial node. Useful to quickly identify and remove outliers from spherical sampling procedure, or group landmarks into anatomical regions for downstream analyses. 


## Funding Acknowledgement
This project is supported by a NSF Advances in Biological Informatics Collaborative grant to Murat Maga (ABI-1759883), Adam Summers (ABI-1759637) and Doug Boyer (ABI-1759839).

<img src="./NSF_4-Color_bitmap_Logo.png" alt="NSF logo" width="256" height="256">

## License
See License.md
