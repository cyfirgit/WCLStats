class Filter(ndb.Model):

def work_pull(pull):
  results = {}
  #Get the requests and parameters.
  #Build a base query string from the Pull attributes.
  #Build Filter objects for each parameter. O(N) N=Parameters
  #Try to request the base query:
      #Save the rankings as results
      
  #For each [filter]: O(N1) N1=Parameters
      #Try to make the request
      #If it fails, save the Filter to be able to pull later.
      #For each {rank}: O(N2) N2=Ranks
      #Make a key string (CharacterName_ServerName_FightID)
      #Add the filter tag to results
