#!/usr/bin/env python
# coding: utf-8

# In[183]:


## Meta Data
# Barak and Shan Shan are trying to auto3dgm!@#$% Nov 28 2018

## Imports
import numpy as np
from numpy import *
from scipy import linalg as LA
from scipy.spatial import distance_matrix, KDTree
from scipy.optimize import linear_sum_assignment as Hungary
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


## Functions
def SubSample(V, n_sub):
    '''
    This function performs farthest points subsampling
    V - vertices from which we wish to sub-sample
    n_sub - number of subsamples
    '''
    D = V.shape[0] # the dimension
    N = V.shape[1] # number of samples
    
    # container for the result
    subsample_indices = np.zeros(n_sub, dtype = np.int) - 1
    
    # Create a search tree
    neighbor_tree = KDTree(V.T)
    
    # create an initial seed
    tmp = V[:,np.random.randint(N)][np.newaxis]
    Dists = distance_matrix( V.T, tmp)
    seed_ind = np.argmax( Dists )
    seed = V[:, seed_ind]
    subsample_indices[0] = seed_ind
    p = seed[np.newaxis]
    # Now iterate for farthest point
    for i in range(1, n_sub):
        newDists = distance_matrix( V.T, p)
        Dists = np.minimum(Dists, newDists)
        max_i = np.argmax( Dists )
        subsample_indices[i] =  max_i
        p = V[:, max_i][np.newaxis]
    return subsample_indices
    
def PrincipalComponentAlignment(X, Y, ref):
    '''
    Aligning the sets of vertices according to PCs
    ref - a boolean indicating weather we wish to account for reflections
    '''
    UX, DX, VX = LA.svd(X, full_matrices = False);
    UY, DY, VY = LA.svd(Y, full_matrices = False);
    
    # going over all possible reflections
    R = []
    if ref:
        R.append(np.dot(UX*np.array( [ 1., 1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., -1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ 1., -1., -1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., 1., -1.] ),UY.T))
    else:
        R.append(np.dot(UX*np.array( [ 1., 1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., 1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ 1., -1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ 1., 1., -1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., -1., 1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ 1., -1., -1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., 1., -1.] ),UY.T))
        R.append(np.dot(UX*np.array( [ -1., -1., -1.] ),UY.T))
    return R

def Kabsch(A, B):
    assert len(A) == len(B)

    N = A.shape[0] # total points

    centroid_A = mean(A, axis=0)
    centroid_B = mean(B, axis=0)
    
    # centre the points
    AA = A - np.tile(centroid_A, (N, 1))
    BB = B - np.tile(centroid_B, (N, 1))

    # dot is matrix multiplication for array
    H = np.dot(AA.T, BB)

    U, S, Vt = LA.svd(H)

    R = np.dot(Vt.T, U.T)
    # # special reflection case
    # if linalg.det(R) < 0:
    #     print("Reflection detected")
    #     Vt[-1,:] *= -1
    #     R = Vt.T * U.T
    return R

## Constants
N1 = 10
N2 = 15
D = 3
N_SUB1 = 5 
N_SUB2 = 5
bSCALE = True
MAX_ITER = 1
THRESH = 1

## Data
# np.random.seed(0)
V1 = np.random.rand(D, N1)
V2 = np.random.rand(D, N2)

### Action Script
## step 1 - Subsample step
# center and scale
if bSCALE:
    a1 = np.mean(V1, axis=1)
    b1 = np.matlib.repmat(a1, N1, 1)
    V1 = V1 - b1.T
    a2 = np.mean(V2, axis=1)
    b2 = np.matlib.repmat(a2, N2, 1)
    V2 = V2 - b2.T
    V1 = V1/np.max(np.linalg.norm(V1,axis=0))
    V2 = V2/np.max(np.linalg.norm(V2,axis=0))
# now subsample V1
sub_ind1 = np.array(SubSample(V1, N_SUB1), dtype = np.int)
V1_sub = V1[:,sub_ind1]
a1 = np.mean(V1_sub, axis=1)
b1 = np.matlib.repmat(a1, N_SUB1, 1)
V1_sub = V1_sub - b1.T
V1_sub = V1_sub/np.max(np.linalg.norm(V1_sub,axis=0))
V1_subsub = V1[:,sub_ind1[:N_SUB2]]
# now subsample V2
sub_ind2 = np.array(SubSample(V2, N_SUB1), dtype = np.int)
V2_sub = V2[:,sub_ind2]
a2 = np.mean(V2_sub, axis=1)
b2 = np.matlib.repmat(a2, N_SUB1, 1)
V2_sub = V2_sub - b2.T
V2_sub = V2_sub/np.max(np.linalg.norm(V2_sub,axis=0))
V2_subsub = V2[:,sub_ind2[:N_SUB2]]

## step 1 - Align and Register
R = PrincipalComponentAlignment(V1_sub, V2_sub, ref=False)
min_cost = np.ones(len(R))*np.inf
permutations = []
for rot, i in zip(R, range(len(R))):
    cost = distance_matrix(V1_sub.T, np.dot(rot, V2_sub).T)
    V1_ind, V2_ind = Hungary(cost)
    min_cost[i] = np.sqrt(np.sum(cost[V1_ind, V2_ind])) # the actual cost of the permutation found
    permutations.append(V2_ind)

best_rot_ind = np.argmin(min_cost)
best_permutation = permutations[best_rot_ind]
best_rot = R[best_rot_ind]

newV2_sub = np.dot(best_rot.T, V2_sub)
i = 0
while True:
    newV2_sub = newV2_sub[:,best_permutation]
    # Do Kabsch
    cur_rot = Kabsch(newV2_sub.T, V1_sub.T)
    newV2_sub = np.dot(cur_rot.T, newV2_sub)
    print("after Kab cost = ", np.linalg.norm(V1_sub - newV2_sub))
    # Do Hungary
    cur_cost = distance_matrix(V1_sub.T, newV2_sub.T)
    cur_V1_ind, cur_permutation = Hungary(cur_cost)
    #print(cur_permutation)
    print("after Hungary cost = ", np.sqrt(np.sum(cur_cost[cur_V1_ind, cur_permutation]**2)))
    if np.sum((cur_permutation - best_permutation) != 0) < THRESH or i>MAX_ITER:
        break
    else:
        if i % 100 == 0:
            #print("Current error is: ", np.sum((cur_permutation - best_permutation) != 0))
            print("current iteration is:", i)
    # update
    best_permutation = cur_permutation
    best_rot = cur_rot
    i += 1
        


# In[179]:


#V1 = np.random.rand(3, 3)
#a1 = np.mean(V1, axis=1)
#b1 = np.matlib.repmat(a1, 3, 1)
#V1 = V1 - b1.T

#R = mat(random.rand(3,3))
#U, S, Vt = np.linalg.svd(R)
#R = U*Vt

#V2 = R*V1
V2_sub = np.dot(best_rot, V2_sub)
err = V1_sub - V2_sub
err = multiply(err, err)
err = sum(err)
print ("RMSE:", err)
print ("If RMSE is near zero, the function is correct!")


fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(V1_sub[0], V1_sub[1], V1_sub[2], c = 'r', marker = 'o')
ax.scatter(V2_sub[0], V2_sub[1], V2_sub[2], c = 'b', marker = '^')

plt.show
