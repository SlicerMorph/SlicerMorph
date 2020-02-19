class JobRun(object):
    """Runs batch tasks in single core, multi core, or cluster environments 

   JobRun carries out tasks either locally or on a cluster by calling a 
   supplied function multiple times, with variable data objects and consistent 
   non-varying function parameters per call. Instances of this class must be 
   supplied with two sets of attributes: 1) local/cluster environment settings 
   (at the most basic level, this can just be a local/cluster switch flag), and 
   2) a Job object. 

    Attributes:
        mode: Processing mode. String, can be 'single', 'multi', or 'cluster'
    """

    def __init__(self, job=None, mode='', run=False):
        self.allowed_modes = ['single', 'multi']
        self.__mode = 'single'
        if mode and mode in self.allowed_modes:
            self.__mode = mode
        
        if job:
            job.validate()
            self.job = job
        
        if run:
            self.job.validate()
            self.execute_jobs()

    def execute_jobs(self):
        if self.__mode and self.__mode in self.allowed_modes:
            if self.__mode == 'single':
                return self.run_single()
            elif self.__mode == 'multi':
                return self.run_multi()
            else:
                raise ValueError('Unexpected mode: {}'.format(self.__mode))
        else:
            raise ValueError('Current mode ({}) not an allowed mode: {}'.format(
                self.__mode, self.allowed_modes))

    def run_single(self):
        """Run jobs locally using a single core"""
        job_dict = {
            'output': {},
            'input': self.job
        }

        results_dict = {}
        for k, v in self.job.data.items():
            """here, key is a tuple representing the initial indices of the mesh_list from Correspondence"""
            #print("workds")
            #print(self.job.func)
            results_dict[k] = self.job.func(**v, **self.job.params)

        job_dict['output'] = results_dict
        return job_dict
        
    def run_multi(self):
        """Run jobs locally using mutliple cores"""

    def run_cluster(self):
        """Run jobs on a cluster environment (not yet implemented TODO TBA)"""
