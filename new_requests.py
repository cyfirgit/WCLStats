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
  #Get the requests and parameters.
  #Build a base query string from the Pull attributes.
  #Build Filter objects for each parameter. O(N) N=Parameters
  
  #Try to request the base query page 1:
      #For each rank: O(N2) N2=Ranks
          #Make a key string (CharacterName_ServerName_FightID)
          #Save the rank to results with that key
      #Use the total to get a max_pages
  #If it fails, try 3 more times; if that fails, give up entirely.
  
  #For each page after page 1:
      #Try to request page
        #For each rank:
            #Make a key string (CharacterName_ServerName_FightID)
            #Save the rank to results with that key
      #If it fails, try 3 more times; if that fails, give up.
  
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
