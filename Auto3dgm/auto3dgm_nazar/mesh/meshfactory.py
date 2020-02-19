from os.path import isfile, splitext
from auto3dgm_nazar.mesh.mesh import Mesh
from numpy import array, ndarray, concatenate, empty, full
from vtk import vtkPLYReader,vtkOBJReader,vtkSTLReader,vtkPolyData, vtkPoints, vtkCellArray
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk, numpy_to_vtkIdTypeArray
from warnings import warn


class MeshFactory(object):
    """Stub of Mesh Factory class.
    Longer class information...
    Attributes:
        attr1: Information.
        attr2: Information.

    MeshFactory (Class with Static Methods)
        createFromFile: receives a string file location, creates a VTK mesh object, returns Mesh object
        createFromData: receives vertex and/or face arrays, creates a VTK mesh object, returns Mesh object
        Rationale: Using a factory decouples mesh creation logic from VTK,
        enabling possibly complex loading behavior and even using non-VTK Mesh classes in the future
        Notes: Should be capable of creating meshes from files with formats .ply, .obj, .stl, and .off
    """

    @staticmethod
    def mesh_from_file(file_path, center_scale=False):
        """Returns a VTK PolyData object from a mesh.
        TODO ing file types: off. (The PyMesh Package might help.)"""
        allowed_filetypes = ['.ply', '.obj','.stl','.off']

        if isfile(file_path) and splitext(file_path)[1] in allowed_filetypes:
            if splitext(file_path)[1] == '.ply':
                reader = vtkPLYReader()

            elif splitext(file_path)[1] == '.obj':
                reader = vtkOBJReader()

            elif splitext(file_path)[1] == '.stl':
                reader = vtkSTLReader()
            elif splitext(file_path)[1] == '.off':
                (vertices, faces)=MeshFactory.off_parser(file_path)
                return MeshFactory.mesh_from_data(vertices, faces, center_scale=center_scale)
            namelist=file_path.split('/')
            name=namelist[len(namelist)-1]
            Name=name.split('\\')
            name=Name[len(Name)-1].split('.')[0]
            reader.SetFileName(file_path)
            reader.Update()
            
            polydata = reader.GetOutput()
            if isinstance(polydata, vtkPolyData):
                return Mesh(polydata, center_scale, name)
            else:
                msg = 'VTK reader output type expected {}, but got {}'.format(
                    'vtkCommonDataModelPython.vtkPolyData', type(polydata))
                raise TypeError(msg)
        else:
            msg = 'File {} not present or not allowed filetype: {}'.format(
                file_path, ', '.join(allowed_filetypes))
            raise OSError(msg)

    @staticmethod
    def mesh_from_data(vertices, faces=empty([0,0]), name=None, center_scale=False, deep=True):
        """Returns a VTK PolyData object from vertex and face ndarrays"""
        vertices = array(vertices, dtype=float)
        faces = array(faces, dtype='int64')

        polydata = vtkPolyData()

        # vertices
        points = vtkPoints()
        points.SetData(numpy_to_vtk(vertices, deep=deep))
        polydata.SetPoints(points)

        # faces
        if isinstance(faces, ndarray) and faces.ndim == 2 and faces.shape[1] == 3:
            faces = concatenate((full([faces.shape[0], 1], 3), faces), axis=1)
            cells = vtkCellArray()
            nf = faces.shape[0]
            vtk_id_array = numpy_to_vtkIdTypeArray(faces.ravel(), deep=deep)
            cells.SetCells(nf, vtk_id_array)
            polydata.SetPolys(cells)

        return Mesh(vtk_mesh=polydata, center_scale=center_scale, name=name)

    @staticmethod
    def off_parser(file_path):
        file=open("hammas.off","r")
        # Checking we have valid headers
        A=file.readline().split()
        if A[0] != 'OFF':
            msg = 'The input file does not seem to be valid off file, first line should read "OFF".'
            raise TypeError(msg)
        #Reading in the number of vertices, faces and edges, and pre-formatting their arrays
        (V,F,E)=map(int,file.readline().strip().split(' '))
        vertices=empty([V,3])
        faces=empty([F,3])
        # Read in the vertices
        for i in range(0,V):
            vertices[i]=list(map(float,file.readline().strip().split(' ')))
        #Read in the faces
        for i in range(0,F):
            line=list(map(int,file.readline().strip().split(' ')))
        # Notify the user that there are non-triangular faces.
        # Non-triangular faces wouldn't be supported by the vtk setup that we have anyway.
        # Better way would be to triangulate the polygons, that can be added if deemed useful
        # Also, we could use warnings
            if len(line)!=4:
                print("Warning: The .off contains non-triangular faces, holes might have been created.")
            if (line[0]!=3 and len(line)==4):
                print("Warning: The .off file contains a face that is defined to be non-triangular. It is a valid triangle, reading it as a triangle.")
            faces[i]=line[1:4]
        #TODO Once the correct format for mesh_from_data face array is clarified, decide if faces should be transposed or not
        return(vertices, faces.T)
