from auto3dgm_nazar.mesh.meshfactory import MeshFactory
from numpy import array, zeros

def print_polyfaces(polydata):
    cell_n = polydata.GetNumberOfCells()
    point_n = polydata.GetCell(1).GetNumberOfPoints()
    faces_new = zeros((cell_n, point_n), dtype=int)
    for i in range(cell_n):
        print('cell/polygon ' + str(i))
        for j in range(point_n):
            print(polydata.GetCell(i).GetPointId(j))

vertices = array([[0, 0, 0],[1, 0, 0],[1, 1, 0],[0, 1, 0],[2, 2, 1]], dtype=int)
faces = array([
	[0, 1, 2],
	[1, 2, 3],
	[1, 3, 4],
  [2, 3, 0]], dtype=int)

mesh = MeshFactory.mesh_from_data(vertices, faces, False)

print(mesh)
print(mesh.vertices)
print(mesh.faces)

"""
Print output should look like this:

<auto3dgm.mesh.mesh.Mesh object at 0x1048962b0>
[[0. 0. 0.]
 [1. 0. 0.]
 [1. 1. 0.]
 [0. 1. 0.]
 [2. 2. 1.]]
[[0 1 2]
 [1 2 3]
 [1 3 4]
 [2 3 0]]
"""


