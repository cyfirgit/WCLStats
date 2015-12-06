# coding: utf-8

#PROJECT TODO:

#For prototype:
    #Build web interface for pull requests
        #submit form processing code
            #remember: Other Trinkets/Both Other Trinkets options
        #My Pulls page
    #Add user account controls

#Later:    
    #Implement decremental request size to respond to timeout issues.
    #Make request names unique within author's requests
    #Fix specialization singular in Request model

import os
import jinja2
import webapp2
import logging
import json

from google.appengine.ext import ndb
from google.appengine.api import users

import requests
import exportdata



JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
    

#***NDB Model classes***    
class Difficulty(ndb.Model):
    name = ndb.StringProperty()
    
    
class Metric(ndb.Model):
    name = ndb.StringProperty()
    
    
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
    results = ndb.BlobKeyProperty()
    
    
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
    author = ndb.KeyProperty(kind='Account')
    
    @classmethod
    def query_request(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(cls.name)

	
#***Page classes***
class MainPage(webapp2.RequestHandler):
    def get(self):
        account = login_check(self, None)
        if account['url'] == 'main':
            self.redirect('/', permanent=True)
        elif account['url'] == 'account':
            self.redirect('/account', permanent=True)
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/', permanent=True)
        
        template_values = {
            'account': account,
            }
        template = JINJA_ENVIRONMENT.get_template("templates/wclstats.html")
        self.response.write(template.render(template_values))
		
		
class RequestBuilderPage(webapp2.RequestHandler):
    def get(self):
        account = login_check(self, 2)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        
        requests = Request.query().fetch()
        
        template_values = {
            'account': account,
            'requests': requests,
        }
        template = JINJA_ENVIRONMENT.get_template(
            "templates/requestbuilder.html")
        self.response.write(template.render(template_values))
        
 
class AboutPage(webapp2.RequestHandler):
    def get(self):
        account = login_check(self, None)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        
        template_values = {
            'account': account,
            'requests': requests,
        }
        template = JINJA_ENVIRONMENT.get_template("templates/about.html")
        self.response.write(template.render(template_values))

		
class MyRequestsPage(webapp2.RequestHandler):
    def get(self):
        account = login_check(self, 2)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        
        requests = Request.query().fetch()
        wcl_classes = Reference.get_by_id('wcl_classes')
        
        template_values = {
            'account': account,
            'requests': requests,
            'wcl_classes': wcl_classes.json,
            }
        template = JINJA_ENVIRONMENT.get_template("templates/myrequests.html")
        self.response.write(template.render(template_values))
        
        
class AccountSettingsPage(webapp2.RequestHandler):
    def get(self):
        account = login_check(self, 0)
        if account['url'] == 'main':
            self.redirect('/', permanent=True)
        elif account['url'] == 'account':
            self.redirect('/account', permanent=True)
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/', permanent=True)
            
        template_values = {
            'account': account,
            'levels': Reference.get_by_id('account_levels').json
            }
        logging.info(template_values['levels'])
        template = JINJA_ENVIRONMENT.get_template("templates/account.html")
        self.response.write(template.render(template_values))


#***POST classes*** 
class BuildRequestForm(webapp2.RequestHandler):
    #Process a user-defined request and store in NDB.
    def post(self):
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        account = login_check(self, 2)
        arguments = self.request.arguments()
        specializations = []
        dimensions = {}
        parameters = []
        spells = []
        batch = []
        
        #Construct the Request object:
        new_request = Request()
        new_request.specialization = []
        new_request.dimensions = []
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
            if dim == 0:
                new_request.trinket_dimension = dimension_key
            else:
                new_request.dimensions.append(dimension_key)
        batch.append(new_request)
        result = ndb.put_multi(batch)
            
        self.response.write(result)
    
    
class SelectRequestForm(webapp2.RequestHandler):
    def post(self):
        account = login_check(self, 2)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        request_type = self.request.get('request_type')
        selected_request = self.request.get('request')
        classes = Reference.get_by_id("wcl_classes").json
        if request_type == 'existing':
            #Query NDB for the request and its dimensions and parameters.
            request_complete = Request.query(
                Request.name == selected_request).fetch()[0]
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
		
        
class NewElementForm(webapp2.RequestHandler):
    def post(self):
        account = login_check(self, 2)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
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
        
		
class DownloadPage(webapp2.RequestHandler):
    def post(self):
        account = login_check(self, 2)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        logging.info("***Beginning Frost Pull***")
        pull = requests.rankings_pull_filtered(boss, frost_parameters, frost_dimensions)
        logging.info("***Compiling frost.csv data***")
        output = exportdata.csv_output(pull, frost_dimensions)
        self.response.headers["Content-Type"] = "application/csv"
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s' % "output.csv"
        self.response.write(output)
        
        
class SaveAccountForm(webapp2.RequestHandler):
    #Update an account via admin page.
    def post(self):
        account = login_check(self, 4)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
        user_id = int(self.request.get('user_id'))
        account = Account.query(user_id=user_id).fetch()[0]
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
        
        
class EditAccountForm(webapp2.RequestHandler):
    #Update an account via admin page.
    def post(self):
        account = login_check(self, 4)
        if account['url'] == 'main':
            self.redirect('/')
        elif account['url'] == 'account':
            self.redirect('/account')
        elif account['url'] == 'login_redirect':
            self.redirect(users.create_login_url(self.request.uri))
        elif account['url'] == 'login':
            account['url'] = users.create_login_url(self.request.uri)
        else:
            account['url'] = users.create_logout_url('/')
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
    
    
#***Functions***
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
        "dps",
        "hps",
        "bossdps",
        "tankhps",
        "playerspeed",
        "krsi"
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
    
    else:
        logging.error("Argument %s not recognized to parse." % argument)
        return None
        
def login_check(handler, level):
    #Each page should flag if it requires a login/account level through this 
    #function.  If it does, require the user to log in and redirect. Otherwise,
    #pass user data to the page if logged in, or None if not logged in.
    user = users.get_current_user()
    if not user:
        if level is not None:
            #No user logged in; page requires login permissions.
            return {'url': 'login_redirect'}
        elif level is None:
            #No user logged in; page requires no permission.
            return {'user': {'level': None}, 
                    'url': 'login'}
    else:
        account = Account.query(Account.user_id == user.user_id()).get()
        if account is not None:
            if level is None:
                #User is logged in; page requires no permissions.
                return {'user': account, 
                        'url': 'login'}
            else:
                #User is logged in; page requires permissions...
                if account.level >= level:
                    #... and user meets the permission requirement.
                    return {'user': account, 
                            'url': 'login'}
                else:
                    #... and user does not meet the permission requirement.
                    return {'user': account,
                            'url': 'main'}
        else:
            #Fires right after logging in for the first time, requiring user to
            #complete site account info.
            new_account = Account(user_id=user.user_id())
            new_account.email = user.email()
            new_account.level = 0;
            new_account.put()
            return {'url': 'account'}
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/requestbuilder', RequestBuilderPage),
    ('/buildrequestform', BuildRequestForm),
    ('/selectrequestform', SelectRequestForm),
    ('/newelement', NewElementForm),
    ('/about', AboutPage),
    ('/output', DownloadPage),
    ('/myrequests', MyRequestsPage),
    ('/account', AccountSettingsPage),
    ('/saveaccount', SaveAccountForm),
    ('/editaccount', EditAccountForm),
    # ('/updateaccount', UpdateAccountForm),
], debug=True)
