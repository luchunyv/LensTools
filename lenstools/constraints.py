"""

.. module:: constraints
	:platform: Unix
	:synopsis: This module implements the usual statistical tools you need to calculate cosmological parameters confidence intervals


.. moduleauthor:: Andrea Petri <apetri@phys.columbia.edu>


"""

from __future__ import division,print_function,with_statement

from operator import mul
from functools import reduce

#########################################################

import numpy as np
from numpy.linalg import solve,inv
from scipy.interpolate import Rbf

from emcee.ensemble import _function_wrapper

#########################################################
#############Default Gaussian data likelihood############
#########################################################

def gaussian_likelihood(chi2,norm=1.0):

	return norm*np.exp(-0.5*chi2)

######################################################################
##########Default chi2 calculation with the sandwich product##########
######################################################################

def chi2(parameters,*args,**kwargs):

	model_feature = _predict(parameters,kwargs["num_bins"],kwargs["interpolator"])
	inverse_covariance = kwargs["inverse_covariance"]

	if model_feature.ndim == 1:
		observed_feature = kwargs["observed_feature"]
	else: 
		observed_feature = kwargs["observed_feature"][np.newaxis,:]

	inverse_covariance_dot = np.dot(observed_feature - model_feature,inverse_covariance)

	return ((observed_feature - model_feature) * inverse_covariance_dot).sum(-1)
	

	

#######################################################################
#############Feature prediction wrapper################################
#######################################################################

def _predict(parameters,num_bins,interpolator):

	#For each feature bin, compute its interpolated value
	if parameters.ndim == 1:
		
		interpolated_feature = np.zeros(num_bins)

		for n in range(num_bins):
			interpolated_feature[n] = interpolator[n]()(*parameters)
		
	else:
			
		interpolated_feature = np.zeros((parameters.shape[0],num_bins))

		for n in range(num_bins):
			interpolated_feature[:,n] = interpolator[n]()(*parameters.transpose())

	return interpolated_feature


##############################################
###########Analysis base class################
##############################################

class Analysis(object):
	
	"""
	The base class of this module; the idea in weak lensing analysis is that one has a set of simulated data, that serves as training model, and then uses that set to fit the observations for the best model parameters.

	:param parameter_set: the points in parameter space that the simulated data cover; the first axis refers to the model, the second to the number of parameters 
	:type parameter_set: array

	:param training_set: the measured feature in each model; the first axis refers to the model, the others to the feature indices (or bins)
	:type training_set: array

	:param observed_set: the measured feature in the data, should be a one dimensional array
	:type observed_set: array

	"""

	_analysis_type = None

	def __init__(self,parameter_set=None,training_set=None):

		assert self._analysis_type is not None,"Don't instantiate this class directly, use one of its subclasses!"
		
		if parameter_set is not None and training_set is not None:
			assert parameter_set.shape[0] == training_set.shape[0],"There should be one feature for each of the simulated models!"

		self.parameter_set = parameter_set
		self.training_set = training_set

	def __repr__(self):

		try:
			return "{0} type analysis, based on {1} models spanning a {2}-dimensional parameter space".format(self._analysis_type,self.parameter_set.shape[0],self.parameter_set.shape[1])
		except AttributeError:
			return "{0} type analysis, no models in it yet!".format(self._analysis_type)

	def add_model(self,parameters,feature):

		"""
		Add a model to the training set of the current analysis

		:param parameters: parameter set of the new model
		:type parameters: array

		:param feature: measured feature of the new model
		:type feature: array

		"""

		#If the analysis doesn't have any models, add the first, otherwise simply vstack them
		if self.parameter_set is None:
			
			assert self.training_set is None

			self.parameter_set = parameters.copy()[np.newaxis,:]
			self.training_set = feature.copy()[np.newaxis,:]

		else:

			#Check for input valudity
			assert parameters.shape[0] == self.parameter_set.shape[1]
			assert feature.shape == self.training_set.shape[1:]

			self.parameter_set = np.vstack((self.parameter_set,parameters))
			self.training_set = np.vstack((self.training_set,feature))




