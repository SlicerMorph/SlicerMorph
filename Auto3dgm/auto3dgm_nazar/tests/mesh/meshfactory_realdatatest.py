#Test script for the mesh factory
from auto3dgm_nazar.mesh.meshfactory import MeshFactory

#Test case 0: Giving out a non-sense file
#Conditions: filestring refers to a non existing file
#Expect: When I try to create a mesh, I get an error
filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/Non-existing file.ply'
MeshFactory.mesh_from_file(filestring)

'''
In [27]: filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/Non-existing file.ply'

In [28]: MeshFactory.mesh_from_file(filestring)
---------------------------------------------------------------------------
OSError                                   Traceback (most recent call last)
<ipython-input-28-dce76620cc80> in <module>()
----> 1 MeshFactory.mesh_from_file(filestring)

/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/gitstuff/auto3dgm/auto3dgm/mesh/meshfactory.py in mesh_from_file(file_path)
     52             msg = 'File {} not present or not allowed filetype: {}'.format(
     53                 file_path, ', '.join(allowed_filetypes))
---> 54             raise OSError(msg)
     55 
     56     @staticmethod

OSError: File /home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/Non-existing file.ply not present or not allowed filetype: .ply, .obj, .stl
'''
# Result: Success!

#Test case 1: Giving out an invalid
#Conditions: filestring refers to a file type not supported
#Expect: When I try to create a mesh, I get an error
filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/.off'
MeshFactory.mesh_from_file(filestring)

'''
In [29]: filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/.off'

In [30]: MeshFactory.mesh_from_file(filestring)
---------------------------------------------------------------------------
OSError                                   Traceback (most recent call last)
<ipython-input-30-dce76620cc80> in <module>()
----> 1 MeshFactory.mesh_from_file(filestring)

/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/gitstuff/auto3dgm/auto3dgm/mesh/meshfactory.py in mesh_from_file(file_path)
     52             msg = 'File {} not present or not allowed filetype: {}'.format(
     53                 file_path, ', '.join(allowed_filetypes))
---> 54             raise OSError(msg)
     55 
     56     @staticmethod

OSError: File /home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/.off not present or not allowed filetype: .ply, .obj, .stl
'''
# Result: Success!

#Test case 2: Giving a valid .ply file
#Conditions: filestring refers to an existing supported file
#Expect: When I try to create a mesh, a mesh is successfully created
filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/12144_U02_Eosimias_crop-smooth.ply'
MeshFactory.mesh_from_file(filestring)


'''
In [12]: filestring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/12144_U02_Eosimias_crop-smooth.ply'

In [13]: MeshFactory.mesh_from_file(filestring)
<class 'vtkCommonDataModelPython.vtkPolyData'>
Out[13]: <auto3dgm.mesh.mesh.Mesh at 0x7f85c374fa58>

'''

# Result: Pass


