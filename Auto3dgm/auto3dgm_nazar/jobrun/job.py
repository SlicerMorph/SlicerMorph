class Job(object):
    """Data structure encapsulating data and parameters for JobRun task.

    Example dict version of Job data
    {
    ‘data’: 
        {
        ‘(0, 1)’: {‘mesh1’: mesh0, 'mesh2': mesh1}, 
        ‘(0, 2)’: {‘mesh1’: mesh0, 'mesh2': mesh2}, 
        ‘(0, 3)’: {‘mesh1’: mesh0, 'mesh2': mesh3}
        }, 
    ‘params’: 
        {
        ‘point_number’: 200, 
        ‘subsample_method’: ‘GPR’
        }, 
    ‘func’: function_reference
    }

    """

    def __init__(self, job_dict={}, data={}, params={}, func=None):
        self.data = {}
        self.params = {}
        self.func = None

        if job_dict:
            self.import_job_dict(job_dict)
        elif data or params or func:
            # print(data)
            self.import_args(data=data, params=params, func=func)

    def import_job_dict(self, job_dict):
        if (job_dict and isinstance(job_dict, dict)):
            if 'data' in job_dict and self.__validate_data(job_dict['data']):
                self.data = job_dict['data']
            if 'params' in job_dict and self.__validate_params(job_dict['params']):
                self.params = job_dict['params']
            if 'func' in job_dict and self.__validate_func(job_dict['func']):
                self.func = job_dict['func']

    def import_args(self, data=None, params=None, func=None):
        if data and self.__validate_data(data):
            self.data = data
            
        if params and self.__validate_params(params):
            self.params = params
        
        if func and self.__validate_func(func):
            self.func = func
        
    def as_dict(self):
        """Returns job data structure as dict"""
        if (self.__validate_data(self.data) 
            and self.__validate_params(self.params) 
            and self.__validate_func(self.func)):
            return {
                'data': self.data,
                'params': self.params,
                'func': self.func
            }

    def validate(self):
        """Check all components and return true if all validate"""
        if (self.data and self.__validate_data(self.data) 
            and self.params and self.__validate_params(self.params) 
            and self.func and self.__validate_func(self.func)):
            return True

    def __validate_data(self, data):
        """data must be dict, every element must be dict with >=1 element
        I don't believe that data[key1][key2] should have 1 element, I think we should enforce >1, 
        since Corresponence never passes a single data[k1][k2] element"""
        if (not data 
            or not isinstance(data, dict) 
            or not len(data)
            or not self.__validate_data_items(data.values())):
            self.__validation_error(error_type='data', var=data)
        return True

    def __validate_data_items(self, items):
        for x in items:
            if not isinstance(x, dict) or not len(x):
                self.__validation_error(error_type='data_item', var=x)
        return True

    def __validate_params(self, params):
        """Params must be dict with at least one value"""
        if not params or not isinstance(params, dict) or not len(params):
            self.__validation_error(error_type='params', var=params)
        return True

    def __validate_func(self, func):
        """Func must be callable"""
        if not func or not callable(func):
            self.__validation_error(error_type='func', var=func)
        return True  

    def __validation_error(self, error_type, var):
        allowed_types = ['data', 'data_item', 'params', 'func']
        if error_type not in allowed_types:
            raise ValueError('Unexpected error type ' + str(error_type))
        else:
            raise ValueError('Unexpected value' + str(var) + 'for type ' + str(error_type))
