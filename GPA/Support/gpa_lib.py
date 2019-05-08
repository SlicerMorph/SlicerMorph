import numpy as np
import os
import fnmatch

#center shape by removing the mean of each column
def centerShape(shape):
    shape=shape-shape.mean(axis=0)
    return shape
    
#scale shape by divinding by frobinius norm    
def scaleShape(shape):
    shape=shape/np.linalg.norm(shape)
    return shape

#align one shape to a reference shape, soley by rotation
def alignShape(refShape,shape):
    """
    Align the shape to the mean.
    """
    u,s,v=np.linalg.svd(np.dot(np.transpose(refShape),shape), full_matrices=True)
    rotationMatrix=np.dot(np.transpose(v), np.transpose(u))
    shape=np.dot(shape,rotationMatrix)
    
    return shape

def procrustesAlign(refShape,shape):
   #center both shapes
    refShape=centerShape(refShape)
    shape=centerShape(shape)
    
    #scale both shapes
    refShape=scaleShape(refShape)
    shape=scaleShape(shape)
    
    # rotate shape to match the refshape
    shape=alignShape(refShape,shape)
    
    return shape
    
def procrustesAlignNoScale(refShape,shape):
   #center both shapes
    refShape=centerShape(refShape)
    shape=centerShape(shape)
    shape=alignShape(refShape,shape)
    
    return shape

# <codecell>

def makeTwoDim(monsters):
    i,j,k=monsters.shape
    tmp=np.zeros((i*j,k))
    for x in range(k):
        vec=np.reshape(monsters[:,:,x],(i*j),order='F')
        tmp[:,x]=vec
    return tmp

def calcMean(vec):
    i,j=vec.shape
    meanVec=np.zeros((i))
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
    twoDim=makeTwoDim(monsters)
    mShape=calcMean(twoDim)
    covMatrix=calcCov(twoDim)
    eigVal, eigVec=np.linalg.eig(covMatrix)
    eigPair=sortEig(eigVal,eigVec)
    transform=makeTransformMatrix(eigPair,pcA,pcB)
    transform=np.transpose(transform)
    coords=np.dot(transform,twoDim)
    tmp=np.column_stack((coords[0,:],coords[1,:]))
    return tmp

#GPA 
def meanShape(monsters):
    return monsters.mean(axis=2)

def alignToOne(monsters):
    i,j,k=monsters.shape
    #scale and center the first monster
    monsters[:,:,0]=centerShape(monsters[:,:,0])
    monsters[:,:,0]=scaleShape(monsters[:,:,0])
    
    #align other monster to it
    for x in range(1,k):
        monsters[:,:,x]=procrustesAlign(monsters[:,:,0],monsters[:,:,x])
          
    return monsters
def alignToOneNoScale(monsters):
    i,j,k=monsters.shape
    #scale and center the first monster
    monsters[:,:,0]=centerShape(monsters[:,:,0])
    
    #align other monster to it
    for x in range(1,k):
        monsters[:,:,x]=procrustesAlignNoScale(monsters[:,:,0],monsters[:,:,x])
    return monsters

def alignToMean(monsters,trys):
    mean1=meanShape(monsters)
    i,j,k=monsters.shape
    for x in range(k):
        monsters[:,:,x]=procrustesAlign(mean1,monsters[:,:,x])
    mean2=meanShape(monsters)
    
    diff=np.linalg.norm(mean1-mean2)
    trys=trys+1
    if diff>.00001 and trys< 50:
        alignToMean(monsters, trys)
    
    return monsters
    
def alignToMeanNoScale(monsters,trys):
    mean1=meanShape(monsters)
    i,j,k=monsters.shape
    for x in range(k):
        monsters[:,:,x]=procrustesAlignNoScale(mean1,monsters[:,:,x])
    mean2=meanShape(monsters)
    
    diff=np.linalg.norm(mean1-mean2)
    trys=trys+1
    if diff>.00001 and trys< 50:
        alignToMeanNoScale(monsters, trys)
    
    return monsters

def centSize(monsters):
    i,j,k=monsters.shape
    size=np.zeros(k)
    for x in range(k):
        size[x]=np.linalg.norm(monsters[:,:,x])
    return size

def doGPA(monsters):
    monsters=alignToOne(monsters)
    mShape=meanShape(monsters)
    monsters=alignToMean(monsters,1)
    mShape=meanShape(monsters)
    return monsters, mShape
 
def doGPANoScale(monsters):
    monsters=alignToOneNoScale(monsters)
    mShape=meanShape(monsters)
    monsters=alignToMeanNoScale(monsters,1)
    mShape=meanShape(monsters)
    return monsters, mShape 

def procDist(monsters,mshape):
    i,j,k=monsters.shape
    
    procDists=np.zeros(k)
    for x in range(k):
        tmp=monsters[:,:,x]-mshape
        procDists[x]=np.linalg.norm(tmp,'fro')
        
    return procDists

def procDistPP(monsters):
    i,j,k=monsters.shape
    
    procDists=np.zeros((k,k))
    for x in range(k):
        for y in range(k):
            tmp=monsters[:,:,x]-monsters[:,:,y]
            procDists[x,y]=np.linalg.norm(tmp,'fro')
        
    return procDists
        
        


def makeTwoDim2(monsters):
    i,j,k=monsters.shape
    tmp=np.zeros((i*j,k))
    for x in range(k):
        vec=np.reshape(monsters[:,:,x],(i*j),order='C')
        tmp[:,x]=vec
    return tmp

