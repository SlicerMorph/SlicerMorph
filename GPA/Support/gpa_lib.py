import numpy as np
import os
import fnmatch
import scipy.linalg as sp

# PCA
def makeTwoDim(monsters):
    i,j,k=monsters.shape
    tmp=np.zeros((i*j,k))
    for x in range(k):
      vec=np.reshape(monsters[:,:,x],(i*j),order='F')
      tmp[:,x]=vec
    tmp -= np.mean(tmp, axis=1, keepdims=True)
    return tmp

def calcMean(vec):
    i,j=vec.shape
    meanVec=np.zeros(i)
    for x in range(j):
        meanVec+=vec[:,x]/float(j)
    return meanVec

def calcCov(vec):
    i,j=vec.shape
    meanVec=calcMean(vec)
    covMatrix=np.zeros((i,i))
    for x in range(j):
      t1=((vec[:,x]-meanVec).T).reshape(i,1)
      t2=(vec[:,x]-meanVec).reshape(1,i)
      covMatrix+=np.dot(t1,t2)/float(j)
    return covMatrix

def sortEig(eVal, eVec):
    i,j=eVec.shape
    ePair=list(range(j))
    for y in range(j):
      ePair[y]=[(np.abs(eVal[y]), eVec[:,y])]
      ePair[y].sort()
      ePair[y].reverse()
    return ePair

def pairEig(eVal, eVec):
    i,j=eVec.shape
    ePair=list(range(j))
    for y in range(j):
      ePair[y]=[(np.abs(eVal[y]), eVec[:,y])]
    return ePair

def makeTransformMatrix(ePair,pcA,pcB):
    tmp=ePair[0][0][1]
    i=tmp.shape
    i=i[0]
    vec1=ePair[pcA][0][1]
    vec2=ePair[pcB][0][1]

    transform=np.zeros((i,2))
    transform[:,0]=vec1.reshape(i).real
    transform[:,1]=vec2.reshape(i).real
    return transform

def plotTanProj(monsters,pcA,pcB):
    i, j, k = monsters.shape
    twoDim=makeTwoDim(monsters)
    mShape=calcMean(twoDim)
    covMatrix=calcCov(twoDim)
    if k > i * j:  # limit results returned if sample number is less than observations
      self.val, self.vec = sp.eigh(covMatrix)
    else:
      self.val, self.vec = sp.eigh(covMatrix, eigvals=(i * j - k, i * j - 1))
    eigVal=eigVal[::-1]
    eigVec=eigVec[:, ::-1]
    eigPair=pairEig(eigVal,eigVec)
    transform=makeTransformMatrix(eigPair,pcA,pcB)
    transform=np.transpose(transform)
    coords=np.dot(transform,twoDim)
    tmp=np.column_stack((coords[0,:],coords[1,:]))
    return tmp

def plotTanProj(monsters,eigSort,pcA,pcB):
    twoDim=makeTwoDim(monsters)
    transform=makeTransformMatrix(eigSort,pcA,pcB)
    transform=np.transpose(transform)
    coords=np.dot(transform,twoDim)
    tmp=np.column_stack((coords[0,:],coords[1,:]))
    return tmp

############## GPA original
#center shape by removing the mean of each column
def centerShape(shape):
    shape=shape-shape.mean(axis=0)
    return shape

#scale shape by divinding by frobinius norm
def scaleShape(shape):
    shape=shape/np.linalg.norm(shape)
    return shape

#align one shape to a reference shape, solely by rotation
def alignShape(refShape,shape):
    """
    Align the shape to the mean.
    """
    u,s,v=sp.svd(np.dot(np.transpose(refShape),shape), full_matrices=True)
    rotationMatrix=np.dot(np.transpose(v), np.transpose(u))
    shape=np.dot(shape,rotationMatrix)
    return shape

def meanShape(monsters):
    return monsters.mean(axis=2)

def procDist(monsters,mshape):
    i,j,k=monsters.shape
    procDists=np.zeros(k)
    for x in range(k):
      tmp=monsters[:,:,x]-mshape
      procDists[x]=np.linalg.norm(tmp,'fro')
    return procDists

################# GPA update
def runGPA(allLandmarkSets):
  i,j,k=allLandmarkSets.shape
  for index in range(k):
    landmarkSet=allLandmarkSets[:,:,index]
    tempSet = applyCenterScale(landmarkSet)
    allLandmarkSets[:,:,index]=tempSet
  allLandmarkSets = procrustesAlign(allLandmarkSets[:,:,0],allLandmarkSets)
  initialMeanShape=meanShape(allLandmarkSets)
  initialMeanShape = scaleShape(initialMeanShape)
  diff=1
  tries=0
  while diff>0.0001 and tries<5:
    allLandmarkSets = procrustesAlign(initialMeanShape,allLandmarkSets)
    currentMeanShape=meanShape(allLandmarkSets)
    diff=np.linalg.norm(initialMeanShape-currentMeanShape)
    initialMeanShape=currentMeanShape
    tries=tries+1
  return allLandmarkSets, currentMeanShape

def procrustesAlign(mean, allLandmarkSets):
  mean = scaleShape(mean)
  i,j,k=allLandmarkSets.shape
  for index in range(k):
    allLandmarkSets[:,:,index] = alignShape(mean, allLandmarkSets[:,:,index])
  return allLandmarkSets

def applyCenterScale(landmarkSet):
  landmarkSet=centerShape(landmarkSet)
  landmarkSet=scaleShape(landmarkSet)
  return landmarkSet

def runGPANoScale(allLandmarkSets):
    i,j,k = allLandmarkSets.shape
    for index in range(k):
      landmarkSet = allLandmarkSets[:,:,index]
      tempSet = applyCenter(landmarkSet)  # center only, no scaling
      allLandmarkSets[:,:,index] = tempSet
    allLandmarkSets = procrustesAlignNoScale(allLandmarkSets[:,:,0], allLandmarkSets)
    initialMeanShape = meanShape(allLandmarkSets)
    initialMeanShape = centerShape(initialMeanShape) # re-center when no scaling
    diff = 1
    tries = 0
    while diff > 0.0001 and tries < 5:
      allLandmarkSets = procrustesAlignNoScale(initialMeanShape, allLandmarkSets)
      currentMeanShape = meanShape(allLandmarkSets)
      currentMeanShape = centerShape(currentMeanShape)  # re-center when no scaling
      diff = np.linalg.norm(initialMeanShape-currentMeanShape)
      initialMeanShape = currentMeanShape
      tries += 1
    for index in range(k):
      allLandmarkSets[:,:,index] = centerShape(allLandmarkSets[:,:,index])
    return allLandmarkSets, currentMeanShape

def procrustesAlignNoScale(mean, allLandmarkSets):
    i,j,k = allLandmarkSets.shape
    mean = centerShape(mean)  # re-center when no scaling
    for index in range(k):
      aligned = alignShape(mean, allLandmarkSets[:, :, index])
      aligned = centerShape(aligned)  # re-center when no scaling
      allLandmarkSets[:,:,index] = aligned
    return allLandmarkSets

def applyCenter(landmarkSet):
  landmarkSet=centerShape(landmarkSet)
  return landmarkSet
