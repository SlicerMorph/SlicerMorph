import vtk
import os

class MeshExport:

    @staticmethod
    def writeToFile(fp,mesh,format='ply'):
        name=mesh.name#.split("/")
        #t=len(tmp)
        #name=tmp[t-1].split(".")[0]
        if format=='ply':
            writer=vtk.vtkPLYWriter()
        if format=='stl':
            writer=vtk.vtkSTLWriter()
        if format=='obj':
            writer=vtk.vtkOBJWriter()
        writer.SetInputData(mesh.polydata)
        writer.SetFileName(os.path.join(fp, name+"."+format))
        writer.Write()    
        return(True)
