# Grid Template Transfer Feature

## Overview

The PlaceLandmarkGrid module now supports transferring grid patch configurations from one specimen to another using manual landmarks. This eliminates the need to manually recreate grids on each specimen, reducing errors and saving time.

## How to Use

### On the Reference Specimen

1. **Place Manual Landmarks**: Create a landmark node with manual landmarks on your reference specimen
2. **Create Grid Patches**: Use the "Place Grids" tab to create grid patches as usual
3. **Select Landmark Node**: In the "Place Grids" tab, select your landmark node from the "Landmark node (optional)" dropdown
4. **Merge Grids**: Switch to the "Merge Grids" tab and merge your grids
   - The patches will be automatically associated with the closest manual landmarks
5. **Save Template**: Click "Save grid template" to save the configuration to a JSON file
   - The template stores:
     - Which landmarks were used as corners for each patch (by index)
     - The grid resolution for each patch
     - The order of landmark indices

### On Target Specimens

1. **Ensure Matching Landmarks**: Make sure your target specimen has manual landmarks placed in the same order as the reference
2. **Select Model and Landmarks**: 
   - Select the model in the "Place Grids" tab
   - Select the landmark node
3. **Load Template**: In the "Merge Grids" tab, click "Load and apply grid template"
   - Select the saved template JSON file
   - The grids will be automatically recreated using the landmark positions
4. **Adjust as Needed**: Fine-tune the grid positions if necessary by adjusting the grid lines
5. **Merge**: Merge the grids as usual

## Template File Format

The grid template is saved as a JSON file with the following structure:

```json
{
  "landmarkNodeName": "ManualLandmarks",
  "patches": [
    {
      "patchID": "0",
      "patchName": "gridPatch_0",
      "resolution": 7,
      "landmarkIndices": [0, 1, 2, 3]
    }
  ]
}
```

- `landmarkNodeName`: Name of the landmark node (for reference only)
- `patches`: Array of patch configurations
  - `patchID`: Unique identifier for the patch
  - `patchName`: Name of the patch
  - `resolution`: Grid resolution (number of rows/columns)
  - `landmarkIndices`: Array of 4 landmark indices used as corners (in order: 0-1-2-3 forming a closed curve)

## Important Notes

- **Landmark Order**: The landmark indices must correspond to the same anatomical points across all specimens
- **Manual Landmark Requirement**: This feature requires manual landmarks to be placed on both reference and target specimens
- **Automatic Association**: When you select a landmark node and merge grids, patches are automatically associated with the closest landmarks
- **Template Portability**: Templates can be reused across multiple specimens that share the same landmark configuration
- **Batch Processing**: This workflow enables batch processing of multiple specimens with pre-defined grid configurations

## Example Workflow

1. Reference specimen: Mouse skull with 20 manual landmarks
2. Create 3 grid patches covering different anatomical regions
3. Associate with landmark node and save template as `mouse_skull_grid_template.json`
4. For each new specimen:
   - Place the same 20 manual landmarks
   - Load the template to automatically recreate the 3 grid patches
   - Adjust if needed and merge

## See Also

- Example template: `Resources/example_grid_template.json`
- PlaceLandmarkGrid main documentation
