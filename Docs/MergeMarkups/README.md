## MergeMarkups
**Summary:** This module provides various utilities regarding tagging and exporting semiLMs points from SlicerMorph for shape analysis. 

### USAGE

**Merge Curves:** This mode allows merging individual open curve nodes into a single Markups node (and eventually to a single file). To merge them, click and highlight the open curve nodes that are presented in the table. Note curves will be merged in the order they are shown in the table. You can change the ordering by dragging  individual curve nodes up and down in the list. If separate curves represent a continuous curve, choose **Contiuous curves** option. This will remove the first semiLM from the second (and subsequent curves) so that there is no redundant point. Click **Merge  highligted nodes** to finalize. If you want to save the file merged node, use the ExportAs module.

**Merge LandmarkSets:** This mode allows combining fixed LM and semiLM sets into a single Markups node, while setting the description of each point to either Fixed (manual or anatomical LMs) or Semi (semi or pseudo landmarks). This can be useful for shape analysis that treat fixed and semiLM differently (for example sliding the semiLMs). To tag individual markup nodes as semi or fixed, highlight in the viewer, choose the appropriate description to apply from the drop-down mene and hit **Apply to highlighted nodes**.   

Once the nodes are appropriately tagged, you can highlight the nodes and hit the **Merge Highlighted nodes** button to create a new node that will contain all the points in selected nodes. Note nodes will be merged in the order they are displayed. You can modify the ordering.  If you want to save the merged node, use the ExportAs module.

**Batch Merge LandmarkSets:** This mode allows the same functionality of **Merge Landmark Sets** mode to be applied to landmark files that are already saved to disk in bulk. Simply select the files for fixed landmarks and semi landmarks separately. Similar to the interactive mode, ordering of files matter. Make sure corresponding file pairs are in the same rank at each table. Choose an output folder and hit **Merge fixed and semi-landmark nodes** button to save the new files. If you want to restart, hit the **Clear landmark file selections**. 
