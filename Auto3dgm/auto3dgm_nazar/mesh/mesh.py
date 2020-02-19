import numpy as np
from vtk.util.numpy_support import vtk_to_numpy # calling vtk_to_numpy doesn't work
import vtk
import math
#import vtkCenterOfMass
#from pdb import set_trace as bp

class Mesh:
    #params: self, and a VTK Object called vtk_mesh
    def __init__(self, vtk_mesh, center_scale=False, name=None):
        self.polydata = vtk_mesh
        self.name = name
        self.initial_centroid = self.centroid
        self.initial_scale = self.scale
        
        if center_scale:
            self.center()
            self.scale_unit_norm()

    ''' we don't have to use getters like this, but using it in this case bc 1) 
    attributes are now pointers and don't have to be updated, 2) can't be 
    overwritten arbitrarily but we could create a setter so that any 
    update goes into the polydata object '''
    @property 
    def vertices(self):
        return vtk_to_numpy(self.polydata.GetPoints().GetData())

    @property
    def get_name(self):
        return self.name

    ''' I wrote ugly code here, but vertex IDs are better than raw per-face point 
    coordinates and VTK does not make getting this easy '''
    @property
    def faces(self):
        cell_n = self.polydata.GetNumberOfCells()
        if cell_n:
            point_n = self.polydata.GetCell(0).GetNumberOfPoints()
            faces = np.zeros((cell_n, point_n), dtype=int)
            for i in range(cell_n):
                for j in range(point_n):
                    faces[i, j] = self.polydata.GetCell(i).GetPointId(j)
            return faces
        else:
            return np.empty([0,3])

    @property
    def centroid(self):
        '''average of all vertices'''
        center = vtk.vtkCenterOfMass()
        center.SetInputData(self.polydata)
        center.SetUseScalarsAsWeights(False)
        center.Update()
        return center.GetCenter()

    @property
    def scale(self):
        return np.linalg.norm(vtk_to_numpy(self.polydata.GetPoints().GetData()), 'fro')

    def center(self):
        transform = vtk.vtkTransform()
        transform.Translate(-self.centroid[0], -self.centroid[1], -self.centroid[2])
        transformt = vtk.vtkTransformPolyDataFilter()
        transformt.SetInputData(self.polydata)
        transformt.SetTransform(transform)
        transformt.Update()
        self.polydata = transformt.GetOutput()

    def scale_unit_norm(self):
        transform = vtk.vtkTransform()
        scale_factor = 1.0/self.scale
        transform.Scale(scale_factor, scale_factor, scale_factor)
        transformt = vtk.vtkTransformPolyDataFilter()
        transformt.SetInputData(self.polydata)
        transformt.SetTransform(transform)
        transformt.Update()
        self.polydata = transformt.GetOutput()

    def rotate(self, arr):
        temp = isValidRotation(arr)
        assert(temp == True)
        sy = math.sqrt(arr[0][0] * arr[0][0] + arr[1][0] * arr[1][0])
        singular = sy < 1e-6
        x, y, z = 0, 0, 0
        if not singular :
            x = math.atan2(arr[2][1], arr[2][2])
            y = math.atan2(-arr[2][0], sy)
            z = math.atan2(arr[1][0], arr[0][0])

        else :
            x = math.atan2(-arr[1][2], arr[1][1])
            y = math.atan2(-arr[2][0], sy)
            z = 0

        rpy = np.array([x, y, z])

        transform = vtk.vtkTransform()
        transform.RotateX(x/math.pi*180)
        transform.RotateY(y/math.pi*180)
        transform.RotateZ(z/math.pi*180)

        transformt = vtk.vtkTransformPolyDataFilter()
        transformt.SetInputData(self.polydata)
        transformt.SetTransform(transform)
        transformt.Update()

        self.polydata = transformt.GetOutput()
        
        return self.polydata

    
def isValidRotation(arr):
    rt = np.transpose(arr)
    identity = np.dot(rt, arr)
    I = np.identity(3)
    n = np.linalg.norm(I - identity)
    return n < 1e-6
