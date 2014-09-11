from __future__ import division,print_function,with_statement

try:
	from lenstools.external import _design
	_design = _design
except ImportError:
	_design = None

import numpy as np

try:
	import matplotlib.pyplot as plt
	from mpl_toolkits.mplot3d import Axes3D
	matplotlib = True
except ImportError:
	matplotlib = False

######################################
#########Design class#################
######################################

class Design(object):

	"""
	
	A class that proves useful in designing simulation sets: the main functionality provided is the uniform sampling of an arbirtarily high dimensional parameter space. The points in parameter space are chosen to be as spread as possible by minimizing a cost function, but enforcing a latin hypercube structure, in which each parameter value appears once

	"""

	def __init__(self):

		#Check for GSL installation problems
		if _design is None:
			raise ImportError("couldn't import the _design library, probably GSL is not installed!")

		#Initialize with 0 points in 0 dimensions
		self.ndim = 0
		self.npoints = 0

		#Useful dictionary containers
		self.parameters = list()
		self.min = dict()
		self.max = dict()
		self.label = dict()
		self.axis = dict()

	def __repr__(self):
		
		if not self.ndim:
			return "This is an empty design!"
		else:
			return "This design has {0} points distributed in a {1}-dimensional parameter space".format(self.npoints,self.ndim)

	def add_parameter(self,parameter_name,min,max,label):

		"""
		Add a dimension to the design by specifying a parameter name, a range and a parameter label (can be in tex format)

		:param parameter_name: the name of the parameter
		:type parameter_name: str.

		:param min: the lower range of the sample interval
		:type min: float.

		:param max: the higher range of the sample interval
		:type max: float.

		:param label: the parameter label you want displayed on a plot, can be in tex format
		:type label: str.

		"""

		assert min<max
		assert parameter_name not in self.parameters,"The parameter is already present!"

		#Fill in containers with the new information
		self.parameters.append(parameter_name)
		self.min[parameter_name] = min
		self.max[parameter_name] = max
		self.label[parameter_name] = label

		#Increase parameter count
		self.axis[parameter_name] = self.ndim
		self.ndim += 1

		#Log the operation
		print("Added a parameter: {0} -> min={1} max={2}".format(parameter_name,min,max))

	def scale(self):
		
		"""
		Scales the points in the design to their respective parameter ranges

		"""

		assert hasattr(self,"points_raw")
		if not hasattr(self,"points"):
			self.points = np.zeros((self.npoints,self.ndim))

		for parameter in self.parameters:
			self.points[:,self.axis[parameter]] = self.min[parameter] + self.points_raw[:,self.axis[parameter]]*(self.max[parameter] - self.min[parameter])


	def put_points(self,npoints):

		"""
		Lay down a number of points on the empty Design: the points are initially layed down on the diagonal of the hypercube

		:param npoints: the number of points to lay down
		:type npoints: int.

		"""
		assert self.ndim>1,"The design must have at least 2 dimensions before laying down points!"
		assert npoints>2, "You must lay down at least 3 points!"

		self.npoints = npoints

		#Lay down points along the diagonal
		self.points_raw = np.outer(np.arange(self.npoints),np.ones(self.ndim)) / (self.npoints - 1)
		
		#Scale to parameter ranges
		self.scale()


	def visualize(self,fig=None,ax=None,parameters=None,**kwargs):

		"""
		Visualize the design configuration using matplotlib

		:param parameters: the parameters to visualize, you can specify two or three of them, by their names. If None, all parameters are visualized
		:type parameters: list.

		"""

		if not matplotlib:
			raise ImportError("matplotlib is not installed, please install it!")

		if parameters is None:
			parameters = self.parameters

		#Check that there are points to plot
		assert hasattr(self,"points"),"There are no points to plot!!"

		#Check that the parameters exist
		for p in parameters:
			assert p in self.parameters,"Parameter {0} is not in your design!".format(p)

		#Check that the parameters to visualize are 2 or 3
		assert len(parameters) in [2,3],"Can plot 2D or 3D projections only!"

		#Instantiate figure and ax objects
		if (fig is None) or (ax is None):
			
			if len(parameters)==2:
				self.fig,self.ax = plt.subplots()
			else:
				self.fig = plt.figure()
				self.ax = self.fig.add_subplot(111,projection="3d")
		
		else:
			
			self.fig,self.ax = fig,ax

		#Lay down the points on the figure
		points = tuple([ self.points[:,self.axis[p]] for p in parameters ])
		self.ax.scatter(*points,**kwargs)

		#Set the labels on the axes
		self.ax.set_xlabel(self.label[parameters[0]])
		self.ax.set_ylabel(self.label[parameters[1]])
		self.ax.set_xlim(self.min[parameters[0]],self.max[parameters[0]])
		self.ax.set_ylim(self.min[parameters[1]],self.max[parameters[1]])

		if len(parameters)==3:
			self.ax.set_zlabel(self.label[parameters[2]])
			self.ax.set_zlim(self.min[parameters[2]],self.max[parameters[2]])

	def savefig(self,filename):

		"""
		Save the visualization to an external file

		:param filename: name of the file on which to save the plot
		:type filename: str.

		"""

		self.fig.savefig(filename)

	def set_title(self,title):

		"""
		Give a title to the visualized design

		:param title: title of the figure
		:type title: str.

		"""

		self.ax.set_title(title)

	################################################################################################################################
	######################These methods make use of the external _design library to compute and optimize design costs###############
	################################################################################################################################

	def diagonalCost(self,Lambda):

		"""
		Computes the cost function of a diagonal configuration with a specified number of points and a metric parameter lambda; the cost function is calculated on the scaled parameter values, which are always between 0 and 1

		:param Lambda: metric parameter of the cost function; if set to 1.0 the cost function corresponds is the Coulomb potential energy
		:type Lambda: float.

		:returns: the value of the cost function for a diagonal configuration

		"""

		assert self.npoints>2,"You must lay down at least 3 points!"
		return _design.diagonalCost(self.npoints,Lambda)

	def cost(self,p,Lambda):

		"""
		Computes the cost function of the current configuration given the metric parameters (p,Lambda)

		:param Lambda: metric parameter of the cost function; if set to 1.0 the cost function corresponds is the Coulomb potential energy
		:type Lambda: float.

		:param p: metric parameter of the cost function; if set to 2.0 the distances between points are the Euclidean ones
		:type p: float.

		:returns: the value of the cost function

		"""

		assert self.ndim>1,"The design must have at least 2 dimensions before laying down points!"
		assert self.npoints>2,"You must lay down at least 3 points!"

		return _design.cost(self.points_raw,p,Lambda)**(1.0/Lambda)

	def sample(self,p,Lambda,seed=0,maxIterations=10000):

		"""
		Evenly samples the parameter space by minimizing the cost function computed with the metric parameters (p,Lambda)

		:param Lambda: metric parameter of the cost function; if set to 1.0 the cost function corresponds is the Coulomb potential energy
		:type Lambda: float.

		:param p: metric parameter of the cost function; if set to 2.0 the distances between points are the Euclidean ones
		:type p: float.

		:param seed: random seed with which the sampler random generator will be initialized
		:type seed: int.

		:param maxIterations: maximum number of iterations that the sampler can perform before stopping
		:type maxIterations: int.

		:returns: the relative change of the cost function the last time it varied during the sampling

		"""

		assert self.ndim>1,"The design must have at least 2 dimensions before laying down points!"
		assert self.npoints>2,"You must lay down at least 3 points!"

		#Create array that holds the values of the cost function
		self.cost_values = np.ones(maxIterations) * -1.0

		deltaPerc = _design.sample(self.points_raw,p,Lambda,maxIterations,seed,self.cost_values)
		self.scale()

		#Cut the cost_values if we stopped before the maxIterations limit
		cut = (self.cost_values==-1).argmin()
		if cut:
			self.cost_values = self.cost_values[:cut]

		return deltaPerc