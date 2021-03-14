## ALPACA

__Summary__: This module provides fast landmark transfer from a 3D model and its associated landmark set to target 3D model(s) through point cloud alignment and deformable mesh registration. Unlike the Slicermorph's semi-landmark methods, it does not require presence of fixed landmarks. Optimal set of parameters that gives the best correspondence can be investigated (and outcome can be visualized) in single alignment mode, and then applied to a number of 3D models in batch mode. Invoked first time, `ALPACA` needs your permission to download [`open3D`](http://www.open3d.org/) library. Depending on the internet speed, download may take sometime but it is a one-time event. A detailed description of the `ALPACA` implementation is available as a [preprint](https://www.biorxiv.org/content/10.1101/2020.09.18.303891v1).

### USAGE

#### SINGLE ALIGNMENT

* __Required parameters__

  * __Source mesh__: User is expected to select the path to the `*.ply` mesh file to be used as a template
  
  * __Source landmarks__: User is expected to select the path to the `*.fcsv` file containing the landmarks to be transferred to the target mesh.
  
  * __Target mesh__: User is expected to select the path to the `*.ply` mesh file to be used as a target (i.e., the specimen we are interested in predicting landmark positions for).
  
  * __Skip scaling__: User is expected to choose whether to isotropically scale the source mesh to match the size of the target mesh.
  
  * __Skip projection__: User is expected to choose whether the pipeline should perform its final and optional post-processing step in which the predicted landmarks are projected to the target surface mesh.

* __Advanced parameters__

  * __Point Density Adjustment__: ALPACA automatically chooses the voxel size to be used when sampling the source and target meshes. This setting allows the user to manually adjust the voxel size. Increasing the `Point Density Adjustment` slider will lead to an increase in the number of sampled points in the the target and source meshes, and vice-versa. In general, we recommend users to aim for 5,000 - 6,000 points per point cloud.
  
  * __Maximum projection factor__: As a final and optional post-processing step of the ALPACA pipeline, the predicted landmarks are projected to the target surface mesh. This setting allows users to regulate the amount of maximum displacement that would be allowed in this final step. The default parameter is to limit point displacement to a maximum of 1% of the mesh size. Increasing this value allows larger displacements to occur.
  
  * __Normal seach radius__: Defines the neighborhood of points used when calculating the surface normals in each point cloud. This parameter is defined relative to the voxel size.
  
  * __FPFH search radius__: Defines the neighborhood of points used when computing the FPFH features.This parameter is defined relative to the voxel size.
  
  * __Maximum corresponding point distance__: Defines the maximum distance between two points up to which the points can be considered corresponding to each other when running RANSAC. Larger values are more permissive than lower values.
  
  * __Maximum RANSAC iterations__: Limits the maximum number of iterations that are allowed when running the RANSAC algorithm (rigid alignment).
  
  * __Maximum RANSAC validation steps__: Limits the maximum number of validation steps that are allowed when running the RANSAC algorithm (rigid alignment).
  
  * __Maximum ICP distance__: Defines the maximum distance between two points up to which the points can be considered corresponding to each other when running the local ICP. Larger values are more permissive than lower values.

  * __Rigidity (alpha)__: Parameter `Alpha` is a regularization parameter that affects the length of the deformation vectors. Lower values of `Alpha` lead to larger overall deformations, and vice versa.

  * __Motion coherence (beta)__: Parameter `Beta` is a regularization parameter that tends to affect the degree of motion coherence of neighboring points. Large values of `Beta` will lead to greater motion coherence among neighboring points, and vice versa.

  * __CPD iterations__: Limits the maximum number of iterations that are allowed when running the CPD algorithm (deformable alignment).
  
  * __CPD tolerance__: Tolerance to be used when stopping the CPD algorithm.
  

#### BATCH PROCESSING

* __Required parameters__

  * __Source mesh__: User is expected to select the path to the `*.ply` mesh file to be used as a template
  
  * __Source landmarks__:User is expected to select the path to the `*.fcsv` file containing the landmarks to be transferred to the target mesh.
  
  * __Target mesh directory__: User is expected to select the path to the directory containing`*.ply` mesh files to be used as targets (i.e., the specimens we are interested in predicting landmark positions for).
  
  * __Target output landmark directory__: User is expected to select the path to the directory on which the ALPACA outputs ( landmarks in`fcsv` format) will be saved.
  
* __Advanced parameters__

  *  Same as single alignment.

### KNOWN ISSUES
**Linux specific:** 
1. For Slicer Stable 4.11.20210226 (r29738), the [scipy library bundled has an issue, rendering ALPACA non-functional](https://discourse.slicer.org/t/slicer-stable-4-11-20210226-issue-with-scipy-package-in-linux/16354). Either use a later preview version on Linux, or use the windows or MacOS versions in stable stream. 
2. open3d relies on a GCLIB2.7 (or newer), which is not available in older Linux distributions such as Centos 7.x. As such, ALPACA will not work any Linux distribution that doesn't fulfill this requirement. 
  
### TUTORIAL

- [Latest ALPACA tutorial](https://github.com/SlicerMorph/Spr_2021/tree/main/Day_4/ALPACA)

