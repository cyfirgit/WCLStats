# coding: utf-8

#PROJECT TODO:

#For prototype:
    #Track down this whoreson memory leak.
    #Change the add/remove buttons to be more intuitive.
    #Change the default pull limit.


#Later:
    #Make request names unique within author's requests
    #Fix specialization singular in Request model
    #Add by-patch filtering to the date range selector of Build Pull modal.
    #Date selection in Build Pull modal at all.
    #Use the deferred library for pull tasks.
    #Change results property around
    #Validation check for dimension names to prevent WCL ranks keywords.
    #Make it stop building new dimensions on update.
    #Progress bars for pulls in progress.

import os
import jinja2
import webapp2
import logging
import json
import cloudstorage as gcs

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import taskqueue

import requests

CURRENT_TIER_ZONE = "Hellfire Citadel"

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
    
    
class RestrictedHandler(webapp2.RequestHandler):
    def login_check(cls, level):
        # Checks the current user against the permissions level of the page and
        # takes appropriate actions if user does not meet requirements.
        user = users.get_current_user()
        if user:
            account = Account.query(Account.user_id == user.user_id()).get()
            if account == None:
                #First login; needs to create account
                new_account = Account(user_id=user.user_id())
                new_account.email = user.email()
                new_account.level = 0
                new_account.put()
                cls.redirect('/account', abort=True)
            else:
                if level == None or account.level >= level:
                    #Logged in / login not reqd or user meets reqd level
                    log_url = users.create_logout_url(cls.request.uri)
                else:
                    #Logged in / user doesn't meet reqd level
                    cls.redirect('/', abort=True)
        else:
            account = None
            if level == None:
                #Not logged in / login not reqd
                log_url = users.create_login_url(cls.request.uri)
            else:
                #Not logged in / login reqd
                cls.redirect('/', abort=True)
                
        result = {'account': account, 'log_url': log_url}
        return result
    

#***NDB Model classes***
class Reference(ndb.Model):
    json = ndb.JsonProperty()
    
    
class Account(ndb.Model):
    user_id = ndb.StringProperty()
    nickname = ndb.StringProperty()
    level = ndb.IntegerProperty()
    email = ndb.StringProperty()


class Pull(ndb.Model):
    request = ndb.KeyProperty(kind='Request')
    date = ndb.DateTimeProperty(auto_now_add=True)
    encounter = ndb.IntegerProperty()
    difficulty = ndb.IntegerProperty()
    metric = ndb.StringProperty()
    spec = ndb.IntegerProperty()
    status = ndb.StringProperty()
    failed_filters = ndb.KeyProperty(repeated=True)
    
    
