import math

class Filter(ndb.Model):
    string = ndb.StringProperty()
    dimension = ndb.KeyProperty(type=Dimension)
    parameter = ndb.KeyProperty(type=Parameter)
    pages = ndb.IntegerProperty(repeated=True, default=[])

def work_pull(pull):
    response = {}
    results = {}
    filters = []
    failed_filters = []
    key_string = u''
    max_pages = 0
    #Build a base query string from the Pull attributes.
    query_base = ("https://www.warcraftlogs.com:443/v1/rankings/encounter/" +
                  str(pull.encounter) + "?metric=" + pull.metric +
                  "&difficulty=" + str(pull.difficulty) +
                  "&class=" + str(request.character_class) +
                  "&spec=" + str(pull.spec) +
                  "&api_key=" + json_pull("apikeys.json")["WCL"]["key"])
    #Get the requests and parameters.
    request = pull.request.get()
    dimensions = request.dimensions.get()
    #Build Filter objects for each parameter. O(N) N=Parameters * spell ids
    for dimension in dimensions:
        parameters = dimension.parameters.get()
        for parameter in parameters:
            new_filter = Filter(dimension = dimension.key,
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
            key_string = rank['name'] + "_" + rank['server'] + "_" + rank['reportID']
            #Save the rank to results with that key
            results[key_string] = rank
        #Use the total to get a max_pages
        max_pages = int(math.ceil(float(response['total']) / 500))
        break
    except PullFailedError:
        raise ProcessFailureError(
            "Could not get ranks count for Pull %d from user %s"
            % (pull.key.id(), pull.parent().id()))
  
    #For each page after page 1:
    for page in range(2, max_pages + 1):
        try:
            response = pull_ranks(query_base + "&page=" + page)
            #For each rank: O(N2) N2=Ranks
            for rank in response['rankings']:
                #Make a key string (name_server_reportID)
                key_string = rank['name'] + "_" + rank['server'] + "_" + rank['reportID']
                #Save the rank to results with that key
                results[key_string] = rank
        except PullFailedError:
            raise ProcessFailureError(
                "Could not get ranks count for Pull %d from user %s"
                % (pull.key.id(), pull.parent().id()))
    
    #For each [filter]: O(N1) N1=Parameters
        failed_pages = []
        #For each page:
            #Try to make the request
                #For each {rank}: O(N2)
                    #Make a key string (CharacterName_ServerName_FightID)
                    #Add the filter tag to results
            #If it fails:
                #Add this page to failed_pages
        #If there are failed pages:
            #Set the .pages property with the list of failed_pages
            filter_.pages = failed_pages
            #Add the filter to failed_filters
  
    #If there are any failed Filters:
        filters = failed_filters
        failed_filters = []
        #For each failed filter: O(N1)
            failed_pages = []
            #For each page:
                #For 3 attempts:
                    #Try the pull:
                        #For each {rank}: O(N2)
                            #Make a key string (CharacterName_ServerName_FightID)
                            #Add the filter tag to results
                        #break
                    #If it fails:
                        #Say so in the logs
                #If all three attempts fail:
                    #Add this page to failed_pages
            #If there are failed pages:
                #Set the .pages property with the list of failed_pages
                filter_.pages = failed_pages
                #Add the filter to failed_filters
  
    #Store the results in Cloud Storage
  
    #If there are still failed filters:
        #Flag the pull as incomplete
        #Store the failed filters in pull.failed_filters


def json_pull(dct):
    #Pull data from a static .json file and load it into memory.
    path = os.path.join(os.path.split(__file__)[0], dct)
    return json.load(open(path))
