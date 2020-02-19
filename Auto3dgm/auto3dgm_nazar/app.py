"""
Main control flow for auto3dgm. Mainly used as a speculative document for now.
"""

from auto3dgm_nazar.dataset.datasetfactory import DatasetFactory
from auto3dgm_nazar.mesh.subsample import Subsample
from auto3dgm_nazar.analysis.correspondence import Correspondence

class Auto3dgmNazar:
	def __init__(self, config={}, run=True):
		'''
		MY TESTED CODE FLOW:
		import auto3dgm
		x = auto3dgm.dataset.datasetfactory.DatasetFactory()
		y = x.ds_from_dir("tests/fixtures")
		subsample_res = auto3dgm.mesh.subsample.Subsample(pointNumber=[2, 3], meshes=y.datasets[0])
		mesh_list = list(subsample_res.ret[2]['output']['output'].values())
		cres = auto3dgm.analysis.correspondence.Correspondence(meshes=mesh_list)
		'''
		#TODO I feel like mesh_dir and output_DIR should be input params
		self.mesh_dir = '' # dir path
		self.output_dir = '' # dir path
		self.ss_points_i = 0
		#TODO: ss_label_i not defined
		self.ss_label_i = 'subsample_' + str(self.ss_label_i)
		self.ss_points_f = 0
		self.ss_label_f = 'subsample_' + str(self.ss_label_f)
		self.ss_type = '' # could be FPS, GPL, or hybrid
		self.use_cluster = 0 # boolean, false/0 is local
		# TODO cluster specific parameters??
		self.allow_reflection = 1
		self.max_iter = 1000
		self.dataset = None

		### INITIAL STEPS ###

		# config will likely come from a set-up file somehow with parameters
		if config:
			self.__import_config(config)

		if run:
			self.start()

	def start(self):
		### INITIAL STEPS ###

		# check parameters look good before proceeding
		self.validate_parameters()

		self.__write_output_dirs()

		### DATA LOAD AND SUBSAMPLE
		#TODO: No ftype param
		self.dataset = DatasetFactory.ds_from_dir(self.mesh_dir, ftype='ply')

		# need to get both sets of subsample results
		ss_points = [self.ss_points_i, self.ss_points_f]
		#TODO: Should use named parameters as the constructor for Subsample, I'm not sure what ss_type refers to.
		#TODO: init doesn't return anything, so I've encoded the results dictionary in subsample_res.ret
		subsample_res = Subsample(self.dataset['mesh'], ss_points, self.ss_type) # dataset class should eventually support multiple named mesh sets and should be dict-style callable like this for mesh TODO: Currently does not support multiple named mesh sets, and the param is dataset.meshes
		ss_meshes_i = subsample_res[ss_points[0]]['output']['results'] #TODO: Results isnt a list of meshes, its a dict
		ss_meshes_f = subsample_res[ss_points[1]]['output']['results']

		#TODO: Add mesh set doesnt exist as a method. Self.dataset isnt a dataset, its a data set collection, maybe create a method to instantiate a new data set, and add it to the Dataset COllection? THis naming is kind of bad
		self.dataset.add_mesh_set(self.ss_label_i, ss_meshes_i)
		self.dataset.add_mesh_set(self.ss_label_f, ss_meshes_f)

		### INITIAL SUBSAMPLE POINTS ANALYSIS ###
		ss_i_correspondence_res = Correspondence( # Correspondence should take an initial alignment object with d, p, and r arrays; also correspondence should handle bundling pairwise results into a single data structure
			meshes=self.dataset[self.ss_label_i],
			initial_alignment=None, 
			globalize=True,
			mirror=self.allow_reflection)
		# Correspondence data structure should be an object with the following attributes: local_align with d, p, and r arrays, mst with minimum spanning tree, and global_align with d, p, and r arrays

		self.dataset.add_analysis_set(self.ss_label_i, ss_i_correspondence_res)

		### FINAL SUBSAMPLE POINTS ANALYSIS ###
		ss_f_correspondence_res = Correspondence( # Correspondence should take an initial alignment object with d, p, and r arrays; also correspondence should handle bundling pairwise results into a single data structure
			meshes=self.dataset[self.ss_label_f],
			initial_alignment=self.dataset.analysis_set[self.ss_label_i].global_align, 
			globalize=True,
			mirror=self.allow_reflection)

		### EXPORT TODO ###


	def validate_parameters(self): # TODO
		return

	def __import_config(self): # TODO
		return 

	def __write_output_dirs(self): # TODO
		return


