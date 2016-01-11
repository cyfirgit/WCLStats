import cloudstorage as gcs
import json

DEFAULT_LIMIT = 5000

class Filter(ndb.Model):
    name = ndb.StringProperty()
    string = ndb.StringProperty()
    selections = ndb.StructuredProperty(Selection, repeated=True)
    failed_pages = ndb.IntegerProperty(repeated=True)
    
class Selection(ndb.Model):
    dimension = ndb.KeyProperty()
    parameter = ndb.KeyProperty()

# Work a pull:
def work_pull(pull):
    request = pull.request.get()
    dimensions = ndb.get_multi(request.dimensions)
    failed_pulls = []
    results = []
    # Flag the pull as processing.
    pull.status = 'Processing'
    # Build a base query string using the shared (non-filter) arguments *except* spec.
    query_base = ("https://www.warcraftlogs.com:443/v1/rankings/encounter/" +
                  str(pull.encounter) + "?metric=" + pull.metric +
                  "&difficulty=" + pull.difficulty +
                  "&class=" + str(request.character_class) +
                  "&limit=" + str(DEFAULT_LIMIT)
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
                      'parameters':dimension.parameters.get()}
        dimensions_pseudo.append(new_pseudo)
    
    # If trinkets are being considered:
    if request.trinket_dimension != None:
        # Make an "unpacked" pseudo-dimension for trinkets, with parameters for:
            # - each possible combination of trinkets
            # - and if necessary:
                # - each trinket being paired with some other, undefined trinket
                # - neither equipped trinket having been defined.'''
        trinket_dimension = request.trinket_dimension.get()
        trinket_pseudo = {'name':'Trinkets', 'parameters':[]}
        trinkets = ndb.get_multi(trinket_dimension.parameters)
        # We use a theorem one stars and bars formula to determine the number of
        # possible combinations of trinkets.  Because k is always 2 (number of 
        # trinket slots,) the formula can be reduced significantly.
        trinket_combinations = (len(trinkets)**2 - len(trinkets)) / 2
        # Build parameters in our pseudo dimension that represent each pair of 
        # defined trinkets.
        slot=[0,1]
        for i in range(trinket_combinations):
            # Iterate the trinket pairings.
            slot[1] += 1
            if slot[1] >= len(trinkets):
                slot[0] += 1
                slot[1] = slot [0] + 1
            # Create a new Parameter representing combining the pair of
            # trinkets.  This Parameter never gets stored in NDB, and is used
            # in this pull worker only.
            new_parameter = main.Parameter(
                name = trinkets[slot[0]].name + "|" + trinkets[slot[1]].name,
                parent = pull.parent,
                include = trinkets[slot[0]].include + trinkets[slot[1]].include
                )
            # Add the new Parameter to the pseudo dimension.
            trinket_pseudo['parameters'].append(new_parameter)
        # If the trinkets dimension is flagged to consider other trinkets:
        if trinket_dimension.other_trinkets = True:
            # Add a trinket to represent some other trinket.  We'll add all
            # included spell IDs as excludes, though later we'll modify that.
            other_trinkets = main.Parameter(exclude=[])
            for trinket in trinkets:
                other_trinkets.exclude += trinket.include
            for trinket in trinkets:
                # Add a new Parameter representing pairing a defined trinket
                # with some other undefined trinket.
                new_parameter = main.Parameter(
                    name = trinket.name + "|Other",
                    include = trinket.include,
                    exclude = other_trinkets.exclude,
                    )
                # At this point, this is a useless parameter.  We need to
                # remove all of our trinket's includes from the exclude list.
                for include in new_parameter.include:
                    for exclude in new_parameter.exclude:
                        if include == exclude:
                            new.parameter.exclude.remove(exclude)
                # Add the new Parameter to the pseudo dimension.
                trinket_pseudo['parameters'].append(new_parameter)
        # Add that pseudo dimension to the dimensions within the request in use.
        dimensions_pseudo.append(trinket_pseudo)
        
    # Create a list, filters, to place Filter objects into.
    filters = []
    # Determine how many filters will be created.
    total_filters = 1
    for dimension in dimensions_pseudo:
        total_filters *= len(dimension['parameters'])
    # Generate a counter array to track which paramaters to use.
    counter = []
    for i in range(len(dimensions_pseudo)):
        counter[i] = 0
    # Structure a filter for each unique combination of parameters by dimension.
    for i in range(total_filters):
        new_filter = Filter(selections=[])
        names = ""
        abilities = ""
        noabilities = ""
        # Iterate the counter.
        for j in range(len(dimensions_pseudo)):
            counter[j] += 1
            if counter[j] < len(dimensions_pseudo[j]['paramaters']):
                break
            else:
                counter[j] = 0        
        # Add selected parameter combo data to helper strings.
        for j in range(len(dimensions_pseudo)):
            for include in dimensions_pseudo[j]['paramaters'][counter[j]].include:
                abilities += str(include) + "."
            for exclude in dimensions_pseudo[j]['paramaters'][counter[j]].exclude:
                noabilities += str(exclude) + "."
            names += dimensions_pseudo[j]['paramaters'][counter[j]].name + "|"
            new_selection = Selection(
                dimension = dimensions_pseudo[j]['key'],
                paramater = dimensions_pseudo[j]['paramaters'][counter[j]].key
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
            total_ranks = rankings_pull(size_check_request)['total']
            break
        except PullFailedError:
            pass
    else:
        raise ProcessFailureError(
            "Could not get ranks count for Pull %d from user %s"
            % (pull.key.id(), pull.parent.id()))
    pull_counter = ((total_ranks / DEFAULT_LIMIT) + 1)
    # Start a progress counter at 0.
    progress_counter = 0
    # For each filter:
    for filter_ in filters:
        filter_results = []
        failed_pages = []
        # Create a dict of dimension/paramater name tuples for the filter.
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
                filter_results += pull_ranks(query_string)
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
            filter_.failed_pages = failed pages
            failed_pulls.append(filter_.put())
            
    # Finish Pull Work.
    return finish_pull(pull, results, failed_pulls)
        
        
# Pull ranks:
def pull_ranks(query_string):
    # Start with a timeout of 15 seconds.
    timeout = 15
    # Make the ranks pull API request.
    while retry == True
        try:
            urlfetch.set_default_fetch_deadline(timeout)
            response = urlfetch.fetch(url)
            result = json.loads(response.content)
            # Return the results.
            return result
        # If pull times out:
        except urlfetch.Error:
            logging.error("Pull failed.")
            # Double the timeout.
            timeout *= 2
            # If this is the fourth attempt, give up.
            if timeout > 60:
                retry = False
    # If it gets here it failed, so Raise PullFailedError.
    raise PullFailedError
        
        
# Retry pull:
def retry_pull(pull)
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
        # Create a dict of dimension/paramater name tuples for the filter.
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
    user_id = pull.key.parent.id()
    filename_core = '/wclstats.appspot.com/' + str(pull_id) + "-" + str(user_id)
    # Try to open existing results for this pull:
    results_filename = filename_core + ".json"
    try:
        gcs_file = gcs.open(results_filename, 'r', content_type='application/json')
        # Add the old results to the new results.
        old_results = json.load(gcs_file.read())
        results.append(old_results)
        gcs_file.close()
        # Overwrite the existing results file in cloud storage with the update.
        gcs_file = gcs.open(results_filename, 'w', content_type='application/json')
        gcs_file.write(json.dump(results, ensure_ascii=False))
        gcs_file.close()
    # If there are no results yet:
    except NotFoundError:
        # Create a results file in cloud storage.
        gcs_file = gcs.open(results_filename, 'w', content_type='application/json')
        gcs_file.write(json.dump(results, ensure_ascii=False))
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
        pull.failed_pulls = None
        pull.status = 'Ready'
    # Else:
    else:
        # Store the failed_pulls list to the pull.
        pull.failed_pulls = failed_pulls
        # Flag the pull as incomplete.
        pull.status = 'Incomplete'
    
    # Update the Pull in NDB.
    pull.put()
