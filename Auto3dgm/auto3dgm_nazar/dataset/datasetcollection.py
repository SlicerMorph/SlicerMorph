class DatasetCollection:
    #params: self,
    #datasets: a list of datasets
    #analysis_sets: a list of analysis objects
    #
    def __init__(self, datasets, analysis_sets=[],dataset_names=[], analysis_set_names=[]):
        
        #No names given
        if not dataset_names:
            dataset_names=list(range(0,len(datasets)))
        #Fewer names than datasets
        else:
            ID=0
            while (len(datasets)>len(dataset_names)):
                if not self.datasets[ID]:
                    dataset_names.append(ID)
                ID+=1
            #More names than datasets
            dataset_names=dataset_names[:len(datasets)]
            #Equally many names and datasets
        self.datasets=dict(zip(dataset_names,datasets))
        #Same trick for the analysis_set
        if not analysis_set_names:
            analysis_set_names=list(range(0,len(analysis_sets)))
        else:
        #Fewer names than datasets
            ID=0
            while (len(analysis_sets)>len(analysis_set_names)):
                if not self.analysis_sets[ID]:
                    analysis_set_names.append(ID)
                ID+=1
            #More names than datasets
            dataset_names=analysis_set_names[:len(analysis_sets)]
            #Equally many names and datasets
        self.analysis_sets=dict(zip(analysis_set_names,analysis_sets))


    def add_dataset(self,dataset,dataset_name):
        #if dataset_name in self.datasets:
        #    msg="The Dataset Collection already contains a dataset with name "+str(dataset_name)
        #    raise OSError(msg)
        #else:
        #    self.datasets[dataset_name]=dataset
        self.datasets[dataset_name]=dataset

    def add_analysis_set(self,analysis_set,analysis_set_name):
        #if analysis_set_name in self.analysis_sets:
        #    msg="The Dataset Collection already contains an analysis set with name "+str(analysis_set_name)
        #    raise OSError(msg)
        #else:
        #    self.analysis_sets[analysis_set_name]=analysis_set
        self.analysis_sets[analysis_set_name]=analysis_set

    def remove_dataset(self,dataset_name):
        if not dataset_name in self.datasets:
            msg="The Dataset Collection does not contain a dataset named "+str(dataset_name)
            raise OSError(msg)
        else:
            del self.datasets[dataset_name]

    def remove_analysis_set(self,analysis_set_name):
        if not analysis_set_name in self.analysis_sets:
            msg="The Dataset Collection does not contain an analysis set named "+str(analysis_set_name)
            raise OSError(msg)
        else:
            del self.analysis_sets[analysis_set_name]