###################################################
#############Fisher matrix analysis################
###################################################

class FisherAnalysis(Analysis):

	_analysis_type = "Fisher"
	_fiducial = 0

	"""
	The class handler of a Fisher matrix analysis, inherits from the base class Analysis

	"""

	def set_fiducial(self,n):

		"""
		Sets the fiducial model (with respect to which to compute the derivatives), default is 0 (i.e. self.parameter_set[0])

		:param n: the parameter set you want to use as fiducial
		:type n: int.

		"""

		assert n < self.parameter_set.shape[0],"There are less than {0} models in your analysis".format(n+1)

		self._fiducial = n

	def compute_derivatives(self):

		"""
		Computes the feature derivatives with respect to the parameter sets using one step finite differences; the derivatives are computed with respect to the fiducial parameter set

		:returns: array of shape (p-1,N), where N is the feature dimension and p is the size of the parameter_set

		"""

		assert self.parameter_set.shape[0] > 1,"You need at least 2 models to proceed in a Fisher Analysis!"

		#Keep a list of the varied parameters so far to avoid duplicates
		self._varied_list = list()

		#Calculate the size of the fiducial and non_fiducial features
		derivative_indices = range(self.parameter_set.shape[0])
		derivative_indices.remove(self._fiducial)
		non_fiducial_features = self.training_set[derivative_indices]
		non_fiducial_parameters = self.parameter_set[derivative_indices]

		derivatives = np.zeros(non_fiducial_features.shape)

		#cycle to parameters to calculate derivatives, and do some sanity checks (for example that the parameters are varied one at a time with respect to the fiducial value)
		for n,p in enumerate(derivative_indices):

			#Check that we vary only one parameter at a time
			comparison = non_fiducial_parameters[n] == self.parameter_set[self._fiducial]
			assert comparison.sum() == len(comparison) - 1,"You must vary one parameter at a time!"

			#Check which is the parameter that we varied
			varied_parameter_index = np.where(comparison==False)[0][0]
			assert varied_parameter_index not in self._varied_list,"You cannot vary a parameter twice!!"
			self._varied_list.append(varied_parameter_index)

			#Calculate the finite difference derivative with respect to this parameter
			derivatives[n]  = (non_fiducial_features[n] - self.training_set[self._fiducial]) / (non_fiducial_parameters[n,varied_parameter_index] - self.parameter_set[self._fiducial,varied_parameter_index])

		#set the derivatives attribute and return the result
		self.derivatives = derivatives

		return derivatives

	def get_varied(self):

		"""
		Displays the ordered list of the indices of the varied parameters 

		"""

		assert hasattr(self,"derivatives"),"You must compute the derivatives first!"

		return self._varied_list

	def fit(self,observed_feature,features_covariance):

		"""
		Maximizes the gaussian likelihood on which the Fisher matrix formalism is based, and returns the best fit for the parameters given the observed feature

		:param observed_feature: observed feature to fit, must have the same shape as self.training_set[0] (or derivatives[0])
		:type observed_feature: array

		:param features_covariance: covariance matrix of the simulated features, must be provided for a correct fit!
		:type features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:returns: array with the best fitted parameter values

		"""

		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"

		#Check for correct shape of input
		assert observed_feature.shape == self.training_set.shape[1:]
		assert features_covariance.shape == observed_feature.shape * 2 or features_covariance.shape == observed_feature.shape

		#If derivatives are not computed, compute them
		if not hasattr(self,"derivatives"):
			self.compute_derivatives()

		#Linear algebra manipulations (parameters = M x features)
		if features_covariance.shape == observed_feature.shape * 2:
			Y = solve(features_covariance,self.derivatives.transpose())
		else:
			Y = (1/features_covariance[:,np.newaxis]) * self.derivatives.transpose()

		XY = np.dot(self.derivatives,Y)
		M = solve(XY,Y.transpose())

		#Compute difference in parameters (with respect to the fiducial model)
		dP = np.dot(M,observed_feature - self.training_set[self._fiducial])

		#Return the actual best fit
		return self.parameter_set[self._fiducial,self._varied_list] + dP



	def fisher_matrix(self,simulated_features_covariance,observed_features_covariance=None):

		"""
		Computes the Fisher matrix of the associated features, that in the end allows to compute the paramtere confidence contours (around the fiducial value)

		:param simulated_features_covariance: covariance matrix of the simulated features, must be provided for a correct fit!
		:type simulated_features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:param observed_features_covariance: covariance matrix of the simulated features, if different from the simulated one; if None the simulated feature covariance is used
		:type observed_features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:returns: 2 dimensional array with the Fisher matrix of the analysis

		"""

		#Check for correct shape of input
		assert simulated_features_covariance is not None,"No science without the covariance matrix, you must provide one!"
		assert simulated_features_covariance.shape == self.training_set.shape[1:] * 2 or simulated_features_covariance.shape == self.training_set.shape[1:]

		#If derivatives are not computed, compute them
		if not hasattr(self,"derivatives"):
			self.compute_derivatives()

		#Linear algebra manipulations (parameters = M x features)
		if simulated_features_covariance.shape ==  self.training_set.shape[1:] * 2:
			Y = solve(simulated_features_covariance,self.derivatives.transpose())
		else:
			Y = (1/simulated_features_covariance[:,np.newaxis]) * self.derivatives.transpose()
		
		XY = np.dot(self.derivatives,Y)

		#If we are using the same covariance matrix for observations and simulations, then XY is the Fisher matrix; otherwise we need to compute M too
		if observed_features_covariance is None:
			
			return XY
		
		else:

			assert observed_features_covariance.shape == self.training_set.shape[1:] * 2 or observed_features_covariance.shape == self.training_set.shape[1:]
			
			M = solve(XY,Y.transpose())
			
			if observed_features_covariance.shape == self.training_set.shape[1:] * 2:
				parameter_covariance = np.dot(M,np.dot(observed_features_covariance,M.transpose()))
			else:
				parameter_covariance = np.dot(M * observed_features_covariance,M.transpose())

			return inv(parameter_covariance)


