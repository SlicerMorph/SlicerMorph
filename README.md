<img src="https://raw.githubusercontent.com/SlicerMorph/SlicerMorph/master/GPA/Resources/Icons/GPA.png" alt="SlicerMorph logo" width="256" height="256">

This is the development repository for our NSF ABI grant

SlicerMorph enable biologists to retrieve, visualize, measure and annotate high-resolution specimen data both from volumetric scans (CTs and MRs) as well as from 3D surface scanners effectively within 3D-Slicer. It also provides a Generalized Procrustes Analysis (GPA) module as well as tools to visualize PCA decomposition of the GPA results.

## Installation
To install SlicerMorph, please first install the Preview Release of [3D-Slicer](https://download.slicer.org/). Open the application and use the [Extensions Manager module](https://www.slicer.org/wiki/Documentation/Nightly/SlicerApplication/ExtensionsManager) to install the SlicerMorph extension. After restarting 3D-Slicer, all SlicerMorph modules will be available in the application.

## Module Descriptions
- **GPA:** Performs generalized Procrustes analysis (GPA) with or without scaling and principle component analysis (PCA) of shape from landmark data and provides visualizations of statistical output.
- **SemiLandmarks:** Provides patch-based resampling of semi-landmarks from a 3D model with associated landmarks. 
- **Transfer SemiLandmarks:** A utility to apply the generated connectivity table from the semiLandmarks module to other 3D models with the same set of landmarks. A new set of semiLandmarks are sampled directly from the new models using the specified connectivity map. Inputs: a directory with 3D models and fcsv (same filename prefix). 
- **Transfer SemiLandmarks Warp:** A utility to transfer a template of semiLandmarks to new 3D models using Thin Plate Splines (TPS) warp. Requires existence identical set of landmarks in the template and new models. 
- **Segment EndoCranium:** Automatically segments the endocranial space in a 3D volume of a vertebrate skull. 
- **Image Stacks:** A general purpose tool to import non-DICOM image sequences (png/jpg/bmp/tiff) into Slicer. Provides option to choose to choose a partial range, downsample along all axis, load every Nth slice (skip a slice). Resultant volume is always a scalar volume (single channel image). 
- **SkyscanReconImport:** Imports an image stack from Bruker/Skyscan reconstruction software (Nrecon) with correct voxel spacing and orientation as a 3D volume.
- **SlicerAnimator:** A prototype of keyframe-based animation of 3D volumes. Supports interpolation of VOIs, transfer functions and rotations. 
- **MorphoSource Browser:** A built-in web browser that provides convenient access to MorphoSource website directly within Slicer. 
- **MorphoSource Query:** A utility to query and download open-access 3D models (ply/stl/object) from MorphoSource (pending).
- **ConvertMorphologikaLandmarks:** Imports a Morphologika formatted landmark file that may contain multiple subjects and exports a Slicer .FCSV landmark file for each individual to a directory specified by the user.
- **ImportSurfaceToSegment:** Imports a 3D surface model as a segmentation and prompts the user to edit it using the Segment Editor module.
- **ReadLandmarkFile:** Imports IDAV landmark editor files with header length specified by the user.

## Funding Acknowledgement
This project is supported by a NSF Advances in Biological Informatics Collaborative grant to Murat Maga (ABI-1759883), Adam Summers (ABI-1759637) and Doug Boyer (ABI-1759839).

<img src="./NSF_4-Color_bitmap_Logo.png" alt="NSF logo" width="256" height="256">

## License
See License.md
