# coding: utf-8

import math
import os
import logging
import json

import main
import cloudstorage as gcs

from google.appengine.ext import ndb
from google.appengine.api import urlfetch

PULL_ATTEMPTS = 3


class PullFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg
        
        
class ProcessFailureError(Exception):
    def __init__(self, msg):
        self.msg = msg

    
def work_pull(pull):
    response = {}
    results = {}
    filters = []
    failed_filters = []
    key_string = u''
    max_page = 0
    dimension_name = ''
    parameter_name = ''
    request = pull.request.get()
    dimensions = ndb.get_multi(request.dimensions)
    #Build a base query string from the Pull attributes.
    query_base = ("https://www.warcraftlogs.com:443/v1/rankings/encounter/" +
                  str(pull.encounter) + "?metric=" + pull.metric +
                  "&difficulty=" + str(pull.difficulty) +
                  "&class=" + str(request.character_class) +
                  "&spec=" + str(pull.spec) +
                  "&api_key=" + json_pull("apikeys.json")["WCL"]["key"])
    #Get the requests and parameters.
    pull_id = pull.key.id()
    user_id = pull.key.parent().id()
    #Build Filter objects for each parameter. O(N) N=Parameters * spell ids
    for dimension in dimensions:
        parameters = ndb.get_multi(dimension.parameters)
        for parameter in parameters:
            new_filter = main.Filter(dimension = dimension.key,
                                parameter = parameter.key)
            filter_string = "&filter="
            if len(parameter.include) > 0:
                filter_string += "abilities"
                for spell in parameter.include:
                    filter_string += "." + str(spell)
                if len(parameter.exclude) > 0:
                    filter_string += "|"
            if len(parameter.exclude) > 0:
                filter_string += "noabilities"
                for spell in parameter.exclude:
                    filter_string += "." + str(spell)
            new_filter.string = filter_string
            filters.append(new_filter)
    
    #Try to request the base query page 1:
    try:
        response = pull_ranks(query_base)
        #For each rank: O(N2) N2=Ranks
        for rank in response['rankings']:
            #Make a key string (name_server_reportID)
            key_string = (rank['name'] + "_" + 
                          rank['server'] + "_" + 
                          rank['reportID'])
            #Save the rank to results with that key
            results[key_string] = rank
        #Use the total to get a max_page
        max_page = int(math.ceil(float(response['total']) / 500)) + 1
    except PullFailedError:
        raise ProcessFailureError(
            "Could not get ranks count for Pull %d from user %s"
            % (pull_id, user_id))
  
    #For each page after page 1:
    for page in range(2, max_page):
        try:
            response = pull_ranks(query_base + "&page=" + str(page))
            #For each rank: O(N2) N2=Ranks
            for rank in response['rankings']:
                #Make a key string (name_server_reportID)
                key_string = (rank['name'] + "_" + rank['server'] + 
                              "_" + rank['reportID'])
                #Save the rank to results with that key
                results[key_string] = rank
        except PullFailedError:
            raise ProcessFailureError(
                "Could not get ranks count for Pull %d from user %s"
                % (pull_id, user_id))
    #For each filter:
    for filter_ in filters:#O(N1) N1=Parameters
        failed_pages = []
        dimension_name = filter_.dimension.get().name
        parameter_name = filter_.parameter.get().name
        #For each page needed to pull all ranks:
        for page in range(1, max_page):
            #Try to make the request
            try:
                response = pull_ranks(query_base + filter_.string + 
                                      "&page=" + str(page))
                #For each {rank}: O(N2)
                for rank in response['rankings']:
                    #Make a key string (CharacterName_ServerName_FightID)
                    key_string = (rank['name'] + "_" + rank['server'] + 
                                  "_" + rank['reportID'])
                    #Add the filter tag to results
                    results[key_string][dimension_name] = parameter_name
            #If it fails:
            except PullFailedError:
                #Add this page to failed_pages
                logging.error("Pull on filter %s: %s failed after %d attempts."
                              % (dimension_name, parameter_name, PULL_ATTEMPTS))
                failed_pages.append(page)
        #If there are failed pages:
        if len(failed_pages) > 0:
            #Set the .pages property with the list of failed_pages
            filter_.pages = failed_pages
            #Add the filter to failed_filters
            failed_filters.append(filter_)
  
    #If there are any failed Filters:
    if len(failed_filters) > 0:
        filters = failed_filters
        failed_filters = []
        #For each failed filter: O(N1)
        for filter_ in failed_filters:
            failed_pages = []
            dimension_name = filter_.dimension.get().name
            parameter_name = filter_.parameter.get().name
            #For each page needed to pull all ranks:
            for page in filter_.pages:
                #Try to make the request
                try:
                    response = pull_ranks(query_base + filter_.string + 
                                          "&page=" + page)
                    #For each {rank}: O(N2)
                    for rank in response['rankings']:
                        #Make a key string (CharacterName_ServerName_FightID)
                        key_string = (rank['name'] + "_" + rank['server'] + 
                                      "_" + rank['reportID'])
                        #Add the filter tag to results
                        results[key_string][dimension_name] = parameter_name
                #If it fails:
                except PullFailedError:
                    #Add this page to failed_pages
                    logging.error("Pull on filter %s: %s failed after %d attempts."
                                  % (dimension_name, parameter_name, PULL_ATTEMPTS))
                    failed_pages.append(page)
            #If there are failed pages:
            if len(failed_pages) > 0:
                #Set the .pages property with the list of failed_pages
                filter_.pages = failed_pages
                #Add the filter to failed_filters
                failed_filters.append(filter_)
            else:
                filter_.pages = []
  
    #Store the results in Cloud Storage
    filename_core = '/wclstats.appspot.com/' + str(pull_id) + "-" + str(user_id)
    results_filename = filename_core + ".json"
    gcs_file = gcs.open(results_filename, 'w', content_type='application/json; charset=utf-8')
    gcs_file.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
    gcs_file.close()
                
    #Check if incomplete filters still exist.  If so, store the filters and
    #flag the pull incomplete.
    if len(failed_filters) > 0:
        pull.failed_filters = ndb.put_multi(failed_filters)
        pull.status = "Incomplete"
    else:
        pull.failed_filters = []
        pull.status = "Ready"
    
    # Update the Pull in NDB.
    pull.put()
    
def json_pull(dct):
    #Pull data from a static .json file and load it into memory.
    path = os.path.join(os.path.split(__file__)[0], dct)
    return json.load(open(path))
    

def static_request(site, type):
    key = json_pull("apikeys.json")[site]["key"]
    url = json_pull("apikeys.json")[site][type] + key
    
    try:
        urlfetch.set_default_fetch_deadline(60)
        response = urlfetch.fetch(url)
        result = json.loads(response.content)
    except urlfetch.Error:
        logging.error("Request from %s for type %s failed." % (site, type))
        return None
        
    return result
    
# Pull ranks:
def pull_ranks(query_string):
    # Start with a timeout of 15 seconds.
    timeout = 30
    retry = True
    # Make the ranks pull API request.
    while retry == True:
        try:
            urlfetch.set_default_fetch_deadline(timeout)
            response = urlfetch.fetch(query_string).content.decode('utf-8')
            result = json.loads(response)
            # Return the results.
            return result
        # If pull times out:
        except urlfetch.Error:
            logging.error("Pull failed; url %s" % query_string)
            # Double the timeout.
            timeout *= 2
            # If this is the fourth attempt, give up.
            if timeout > 120:
                retry = False
    # If it gets here it failed, so Raise PullFailedError.
    raise PullFailedError("Pull failed with query string %s" % query_string)