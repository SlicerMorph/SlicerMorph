import numpy as np
import os
import fnmatch
import scipy.linalg as sp

# PCA
def makeTwoDim(monsters):
    # Reshape (n_landmarks, 3, n_subjects) to (3*n_landmarks, n_subjects) in Fortran order,
    # then center each row across subjects.
    i, j, k = monsters.shape
    tmp = monsters.reshape(i * j, k, order='F').astype(np.float64, copy=True)
    tmp -= np.mean(tmp, axis=1, keepdims=True)
    return tmp

def calcMean(vec):
    return vec.mean(axis=1)

def calcCov(vec):
    # Vectorized covariance: (X - mean) @ (X - mean).T / N
    # Matches the original convention of dividing by N (not N-1).
    i, j = vec.shape
    centered = vec - vec.mean(axis=1, keepdims=True)
    return (centered @ centered.T) / float(j)

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
