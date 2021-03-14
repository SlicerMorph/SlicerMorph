## CreateSemiLMPatches
**Summary:** 
Provides triangular patches of semi-landmarks that are constrained by three fixed anatomical landmarks. The input into the module is a 3D model and its accompanying set of fixed landmarks. Users generate, visualize, and edit the patches by specifying triplets of fixed landmarks that form a triangle. A template triangular grid with a user-specified number of semi-landmark points is registered to the vertices of the bounding triangle using a thin-plate-spline deformation. The vertices of the triangular sampling grid are then projected to the surface of the specimen along the estimated normal vectors. After placement, the patches can be merged together into a single landamark node and a table is generated specifying the final landmark point connectivity.

### USAGE

#### CreateSemiLMPatches PARAMETERS
These parameters are required to be set to use the module.

* __Model:__ This node selector specifies the model where the semi-landmarks will be placed. 

* __Landmark set:__ This node selector specifies the fixed anatomical landmark set corresponding to the model.

* __Semi-landmark grid points:__ This field takes three values which correspond to the landmark numbers of the points used to construct the triangle patch.

* __Select number of rows/columns in resampled grid:__ This value sets the number of points that will placed in each triangle patch. This number can be adjusted for each patch, but if the grid is reconstructed using the `PlaceSemiLandmarkPatches` module, one sampling value will be used for all patches.

#### CreateSemiLMPatches ADVANCED PARAMETERS
The advanced parameters are settings that can be adjusted to improve the performance of the module. Most users will not need to change the default settings.

* __Set maximum projection distance:__ The maximum projection distance specifies the maximum search distance used to project a point to the surface, as a percentage of the image length. This value may need to be decreased in cases where there are multiple structures in an image and the points from one stucture are being projected to a more external surface.

* __Set smoothing of projection vectors:__ The projection vectors are estimated from the vertices of a triangular patch. Increasing the smoothing parameter of the projection vectors will larger area around the vertices. This will help improve the performance when the mesh surface may contain noise or holes.

#### Using the CreateSemiLMPatches OUTPUT
* After generating the patches and merging, save the merged semi-landmark node and the landmark connectivity table.

* The landmark connectivity table can be used to apply the same semi-landmark patches across a data set using the `PlaceSemiLandmarkPatches` module. Each image will need to have manual landmarks placed.

* The merged semi-landmarks can be projected to other images in a data set using the `ProjectSemiLM` module. Each image is required to have manual landmarks placed.

* The merged semi-landmarks can be transferred to other images in a data set using the `Alpaca` module. The images in the data set are not required to have manual landmarks for this method. 

### TUTORIAL
For more details, please see the [CreateSemiLMPatches tutorial](https://github.com/SlicerMorph/Spr_2021/blob/main/Day_3/Patch-based_semiLMs/Patch-based_semiLMs.md)
CreateSemiLMPatches video tutorials:
1. [Creating Patches](https://www.youtube.com/watch?v=SArudRq-M4A)
2. [Applying Patches to new samples](https://www.youtube.com/watch?v=UD2tmFuaSJg)






