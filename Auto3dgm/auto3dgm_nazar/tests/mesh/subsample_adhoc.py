from auto3dgm_nazar.mesh.meshfactory import MeshFactory
from auto3dgm_nazar.mesh.subsample import Subsample
from numpy import array

vertices = array([[0, 0, 0],[1, 0, 0],[1, 1, 0],[0, 1, 0],[2, 2, 1]])
seed = vertices[[1,4]]

mesh = MeshFactory.mesh_from_data(vertices)

submesh_noseed = Subsample.far_point_subsample(mesh, 4)
print(submesh_noseed)
print(submesh_noseed.vertices)
print(submesh_noseed.faces)

submesh_seed = Subsample.far_point_subsample(mesh, 4, seed)
print(submesh_seed)
print(submesh_seed.vertices)
print(submesh_seed.faces)

"""

Print results for first set will be random, but second set will be stable

Print results should look something like this:
<auto3dgm.mesh.mesh.Mesh object at 0x117cd5518>
[[0 0 0]
 [2 2 1]
 [1 1 0]
 [1 0 0]]
[]
<auto3dgm.mesh.mesh.Mesh object at 0x10f5e31d0>
[[1 0 0]
 [2 2 1]
 [0 1 0]
 [0 0 0]]
[]
"""