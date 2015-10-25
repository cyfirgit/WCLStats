# coding: utf-8

#Module to interface with external apps and their apis.  This includes the
#functions to build the rankings data.  Which is probably not the best of
#organizational schemes, but gets the job done right now.

#Here's the deal: yes, my use of "parameter" and "dimension" is inconsistent as
#hell.  I totally plan to fix it after I have a working prototype for people to
#break.

import json
import os
import logging
import math

from google.appengine.api import urlfetch


class PullTimeoutError(Exception):
	def __init__(self, msg):
		self.msg = msg
	
	
def rankings_pull_filtered(encounterID, parameters, dimensions):
	#This is the function that should be the core of any full request.  It uses
	#the other functions below to actually structure, scale, and implement the
	#request.
	
	filters = build_filters(dimensions)
	result = []
	
	for filter in filters:
		get_filter = []
		pull_parameters = parameters
		pull_parameters["filter"] = filter["filter"]

		logging.info("Pulling ranks for %s" % filter["name"])
		
		try:
			get_filter = rankings_pull_all_pages(encounterID, pull_parameters)
		except PullTimeoutError as e:
			logging.error(e.msg)
			return None
		
		for item in get_filter:
			for dimension in filter["dimensions"]:
				item[dimension] = filter["dimensions"][dimension]
		result += get_filter
	
	return result
	
	
def build_filters(dimensions):
	#Take a dictionary of dimensions and create a set of unique filters for
	#each permution of combining parameters from those dimensions.
	filter_count = 1
	filter_options = []
	filter_counter = []
	filter_reference = {}
	dimension_reference = {}
	result = []
	dimension_counter = 0
	for dimension in dimensions:
		filter_count *= len(dimensions[dimension])
		filter_options.append(len(dimensions[dimension]))
		filter_counter.append(0)
		item_counter = 0
		current = len(filter_counter) - 1
		dimension_reference[dimension_counter] = dimension
		filter_reference[current] = {}
		for item in dimensions[dimension]:
			filter_reference[current][item_counter] = item
			item_counter += 1
		dimension_counter += 1
			
	#filter dictionary format-
	#name:
	#dimensions: [dimension1, dimension2...]
	#filter: 
	
	for i in range(filter_count):
		for j in range(len(dimensions)):
			if filter_counter[j] < filter_options[j]:
				include = "abilities"
				exclude = "noabilities"
				filter_name = ""
				filter_built = {"dimensions":{}}
				
				for k in range(len(dimensions)):
					filter_k = filter_reference[k][filter_counter[k]]
					
					filter_name += filter_k
					dimension_name = dimension_reference[k]
					filter_built["dimensions"][dimension_name] = filter_k
					if k < len(dimensions) - 1:
						filter_name += "|"
						
					current_dimension = dimensions[dimension_name][filter_k]
					if current_dimension["include"] != None:
						for spellID in current_dimension["include"]:
							include += "." + str(spellID)
					if current_dimension["exclude"] != None:
						for spellID in current_dimension["exclude"]:
							exclude += "." + str(spellID)
					
				if len(include) == 9:
					include = ""
				else:
					if len(exclude) == 11:
						exclude = ""
					else:
						exclude = "|" + exclude
						
				filter_built["filter"] = include + exclude
				filter_counter[0] += 1
				filter_built["name"] = filter_name
				result.append(filter_built)
				break
			else:
				filter_counter[j] = 0
				filter_counter[j + 1] += 1
	
	return result
		
	
