## ImportFromURL
**Summary:** Imports any Slicer supported dataset (3D models, volumes, markups etc) from the provided URL. It assumes the file name and extension are available as part of the URL or the correct data format is known.  

### USAGE
**URL:** Paste the URL to be retrieved (e.g., https://github.com/SlicerMorph/SampleData/blob/master/4074_skull.vtk?raw=true). Both **File Name** and **Node Name** will be automatically populated. 

### KNOWN ISSUES
URL must contain the file name and extension for the data to be correctly loaded. However, if URL doesn't have the file name, but the data format is known (e.g., ply), then the user can edit the **File Name** and **Node Name** fields manually to create an arbitrary file name with the known extension. 