#######################################################
#############Full analysis#############################
#######################################################

class LikelihoodAnalysis(Analysis):

	_analysis_type = "Likelihood"

	"""
	The class handler of a full likelihood analysis; the parameter likelihood function is calculated with an interpolation of various kind between simulation points

	"""

	def __init__(self,parameter_set=None,training_set=None):
		super(LikelihoodAnalysis,self).__init__(parameter_set=parameter_set,training_set=training_set) 
		self._likelihood_function = gaussian_likelihood

	def set_likelihood(self,function=None):

		"""
		Sets the likelihood function to a custom function input by the user: the default is the usual exp(-0.5*chi^2)

		"""

		assert function is not None
		self._likelihood_function = function

	def train(self,use_parameters="all",**kwargs):

		"""
		Builds the interpolators for each of the feature bins using a radial basis function approach

		:param use_parameters: which parameters actually vary in the supplied parameter set (it doesn't make sense to interpolate over the constant ones)
		:type use_parameters: list. or "all"

		:param kwargs: keyword arguments to be passed to the interpolator constructor

		"""

		#input sanity check
		if use_parameters != "all":
			assert type(use_parameters) == list
			used_parameters = self.parameter_set[:,use_parameters].transpose()
		else:
			used_parameters = self.parameter_set.transpose()

		#Compute total number of feature bins and reshape the training set accordingly
		self._num_bins = reduce(mul,self.training_set.shape[1:])
		flattened_training_set = self.training_set.reshape((self.training_set.shape[0],self._num_bins))

		#Build one interpolator for each feature bin (not optimal but we suck it up for now)
		self._interpolator = list()

		for n in range(self._num_bins):

			self._interpolator.append(_interpolate_wrapper(Rbf,args=(tuple(used_parameters) + (flattened_training_set[:,n],)),kwargs=kwargs))

		return None

	def predict(self,parameters):

		"""
		Predicts the feature at a new point in parameter space using the bin interpolators, trained with the simulated features

		:param parameters: new points in parameter space on which to compute the chi2 statistic; it'a (N,p) array where N is the number of points and p the number of parameters, or array of size p if there is only one point
		:type parameters: array  

		"""

		#If you didn't do training before, train now with the default settings
		if not hasattr(self,"_interpolator"):
			self.train()

		#Interpolate to compute the features
		interpolated_feature = _predict(parameters,self._num_bins,self._interpolator)

		#Return the result
		if parameters.ndim == 1:
			return interpolated_feature.reshape(self.training_set.shape[1:])
		else:
			return interpolated_feature.reshape((parameters.shape[0],) + self.training_set.shape[1:])


	def chi2(self,parameters,observed_feature,features_covariance,split_chunks=None,pool=None):

		"""
		Computes the chi2 part of the parameter likelihood with the usual sandwich product with the covariance matrix; the model features are computed with the interpolators

		:param parameters: new points in parameter space on which to compute the chi2 statistic
		:type parameters: (N,p) array where N is the number of points and p the number of parameters

		:param observed_feature: observed feature on which to condition the parameter likelihood
		:type observed_feature: array

		:param features_covariance: covariance matrix of the features, must be supplied
		:type features_covariance: array

		:param split_chunks: if set to an integer bigger than 0, splits the calculation of the chi2 into subsequent chunks, each that takes care of an equal number of points. Each chunk could be taken care of by a different processor
		:type split_chunks: int.

		:returns: array with the chi2 values, with the same shape of the parameters input

		"""

		#Sanity checks
		assert observed_feature is not None 
		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"
		assert observed_feature.shape == self.training_set.shape[1:]
		assert features_covariance.shape == observed_feature.shape * 2

		#If you didn't do training before, train now with the default settings
		if not hasattr(self,"_interpolator"):
			self.train()

		#Reformat the parameter input into a list of chunks
		if parameters.ndim==1:
			num_points = 1
		else:
			num_points = parameters.shape[0]

		if split_chunks is None:
			
			parameter_chunks = [parameters]
		
		elif split_chunks > 0:
			
			assert num_points%split_chunks == 0,"split_chunks must divide exactly the number of points!!"
			chunk_length = num_points//split_chunks
			parameter_chunks = [ parameters[n*chunk_length:(n+1)*chunk_length] for n in range(split_chunks) ]

		else:

			raise ValueError("split_chunks must be >0!!")

		#Compute the inverse of the covariance matrix once and for all
		covinv = inv(features_covariance)

		#Build the keyword argument dictionary to be passed to the chi2 calculator
		kwargs = {"num_bins":self._num_bins,"interpolator":self._interpolator,"inverse_covariance":covinv,"observed_feature":observed_feature}

		#Hack to make the chi2 pickleable (from emcee)
		chi2_wrapper = _function_wrapper(chi2,tuple(),kwargs)

		#Finally map chi2 calculator on the list of chunks
		if pool is not None:
			M = pool.map
		else:
			M = map
		
		chi2_list = M(chi2_wrapper,parameter_chunks)

		return np.array(chi2_list).reshape(num_points)


	def likelihood(self,chi2_value,**kwargs):

		"""
		Computes the likelihood value with the selected likelihood function, given the pre-computed chi2 value

		:param chi2_value: chi squared values 
		:type chi2_value: array

		:param kwargs: keyword arguments to be passed to your likelihood function

		"""

		return self._likelihood_function(chi2_value,**kwargs) 




###########################################################################
###########Hack to make scipy interpolate objects pickleable###############
###########################################################################

class _interpolate_wrapper(object):

	def __init__(self,f,args,kwargs):
		self.f = f
		self.args = args
		self.kwargs = kwargs
	
	def __call__(self):
		try:
			return self.f(*self.args,**self.kwargs)
		except:
			import traceback
			print("lenstools: Exception while building the interpolators")
			print(" exception:")
			traceback.print_exc()
			raise
