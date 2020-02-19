from auto3dgm_nazar.dataset.datasetfactory import DatasetFactory
from auto3dgm_nazar.mesh.subsample import Subsample
from auto3dgm_nazar.analysis.correspondence import Correspondence
import os

cwd=os.getcwd()
mesh_dir = cwd+"/input/"

# Create a DatasetCollection with meshes from a sample directory 
dc = DatasetFactory.ds_from_dir(dir_path=mesh_dir, center_scale=True)
print(dc)
print(dc.datasets)
print(dc.analysis_sets) # Why is the initial dataset copied as an analysis_set?

# Generate two sets of subsamples with 100 and 200 points each
subsample_points = [100, 200]
subsample_results = Subsample(dc.datasets[0], subsample_points, 'FPS') # this absolutely does not work

# Add these results as additional datasets to our DatasetCollection
dc.add_dataset(subsample_results[100]['output']['results'], 'ss100')
dc.add_dataset(subsample_results[200]['output']['results'], 'ss200')

# Generate Correspondence results for first (100) subsample points dataset
# Correspondence data structure should be an object with the following attributes: local_align with d, p, and r arrays, mst with minimum spanning tree, and global_align with d, p, and r arrays
ss_100_correspondence_res = Correspondence( 
	meshes=dc.datasets['ss100'],
	initial_alignment=None, 
	globalize=True,
	mirror=True)
dc.add_analysis_set(ss_100_correspondence_res, 'ss100')

# Generate Correspondence results for second (200) subsample points dataset
# Correspondence here takes an optional initial alignment object with d, p, and r arrays
ss_200_correspondence_res = Correspondence( # Correspondence should take an initial alignment object with d, p, and r arrays; also correspondence should handle bundling pairwise results into a single data structure
	meshes=dc.datasets['ss200'],
	initial_alignment=dc.analysis_sets['ss100'].global_align, 
	globalize=True,
	mirror=True)
dc.add_analysis_set(ss_200_correspondence_res, 'ss200')


# Alternative test flow: Subsample one resolution at a time

from auto3dgm_nazar.dataset.datasetfactory import DatasetFactory
from auto3dgm_nazar.mesh.subsample import Subsample
from auto3dgm_nazar.analysis.correspondence import Correspondence
import os

cwd=os.getcwd()
mesh_dir = cwd+"/input/"

# Create a DatasetCollection with meshes from a sample directory 
dc = DatasetFactory.ds_from_dir(dir_path=mesh_dir, center_scale=True)
print(dc)
print(dc.datasets)
print(dc.analysis_sets) # Why is the initial dataset copied as an analysis_set?

# Generate two sets of subsamples with 100 and 200 points each
subsample_points = 100
subsample_results1 = Subsample(dc.datasets[0], subsample_points, 'FPS') # this absolutely does not work
subsample_points = 200
subsample_results2 = Subsample(dc.datasets[0], subsample_points, 'FPS') # this absolutely does not work



# Add these results as additional datasets to our DatasetCollection
dc.add_dataset(dataset=subsample_results1.pts, dataset_name= 'ss100')
dc.add_dataset(dataset=subsample_results2.pts, dataset_name= 'ss200')

# Generate Correspondence results for first (100) subsample points dataset
# Correspondence data structure should be an object with the following attributes: local_align with d, p, and r arrays, mst with minimum spanning tree, and global_align with d, p, and r arrays
ss_100_correspondence_res = Correspondence( 
	meshes=dc.datasets['ss100'],
	initial_alignment=None, 
	globalize=True,
	mirror=True)
dc.add_analysis_set(ss_100_correspondence_res, 'ss100')

# Generate Correspondence results for second (200) subsample points dataset
# Correspondence here takes an optional initial alignment object with d, p, and r arrays
ss_200_correspondence_res = Correspondence( # Correspondence should take an initial alignment object with d, p, and r arrays; also correspondence should handle bundling pairwise results into a single data structure
	meshes=dc.datasets['ss200'],
	initial_alignment=dc.analysis_sets['ss100'].global_align, 
	globalize=True,
	mirror=True)
dc.add_analysis_set(ss_200_correspondence_res, 'ss200')
