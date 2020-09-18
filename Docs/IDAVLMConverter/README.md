## IDAVLMConverter
This module converter raw landmark coordinates (.pts format) exported from the IDAV Landmark Editor into fcsv format. It does not accept the Landmark Editor's project files (.land format). 
It should be noted that the 3D Models and coordinates exported from the IDAV Landmark Editor are in RAS coordinate system. By default, Slicer assumes all 3D models to be saved in LPS coordinate, unless explicitly stated. The coordinate system assumption for a 3D model can be changed during the load time by setting the  coordinate system  option from **default** to **RAS**
