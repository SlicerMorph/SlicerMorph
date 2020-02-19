# A very simple test script for the locgpd functionality
from auto3dgm_nazar.dataset.datasetfactory import *
from auto3dgm_nazar.analysis.correspondence import Correspondence
from auto3dgm_nazar.mesh.meshfactory import MeshFactory
import numpy as np

# Two meshes. Note that B is obtained from A via permutation (123): x goes to y, y goes to z, z goes to x.
# So the rotation matrix should look like
# [0	1	0]
# [0	0	1]
# [1	0	0]

A=np.array([[3,1,2],[10,7,2],[7,3,3],[18,3,0]])
B=np.array([[2,3,1],[2,10,7],[3,7,3],[0,18,3]])

class Pseudomesh:
    def __init__(self,A):
        self.vertices=A

T=Pseudomesh(A)
D=Pseudomesh(B)
mesh1=T
mesh2=D
a=[T,D]

BB=Correspondence.best_pairwise_PCA_alignment(mesh1, mesh2,0)
AA=Correspondence.locgpd(mesh1,mesh2,0,0,5,0)

print(BB)
'''
In [36]: BB
Out[36]: 
(array([0, 1, 2, 3]),
 array([[  1.38777878e-16,   1.00000000e+00,   2.49800181e-16],
        [ -1.11022302e-16,  -3.60822483e-16,   1.00000000e+00],
        [  1.00000000e+00,  -1.38777878e-17,   1.66533454e-16]]))

'''
print(AA[1])
'''
Out[40]: 
array([[  4.49640325e-15,   1.00000000e+00,  -3.87190280e-15],
       [ -3.94129174e-15,   3.94129174e-15,   1.00000000e+00],
       [  1.00000000e+00,  -4.38538095e-15,   4.21884749e-15]])

'''
# So the alignment works as expected. However, when we integrate the mesh class:

mesh1=MeshFactory.mesh_from_data(A)
mesh2=MeshFactory.mesh_from_data(B)

BB=Correspondence.best_pairwise_PCA_alignment(mesh1, mesh2,0)
print(BB)
'''
Out[45]: 
(array([3, 1, 2, 0]), array([[ 0.18660992, -0.95001991, -0.25027765],
        [ 0.02395067, -0.25027765,  0.96787781],
        [ 0.9821421 ,  0.18660992,  0.02395067]]))

'''

AA=Correspondence.locgpd(mesh1,mesh2,0,0,5,0)

print(AA[1])
'''
Out[46]: 
array([[ 0.71252281,  0.70142588,  0.01769116],
       [-0.65124992,  0.65174907,  0.38871159],
       [ 0.26112217, -0.28848724,  0.92118962]])

'''
# The PCA gives now weird results, and the locgpd goes completely haywire

