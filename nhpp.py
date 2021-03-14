import numpy as np

"""
Author: Matthew Campbell
Date of creation: 2/21/21
Date last edited: 3/13/21

PURPOSE: This package is (currently) a standalone module for
generating non-homogeneous Poisson processes (nhpp).
Homogeneous Poisson processes are easily generated by specifying
an arrival rate, lambda, then generating samples from 
X ~ exp(1 / lambda). These samples indicate the inter-arrival
times between events, or the delay between events.

	The above case is only true when lambda is a constant.
Generalizing to the case of lambda(t), a time-dependent arrival
rate, is much trickier to implement. Two main approaches exist
to tackle this issue: (1) relate the INTEGRATED rate function
LAMBDA(t) to a homogeneous Poisson process via an inversion function,
or (2), use a "thinning" method which acts as an acceptance-rejection
sampling routine.

	The method get_arrivals employs the former approach alone when
no function parameter is passed, and a combination of the two approaches
otherwise. The input allows the user to specify a piecewise linear 
approximation to their true arrival rate function. If the true arrival
rate function is known, then the piecewise linear function needs only
to dominate it everywhere on the domain. Returned is a list containing
the arrival times governed by the arrival rate function.

EXAMPLE USAGE:
# Specify the piecewise linear arrival rate via knots.
# Below we specify arrival_rate = 1 at time = 0, arrival_rate = 2 at time = 5,
# arrival_rate = 1 at time = 2.5 (linearity between time = 0 and time = 5), etc.
>>> knots = {0: 1, 5: 2, 12: 0.3, 15: 0.3, 16: 0, 18: 0, 20: 2}

>>> arrs = nhpp.get_arrivals(knots)

# Print out our arrival times.
>>> for arr in arrs:
		print(round(arr, 2))

###
Example USAGE WITH FUNCTION:
# Define knots of a dominating piecewise linear function:
>>> knots = {0: 0, 2.5: 8, 5: 0}
# Define true rate function (polynomial in our case):
>>> def rate_function(t):
		return t * (5 - t)

>>> arrs = nhpp.get_arrivals(knots, rate_function)

# Print out our arrival times.
>>> for arr in arrs:
		print(round(arr, 2))
"""

def _get_piecewise_val(knots, t):
	"""
	Based on the knots specified for a piecewise linear function
	and a point in the domain 't', return the value of the piecewise
	linear function.

	knots: dictionary where keys and values should all be numeric.
	t: numeric within the domain specified by the knots.

	returns: float
	"""
	knots = {i: knots[i] for i in sorted(knots.keys())}

	knot_times = list(knots.keys())
	knot_vals = list(knots.values())

	if t < knot_times[0] or t > knot_times[-1]:
		raise ValueError(f"Cannot determine piecewise value for t={t}")

	s = []

	for i in range(1, len(knot_times)):
		s.append((knot_vals[i] - knot_vals[i-1]) / 
			(knot_times[i] - knot_times[i-1]))

	j = 0
	while knot_times[j+1] < t:
		j += 1
	return knot_vals[j] + s[j]*(t - knot_times[j])


def _get_sorted_pairs(dic):
	dic = {i: dic[i] for i in sorted(dic.keys())}

	keys = list(dic.keys())
	vals = list(dic.values())
	return keys, vals

def _get_rate_slopes(knot_vals, knot_times):
	"""
	Gets the slopes of each section of the rate function.

	Note that we should be o.k. against division by zero,
	but we'll raise an error just in case knot_times
	somehow gets passed in manually.
	"""
	if len(knot_times) != len(list(set(knot_times))):
		raise ValueError("Cannot infer piecewise function from knots.")
		
	return [(knot_vals[i] - knot_vals[i-1]) / 
			(knot_times[i] - knot_times[i-1]) for i in range(1, len(knot_times))]


def _get_integrated_rate_values(knot_vals, knot_times):
	L = [0]
	for i in range(1, len(knot_times)):
		L.append(L[-1] + 
			0.5 * (knot_vals[i] + knot_vals[i-1]) * 
			(knot_times[i] - knot_times[i-1])
			)
	return L


def _check_is_dict(a):
	if type(a) != dict:
		raise TypeError('Value passed must be a dictionary.')

def _check_arrivals_positive(knot_vals):
	for val in knot_vals:
		if val < 0:
			raise ValueError


def get_arrivals(knots: dict, func=None, *func_args, **func_kwargs) -> list :
	"""
	Generate a sequence from a nonhomogeneous Poisson process
	specified by a piecewise linear function determined from
	the knots parameter. The knots should specify the (domain, range)
	of each segment's knot.

	knots: dictionary where keys and values should all be numeric.
	func: function that takes a single float and returns a float.
		Note that the function must be DOMINATED by the piecewise
		linear knots, f(x) >= g(x), everywhere in the domain.

	func_args: additional args to func
	fung_kwargs: additional kwargs to func

	returns: list of floats
	"""
	_check_is_dict(knots)

	knot_times, knot_vals = _get_sorted_pairs(knots)

	_check_arrivals_positive(knot_vals)

	def _inv_int_rate_func(u, j):
		"""
		Inner function defined here due to its dependence
		on the specific knots. Calculates the inverted
		INTEGRATED rate function.
		"""
		res = 0
		if s[j] != 0:
			res = knot_times[j] + 2 * (u - L[j]) / (
				knot_vals[j] + np.sqrt(
					knot_vals[j]**2 + 2 * s[j] * (u - L[j])
					)
				)
		else: # Case when slope of rate is 0
			res = knot_times[j] + (u - L[j]) / knot_vals[j]
		return res

	s = _get_rate_slopes(knot_vals, knot_times)
	L = _get_integrated_rate_values(knot_vals, knot_times)

	a = [0] # Arrival times for nonhomogeneous poisson process
	u = [0] # Arrival times for homogeneous poisson process 
	j = 0   # Counter to see which 'piece' of the integrated rate function we are in.

	while True:
		u_next = u[-1] + np.random.exponential(1.0)
		if u_next >= L[-1]:
			break
		while L[j+1] < u_next and j < len(knot_times):
			j += 1
		a_next = _inv_int_rate_func(u_next, j)
		
		if func:
			# In this branch we reject a_next if an independently
			# drawn uniform RV falls out of our acceptance region,
			# i.e., the ratio of the smooth function and the
			# piecewise approx.

			ind_unif = np.random.uniform(0,1)
			prob_ratio = func(a_next, *func_args, **func_kwargs) / _get_piecewise_val(knots, a_next)
			if prob_ratio > 1:
				raise ValueError('Piecewise function does not dominate smooth function.')
			if ind_unif < prob_ratio:
				a.append(a_next)
			u.append(u_next)

		else:
			a.append(a_next)
			u.append(u_next)
	return a[1:]
