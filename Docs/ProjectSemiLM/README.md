## ProjectSemiLM
**Summary:** This module provides a utility to transfer a template of semilandmarks from a base 3D model to new 3D models using Thin Plate Splines (TPS) warp. A set of corresponding anatomical landmarks in the template and each target model is required. 

### USAGE
#### ProjectSemiLM PARAMETERS
* __Base mesh__ Selects the reference model used to place the initial semi-landmark points (using any method) from the scene.

* __Base landmarks__ Selects the fixed, anatomical landmarks placed on the reference model from the scene.

* __Base semi-landmarks__ Selects the semi-landmark points placed on the reference model from the scene.

* __Mesh directory__ Specifies the directory of models that will have semi-landmarks placed by this module.

* __Landmark directory__ Specifies the directory of fixed, anatomical landmarks corresponding to the models that will have semi-landmarks placed by this module. The landmarks should be stored as `.fcsv` files and have the same filename prefix as the corresponding model.

* __Output directory__ Specifies the directory where the semi-landmark files for each of the new models will be stored as `.fcsv` files.

#### LIMITATIONS
* This method requires fixed, anatomical landmarks to be placed on the template and each target mesh. If these are not available, the `ALPACA` module can be used as an alternative.

* The performance of this method will depend on the number and distribution of the anatomical landmarks, the amount of morphological variation in the dataset, and the selection of an appropriate reference model.

* It is recommended to use an average model as the base reference model, if one is available.

### TUTORIAL
For an example using the `CreatSemiLMPatches` module to create a semi-landmark set on a templateand the `ProjectSemiLM` module to transfer the semi-landmarks to each model in a directory, please see the [CreatSemiLMPatches tutorial](https://github.com/SlicerMorph/S_2020/blob/master/Day_3/Patch-based_semiLMs/Patch-based_semiLMs.md).