def build_trinket_dimensions(trinkets):
	#Take a set of trinket options and generate a dimensions dictinary that can
	#be appended to the other dimensions.  This function will always return a 
	#list of dimensions that only factors in the selected trinkets; the user
	#must specifically include "Other Trinkets" as a trinket choice to see e.g.
	#ranks where only one of the selected trinkets is in use.
	''' Trinkets come in as:
	[
		{
			"name": "",
			"include": [1, 2, ... n],
			"exclude": [1, 2, ... n]
			}
		]
	Dictionary goes out as:
	{
		"Trinket1|Trinket2": {
			"include": [1, 2, ... n],
			"exclude": [1, 2, ... n]
			}
		}
	'''
	slot = [0,1]
	result = {}
	trinkets_exclude_all = []
	both_other_trinkets_flag = False
	kill_index = None
	
	#We need to create a list of all trinket effects we're considering.  During
	#the loop, we'll remove the other trinket's effect from this list for each
	#trinket considered.  During this loop we'll also flag to construct a
	#dimension for "Both Other Trinkets"
	for trinket in trinkets:
		if trinket["include"] != None:
			trinkets_exclude_all += trinket["include"]
		if trinket["name"] == "Both Other Trinkets":
			both_other_trinkets_flag = True
			kill_index = trinkets.index(trinket)
	if kill_index != None:
		trinkets.pop(kill_index)
	if both_other_trinkets_flag == True:
		result["Both Other Trinkets"] = {}
		result["Both Other Trinkets"]["include"] = None
		result["Both Other Trinkets"]["exclude"] = trinkets_exclude_all

	#We use a theorem one stars and bars formula to determine the number of
	#possible combinations of trinkets.  Because k is always 2 (number of 
	#trinket slots,) the formula can be reduced significantly.		
	dimensions = (len(trinkets)**2 - len(trinkets)) / 2
	
	for dimension in range(dimensions):
	
		#If one of the trinkets is "Other Trinkets", apply an "exclude" to it
		#equal to the "include" of every trinket except the paired counterpart.
		if trinkets[slot[0]]["name"] == "Other Trinkets":
			other_trinkets_exclude = list(trinkets_exclude_all)
			for i in range(len(trinkets[slot[1]]["include"])):
				other_trinkets_exclude.remove(trinkets[slot[1]]["include"][i])
			trinkets[slot[0]]["exclude"] = other_trinkets_exclude
		elif trinkets[slot[1]]["name"] == "Other Trinkets":
			other_trinkets_exclude = list(trinkets_exclude_all)
			for i in range(len(trinkets[slot[0]]["include"])):
				other_trinkets_exclude.remove(trinkets[slot[0]]["include"][i])
			trinkets[slot[1]]["exclude"] = other_trinkets_exclude
		
		
		pair = {"include": [], "exclude": []}
		name = trinkets[slot[0]]["name"] + "|" + trinkets[slot[1]]["name"]
		if trinkets[slot[0]]["include"] != None:
			pair["include"] += trinkets[slot[0]]["include"]
		if trinkets[slot[1]]["include"] != None:
			pair["include"] += trinkets[slot[1]]["include"]
		if trinkets[slot[0]]["exclude"] != None:
			pair["exclude"] += trinkets[slot[0]]["exclude"]
		if trinkets[slot[1]]["exclude"] != None:
			pair["exclude"] += trinkets[slot[1]]["exclude"]
			
		if len(pair["include"]) == 0:
			pair["incldue"] = None
		if len(pair["exclude"]) == 0:
			pair["exclude"] = None
		
		result[name] = pair
		
		#increment trinket pairings
		if slot[1] + 1 < len(trinkets):
			slot[1] += 1
		elif slot[0] + 1 < slot[1]:
			slot[0] += 1
			slot[1] = slot[0] + 1
			
	return result
		
	
def rankings_pull_all_pages(encounterID, parameters):
	#Take a set of dimensions(w/ a unique set of parameters,) and pull all
	#pages of applicable rankings.
	
	parameters["limit"] = 5000
	parameters["page"] = 1
	
	for attempt in range(50):
		logging.info("Pull %d on first page" % (attempt + 1))
		first_pull = rankings_pull(encounterID, parameters)
		if first_pull != None:
			break
	else:
		logging.info("Could not retreive initial page.")
		raise PullTimeoutError("Inital pull failed after 50 attempts.")
	
	logging.info("Total rankings found: %d" % first_pull["total"])
	total_pages = int(math.ceil(first_pull["total"] / parameters["limit"])) + 1
	result = first_pull["rankings"]
	
	for i in range(2, total_pages + 1):
		parameters["page"] = i
		for j in range(50):
			logging.info("Pull %d on page %d of %d" % ((j + 1), i, total_pages))
			next_pull = rankings_pull(encounterID,parameters)
			if next_pull != None:
				result += next_pull["rankings"]
				break
		else:
			raise PullTimeoutError("Pull %d of %d failed after 50 attempts." %\
								   (i, total_pages))
				
	return result
	
	
def rankings_pull(encounterID, parameters):
	#Pull a single page of ranks.
	key = json_pull("apikeys.json")["WCL"]["key"]
	url_base = "https://www.warcraftlogs.com:443/v1/rankings/encounter/"
	url_middle = str(encounterID) + "?"
	
	#In this loop, we take each parameter and stick it into the request url.
	for parameter in parameters:
		if parameters[parameter] != None:
			url_middle += "&" + parameter + "=" + str(parameters[parameter])
	
	url = url_base + url_middle + "&api_key=" + key
		
	try:
		urlfetch.set_default_fetch_deadline(60)
		response = urlfetch.fetch(url)
		result = json.loads(response.content)
	except urlfetch.Error:
		logging.error("Pull failed.")
		return None
	
	return result
	
				  	
def json_pull(dct):
	#Pull data from a static .json file and load it into memory.
	path = os.path.join(os.path.split(__file__)[0], dct)
	return json.load(open(path))
	







