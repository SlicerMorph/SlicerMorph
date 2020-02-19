from auto3dgm.mesh.meshfactory import MeshFactory

#Another test for the off files:
#Setup: There is a valid off file tooth.off
a=MeshFactory.mesh_from_file("tooth.off")
"""
<class 'vtkCommonDataModelPython.vtkPolyData'>
"""

a.vertices
"""
array([[ 23.1074,  12.3061,  44.2893],
       [ 23.1281,  12.3142,  44.2809],
       [ 23.1233,  12.296 ,  44.2963],
       ..., 
       [ 22.2795,  14.2197,  47.1709],
       [ 22.2679,  14.236 ,  47.1686],
       [ 22.232 ,  14.2798,  47.163 ]])
"""

# This fails currently, but is not a show stopper
a.faces
"""
array([], shape=(0, 3), dtype=float64)
"""