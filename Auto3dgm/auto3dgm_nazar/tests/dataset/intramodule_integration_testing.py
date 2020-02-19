'''
A primitive integration testing for the data set module
'''
from auto3dgm._nazar.dataset.datasetfactory import *
directorystring='/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/'
A=DatasetFactory.ds_from_dir(directorystring)

filelist=[]
filelist.append('/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/12144_U02_Eosimias_crop-smooth.ply')
filelist.append('/home/safari/Desktop/tutkimus/Slicer/HackathonJAN/testdata/20_Test_Teeth_PLY/12144_U05_Eosimias_crop-smooth.ply')

B=DatasetFactory.ds_from_filelist(filelist)

'''
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>
<class 'vtkCommonDataModelPython.vtkPolyData'>

In [4]: A
Out[4]: <auto3dgm.dataset.datasetcollection.DatasetCollection at 0x7f3e64425a58>
'''

dir(A)

'''
dir(A)
Out[10]: 
['__class__',
 '__delattr__',
 '__dict__',
 '__dir__',
 '__doc__',
 '__eq__',
 '__format__',
 '__ge__',
 '__getattribute__',
 '__gt__',
 '__hash__',
 '__init__',
 '__le__',
 '__lt__',
 '__module__',
 '__ne__',
 '__new__',
 '__reduce__',
 '__reduce_ex__',
 '__repr__',
 '__setattr__',
 '__sizeof__',
 '__str__',
 '__subclasshook__',
 '__weakref__',
 'add_analysis_set',
 'add_data_set',
 'analysis_sets',
 'datasets',
 'remove_data_set']
'''
A.datasets
'''
{0: [<auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fda0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fd68>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fcf8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fdd8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fd30>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442fe10>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442ff98>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442ff60>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442ffd0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e6442f160>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fdd30>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fdcc0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd940>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd908>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd828>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd7b8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd7f0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd668>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd630>,
  <auto3dgm.mesh.mesh.Mesh at 0x7f3e642fd5f8>]}
'''
B=A.datasets[0]
B[0]
B[0].vertices
'''
array([[  8.12993869e-02,  -1.31682634e-01,  -1.38612106e-01],
       [  8.71988162e-02,  -1.31082773e-01,  -1.40313461e-01],
       [  8.75993595e-02,  -1.26682520e-01,  -1.39611557e-01],
       ..., 
       [ -2.47015152e-02,  -1.78782701e-01,   1.37488052e-01],
       [  6.19944045e-03,  -1.96682215e-01,   1.36587784e-01],
       [ -1.35000016e-06,  -1.93282366e-01,   1.37587234e-01]], dtype=float32)
'''
A.datasets
'''
{0: [<auto3dgm.mesh.mesh.Mesh at 0x7fbab493fa58>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fa90>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fb38>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fb00>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fba8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fac8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fb70>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fbe0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fc18>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fc50>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fc88>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fcc0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fcf8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fd30>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fd68>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fda0>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fdd8>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fe10>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fe48>,
  <auto3dgm.mesh.mesh.Mesh at 0x7fbab493fe80>]}

'''
A.remove_dataset(A,0)
A.datasets
'''
{}
'''

