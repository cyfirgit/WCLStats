DEFAULT_LIMIT = 5000

class Filter(ndb.Model):
    name = ndb.StringProperty()
    string = ndb.StringProperty()
    selections = ndb.StructuredProperty(Selection, repeated=True)
    
class Selection(ndb.Model):
    dimension = ndb.KeyProperty()
    parameter = ndb.IntegerProperty()

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
                  "&limit=" + str(DEFAULT_LIMIT))
    
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
                paramater = counter[j]
                )
            # Add Selection to the Filter.
            new_filter.selections.append(new_selection)
        # Add the entry to filters.
        filter_string = "&filter="
        if abilities != "":
            filter_string += "abilities." + abilities[:-1] + "|"
        if noabilities != "":
            filter_string += "noabilities." + noabilities[:-1] + "|"
        new_filter.name = names[:-1]
        new_filter.string = filter_string[:-1]
        filters.append(new_filter)
        
        
    # Determine how many total pulls will be necessary.
    pull_counter = {}
    for spec in request.specialization:
        # Build a spec-specific query string of base string + spec argument.
        spec_base = query_base + "&spec=" + str(spec)
        # Determine how many pulls would be necessary for all ranks in the spec.
        # This can be done in a resource-light manner by doing a dummy ranks
        # pull with the filter 'abilities.9', as spell_ID 9 is not a spell and
        # will filter out all actual ranks, returning only a total ranks value
        # for the spec.
        size_check_request = spec_base + "&filter=abilities.9"
        for attempt in range(10):
            try:
                total_ranks = rankings_pull(size_check_request)['total']
                break
            except PullFailedError:
                pass
        else:
            raise ProcessFailureError(
                "Could not get ranks count for Pull %d from user %s on spec %d"
                % (pull.key.id(), pull.parent.id(), spec))
        pull_counter[spec] = ((total_ranks / DEFAULT_LIMIT) + 1)
    # Add a total pulls entry.
    pull_counter['total'] = 0
    for spec in request.specialization:
        pull_counter['total'] += pull_counter[spec] * len(filters)
    # Start the progress counter at 0.
    progress_counter = 0
    # For each spec:
    for spec in request.specialization:
        # Build a spec-specific query string of base string + spec argument.
        spec_base = query_base + "&spec=" + str(spec)
        # For each filter:
        for filter in filters:
            # Add the filter string to the spec query string.
            query_string = spec_base + filter.string
            # For each pull required:
            for page in range(1, (pull_counter[spec] + 1)):
                # Add the page number to the filter query string.
                query_string += "&page=" + str(page)
                # Pull ranks and add to combined results.
                try:
                    results += pull_ranks(query_string)
                except PullFailedError as e:
                    failed_pulls.append(query_string)
                    logging.error(e.msg)
                # Increment the progress counter.
                progress_counter += 1
    # Finish Pull Work.
    return finish_pull(pull, results, failed_pulls)
    
        
        
# Pull ranks:
    
    # Start with a timeout of 15 seconds.
    
    # Make the ranks pull API request.
    
    # If the pull succeeds:
    
        # For each rank returned:
        
            # Tag the rank with applicable parameter data.
            
        # Return the results.
        
    # Else if pull times out:
    
        # Double the timeout.
        
        # If this is less than / equal to 3rd attempt:
        
            # Try again. 

    # If it gets here it failed, so Raise FailedPull Exception
        
        
        
# Retry pull:
    
    # Flag the pull as processing.

    # Start a new failed_pulls list.
    
    # For each failed pull string:
    
        # Pull ranks.
        
    # Finish Pull.
    
        
        
# Finish Pull:
    
    # If combined results blob is empty:
    
        # Store the combined results to the pull as a blob.
        
    # Else:
        
        # Append the combined results to the existing blob.
    
    # If failed_pulls is empty:
    
        # Encode the results as a csv.
        
        # Store the csv in cloud storage.
        
        # Deleted the unencoded results blob.
        
        # Flag the pull as complete.
        
    # Else:
    
        # Store the failed_pulls list to the pull.
        
        # Flag the pull as incomplete.