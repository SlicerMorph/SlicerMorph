## GEVolImport

### Summary
This module imports VOL files output by the GE/tome microCT scanner into 3D Slicer. It parses the PCR file to obtain the 3D image dimensions, voxel spacing, data format and other relevant metadata about the VOL file and generate a NHDR file to load the VOL file into Slicer.

### Usage
Click `...` button to and navigate to the **XXXXX.pcr** file, where XXXXX is the name of the VOL file you would like to import. It is assumed that the .VOL file resides in the same place as the .PCR file

### Output Files:
Hit the Generate NHDR button, this will create a NHDR file for you in the same directory of the PCR and VOL files to be able to load the volume next time, as well as immediately loading it into the active scene.

### Known Limitations:
Currently only FLOAT (32 bit), UNSIGNED 16 BIT INTEGER and UNSIGNED 8 BIT INTEGER data types are supported. Please contact us with a sample dataset to enable additional data types.
