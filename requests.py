# coding: utf-8

#Module to handle structuring and executing requests against external apis.

import json
import os
import logging
import math

import main
import cloudstorage as gcs

from google.appengine.ext import ndb
from google.appengine.api import urlfetch

DEFAULT_LIMIT = 5000
    
class Selection(ndb.Model):
    dimension = ndb.KeyProperty()
    parameter = ndb.KeyProperty()

class Filter(ndb.Model):
    name = ndb.StringProperty()
    string = ndb.StringProperty()
    selections = ndb.StructuredProperty(Selection, repeated=True)
    failed_pages = ndb.IntegerProperty(repeated=True)

class PullFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg
        
        
class ProcessFailureError(Exception):
    def __init__(self, msg):
        self.msg = msg
    
                      
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


# Work a pull:
def work_pull(pull):
    request = pull.request.get()
    dimensions = ndb.get_multi(request.dimensions)
    # If trinkets are being considered:
    if request.trinket_dimension != None:
        trinket_dimension = request.parsed_trinket_dimension.get()
        dimensions.append(trinket_dimension)
    failed_pulls = []
    results = []
    # Flag the pull as processing.
    pull.status = 'Processing'
    # Build a base query string using the shared (non-filter) arguments *except* spec.
    query_base = ("https://www.warcraftlogs.com:443/v1/rankings/encounter/" +
                  str(pull.encounter) + "?metric=" + pull.metric +
                  "&difficulty=" + str(pull.difficulty) +
                  "&class=" + str(request.character_class) +
                  "&limit=" + str(DEFAULT_LIMIT) +
                  "&spec=" + str(pull.spec) +
                  "&api_key=" + json_pull("apikeys.json")["WCL"]["key"])
    
    # Build a list of "unpacked" pseudo dimensions - dictionaries in the format
    '''{
        'name': dimension.name,
        'key': dimension.key,
        'parameters': [Parameter, Parameter, ...],
        }'''
    dimensions_pseudo = []
    for dimension in dimensions:
        new_pseudo = {'name':dimension.name, 
                      'key': dimension.key,
                      'parameters':ndb.get_multi(dimension.parameters)}
        dimensions_pseudo.append(new_pseudo)
        
    # Create a list, filters, to place Filter objects into.
    filters = []
    # Determine how many filters will be created.
    total_filters = 1
    for dimension in dimensions_pseudo:
        total_filters *= len(dimension['parameters'])
    # Generate a counter array to track which parameters to use.
    counter = []
    for i in range(len(dimensions_pseudo)):
        counter.append(0)
    # Structure a filter for each unique combination of parameters by dimension.
    for i in range(total_filters):
        new_filter = Filter(selections=[])
        names = ""
        abilities = ""
        noabilities = ""
        # Iterate the counter.
        for j in range(len(dimensions_pseudo)):
            counter[j] += 1
            if counter[j] < len(dimensions_pseudo[j]['parameters']):
                break
            else:
                counter[j] = 0        
        # Add selected parameter combo data to helper strings.
        for j in range(len(dimensions_pseudo)):
            for include in dimensions_pseudo[j]['parameters'][counter[j]].include:
                abilities += str(include) + "."
            for exclude in dimensions_pseudo[j]['parameters'][counter[j]].exclude:
                noabilities += str(exclude) + "."
            names += dimensions_pseudo[j]['parameters'][counter[j]].name + "|"
            new_selection = Selection(
                dimension = dimensions_pseudo[j]['key'],
                parameter = dimensions_pseudo[j]['parameters'][counter[j]].key
                )
            # Add Selection to the Filter.
            new_filter.selections.append(new_selection)
        # Add the entry to filters.
        filter_string = query_base + "&filter="
        if abilities != "":
            filter_string += "abilities." + abilities[:-1] + "|"
        if noabilities != "":
            filter_string += "noabilities." + noabilities[:-1] + "|"
        new_filter.name = names[:-1]
        new_filter.string = filter_string[:-1]
        filters.append(new_filter)
        
    # Determine how many pulls would be necessary for all ranks. This
    # can be done in a resource-light manner by doing a dummy ranks pull
    # with the filter 'abilities.9', as spell_ID 9 is not a spell and will
    # filter out all actual ranks, returning only a total ranks value.
    size_check_request = query_base + "&filter=abilities.9"
    for attempt in range(10):
        try:
            total_ranks = pull_ranks(size_check_request)['total']
            break
        except PullFailedError:
            pass
    else:
        raise ProcessFailureError(
            "Could not get ranks count for Pull %d from user %s"
            % (pull.key.id(), pull.parent().id()))
    pull_counter = ((total_ranks / DEFAULT_LIMIT) + 1)
    # Start a progress counter at 0.
    progress_counter = 0
    # For each filter:
    for filter_ in filters:
        filter_results = []
        failed_pages = []
        # Create a dict of dimension/parameter name tuples for the filter.
        selections = {}
        for selection in filter_.selections:
            dimension = selection.dimension.get()
            parameter = selection.parameter.get()
            selections[dimension.name] = parameter.name
        # For each pull required:
        for page in range(1, (pull_counter + 1)):
            # Add the page number to the filter query string.
            query_string = filter_.string + "&page=" + str(page)
            # Pull ranks and add to combined results.
            try:
                filter_results += pull_ranks(query_string)['rankings']
            except PullFailedError as e:
                failed_pages.append(page)
                logging.error(e.msg)
            # Increment the progress counter.
            progress_counter += 1
        # Add the tuples in selections to each rank dict
        for rank in filter_results:
            rank.update(selections)
        # Add filter_results to results
        results += filter_results
        # Store failed pulls in NDB and add to failed_pulls
        if len(failed_pages) > 0:
            filter_.failed_pages = failed_pages
            failed_pulls.append(filter_.put())
            
    # Finish Pull Work.
    return finish_pull(pull, results, failed_pulls)
        
        
