# coding: utf-8

import math
import os
import logging
import json

import main
import cloudstorage as gcs

from google.appengine.ext import ndb
from google.appengine.api import urlfetch
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

PULL_ATTEMPTS = 3


class PullFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg
        
        
class ProcessFailureError(Exception):
    def __init__(self, msg):
        self.msg = msg

    
def work_pull(pull):
    author = pull.key.parent().get()
    request = pull.request.get()
    
    main.vislog('Starting "%s" by %s' % (request.name, author.nickname))
    
    pull_id = pull.key.id()
    user_id = pull.key.parent().id()
    response = {}
    results = {}
    filters = []
    failed_filters = []
    key_string = u''
    max_page = 0
    dimension_name = ''
    parameter_name = ''
    dimensions = ndb.get_multi(request.dimensions)
    #Add the trinket dimension to dimensions.
    dimensions.append(request.trinket_dimension.get())
    #Build a base query string from the Pull attributes.
    query_base = ("https://www.warcraftlogs.com:443/v1/rankings/encounter/" +
                  str(pull.encounter) + "?metric=" + pull.metric +
                  "&difficulty=" + str(pull.difficulty) +
                  "&class=" + str(request.character_class) +
                  "&spec=" + str(pull.spec) +
                  "&api_key=" + json_pull("apikeys.json")["WCL"]["key"] + 
                  "&limit=500")
    #Get the requests and parameters.
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
        response = pull_ranks(query_base + "&page=1")
        #For each rank: O(N2) N2=Ranks
        for rank in response['rankings']:
            #Make a key string (name_server_reportID)
            key_string = (rank['name'] + "_" + 
                          rank['server'] + "_" + 
                          rank['reportID'])
            #Save the rank to results with that key
            results[key_string] = rank
        #Use the total to get a max_page
        max_page = int(math.ceil(float(response['total']) / 500))
    except PullFailedError:
        raise ProcessFailureError(
            "Could not get ranks count for Pull %d from user %s"
            % (pull_id, user_id))
  
    #For each page after page 1:
    for page in range(2, max_page + 1):
        try:
            logging.info('Building initial results for page %d' % page)
            response = pull_ranks(query_base + "&page=" + str(page))
            #For each rank: O(N2) N2=Ranks
            for rank in response['rankings']:
                #Make a key string (name_server_reportID)
                key_string = (rank['name'] + "_" + 
                              rank['server'] + "_" + 
                              rank['reportID'])
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
        for page in range(1, max_page + 1):
            #Try to make the request
            try:
                logging.info('Pulling page %d of filter %s|%s' % (page, dimension_name, parameter_name))
                response = pull_ranks(query_base + filter_.string + 
                                      "&page=" + str(page))
                #For each {rank}: O(N2)
                for rank in response['rankings']:
                    #Make a key string (CharacterName_ServerName_FightID)
                    key_string = (rank['name'] + "_" + 
                                  rank['server'] + "_" + 
                                  rank['reportID'])
                    #Add the filter tag to results
                    if dimension_name == "Trinkets":
                        try:
                            if 'Trinket1' in results[key_string]:
                                results[key_string]['Trinket2'] = parameter_name
                            else:
                                results[key_string]['Trinket1'] = parameter_name
                        except KeyError:
                            logging.error('Could not add %s to dimension %s on key %s' %(parameter_name, dimension_name, key_string))
                    else:
                        try:
                            results[key_string][dimension_name] = parameter_name
                        except KeyError:
                            logging.error('Could not add %s to dimension %s on key %s' %(parameter_name, dimension_name, key_string))
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
                        key_string = (rank['name'] + "_" + 
                                      rank['server'] + "_" + 
                                      rank['reportID'])
                        #Add the filter tag to results
                    if dimension_name == "Trinkets":
                        try:
                            if results[key_string]['Trinket1'] != None:
                                results[key_string]['Trinket2'] = parameter_name
                        except KeyError:
                            results[key_string]['Trinket1'] = parameter_name
                    else:
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
        main.vislog("Starting csv build")
        #Take the collected ranks from a pull request and formats them into a 
        #.csv file.  
        csvfile = ""
        #Determine if the pull is for a mythic encounter.
        difficulties = main.Reference.get_by_id('difficulties').json
        for difficulty in difficulties:
            if difficulty['name'] == "Mythic":
                mythic_level = difficulty['id']
        is_mythic = pull.difficulty is mythic_level
        #These are the fields that WCL kicks out in any ranks pull.
        fieldnames = ["name", "class", "spec", "itemLevel", "total",
                      "duration", "size", "link", "guild", "server"]
        #If there's a trinket dimension, add it to the list of dimensions.
        if request.trinket_dimension != None:
            fieldnames.append('Trinket1')
            fieldnames.append('Trinket2')
        #Add all of the request dimensions add fields for the csv file.
        for dimension in dimensions:
            if dimension.name != 'Trinkets':
                fieldnames.append(dimension.name)
        
        #Start the file with the field names.
        for field in fieldnames:
            csvfile += field + ","
        csvfile += "\n"
        
        #Take each rank and format it as csv.
        for rank in results:
            rank_line = ""
            for item in fieldnames:
                #If the item is the report link, take the fightID and turn it 
                #into an actual URL.
                if item == "link":
                    rank_line += "https://www.warcraftlogs.com/reports/" + \
                                results[rank]["reportID"] + "#fight=" + \
                                str(results[rank]["fightID"]) + ","
                #Mythic ranks pulls don't include a size field, so if it's a 
                #mythic pull, we need to manually add "20" as the size.
                elif item == "size":
                    if is_mythic:
                        rank_line += str(20) + ","
                    else:
                        rank_line += unicode(results[rank][item]) + ","
                #For anything else, just get the applicable data and plug it in
                #under the correpsonding field name.
                else:
                    try:
                        rank_line += unicode(results[rank][item]) + ","
                    except KeyError:
                        rank_line += unicode("-,")
            rank_line += "\n"
            csvfile += rank_line
      
        #Store the csv in Cloud Storage
        results_filename = filename_core + ".csv"
        blobstore_filename = '/gs' + results_filename
        gcs_file = gcs.open(results_filename, 'w', content_type='application/csv; charset=utf-8')
        gcs_file.write(csvfile.encode('utf-8'))
        gcs_file.close()
        pull.results = blobstore.create_gs_key(blobstore_filename)
        pull.status = "Ready"
    
    # Update the Pull in NDB.
    pull.put()
    
    main.vislog('"%s" by %s %s' % (request.name, author.nickname, pull.status))
    
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
