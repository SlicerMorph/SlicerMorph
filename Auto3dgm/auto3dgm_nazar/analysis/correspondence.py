from numpy import linalg
from scipy.optimize import linear_sum_assignment
from scipy.spatial import distance_matrix, KDTree, distance
from scipy.optimize import linear_sum_assignment as Hungary
from scipy.sparse import csr_matrix, identity, find, lil_matrix, coo_matrix
from scipy.sparse.csgraph import minimum_spanning_tree, shortest_path
from scipy import sparse as sp
from scipy.sparse.linalg import norm
from scipy import square
import numpy as np
from pprint import pprint
from auto3dgm_nazar import jobrun
from auto3dgm_nazar.jobrun import jobrun
from auto3dgm_nazar.jobrun import job
from auto3dgm_nazar.jobrun.jobrun import JobRun
from auto3dgm_nazar.jobrun.job import Job
import os
file_path = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('MOSEKLM_LICENSE_FILE', os.path.join(file_path, '../lib/mosek.lic'))
import sys
import mosek
import pdb
from mosek.fusion import *
import scipy.io as sio

class Correspondence:
    #params: self,
    #meshes: either a mesh object or a list (should be list) or a dictionary of mesh objects
    #meshes: a list of meshes 
    #globalize: flag for performing globalized pairwise alignment (default:yes)
    #mirror: flag for allowing mirrored meshes (default: no)
    #reference_index= index of the mesh that other meshes are aligned against
    
    def __init__(self, meshes, globalize=1, mirror=0, initial_alignment=None):
        #assumes that meshes is an ordered list of meshes
        self.globalizeparam=globalize
        self.mirror=mirror
        self.meshes=meshes
        self.initial_alignment=initial_alignment
        if self.initial_alignment:
            self.initial_pa_alignment=self.localize()
        n = len(meshes)
        n_pts = meshes[0].vertices.shape[0]

        job_data = self.generate_job_data()
        job_params = self.generate_params()
        job_func = self.generate_func()

        new_job = Job(data=job_data, params=job_params, func=job_func)
        new_jobrun = JobRun(job=new_job)
        output = new_jobrun.execute_jobs()
        #dependent on changing line 52 from jobrun (job_dict['output']['results'].... -> job_dict['output'] = results_dict)
        #also depends on results_dict being in d->float, p->permutation r-> rotaiton mapping
        self.results_dict = output['output']
        
        self.d_ret = np.empty([n, n])
        #self.p_ret = np.empty([n, n, n_pts], dtype=int)
        self.p_ret = {}
        #what is permutation
        self.r_ret = np.array([[None for x in range(n)] for y in range(n)])


        for key in self.results_dict.keys():
            #key will be a tuple
            self.d_ret[key[0]][key[1]] = self.results_dict[key]['d']

            x = self.results_dict[key]['p']
            if key[0] not in self.p_ret:
                self.p_ret[key[0]] = {}
            self.p_ret[key[0]][key[1]] = self.results_dict[key]['p']

            self.r_ret[key[0]][key[1]] = self.results_dict[key]['r']
        self.pairwise_alignment = {'d': self.d_ret, 'r': self.r_ret, 'p': self.p_ret}    

        #print('+++++')
        #print(self.d_ret)
        #print(self.p_ret)
        #print(self.r_ret)

        if self.globalizeparam:
            self.mst_matrix = Correspondence.find_mst(self.d_ret)
            self.globalized_alignment = self.globalize(self.pairwise_alignment, self.mst_matrix)

    def localize(self):
        if not self.initial_alignment:
            return
        p = {}
        r = np.array([[None for x in range(len(self.initial_alignment['r']))] for y in range(len(self.initial_alignment['r']))])
        for i in range(0, len(self.initial_alignment['r'])):
            for j in range(0, len(self.initial_alignment['r'])):            
                r[i][j] = self.initial_alignment['r'][i].T @ self.initial_alignment['r'][j]
                if i not in p:
                    p[i] = {}
                p_temp = self.initial_alignment['p'][j] @ self.initial_alignment['p'][i].T
                p[i][j] = self.permutation_sparse_to_flat(p_temp)
        return {'r': r, 'p': p}


    def generate_job_data(self):
        ret = {}
        for indexf, first in enumerate(self.meshes):
            for indexs, second in enumerate(self.meshes):
                if not Correspondence.has_pair(indexf, indexs, ret):
                    if self.initial_alignment is None:
                        initial_alignment = None
                    else:
                        initial_alignment = {
                            'r': self.initial_pa_alignment['r'][indexf][indexs],
                            'p': self.initial_pa_alignment['p'][indexf][indexs]
                        }
                    val = Correspondence.dict_val_gen(first, second, initial_alignment=initial_alignment)
                    toopl = (indexf, indexs)
                    ret[toopl] = val
                
        return ret

    def generate_params(self):
            return {'mirror': self.mirror}

    def generate_func(self):
        return self.align


    @staticmethod
    def dict_val_gen(first, second, initial_alignment=None):
        return {'mesh1': first, 'mesh2': second, 'initial_alignment': initial_alignment}

    @staticmethod
    def has_pair(key1, key2, dictionary):
        tooplf = (key1, key2)
        toopls = (key2, key1)
        if (tooplf in dictionary.keys()) or (toopls in dictionary.keys()):
            #for testing, this has been set to False, Typically, should be set to True
            return False
        return False

    @staticmethod
    def find_mst(distance_matrix):
        return minimum_spanning_tree(csr_matrix(distance_matrix)).toarray()

    @staticmethod
    def graphshortestpaths(graph, index, reference):
        '''
        returns a [dist, pat] object with dist (double of distance between index and reference) and path (1xN vector representing path from reference->index)
        '''
        [dist_matrix, predecessors] = shortest_path(graph, return_predecessors=True)
        dist = dist_matrix[reference, index]
        pat = Correspondence.getpath(predecessors, index, reference)
        return [dist, pat]

    @staticmethod
    def globalize(pa, tree, base=0, type='mst'):
        '''
        takes a pairwise alignment (pa) formatted as a 3-entry array [D, R, P] and a tree (NP-matrix) and returns
        the global alignment obtained by propagating the tree as a list
        '''
        n = len(tree)
        tree = tree + tree.T
        [c, r] = np.nonzero(tree)
        mm = min(r[0], c[0])
        MM = max(r[0], c[0])
        pa_r = pa['r']
        pa_p = pa['p']
        N = pa_p[mm][MM].shape[0]

        retR = [None] * n
        retP = [None] * n

        if type is 'mst':
            for li in range(0, n):
                [dist, pat] = Correspondence.graphshortestpaths(tree+tree.transpose(), li, base)
                P = identity(N, dtype=int)
                R = np.identity(3)
                for lj in range(1, len(pat)):
                    if pat[lj-1] > pat[lj]:
                    #P = P @ Correspondence.permutation_flat_to_sparse(pa_p[pat[lj]][pat[lj-1]])
                        P = P @ pa_p[pat[lj]][pat[lj-1]]
                        R = pa_r[pat[lj], pat[lj-1]] @ R
                    else:
                        P = P @ pa_p[pat[lj-1]][pat[lj]].transpose()
                        R = pa_r[pat[lj-1], pat[lj]].transpose() @ R
                retR[li] = R
                retP[li] = P
        return {'r': retR, 'p': retP}               

    @staticmethod
    def getpath(predecessors, index, reference):
        ancestors = predecessors[reference]
        tracer=index
        ret=[]
        while(tracer != reference):
            ret.append(tracer)
            tracer = ancestors[tracer]
        ret.append(reference)
        #ret.reverse()
        return ret

    @staticmethod
    def permutation_flat_to_sparse(p):
        data = np.ones(p.shape[0], dtype=int)
        cols = np.array(range(0,p.shape[0]), dtype=int)
        return csr_matrix((data, (p, cols)), shape=(p.shape[0], p.shape[0]))

    @staticmethod
    def permutation_sparse_to_flat(p):
        return find(p)[0]

    @staticmethod
    # An auxiliary method for computing the initial pairwise-alignment
    # Computes the principal components of two meshes and all possible rotations of the 3-axes)
    # params: mesh1, mesh2 meshes that have vertices that are 3 x n matrices
    #        mirror: a flag for whether or not mirror images of the shapes should be considered
    def principal_component_alignment(mesh1, mesh2, mirror):
        X = mesh1.vertices.T
        Y = mesh2.vertices.T
        UX, DX, VX = linalg.svd(X, full_matrices=False)
        UY, DY, VY = linalg.svd(Y, full_matrices=False)
        P=[]
        R=[]

        P.append(np.array([1, 1, 1]))
        P.append(np.array([1, -1, -1]))
        P.append(np.array([-1, -1, 1]))
        P.append(np.array([-1, 1, -1]))
        if (mirror == 1):
            P.append(np.array([-1, 1, 1]))
            P.append(np.array([1, -1, 1]))
            P.append(np.array([1, 1, -1]))
            P.append(np.array([-1, -1, -1]))
        for i in P:
            R.append(np.dot(np.dot(UX, np.diag(i)), UY.T))
        return R
    
    '''
    @staticmethod
    # Computes the best possible initial alignment for meshes 1 and 2
    # Mesh 1 is used as the reference
    # params: mesh1, mesh2 meshes that have vertices that are 3 x n matrices
    #        mirror: a flag for whether or not mirror images of the shapes should be considered
    def best_pairwise_PCA_alignment(mesh1, mesh2, mirror):
        #print(mesh1.name)
        #print(mesh2.name)
        R = Correspondence.principal_component_alignment(mesh1, mesh2, mirror)
        M_0 = np.ones([len(mesh1.vertices), len(mesh1.vertices)])
        permutations = []
        min_cost = np.ones(len(R)) * np.inf
        for rot, i in zip(R, range(len(R))):
            cost = distance_matrix(mesh1.vertices, np.dot(rot, mesh2.vertices.T).T)**2
            # The hungarian algorithm:
            P, d = Correspondence.linassign(M_0, cost)
            min_cost[i] = d
            print('eight rotation error is', np.sqrt(d))
            permutations.append(P)

        best_rot_ind = np.argmin(min_cost)
        best_permutation = permutations[best_rot_ind]
        best_rot = R[best_rot_ind]
        d = min_cost[best_rot_ind]

        return {'p': best_permutation, 'r': best_rot, 'd': d}
    '''

    @staticmethod
    # Returns the meshed aligned by the initial PCA component pairing.
    # Everything is aligned against the mesh specified by the reference_index
    def initial_rotation(self):
        mesh1 = self.mesh_list[self.reference_index]
        Rotations = []
        for i in self.mesh_list:
            Rotations.append(self.best_pairwise_PCA_alignment(mesh1, i, self))
        return Rotations

    @staticmethod
    def permutation_from_rotation(mesh1, mesh2, R):
        #cost = distance_matrix(mesh1.vertices, np.dot(R, mesh2.vertices.T).T)**2
        # The hungarian algorithm:
        #M_0 = np.ones([len(mesh1.vertices), len(mesh1.vertices)])
        #P, d = Correspondence.linassign(M_0, cost)
        V1 = mesh1.vertices.T
        V2 = mesh2.vertices.T
        gamma = 1.5 * Correspondence.ltwoinf(V1.T - np.dot(R, V2).T)
        M, MD2 = Correspondence.jrangesearch(V1.T, np.dot(R, V2).T, gamma)
        P, d = Correspondence.linassign(M, MD2)
        return P, d

    @staticmethod
    # Computes the Local Generalized Procrustes Distance between meshes.
    # NOTE: Params R_0, M_0 needs specification.
    def locgpd(mesh1, mesh2, R_0=None, M_0=None, max_iter=1000, mirror=False):
        # print out which mesh to work with
        #print(mesh1.name)
        #print(mesh2.name)
        # number of vertices
        N = len(mesh1.vertices)
        # V1 and V2 are of size 3 * N
        V1 = mesh1.vertices.T
        V2 = mesh2.vertices.T
        if M_0 is None:
            M_0 = np.ones([N, N])
        # compute distance
        D = distance.cdist(V1.T, np.dot(R_0, V2).T)
        MD2 = square(D)
        # compute initial mappings and correspondences
        P_0, trash = Correspondence.linassign(M_0, MD2)
        # compute loops
        P = P_0; R = R_0; d = np.linalg.norm(V1 - np.dot(R, V2@P));
        P_prev = sp.eye(N); gamma = 0;
        i = 0;
        while np.linalg.norm((abs(P-P_prev).sum(axis=0)).sum(axis=1)) > 0:
            # norm(P - P_prev) 
            i += 1
            P_prev = P; R_prev = R; d_prev = d;
            # Do Kabsch
            newV2 = V2 @ P_prev
            R = Correspondence.Kabsch(V1.T, newV2.T)
            d = np.linalg.norm(V1 - np.dot(R, newV2))
            # Do Hungary
            gamma = 1.5 * Correspondence.ltwoinf(V1 - np.dot(R, newV2))
            M, MD2 = Correspondence.jrangesearch(V1.T, np.dot(R, V2).T, gamma)
            P, trash = Correspondence.linassign(M, MD2)
            #d = np.linalg.norm(V1 - np.dot(R, V2@P))

            if i > max_iter or abs(d_prev-d)< (0.00001 * d_prev):
                break
            else:
                if i % 100 == 0:
                    print("Current error is: ", d)
        return {'d': d, 'r': R, 'p': P, 'g': gamma}

    @staticmethod
    def gpd(mesh1, mesh2, mirror=False):
        R_0 = Correspondence.principal_component_alignment(mesh1, mesh2, mirror)
        M_0 = np.ones([len(mesh1.vertices), len(mesh1.vertices)])
        tst_P = []
        tst_R = []
        tst_d = np.ones(len(R_0)) * np.inf
        tst_gamma = np.ones(len(R_0)) * np.inf
        
        for rot, i in zip(R_0, range(len(R_0))):
            temp = Correspondence.locgpd(mesh1=mesh1, mesh2=mesh2, R_0=rot, M_0=M_0, max_iter=1000, mirror=False)
            tst_P.append(temp['p'])
            tst_R.append(temp['r'])
            tst_d[i] = temp['d']
            tst_gamma[i] = temp['g']
            
        best_ind = np.argmin(tst_d)
        P = tst_P[best_ind]
        R = tst_R[best_ind]
        d = tst_d[best_ind]
        gamma = tst_gamma[best_ind]
        return {'d': d, 'r': R, 'p': P, 'g': gamma}
        
    @staticmethod
    def ltwoinf(X):
        """l2-inf norm of x, i.e.the maximum 12 norm of the columns of x"""
        d = np.sqrt(max(np.square(X).sum(axis=0)))
        return d

    @staticmethod
    def Kabsch(A, B):
        assert len(A) == len(B)

        N = A.shape[0]  # total points

        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)

        # centre the points
        AA = A - np.tile(centroid_A, (N, 1))
        BB = B - np.tile(centroid_B, (N, 1))

        # dot is matrix multiplication for array
        H = np.dot(AA.T, BB)
        U, S, Vt = linalg.svd(H)
        R = np.dot(U, Vt)
        return R

    '''
    @staticmethod
    def align(mesh1, mesh2, mirror, initial_alignment=None):
        n = len(mesh1.vertices)
        if not initial_alignment:
            initial_alignment = Correspondence.best_pairwise_PCA_alignment(mesh1=mesh1, mesh2=mesh2, mirror=mirror)
        return Correspondence.locgpd(mesh1=mesh1, mesh2=mesh2, R_0=initial_alignment['r'], M_0=np.ones((n, n)), mirror=mirror)
    '''
    
    @staticmethod
    def align(mesh1, mesh2, mirror, initial_alignment=None):
        n = len(mesh1.vertices)
        if not initial_alignment:
            return Correspondence.gpd(mesh1=mesh1, mesh2=mesh2, mirror=mirror)
        else:
            return Correspondence.locgpd(mesh1=mesh1, mesh2=mesh2, R_0=initial_alignment['r'], M_0=np.ones((n, n)), mirror=mirror)
    
    @staticmethod
    def jrangesearch(X,Y,epsilon):
        D = distance.cdist(X, Y)
        MD2full = square(D)
        r, c, v = find(D<epsilon)
        dM = np.ones(r.shape)
        dMD2 = MD2full[r,c]
        I = X.shape[0]
        M = sp.csr_matrix((dM, (r, c)),shape=(I,I))
        MD2 = sp.csr_matrix((dMD2, (r, c)),shape=(I,I))
        return (M, MD2)
    
    
    '''
    @staticmethod
    def ltwoinf(X):
        Y = np.sqrt(max(np.sum(np.multiply(X,X),axis=0)))
        return Y
    '''

    @staticmethod
    def linassign(A, D):
        N = A.shape[0]
        if not sp.isspmatrix(A):
            #print('nonSparseHungary')
            rowId, colId = Hungary(D)
            P = sp.coo_matrix((np.ones(N),(rowId,colId)),shape=(N, N))
            P = P.T
            d = D[rowId, colId].sum()
        else:
            if np.array_equal(A.todense(), np.ones((N, N))):
                #print('Hungary')
                rowId, colId = Hungary(D.todense())
                P = sp.coo_matrix((np.ones(N),(rowId,colId)),shape=(N, N))
                P = P.T
                d = D[rowId, colId].sum()
            elif np.array_equal(A.todense(), np.zeros((N, N))):
                P = sp.eye(N)
                d = 0
            else:
                #use mosek to speed up
                ### identify number of variables
                #print('Mosek')
                #print(D)
                tmpD = np.reshape(D, (1, N*N))
                zerovars, ivars, dissimilarity_for_lp_red = find(tmpD)
                n_vars = ivars.shape[0]
                
                ### build the constraint matrix A indicating all rows and columns of P should sum to 1
                Aeq1 = sp.kron(sp.eye(N), np.ones(N))
                Aeq2 = sp.kron(np.ones(N), sp.eye(N))
                Aeq = sp.vstack([Aeq1, Aeq2])
                
                ### convert to csc matrix and reduce size
                Aeq = Aeq.tocsc()
                Aeq_red = Aeq[:, ivars]
                rows, cols, values = find(Aeq_red)
                
                ### send to mosek optimization
                with Model('example') as M:
                    # Create variable 'x' of length n_vars
                    x = M.variable("x", n_vars, Domain.greaterThan(0.))
                    # Create constraints
                    A = Matrix.sparse(2*N, n_vars, rows, cols, values)
                    M.constraint(Expr.mul(A, x), Domain.equalsTo(1.))
                    # Set the objective funciton to (c^t * x)
                    c = dissimilarity_for_lp_red
                    M.objective("obj", ObjectiveSense.Minimize, Expr.dot(c, x))
                    # Solve the problem
                    M.solve()
                    #Get the solution values
                    sol = x.level()
                # retrive solution
                P_red = sol
                d = np.dot(c, sol)
                # iron the numerical wrinkles
                P_red[sol<0.1] = 0
                temp1 = np.zeros(n_vars)
                tempP = sp.csr_matrix((P_red, (ivars, temp1)),shape=(N*N,1))
                tempP.shape
                P = np.reshape(tempP, (N, N))
                P = P.T
        return (P, d)



