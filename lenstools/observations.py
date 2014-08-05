"""

.. module:: observations
	:platform: Unix
	:synopsis: This module handles the book keeping of a observation set map names (for example the CFHTLens subfields)


.. moduleauthor:: Andrea Petri <apetri@phys.columbia.edu>


"""

from __future__ import division,print_function,with_statement

import os

################################################
###############CFHTLens class###################
################################################

class CFHTLens(object):

	"""
	Class handler of the CFHTLens reduced data set, already split in 13 3x3 deg^2 subfields 

	"""

	def __init__(self,root_path=None):

		assert root_path is not None,"You must specify the root path of your CFHTLens subfield observations local copy!"
		self.root_path = root_path

	def getName(self,subfield=1,smoothing=0.5):

		full_name = os.path.join(self.root_path,"KS_obs")
		full_name += "_subfield{0}_".format(subfield)
		full_name += "sigma{0:02d}".format(int(smoothing*10))
		full_name += ".fit"

		return full_name