# Pull ranks:
def pull_ranks(query_string):
    # Start with a timeout of 15 seconds.
    timeout = 30
    retry = True
    # Make the ranks pull API request.
    while retry == True:
        try:
            logging.info("Attempting %s" % query_string)
            urlfetch.set_default_fetch_deadline(timeout)
            response = urlfetch.fetch(query_string)
            result = json.loads(response.content)
            # Return the results.
            return result
        # If pull times out:
        except urlfetch.Error:
            logging.error("Pull failed.")
            # Double the timeout.
            timeout *= 2
            # If this is the fourth attempt, give up.
            if timeout > 120:
                retry = False
    # If it gets here it failed, so Raise PullFailedError.
    raise PullFailedError("Pull failed with query string %s" % query_string)
        
        
# Retry pull:
def retry_pull(pull):
    progress_counter = 0
    pull_counter = 0
    filters = ndb.get_multi(pull.failed_pulls)
    failed_filters = filters
    for filter_ in filters:
        pull_counter += len(filter_.failed_pages)
    succeeded_pulls = []
    results = []
    # Flag the pull as processing.
    pull.status = 'Processing'
    # For each failed filter:
    for filter_ in filters:
        # Create a dict of dimension/parameter name tuples for the filter.
        selections = {}
        for selection in filter_.selections:
            dimension = selection.dimension.get()
            parameter = selection.parameter.get()
            selections[dimension.name] = parameter.name
        # For each failed page:
        for page in filter_.failed_pages:
            # Add the page number to the filter query string.
            query_string = filter_.string + "&page=" + str(page)
            # Pull ranks and add to combined results.
            try:
                ranks += pull_ranks(query_string)
                for rank in ranks:
                    rank.update(selections)
                filter_.failed_pages.remove(page)
            except PullFailedError as e:
                failed_pages.append(page)
                logging.error(e.msg)
            # Increment the progress counter.
            progress_counter += 1
        # If the filter was successfully completed, remove it from the list.
        if len(filter_.failed_pages) == 0:
            failed_filters.remove(filter_)
            succeeded_pulls.append(filter_)
    # Update any filters still in failed state.
    if len(failed_filters) > 0:
        failed_pulls = ndb.put_multi(failed_filters)
    # Delete any successful filters.
    if len(successful_filters) > 0:
        ndb.delete_multi(succeeded_pulls)
    # Finish Pull.
    return finish_pull(pull, results, failed_pulls)
        
        
