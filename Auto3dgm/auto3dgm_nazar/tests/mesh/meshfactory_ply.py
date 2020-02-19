from auto3dgm_nazar.mesh.meshfactory import MeshFactory

filestring='../fixtures/int_vertex_super_simple.ply'
m = MeshFactory.mesh_from_file(filestring)

print(m)
print(m.vertices)
print(m.faces)

"""
Print output should look like this:

<class 'vtkCommonDataModelPython.vtkPolyData'>
<auto3dgm.mesh.mesh.Mesh object at 0x10f8c85f8>
[[0. 1. 2.]
 [1. 2. 3.]
 [2. 3. 4.]
 [3. 4. 5.]
 [4. 5. 6.]
 [5. 6. 7.]]
[[0 1 2]
 [0 2 3]
 [4 5 6]]
"""