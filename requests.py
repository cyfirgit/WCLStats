# coding: utf-8

#Module to handle structuring and executing requests against external apis.

#Here's the deal: yes, my use of "parameter" and "dimension" is inconsistent as
#hell.  I totally plan to fix it after I have a working prototype for people to
#break.

import json
import os
import logging
import math

import main

from google.appengine.ext import ndb
from google.appengine.api import urlfetch


class PullTimeoutError(Exception):
    def __init__(self, msg):
        self.msg = msg
    
    
def rankings_pull_filtered(pull):
    #This is the function that should be the core of any request pull.  It uses
    #the other functions below to actually structure, scale, and implement the
    #pull.
    
    result = []
    request = pull.request.get()
    encounter_id = pull.encounter,
    pull_parameters = {
        "metric": pull.metric,
        "difficulty": pull.difficulty,
        "class": request.character_class,
        }
    
    for spec in request.specialization:
        dimensions = {}
        pull_parameters['spec'] = spec
        
        #Pull NDB objects from stored keys and store them in a dictionary.
        ''' Dictionary goes out as:
            {
                "dimension name": {
                    "parameter name": {
                        "include": [spell_id, spell_id] OR None,
                        "exclude": [spell_id, spell_id] OR None
                        }
                    }
                }
            '''
        dimensions_objects = ndb.get_multi(request.dimensions)
        for dimension in dimensions_objects:
            dimensions[dimension.name] = {}
            dim_parameters = ndb.get_multi(dimension.parameters)
            for parameter in dim_parameters:
                dimensions[dimension.name][parameter.name] = {
                    "include": parameter.include,
                    "exclude": parameter.exclude
                    }
        #Add a dimension for trinkets if the request analyzes trinkets.
        if request.trinket_dimension != None:
            trinkets = main.Dimension.get_by_id(request.trinket_dimension.id())
            dimensions["Trinkets"] = build_trinket_dimensions(trinkets)
        
        #Build a list of filters to pull against from WCL, then send the pulls.
        filters = build_filters(dimensions)
        main.vislog(filters)
        for filter in filters:
            get_filter = []
            pull_parameters['filter'] = filter['filter']
            
            logging.info("Pulling ranks for %s" % filter["name"])
            
            try:
                get_filter = rankings_pull_all_pages(pull, pull_parameters)
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
        
    
def build_trinket_dimensions(trinkets_dimension):
    #Take a set of trinket options and generate a dimensions dictionary to be
    #appended to the other dimensions.
    ''' Dictionary goes out as:
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
    
    #We need to create a list of all trinket effects we're considering.  During
    #the loop, we'll remove the other trinket's effect from this list for each
    #trinket considered.
    trinkets = ndb.get_multi(trinkets_dimension.parameters)
    for trinket in trinkets:
        if trinket.include != None:
            trinkets_exclude_all += trinket.include
    if trinkets_dimension.other_trinkets == True:
        result["Both Other Trinkets"] = {}
        result["Both Other Trinkets"]["include"] = None
        result["Both Other Trinkets"]["exclude"] = trinkets_exclude_all
        trinkets.append(main.Parameter(name="Other Trinkets"))
    
    #We use a theorem one stars and bars formula to determine the number of
    #possible combinations of trinkets.  Because k is always 2 (number of 
    #trinket slots,) the formula can be reduced significantly.        
    dimensions = (len(trinkets)**2 - len(trinkets)) / 2
    
    for dimension in range(dimensions):
    
        #If one of the trinkets is "Other Trinkets", apply an "exclude" to it
        #equal to the "include" of every trinket except the paired counterpart.
        if trinkets[slot[0]].name == "Other Trinkets":
            other_trinkets_exclude = list(trinkets_exclude_all)
            for i in range(len(trinkets[slot[1]].include)):
                other_trinkets_exclude.remove(trinkets[slot[1]].include[i])
            trinkets[slot[0]].exclude = other_trinkets_exclude
        elif trinkets[slot[1]].name == "Other Trinkets":
            other_trinkets_exclude = list(trinkets_exclude_all)
            for i in range(len(trinkets[slot[0]].include)):
                other_trinkets_exclude.remove(trinkets[slot[0]].include[i])
            trinkets[slot[1]].exclude = other_trinkets_exclude
        
        
        pair = {"include": [], "exclude": []}
        name = trinkets[slot[0]].name + "|" + trinkets[slot[1]].name
        if trinkets[slot[0]].include != None:
            pair["include"] += trinkets[slot[0]].include
        if trinkets[slot[1]].include != None:
            pair["include"] += trinkets[slot[1]].include
        if trinkets[slot[0]].exclude != None:
            pair["exclude"] += trinkets[slot[0]].exclude
        if trinkets[slot[1]].exclude != None:
            pair["exclude"] += trinkets[slot[1]].exclude
        
        if len(pair["include"]) == 0:
            pair["include"] = None
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
        
    
def rankings_pull_all_pages(pull, parameters):
    #Take a set of dimensions(w/ a unique set of parameters,) and pull all
    #pages of applicable rankings.
    
    limit = 5000
    parameters['limit'] = limit
    
    for attempt in range(50):
        logging.info("Pull %d on first page" % (attempt + 1))
        first_pull = rankings_pull(pull.encounter, parameters)
        if first_pull != None:
            break
    else:
        logging.info("Could not retreive initial page.")
        raise PullTimeoutError("Inital pull failed after 50 attempts.")
        
    logging.info("Total rankings found: %d" % first_pull["total"])
    total_pages = int(math.ceil(first_pull["total"] / limit)) + 1
    result = first_pull["rankings"]
    
    for i in range(2, total_pages + 1):
        page = i
        for j in range(50):
            logging.info("Pull %d on page %d of %d" % ((j + 1), i, total_pages))
            next_pull = rankings_pull(pull.encounter, parameters)
            if next_pull != None:
                result += next_pull["rankings"]
                break
        else:
            raise PullTimeoutError("Pull %d of %d failed after 50 attempts." %\
                                   (i, total_pages))
                
    return result
    
    
def rankings_pull(encounter_id, parameters):
    #Pull a single page of ranks.
    key = json_pull("apikeys.json")["WCL"]["key"]
    url_base = "https://www.warcraftlogs.com:443/v1/rankings/encounter/"
    url_middle = str(encounter_id) + "?"
    
    #In this loop, we take each parameter and stick it into the request url.
    for parameter in parameters:
        if parameters[parameter] != None:
            url_middle += "&" + parameter + "=" + str(parameters[parameter])
    
    url = url_base + url_middle + "&api_key=" + key
    main.vislog(url)
        
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
    main.vislog('Adding trinket dimensions')
    if request.trinket_dimension != None:
        dimensions.insert(0, main.Dimension.get_by_id(request.trinket_dimension.id()))
    #Add all of the request dimensions add fields for the csv file.
    main.vislog('Building field names')
    for dimension in dimensions:
        fieldnames.append(dimension.name)
    
    #Start the file with the field names.
    main.vislog('Adding field names to file')
    for field in fieldnames:
        csvfile += field + ","
    csvfile = new_line(csvfile)
    
    #Take each rank and format it as csv.
    main.vislog('Starting rank writes')
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





