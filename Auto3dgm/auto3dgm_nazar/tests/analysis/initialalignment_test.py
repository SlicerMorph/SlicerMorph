# A sanity check for the pairwise alignment algorithm
import dataset
import analysis
import mesh
import jobrun
from analysis.correspondence import Correspondence
import numpy as np

A=np.array([[3,0.01,0],[10,0.02,0],[7,0,0.02],[18,0.007,0.2]]).T
B=np.array([[0,3,0.01],[0,10,0.01],[0,17,0.05],[0,25,0.4]]).T
#C=np.array([[0,2,0],[0,0,2],[0,2.01,3],[1,5,1]]).T
a=[A,B]#,C]

kor1=Correspondence(a, mirror=0)
kor2=Correspondence(a, mirror=1)


AA=kor1.initial_rotation(kor1)
BB=kor2.initial_rotation(kor2)
