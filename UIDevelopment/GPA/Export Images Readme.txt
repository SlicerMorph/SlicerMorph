Export Images Readme

After the module has been linked it will appear in the large list of modules.

To Use:
 Select a view and render mode.  Be careful to only check one box.  The select and input and output directory.  Then hit the apply button.  

The Result:
 A folder will be created in the specified output directory.  If the folder already exist, existing images in the folder will be over written if the file names are the same.  The output png file will be written to this folder.  The naming convention is name_of_mrml_file_ViewLetter.png.  Where the ViewLetter is a single capital letter corresponding to the view chosen.

Be Careful of:
 1. If writing to an existing folder, existing images may be overwritten.
 2. Make sure you have write privileges in the output directory, otherwise the code will fail.
 3. Only check on View box and one Render Mode box.  If more are checked it will select the latter.
 4. If you do not select and input and output directory, the code will fail.

Warnings:
 If the code fails, all warnings and errors can be viewed by opening the Slicer python interactor.
