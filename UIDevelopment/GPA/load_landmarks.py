#!/usr/bin/python
# Filename: load_landmarks.py

# import os
# import glob
# import csv
# import fnmatch
# import numpy as np

# def myTest():
#   print "test Passed"

# def importLandMarks(filePath):
#   """
#   Imports the landmarks from a .fcsv file.
#   Does not import sample if a  landmark is -1000
#   Adjusts the resolution is log(nhrd) file is found
#   returns kXd array of landmark data.
#   k=# of landmarks
#   d=dimension
#   """
#   # import data file
#   datafile=open(filePath,'r')
#   data=[]
#   for row in datafile:
#     data.append(row.strip().split(','))
#   # Make Landmark array
#   dataArray=np.zeros(shape=(len(data)-3,3))
#   for i in range(0, len(data)-3):
#     tmp=data[i+3]
#     if -1000 in tmp[1:4]:
#       # print "-1000"
#       return None

#     dataArray[i,0:3]=tmp[1:4]
#       # print type(dataArray[i,2] )

#     #read resolution 
#   dirName=os.path.dirname(filePath)
#   fileName=os.path.basename(filePath)
#     # resolution=parseNHDR(dirName, fileName )

#     # if resolution:
#     #   dataArray=dataArray*resolution

#   return dataArray



# def walk_dir( top_dir):
#   """
#     Returns a list of all fcsv files in a diriectory, including sub-directories.
#   """
#   dir_to_explore=[]
#   file_to_open=[]
#   for path, dir, files in os.walk(top_dir):
#     for filename in files:
#       if fnmatch.fnmatch(filename,"*.fcsv"):
#       #print filename
#         dir_to_explore.append(path)
#         file_to_open.append(filename)
#   return dir_to_explore, file_to_open

# def initDataArray(dirs, file):  
#   """
#   returns an np array for the storage of the landmarks.
#   """
#   k=len(dirs) 
#   # print k
#   j=3 
#   # import data file
#   datafile=open(dirs[0]+os.sep+file,'r')
#   data=[]
#   for row in datafile:
#     data.append(row.strip().split(','))
#   i= len(data)-3
#   landmarks=np.zeros(shape=(i,j,k))
#   return landmarks

# def importAllLandmarks(inputDirControl):
#   """
#   Import all of the landmarks.
#   Controls are stored frist, then experimental landmarks, in a np array
#   Returns the landmark array and the number of experimetnal and control samples repectively.
#   """
#   # get files and directories
#   dirs, files=walk_dir(inputDirControl)
#   print dirs, files
#   # initilize and fill control landmakrs
#   landmarksControl=initDataArray(dirs,files[0])
#   iD,jD,kD=landmarksControl.shape
#   nControl=kD
#   iD=iD.__int__();jD=jD.__int__();kD=kD.__int__()
#   # fill landmarks
#   for i in range(0,len(files)):
#     tmp=importLandMarks(dirs[i]+os.sep+files[i])
#     #  check that landmarks where imported, if not delete zeros matrix
#     if type(tmp) is not 'NoneType':
#       it,at=tmp.shape
#       it=it.__int__(); at=at.__int__()
#       if it == iD and at == jD:
#         landmarksControl[:,:,i]=tmp
#       else:
#         np.delete(landmarksControl,i,axis=2)
#       else:
#         np.delete(landmarksControl,i,axis=2)

#   return landmarksControl