class Parameter(ndb.Model):
    name = ndb.StringProperty()
    include = ndb.IntegerProperty(repeated=True)
    exclude = ndb.IntegerProperty(repeated=True)
    
    @classmethod
    def query_parameter(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(cls.name)
    
    
class Dimension(ndb.Model):
    name = ndb.StringProperty()
    parameters = ndb.KeyProperty(kind='Parameter', repeated=True)
    other_trinkets = ndb.BooleanProperty()
    
    @classmethod
    def query_dimension(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(cls.name)
    
	
class Request(ndb.Model):
    name = ndb.StringProperty()
    character_class = ndb.IntegerProperty()
    specialization = ndb.IntegerProperty(repeated=True)
    dimensions = ndb.KeyProperty(kind='Dimension', repeated=True)
    trinket_dimension = ndb.KeyProperty(kind='Dimension')
    parsed_trinket_dimension = ndb.KeyProperty(kind='Dimension')
    
    @classmethod
    def query_request(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(cls.name)

        
class Filter(ndb.Model):
    string = ndb.StringProperty()
    dimension = ndb.KeyProperty(kind=Dimension)
    parameter = ndb.KeyProperty(kind=Parameter)
    pages = ndb.IntegerProperty(repeated=True)

	
#***Page classes***
class MainPage(RestrictedHandler):
    def get(self):
        check = self.login_check(None)
        template_values = {
            'account': check['account'],
            'log_url': check['log_url'],
            }
        template = JINJA_ENVIRONMENT.get_template("templates/wclstats.html")
        self.response.write(template.render(template_values))
		
		
class RequestBuilderPage(RestrictedHandler):
    def get(self):
        check = self.login_check(2)
        if 'request' in self.request.GET:
            request_id = int(self.request.GET['request'])
            query_result = Request.get_by_id(request_id,
                                             parent=check['account'].key)
            if query_result != None:
                selected_request = query_result
            else:
                selected_request = None
        else:
            selected_request = None
        requests = Request.query(ancestor=check['account'].key).fetch()
        
        template_values = {
            'selected_request': selected_request,
            'account': check['account'],
            'log_url': check['log_url'],
            'requests': requests,
        }
        template = JINJA_ENVIRONMENT.get_template(
            "templates/requestbuilder.html")
        self.response.write(template.render(template_values))
        
 
class AboutPage(RestrictedHandler):
    def get(self):
        check = self.login_check(None)
        
        template_values = {
            'account': check['account'],
            'log_url': check['log_url'],
            'requests': requests,
        }
        template = JINJA_ENVIRONMENT.get_template("templates/about.html")
        self.response.write(template.render(template_values))

		
class MyRequestsPage(RestrictedHandler):
    def get(self):
        check = self.login_check(2)
        
        requests = Request.query(ancestor=check['account'].key).fetch()
        wcl_classes = Reference.get_by_id('wcl_classes').json
        zones = Reference.get_by_id('wcl_zones').json
        for zone in zones:
            #Right now I'm limiting pulls to the current tier.  Maybe later for
            #others, but I don't know how useful it would be anyway.
            if zone['name'] == CURRENT_TIER_ZONE:
                encounters = zone['encounters']
                break
        metrics = Reference.get_by_id('metrics').json
        difficulties = Reference.get_by_id('difficulties').json
        
        template_values = {
            'account': check['account'],
            'log_url': check['log_url'],
            'requests': requests,
            'wcl_classes': wcl_classes,
            'encounters': encounters,
            'metrics': metrics,
            'difficulties': difficulties,
            }
        template = JINJA_ENVIRONMENT.get_template("templates/myrequests.html")
        self.response.write(template.render(template_values))
        
        
class MyPullsPage(RestrictedHandler):
    def get(self):
        check = self.login_check(2)
        
        # Get user's pulls
        pulls = Pull.query(ancestor=check['account'].key).fetch()
        # For each pull, get the name of the associated request and add it to a
        # dictionary of request names with pull ids as the keys
        requests = {}
        for pull in pulls:
            request = pull.request.get()
            requests[pull.key.id()] = request
        # Get the reference dictionaries needed for the page
        difficulties_json = Reference.get_by_id('difficulties').json
        metrics_json = Reference.get_by_id('metrics').json
        wcl_classes = Reference.get_by_id('wcl_classes').json
        # For encounters, get the zones reference and drill down to the current
        # tier encounters.
        zones = Reference.get_by_id('wcl_zones').json
        for zone in zones:
            if zone['name'] == CURRENT_TIER_ZONE:
                encounters_json = zone['encounters']
                break
        
        # Take the _json lists and convert to dictionaries.
        difficulties = {}
        metrics = {}
        encounters = {}
        for difficulty in difficulties_json:
            difficulties[difficulty['id']] = difficulty['name']
        for metric in metrics_json:
            metrics[metric['id']] = metric['name']
        for encounter in encounters_json:
            encounters[encounter['id']] = encounter['name']
            
        # Construct the template
        template_values = {
            'account': check['account'],
            'log_url': check['log_url'],
            'pulls': pulls,
            'requests': requests,
            'difficulties': difficulties,
            'encounters': encounters,
            'metrics': metrics,
            'wcl_classes': wcl_classes,
            }
        template = JINJA_ENVIRONMENT.get_template("templates/mypulls.html")
        self.response.write(template.render(template_values))
        
        
class AccountSettingsPage(RestrictedHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            acc_check = Account.query(Account.user_id==user.user_id()).get()
            if acc_check != None:
                check = self.login_check(0)
            else:
                check = {
                    'account': acc_check, 
                    'log_url': users.create_logout_url(self.request.uri)
                    }
        else:
            check = self.login_check(0)
            
        template_values = {
            'account': check['account'],
            'log_url': check['log_url'],
            'levels': Reference.get_by_id('account_levels').json
            }
        template = JINJA_ENVIRONMENT.get_template("templates/account.html")
        self.response.write(template.render(template_values))
        
        


#***POST classes*** 
class BuildRequestForm(RestrictedHandler):
    #Process a user-defined request and store in NDB.
    def post(self):
        check = self.login_check(2)
        
        arguments = self.request.arguments()
        specializations = []
        dimensions = {}
        parameters = []
        spells = []
        batch = []
        #Construct (or pull) the Request object:
        request = Request.query(Request.name==self.request.get('request_name'),
                                ancestor=check['account'].key).get()
        if request != None:
            new_request = request
        else:
            new_request = Request(parent=check['account'].key)
        new_request.specialization = []
        new_request.dimensions = []
        new_request.trinket_dimension = None
        for argument in arguments:
            element = parse_argument(argument)
            if element != None:
                if element["type"] == "name":
                    new_request.name = self.request.get(argument)
                elif element["type"] == "character_class":
                    new_request.character_class = int(
                        self.request.get(argument))
                elif element["type"] == "specialization":
                    new_request.specialization.append(int(
                        self.request.get(argument)))
                elif element["type"] == "trinkets":
                    new_dimension = Dimension(name='Trinkets')
                    switch = self.request.get('include_other_trinkets')
                    if switch == 'on':
                        new_dimension.other_trinkets = True
                    dimensions[0] = {'obj': new_dimension}
                elif element["type"] == "dimension":
                    new_dimension = Dimension(name=self.request.get(argument))
                    dimensions[int(element["id"])] = {'obj': new_dimension}
                elif element["type"] == "parameter":
                    new_parameter = Parameter(name=self.request.get(argument))
                    parameters.append({
                        'dimension': int(element["id"][0]),
                        'parameter': int(element["id"][1]),
                        'obj': new_parameter
                        })
                elif element["type"] == "spell_id":
                    element["value"] = self.request.get(argument)
                    spells.append(element)
                elif element["type"] == "no_trinkets":
                    del new_request.trinket_dimension
        for param in parameters:
            dimensions[param['dimension']][param['parameter']]=param['obj']
        for spell in spells:
            if spell['id'][2] == 1:
                dimensions[spell['id'][0]][spell['id'][1]].include.append(
                    int(spell['value']))
            elif spell['id'][2] == 2:
                dimensions[spell['id'][0]][spell['id'][1]].exclude.append(
                    int(spell['value']))
            else:
                logging.error("Spell id %s has unrecognized type." % element)
        for dim in dimensions:
            dimension = dimensions[dim]
            for value in dimension:
                if value != 'obj':
                    param = dimension[value]
                    param_key = param.put()
                    dimension['obj'].parameters.append(param_key)
                batch.append(dimension['obj'])
            dimension_key = dimension['obj'].put()
            if dim == 0 and self.request.get('no_trinkets') != 1:
                new_request.trinket_dimension = dimension_key
                parsed_trinket_dimension = parse_trinkets(dimension['obj'])
                new_request.parsed_trinket_dimension = parsed_trinket_dimension
            else:
                new_request.dimensions.append(dimension_key)
        batch.append(new_request)
        result = ndb.put_multi(batch)
            
        self.redirect('/myrequests')
    
    
class SelectRequestForm(RestrictedHandler):
    def post(self):
        check = self.login_check(2)
        
        request_type = self.request.get('request_type')
        classes = Reference.get_by_id("wcl_classes").json
        if request_type == 'existing':
            selected_request = int(self.request.get('request'))
            #Query NDB for the request and its dimensions and parameters.
            request_complete = Request.get_by_id(selected_request, parent=check['account'].key)
            dimensions_qry = ndb.get_multi(request_complete.dimensions)
            dimensions = []
            for dimension in dimensions_qry:
                parameters_qry = ndb.get_multi(dimension.parameters)
                parameters = []
                for parameter in parameters_qry:
                    parameters.append({
                        "name": parameter.name,
                        "include": parameter.include,
                        "exclude": parameter.exclude
                        })
                dimensions.append({
                    "name": dimension.name,
                    "parameters": parameters
                    })
            if request_complete.trinket_dimension != None:
                trinkets_keys = Dimension.get_by_id(
                    request_complete.trinket_dimension.id())
                other_trinkets = trinkets_keys.other_trinkets
                trinkets_objects = ndb.get_multi(trinkets_keys.parameters)
                trinkets = []
                for trinket in trinkets_objects:
                    new_trinket = {
                        'name': trinket.name,
                        'include': trinket.include,
                        'exclude': trinket.exclude
                        }
                    trinkets.append(new_trinket)
            else:
                trinkets = []
                other_trinkets = None
                
            #Flag the class in the request as selected
            class_index = None
            for class_ in classes:
                if class_['id'] == request_complete.character_class:
                    class_index = classes.index(class_)
            request_data = {
                'selected_request': selected_request,
                'character_class': request_complete.character_class,
                'specializations': request_complete.specialization,
                'dimensions': dimensions,
                'trinkets': trinkets,
                'other_trinkets': other_trinkets,
                'class_index': class_index,
                }
        else:
            selected_request = self.request.get('request')
            request_data = {
                'selected_request': selected_request,
                'character_class': 'new',
                }
            
        template_values = {
            'request_type': request_type,
            'request': request_data,
            'classes': classes,
        }
        
        template = JINJA_ENVIRONMENT.get_template("templates/requestform.html")
        self.response.write(template.render(template_values))
		
        
class NewElementForm(RestrictedHandler):
    def post(self):
        check = self.login_check(2)
        id_array = self.request.get('id_array')
        type = self.request.get('type')
        input_value = self.request.get('input_value')
        element_id = self.request.get('element_id')
        
        id_list = id_array.split(",")
        
        if type == 'spell':
            input_value_formatted = input_value
        elif type == 'specializations':
            input_value_formatted = int(input_value) - 1
        else:
            input_value_formatted = {'name':input_value}
            
        template_values = {
            'id_array': id_list,
            'type': type,
            'input_value': input_value_formatted,
            }
        if type == 'specializations':
            classes = Reference.get_by_id("wcl_classes").json
            template_values['classes'] = classes
            
        template = JINJA_ENVIRONMENT.get_template("templates/newelement.html")
        rendered_template = template.render(template_values)
        new_element = {
            'template': rendered_template,
            'element_id': element_id,
            }
        new_element_json = json.dumps(new_element)
        self.response.write(new_element_json)
        
		
class DownloadPage(RestrictedHandler):
    def post(self):
        check = self.login_check(2)
        
        logging.info("***Beginning Frost Pull***")
        pull = requests.rankings_pull_filtered(boss, frost_parameters, frost_dimensions)
        logging.info("***Compiling frost.csv data***")
        output = exportdata.csv_output(pull, frost_dimensions)
        self.response.headers["Content-Type"] = "application/csv"
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s' % "output.csv"
        self.response.write(output)
        
        
class SaveAccountForm(RestrictedHandler):
    #Update an account via admin page.
    def post(self):
        check = self.login_check(4)
        
        user_id = self.request.get('user_id')
        account = Account.query(Account.user_id==user_id).get()
        account.username = self.request.get('username')
        account.email = self.request.get('email')
        account.level = int(self.request.get('level'))
        account.put()
        
        template = JINJA_ENVIRONMENT.get_template("templates/newelement.html")
        template_values = {'user': account}
        rendered_template = template.render(template_values)
        new_element = {
            'template': rendered_template,
            'element_id': 'account_row'
            }
        new_element_json = json.dumps(new_element)
        self.response.write(new_element_json)
        
        
class UpdateAccountForm(RestrictedHandler):
    #User self-updating of nickname and email.
    def post(self):
        check = self.login_check(0)
        
        account = check['account']
        account.nickname = self.request.get('nickname')
        account.email = self.request.get('email')
        account.put()
        
        self.redirect('/')
        
        
class EditAccountForm(RestrictedHandler):
    #Update an account via admin page.
    def post(self):
        check = self.login_check(4)
        
        user_id = int(self.request.get('user_id'))
        account = Account.query(user_id=user_id).fetch()[0]
        
        template = JINJA_ENVIRONMENT.get_template("templates/newelement.html")
        template_values = {'user': account}
        rendered_template = template.render(template_values)
        new_element = {
            'template': rendered_template,
            'element_id': 'account_row_edit'
            }
        new_element_json = json.dumps(new_element)
        self.response.write(new_element_json)
        

class BuildPullForm(RestrictedHandler):
    #Take a request and build one or more pulls from it, then put those pulls
    #into the taskqueue.
    def post(self):
        check = self.login_check(2)
        # Get the request being pulled against
        request_id = int(self.request.get('request_id'))
        request = Request.get_by_id(request_id, parent=check['account'].key)
        # Get all the difficulties and encounters for the pull
        difficulties = self.request.POST.getall('difficulty')
        encounters = self.request.POST.getall('encounter')
        # Get the metric to examine
        metric = self.request.get('metric')
        # For each difficulty/encounter/spec combination:
        for difficulty in difficulties:
            for encounter in encounters:
                for spec in request.specialization:
                    # add a Pull object to the database
                    new_pull = Pull(parent=check['account'].key,
                                    request=request.key,
                                    difficulty=int(difficulty),
                                    encounter=int(encounter),
                                    metric=metric,
                                    spec=spec,
                                    status='Queued',
                                    )
                    new_pull.put()
                    # add a pull task for that Pull object to the taskqueue
                    taskqueue.add(url='/tasks/pull', 
                                  params = {'user_id': str(check['account'].key.id()), 
                                            'pull_id': str(new_pull.key.id())}
                                  )
        # Redirect the user to their My Pulls page.	
        self.redirect('/mypulls')
        
class PullWorker(webapp2.RequestHandler):
    # Pull request task for the task queue.
    def post(self):
        vislog('Task Started')
        # Get the pull to add to the taskqueue.
        user_id = int(self.request.get('user_id'))
        pull_id = int(self.request.get('pull_id'))
        pull = Pull.get_by_id(pull_id, parent=ndb.Key('Account', user_id))
        # Flag the pull as in process.
        pull.status = 'Processing'
        pull.put()
        # Run the pull through the pull request process
        requests.work_pull(pull)
    
#***Functions***
def parse_trinkets(trinket_dimension):
    # Make a dimension with parameters for:
        # - each possible combination of trinkets
        # - and if necessary:
            # - each trinket being paired with some other, undefined trinket
            # - neither equipped trinket having been defined.'''
    parameters = []
    trinkets = ndb.get_multi(trinket_dimension.parameters)
    # We use a theorem one stars and bars formula to determine the number of
    # possible combinations of trinkets.  Because k is always 2 (number of 
    # trinket slots,) the formula can be reduced significantly.
    trinket_combinations = (len(trinkets)**2 - len(trinkets)) / 2
    # Build parameters in our new dimension that represent each pair of 
    # defined trinkets.
    slot=[0,0]
    for i in range(trinket_combinations):
        # Iterate the trinket pairings.
        slot[1] += 1
        if slot[1] >= len(trinkets):
            slot[0] += 1
            slot[1] = slot [0] + 1
        # Create a new Parameter representing combining the pair of
        # trinkets.  This Parameter never gets stored in NDB, and is used
        # in this pull worker only.
        new_parameter = Parameter(
            name = trinkets[slot[0]].name + "|" + trinkets[slot[1]].name,
            include = trinkets[slot[0]].include + trinkets[slot[1]].include
            )
        # Add the new Parameter to the parameters list.
        parameters.append(new_parameter)
    # If the trinkets dimension is flagged to consider other trinkets:
    if trinket_dimension.other_trinkets == True:
        # Add a trinket to represent some other trinket.  We'll add all
        # included spell IDs as excludes, though later we'll modify that.
        other_trinkets = Parameter(name="Both Other Trinkets", exclude=[])
        for trinket in trinkets:
            other_trinkets.exclude += trinket.include
        parameters.append(other_trinkets)
        for trinket in trinkets:
            # Add a new Parameter representing pairing a defined trinket
            # with some other undefined trinket.
            new_parameter = Parameter(
                name = trinket.name + "|Other",
                include = trinket.include,
                exclude = other_trinkets.exclude,
                )
            # At this point, this is a useless parameter.  We need to
            # remove all of our trinket's includes from the exclude list.
            for include in new_parameter.include:
                for exclude in new_parameter.exclude:
                    if include == exclude:
                        new_parameter.exclude.remove(exclude)
            # Add the new Parameter to the parameters list.
            parameters.append(new_parameter)
    # Create a new dimension, parsed_trinket_dimension, to contain the new
    # parameters.
    parsed_trinket_dimension = Dimension(name='Trinkets')
    # Store the parameters to NDB and add the keys to p_t_d.
    parsed_trinket_dimension.parameters = ndb.put_multi(parameters)
    # Store parsed_trinket_dimension to NDB and return the key.
    return parsed_trinket_dimension.put()


def initialize():
    #Used at service startup to populate NDB with class and zone data.
    class_data = requests.static_request("WCL", "classes")
    zone_data = requests.static_request("WCL", "zones")
    difficulties_manual = [
        {
            "id": 1,
            "name": "LFR"
            },
        {
            "id": 2,
            "name": "Flex"
            },
        {
            "id": 3,
            "name": "Normal"
            },
        {
            "id": 4,
            "name": "Heroic"
            },
        {
            "id": 5,
            "name": "Mythic"
            }
        ]
    metrics_manual = [
        {
            "id": "dps",
            "name": "DPS"
            },
        {
            "id": "hps",
            "name": "HPS"
            },
        {
            "id": "bossdps",
            "name": "Weighted DPS"
            },
        {
            "id": "tankhps",
            "name": "Tank HPS"
            },
        {
            "id": "playerspeed",
            "name": "Speed"
            },
        {
            "id": "krsi",
            "name": "KRSI"
            },
        ]
        
    account_levels_manual = {
        0: 'User',
        1: 'Moderator',
        2: 'Theorycrafter',
        3: 'Tester',
        4: 'Admin',
        }
        
    result = []
    
    wcl_classes = Reference(id="wcl_classes")
    wcl_classes.json = class_data
    result.append(wcl_classes)
    
    wcl_zones = Reference(id="wcl_zones")
    wcl_zones.json = zone_data
    result.append(wcl_zones)
    
    metrics = Reference(id="metrics")
    metrics.json = metrics_manual
    result.append(metrics)
    
    difficulties = Reference(id="difficulties")
    difficulties.json = difficulties_manual
    result.append(difficulties)
    
    account_levels = Reference(id="account_levels")
    account_levels.json = account_levels_manual
    result.append(account_levels)
    
    ndb.put_multi(result)
    
def parse_argument(argument):
    #Takes a form element name and parses it into meaninful data.
    ''' Expected element names:
        "request_name"
        "character_class"
        "specialization_X"
        "trinkets"
        "dimension_A" (A: dimension)
        "parameter_A_B" (A: dimension, B: parameter)
        "spell_id_A_B_C_D" (A: dimension, B: parameter, C:include=1,exclude=2
                            D: spell id index)
        
        Returns a dict as follows:
        {
            "type": element type,
            "id": [dimension, parameter, spell_id_type, spell_id]**
            }
        ** Only exists for dimensions, parameters, and spell ids
        '''
    type_slug = argument[:9]
    if type_slug == "spell_id_":
        type = "spell_id"
        if argument.find("new") == -1:
            #Dimension
            snip = argument[9:]
            end_snip = snip.find("_")
            dimension = int(snip[:end_snip])
            #Parameter
            snip_2 = snip[(end_snip + 1):]
            end_snip = snip_2.find("_")
            parameter = int(snip_2[:end_snip])
            #Spell ID Type (include/exclude)
            snip_3 = snip_2[(end_snip + 1):]
            end_snip = snip_3.find("_")
            spell_id_type = int(snip_3[:end_snip])
            result = {
                "type": type,
                "id": [dimension, parameter, spell_id_type]
                }
            return result
        else:
            return None
            
    elif type_slug == "parameter":
        type = "parameter"
        if argument.find("new") == -1:
            #Dimension
            snip = argument[10:]
            end_snip = snip.find("_")
            dimension = int(snip[:end_snip])
            #Parameter
            parameter = snip[(end_snip + 1):]
            result = {
                "type": type,
                "id": [dimension, parameter]
                }
            return result
        else:
            return None
            
    elif type_slug == "dimension":
        type = "dimension"
        if argument.find("new") == -1:
            #Dimension
            dimension = int(argument[10:])
            result = {
                "type": type,
                "id": dimension
                }
            return result
        else:
            return None
        
    elif type_slug == "trinkets":
        result = {"type": "trinkets"}
        return result
        
    elif type_slug == "request_n":
        result = {"type": "name"}
        return result
        
    elif type_slug == "specializ":
        result = {"type": "specialization"}
        return result
        
    elif type_slug == "character":
        result = {"type": "character_class"}
        return result
    
    elif type_slug == "no_trinke":
        result = {"type": "no_trinkets"}
        
    else:
        logging.error("Argument %s not recognized to parse." % argument)
        return 
        
def vislog(message):
    logging.info('****** ' + str(message) + ' ******')
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/about', AboutPage),
    ('/account', AccountSettingsPage),
    ('/buildpull', BuildPullForm),
    ('/buildrequestform', BuildRequestForm),
    ('/editaccount', EditAccountForm),
    ('/mypulls', MyPullsPage),
    ('/myrequests', MyRequestsPage),
    ('/newelement', NewElementForm),
    ('/output', DownloadPage),
    ('/requestbuilder', RequestBuilderPage),
    ('/selectrequestform', SelectRequestForm),
    ('/saveaccount', SaveAccountForm),
    ('/updateaccount', UpdateAccountForm),
    ('/tasks/pull', PullWorker),
], debug=False)
