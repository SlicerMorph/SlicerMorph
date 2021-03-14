## MorphoSourceImport module is currently non-functional as MorphoSource is testing a new API as part of their v2.0 beta release. Once MorphoSource v2.0 goes full production, we will update the module.

## MorphoSourceImport
**Summary:** This module enables to query and download <a href="https://docs.google.com/spreadsheets/d/1fhdVv2JwvUJAC4dvSgKZi2pwSl7dPGaB-ksYsB64k4U/edit#gid=0"> publicly available 3D meshes</a> from MorphoSource website directly into the Slicer. The user has to register with the MorphoSource website. 

### USAGE

**MORPHOSOURCE**\
Enter you username and password as registered with the website and hit **Log in**. When successfully logged into MorphoSource, **"Attempting log in: True"** message will be displayed in the Python console.

**QUERY PARAMETERS**\
**Order:** Enter the order you would like to query using the same taxonomy as in mesh list cited above. Wild card `*` can be used (e.g. `Carnivora` or `Carni*`)\
**Element:** Enter the element you would to query (e.g., Humerus) as specified in the mesh list cited above. Wild card `*` can be used (e.g. `Humerus` or `Humer*`)\


**QUERY RESULTS**\
Table will populated with the returned hits. If no hits were found, a **"No download links found for query"** warning message displayed in the Python window. In that case, broaden your search parameters or use wild cards.

**Open Specimen Page:** User can highlight a single row and navigate to the specific specimen page on the MorphoSource website using the internal web browser.\
**Load Selected Model(s):** Multiple rows can be highlighted to download models directly into the scene.\ 


**LIMITATIONS:** Query returns only the first 1000 results. Order names needs to spelled exactly as indicated on the Only publicly available mesh models are queried or retrieved. For volume and raw dataset, please download them directly from MorphoSource website after agreeing to their use policy. You can use the `ImageStacks` module to import volume datasets.  

### TUTORIAL
Please see https://github.com/SlicerMorph/S_2020/blob/master/Day_1/MorphoSourceImport/MorphoSourceImport.md






