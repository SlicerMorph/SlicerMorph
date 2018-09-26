BMP  ToolBox Readme:

After the module has been linked it will appear in the Maga Lab module folder.

To Use:
Select an bmp image sequence to import using the ‘Select Input Image Sequence’  button.  Check boxes to select image adjustments.  Click apply when ready.  It can take a minute to run.  During this time Slicer may appear frozen.  Up to four input image sequances can be accepted.  

Be Careful of:
Make sure the image sequence is sequentially names.  If not, it will not import.

Image Adjustments :
If selected the following adjustments are made.
	1. The window level range is set to [0,256]
	2. The scalar opacity function has two points added, (mean +standard deviation, 0) and (mean +2*standard 		deviation, 1)
	3. The color transfer function is adjusted to have three points; (0, black), (mean +2*standard deviation), 	   (256,white)

Note: The mean and standard deviation are calculated from the histogram of the whole volume.
