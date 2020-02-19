import auto3dgm_nazar
import sys
import numpy as np
import pdb

low_res = 100
high_res = 200
np.set_printoptions(suppress=True)
np.set_printoptions(precision=4)
dataset_coll = auto3dgm_nazar.dataset.datasetfactory.DatasetFactory.ds_from_dir("auto3dgm_nazar/tests/fixtures/sample", center_scale=False)
orig_meshes = dataset_coll.datasets[0]
seed = {}
for m in orig_meshes:
	print(m.name)
	# print(m.vertices[0:9])
	# print(m.centroid)
	# print(m.scale)
	seed[m.name] = m.vertices[0:1]
ss = auto3dgm_nazar.mesh.subsample.Subsample(pointNumber=[low_res,high_res], meshes=orig_meshes, seed=seed, center_scale=True)
ss_res = ss.ret

low_res_meshes = []
for name, mesh in ss_res[low_res]['output']['output'].items():
	mesh.name = name
	low_res_meshes.append(mesh)
high_res_meshes = []
for name, mesh in ss_res[high_res]['output']['output'].items():
	mesh.name = name
	high_res_meshes.append(mesh)
m1 = low_res_meshes[0]
corr = auto3dgm_nazar.analysis.correspondence.Correspondence(meshes=low_res_meshes)
ga=corr.globalized_alignment
print(ga)
#imp.reload(auto3dgm_nazar.analysis.correspondence)
print('now working on high resolution')
corr_high = auto3dgm_nazar.analysis.correspondence.Correspondence(meshes=high_res_meshes, initial_alignment=ga)
ga_final = corr_high.globalized_alignment
#corr2 = auto3dgm_nazar.analysis.correspondence.Correspondence(meshes=low_res_meshes)
