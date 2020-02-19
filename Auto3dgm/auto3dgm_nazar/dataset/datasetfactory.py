from os import listdir
from os.path import isfile, splitext, join
from auto3dgm_nazar.mesh.meshfactory import MeshFactory 
from auto3dgm_nazar.dataset.datasetcollection import DatasetCollection
from auto3dgm_nazar.mesh.subsample import Subsample 
from numpy import empty

class DatasetFactory(object):
    __ftypes = ['.ply', '.obj', '.stl', '.off']
    #params: directory string
    #params: filetype
    @staticmethod
    def ds_from_dir(dir_path, center_scale=False):
        c = [join(dir_path, x) for x in listdir(dir_path)]
        files = [f for f in c if isfile(f) and splitext(f)[1] in DatasetFactory.__ftypes]
        if not files:
            msg = 'No appropriate files were found in '+dir_path
            raise OSError(msg)
        meshes=[]
        mesheslist=[]
        for file in files: 
            meshes.append(MeshFactory.mesh_from_file(file, center_scale))
        mesheslist.append(meshes)
        return(DatasetCollection(datasets=mesheslist))
    #params: filelist: a list of files
    @staticmethod
    def ds_from_filelist(filelist):
        meshes=[]
        mesheslist=[]
        for file in filelist: 
            meshes.append(MeshFactory.mesh_from_file(file))
        mesheslist.append(meshes)
        return(DatasetCollection(datasets=mesheslist))
    #params: vertices: a list of vertex matrices, each element of the list is associated with a mesh
    #        faces: a list of face relations, each element of the list is associated to a mesh
    #        deep: a boolean instantion parameter passed to meshFactory. The value is necessarily same for all the meshes.
    @staticmethod
    def ds_from_meshdata(vertices,faces,deep=True):
        for i in range(0,len(vertices)): 
            meshes.append(MeshFactory.mesh_from_data(vertices[i],faces[i],deep))
        mesheslist.append(meshes)
        return(DatasetCollection(datasets=mesheslist))
    #params:
    # A Dataset object Dataset
    # n number of points to subsample
    # subsamplingmethod: either 'GPL' or 'FPS', defaults to FPS
    # seed
    @staticmethod
    def ds_from_subsampling(Dataset,n,subsamplingmethod='FPS',seed=empty([0,0])):
        meshes=Dataset.meshes
        subsampled_meshes=[]
        if(subsamplingmethod=='GPL'):
            for i in meshes:
                subsampled_meshes.append(Subsample.gpl_subsample(mesh, n, seed))
        elif(subsamplingmethod=='FPS'):
            for i in meshes:
                subsampled_meshes.append(Subsample.far_point_subsample(mesh, n, seed))
        else:
            msg = 'The subsampling method needs to be either GPL or FPS.'
            raise OSError(msg)
        mesheslist.append(subsampled_meshes)
        return(DatasetCollection(datasets=mesheslist))






