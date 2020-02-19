#Test script for the dataset factory
from auto3dgm_nazar.dataset.datasetfactory import DatasetFactory

#Test case 1:
#Conditions: directorystring refers to an invalid directory
#Action: I try to create a dataset using the directory string
#Expected result: I get and error
directorystring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY'
DatasetFactory.ds_from_dir(directorystring)

"""
In [1]: #Test script for the dataset factory

In [2]: from auto3dgm.dataset.datasetfactory import DatasetFactory

In [3]: 

In [3]: #Test case 1:

In [4]: #

In [5]: directorystring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY'

In [6]: DatasetFactory.ds_from_dir(directorystring)
---------------------------------------------------------------------------
OSError                                   Traceback (most recent call last)
<ipython-input-6-ca24c7604382> in <module>()
----> 1 DatasetFactory.ds_from_dir(directorystring)

/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/gitstuff/auto3dgm/auto3dgm/dataset/datasetfactory.py in ds_from_dir(directorystring, ftype)
     12         if not files:
     13             msg = 'No .'+ftype+' files were found in '+path
---> 14             raise OSError(msg)
     15         meshes=[]
     16         for file in files:

OSError: No .ply files were found in /home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY
"""
#Result: Pass

#Test case 2:
#Conditions: directorystring refers to a valid directory containing supported files
#Action: I try to create a dataset using the directorystring
#Expected result: A dataset is created
directorystring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/'
DatasetFactory.ds_from_dir(directorystring)


"""
In [7]: 

In [7]: #Test case 2:

In [8]: directorystring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/'

In [9]: DatasetFactory.ds_from_dir(directorystring)
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
Out[9]: <auto3dgm.dataset.dataset.Dataset at 0x7f85c374fba8>


"""

#Result: Pass