# Finish Pull:
def finish_pull(pull, results, failed_pulls):
    pull_id = pull.key.id()
    user_id = pull.key.parent().id()
    filename_core = '/wclstats.appspot.com/' + str(pull_id) + "-" + str(user_id)
    # Try to open existing results for this pull:
    results_filename = filename_core + ".json"
    try:
        gcs_file = gcs.open(results_filename, 'r')
        # Add the old results to the new results.
        old_results = json.load(gcs_file)
        results.append(old_results)
        gcs_file.close()
        # Overwrite the existing results file in cloud storage with the update.
        gcs_file = gcs.open(results_filename, 'w', content_type='application/json')
        gcs_file.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
        gcs_file.close()
    # If there are no results yet:
    except gcs.NotFoundError:
        # Create a results file in cloud storage.
        gcs_file = gcs.open(results_filename, 'w', content_type='application/json')
        gcs_file.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
        gcs_file.close()
    
    # If failed_pulls is empty:
    if len(failed_pulls) == 0:
        csv_filename = filename_core + ".csv"
        # Encode the results as a csv.
        csv_results = csv_output(results, pull)
        # Store the csv in cloud storage.
        gcs_file = gcs.open(csv_filename, 'w', 
                            content_type='text/csv; charset=UTF-8; header=present')
        gcs_file.write(csv_results.encode('utf-8'))
        gcs_file.close()
        # Flag the pull as complete.
        del pull.failed_pulls
        pull.status = 'Ready'
    # Else:
    else:
        # Store the failed_pulls list to the pull.
        pull.failed_pulls = failed_pulls
        # Flag the pull as incomplete.
        pull.status = 'Incomplete'
    
    # Update the Pull in NDB.
    pull.put()
    
    
def csv_output(ranks, pull):
    #Take the collected ranks from a pull request and formats them into a .csv
    #file.  
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
    #Get the request (and then its dimensions.)
    request = main.Request.get_by_id(pull.request.id(), parent=pull.key.parent())
    dimensions = ndb.get_multi(request.dimensions)
    #If there's a trinket dimension, add it to the list of dimensions.
    if request.trinket_dimension != None:
        dimensions.insert(0, main.Dimension.get_by_id(request.trinket_dimension.id()))
    #Add all of the request dimensions add fields for the csv file.
    for dimension in dimensions:
        fieldnames.append(dimension.name)
    
    #Start the file with the field names.
    for field in fieldnames:
        csvfile += field + ","
    csvfile = new_line(csvfile)
    
    #Take each rank and format it as csv.
    for rank in ranks:
        for item in fieldnames:
            #If the item is the report link, take the fightID and turn it into
            #an actual URL.
            if item == "link":
                csvfile += "https://www.warcraftlogs.com/reports/" + \
                            rank["reportID"] + "#fight=" + \
                            str(rank["fightID"]) + ","
            #Mythic ranks pulls don't include a size field, so if it's a mythic
            #pull, we need to manually add "20" as the size.
            elif item == "size":
                if is_mythic:
                    csvfile += str(20) + ","
                else:
                    csvfile += unicode(rank[item]) + ","
            #For anything else, just get the applicable data and plug it in
            #under the correpsonding field name.
            else:
                csvfile += unicode(rank[item]) + ","
        csvfile = new_line(csvfile)
    return csvfile
    
            
def new_line(string):
    #Replaces the final comma of a rank with a newline (\n).
    index = len(string)
    s = string[:(index - 1)]
    string = s + "\n"
    return string





