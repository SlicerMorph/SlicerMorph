class Dataset:
    #params: self
    #meshes: a list of mesh objects or a mesh object
    def __init__(self, meshes):
        if(isinstance(meshes, list)):
            self.meshes=meshes
        elif hasattr(meshes,'vertices'):
            meshlist=[]
            meshlist.append(meshes)
            self.meshes=meshlist 
        else:
            msg = 'Input not a list nor a valid mesh object'
            raise OSError(msg)
