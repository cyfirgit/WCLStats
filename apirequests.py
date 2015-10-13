# coding: utf-8
#Module to interface with external apps and their apis.

import json
import os
import logging
import math
import hashlib

from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.ext import ndb
	
	
def static_pull(site, api):
	#This will create a JSON object with the static from an external app i.e. 
	   #WCL or Blizzard.
	site_data = json_pull("apikeys.json")[site]
	url = site_data[api] + site_data["key"]
	
	#XXXThis whole block will need to be updated with whatever front end
	   #framework I use.XXX
	try:
		response = urlfetch.fetch(url)
	except urlfetch_errors.DeadlineExceededError:
		logging.error("Timeout recieving data from %s." % site)
		return None
	except urlfetch_errors.DownloadError:
		logging.error("Network error recieving data from %s." % site)
		return None
	except:
		logging.error("%s data pull encounterd an unknown error" % site)
		return None
	
	return json.loads(response.content)
	
	
'''def rankings_pull_filtered(encounterID, parameters, dimensions):
	result = {}
	
	for dimension in dimensions:
		dimension_ranks = []
		
		#Do a pull for each element in the dimension & combine the results.
		for element in dimension["elements"]:
			pull_parameters = parameters
			
			#Create the "filter=" parameter for the element.
			if element["include"] != None:
				pull_parameters["filter"] = "abilities."
				for spellID in element["include"]:
					s = pull_parameters["filter"] + str(spellID) + "."
					pull_parameters["filter"] = s
				index = len(pull_parameters["filter"])
				s = pull_parameters["filter"][:(index - 1)]
				pull_parameters["filter"] = s
				if element["exclude"] != None:
					s = pull_parameters["filter"] + "|noabilities."
					pull_parameters["filter"] = s
					for spellID in element["exclude"]:
						s = pull_parameters["filter"] + str(spellID) + "."
						pull_parameters["filter"] = s
					index = len(pull_parameters["filter"])
					s = pull_parameters["filter"][:(index - 1)]
					pull_parameters["filter"] = s
			else:
				if element["exclude"] != None:
					pull_parameters["filter"] = "noabilities."
					for spellID in element["exclude"]:
						s = pull_parameters["filter"] + str(spellID) + "."
						pull_parameters["filter"] = s
					index = len(pull_parameters["filter"])
					s = pull_parameters["filter"][:(index - 1)]
					pull_parameters["filter"] = s
				
			#Pull the ranks based on filter criteria & add the element data.
			logging.info("Beginning rankings request for %s" % element["name"])
			for i in range(3):
				element_ranks = rankings_pull_all_pages(encounterID, pull_parameters)
				if element_ranks != None:
					break
				else:
					logging.info("Attempt %d failed." % i)
			else:
				logging.error("Could not establish a successful pull. Aborted.")
				return None
			logging.info("Appending element attribute to retrieved ranks")
			for rank in element_ranks:
				rank[dimension["name"]] = element["name"]
				
			dimension_ranks += element_ranks
				
		if len(result) == 0:
			#If this is the first dimension examined, build results.
			for rank in dimension_ranks:
				rankID = hash_rank(rank["reportID"], rank["name"], 
								   rank["startTime"])
				result[rankID] = rank
		else:
			return result
			#Otherwise, append the new dimension to existing results.
			# for rank in dimension_ranks:
				# rankID = hash_rank(rank["reportID"], rank["name"], 
								   # rank["startTime"])
				# result[rankID][dimension["name"]] = element["name"]
				
	return result'''
	
def rankings_pull_filtered(encounterID, parameters, dimensions):
	filters = build_filters(dimensions)
	result = []
	
	for filter in filters:
		get_filter = []
		pull_parameters = parameters
		pull_parameters["filter"] = filter["filter"]
		for i in range(3):
			logging.info("Try %d to pull rankings for %s" % ((i + 1), filter["name"]))
			get_filter = rankings_pull_all_pages(encounterID, pull_parameters)
			if get_filter != None:
				break
			else:
				logging.info("Attempt %d failed." % (i + 1))
		else:
			logging.error("Could not complete pull in 3 attempts.  Aborted.")
			return None
		for item in get_filter:
			for dimension in filter["dimensions"]:
				item[dimension] = filter["dimensions"][dimension]
		result += get_filter
	
	return result
	
def build_filters(dimensions):
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
	
		
	
				
		
'''def hash_rank(reportID, name, startTime):
	rank_hash = hashlib.sha1()
	rank_hash.update(reportID)
	rank_hash.update(name.encode('utf-8'))
	rank_hash.update(str(startTime))
	return rank_hash.hexdigest()'''
		
	
def rankings_pull_all_pages(encounterID, parameters):
	parameters["limit"] = 1000
	parameters["page"] = 1
	missed_pages = []
	
	logging.info("Attempting first pull")
	for attempt in range(3):
		first_pull = rankings_pull(encounterID, parameters)
		if first_pull != None:
			break
	else:
		logging.error("Could not retreive initial page.")
		return None
	logging.info("Total rankings found: %d" % first_pull["total"])
	total_pages = int(math.ceil(first_pull["total"] / parameters["limit"])) + 1
	result = first_pull["rankings"]
	
	for i in range(2, total_pages + 1):
		parameters["page"] = i
		logging.info("Attempting pull on page %d of %d" % (i, total_pages))
		next_pull = rankings_pull(encounterID,parameters)
		if next_pull != None:
			result += next_pull["rankings"]
		else:
			missed_pages.append(i)
			if len(missed_pages) > total_pages:
				logging.error("Too many pull errors.  Aborting.")
				return None
				
	for page in missed_pages:
		logging.info("Second attempt on page %d of %d" % (page, total_pages))
		next_pull = rankings_pull(encounterID,parameters)
		if next_pull != None:
			result += next_pull["rankings"]
			missed_pages.remove(page)
	
	if len(missed_pages) == 0:
		logging.info("Pull successful. %d rankings retrieved." % \
					 first_pull["total"])
	else:
		missed_list = ""
		for page in missed_pages:
			missed_list += "%d, " % page
		index = len(missed_list)
		missed_pages_list = missed_list[:(index - 3)] + "and " + \
							missed_list[(index - 3):(index - 2)]
		logging.info("Could not retrieve pages %s of %d total pages." % \
					 (missed_pages_list, total_pages))
				
	return result
	
	
def rankings_pull(encounterID, parameters):
	#Pull rankings from WCL based on passed parameters.
	site = "WCL"
	key = json_pull("apikeys.json")["WCL"]["key"]
	url_base = "https://www.warcraftlogs.com:443/v1/rankings/encounter/"
	url_middle = str(encounterID) + "?"
	
	for parameter in parameters:
		if parameters[parameter] != None:
			url_middle += "&" + parameter + "=" + str(parameters[parameter])
	
	url = url_base + url_middle + "&api_key=" + key
	
		#XXXThis whole block will need to be updated with whatever front end
	   #framework I use.XXX
	try:
		response = urlfetch.fetch(url)
	except urlfetch_errors.DeadlineExceededError:
		logging.error("Timeout recieving data from %s." % site)
		return None
	except urlfetch_errors.DownloadError:
		logging.error("Network error recieving data from %s." % site)
		return None
	except:
		logging.error("%s data pull encounterd an unknown error" % site)
		return None
	
	return json.loads(response.content)
	
				  	
def json_pull(dct):
	path = os.path.join(os.path.split(__file__)[0], dct)
	return json.load(open(path))





