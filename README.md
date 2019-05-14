# Slicer Morph
This is the development repository for our NSF ABI grant

SlicerMorph enable biologists to retrieve, visualize, measure and annotate high-resolution specimen data both from volumetric scans (CTs and MRs) as well as from 3D surface scanners effectively within 3D-Slicer. It also provides a Generalized Procrustes Analysis (GPA) module as well as tools to visualize PCA decomposition of the GPA results.

## Module Descriptions
- ConvertMorphologikaLandmarks: Imports a Morphologika formatted landmark file that may contain multiple subjects and exports a Slicer .FCSV landmark file for each individual to a directory specified by the user.
- GPA: Performs generalized Procrustes analysis (GPA) and principle component analysis (PCA) of shape from landmark data and provides visualizations of statistical output.
- ImportSurfaceToSegment: Imports surface data as a segmentation and prompts the user to edit using the Segment Editor module.
- MorphoSource: MorphoSource is a publicly available repository for 3D media representing biological specimens. This module provides convenient access and data import from M/S into Slicer.
- ReadLandmarkFile: Imports landmark files with header length specified by the user.
- SkyscanReconImport: Imports Skyscan formatted image data.

## License
See License.md
