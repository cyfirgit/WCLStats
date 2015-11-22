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

import pprint

from google.appengine.ext import ndb

import requests
import exportdata



JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
    
    
class Difficulty(ndb.Model):
    name = ndb.StringProperty()
    
    
class Metric(ndb.Model):
    name = ndb.StringProperty()
    
    
class Reference(ndb.Model):
    json = ndb.JsonProperty()
    
    
class Account(ndb.Model):
    name = ndb.StringProperty()
    email = ndb.StringProperty()
    blizzard_id = ndb.StringProperty()


class Pull(ndb.Model):
    request = ndb.KeyProperty(kind='Request')
    date = ndb.DateTimeProperty(auto_now_add=True)
    bosses = ndb.IntegerProperty(repeated=True)
    difficulties = ndb.IntegerProperty(repeated=True)
    metrics = ndb.StringProperty(repeated=True)
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
    
	
class MainPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("templates/wclstats.html")
        self.response.write(template.render({}))
		
		
class RequestBuilderPage(webapp2.RequestHandler):
    def get(self):
        requests = Request.query().fetch()
        template_values = {
            'requests': requests,
        }
        
        template = JINJA_ENVIRONMENT.get_template("templates/requestbuilder.html")
        self.response.write(template.render(template_values))
        
        
class BuildRequestForm(webapp2.RequestHandler):
    #Process a user-defined request and store in NDB.
    def post(self):
        arguments = self.request.arguments()
        specializations = []
        dimensions = {}
        parameters = []
        includes = []
        excludes = []
        
        #Construct the Request object:
        new_request = ndb.Request()
        new_request.specialization = []
        new_request.dimensions = []
        for argument in arguments:
            element = parse_argument(argument)
            if element != None:
                if element["type"] == "name":
                    new_request.name = self.request.get(argument)
                elif element["type"] == "character_class":
                    new_request.character_class = int(self.request.get(argument))
                elif element["type"] == "specialization":
                    new_request.specialization.append(int(self.request.get(argument)))
                elif element["type"] == "trinkets":
                    dimensions[0] = {"name": "Trinkets", "parameters": {}}
                elif element["type"] == "dimension":
                    dimensions[element["element_id"]] = {
                        "name": self.request.get(argument),
                        "parameters": {}
                        }
                elif element["type"] == "parameter":
                    new_parameter = {
                        "name": self.request.get(argument),
                        "include": []
                        "exclude": []
                        "element_id": element["element_id"]
                        }
                    parameters.append(new_parameter)
                elif element["type"] == "spell_id":
                    new_spell_id = {
                        "spell_id": int(self.request.get(argument)),
                        "element_id": element["element_id"]
                        }
                    if element["element_id"][2] == "include":
                        includes.append(new_spell_id)
                    elif element["element_id"][2] == "exclude":
                        excludes.append(new_spell_id)
                    else:
                        logging.error("Could not handle spell id %s" % argument)
                
                #Next up: Sort through |parameters| and then |includes| & 
                #|excludes| and apply them to the appropriate dimension.
                #Then dump everything into |new_request| and put_multi all the
                #new NDB objects.
                
            
        
        self.response.write('Hi')
    
    
class SelectRequestForm(webapp2.RequestHandler):
    def post(self):
        request_type = self.request.get('request_type')
        selected_request = self.request.get('request')
        classes = Reference.get_by_id("wcl_classes").json
        if request_type == 'existing':
            #Query NDB for the request and its dimensions and parameters.
            request_complete = Request.query(Request.name == selected_request).fetch()[0]
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
            trinkets_keys = Dimension.get_by_id(request_complete.trinket_dimension.id())
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
                
            #Flag the class in the request as selected
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
        
		
class AboutPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("templates/about.html")
        self.response.write(template.render({}))

		
class DownloadPage(webapp2.RequestHandler):
    def post(self):
        logging.info("***Beginning Frost Pull***")
        pull = requests.rankings_pull_filtered(boss, frost_parameters, frost_dimensions)
        logging.info("***Compiling frost.csv data***")
        output = exportdata.csv_output(pull, frost_dimensions)
        self.response.headers["Content-Type"] = "application/csv"
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s' % "output.csv"
        self.response.write(output)    
    
        
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
            "element_id": [dimension, parameter, spell_id_type, spell_id]**
            }
        ** Only exists for dimensions, parameters, and spell ids
        '''
    type_slug = argument[:9]
    if type_slug == "spell_id_":
        type = "spell_id"
        if argument.find("new") > -1:
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
            #Spell ID
            snip_4 = snip_3[(end_snip + 1):]
            end_snip = snip_4.find("_")
            spell_id_type = int(snip_4[:end_snip])
            result = {
                "type": type,
                "element_id": [dimension, parameter, spell_id_type, spell_id]
                }
            return result
        else:
            return None
            
    elif type_slug == "parameter":
        type = "parameter"
        if argument.find("new") > -1:
            #Dimension
            snip = argument[9:]
            end_snip = snip.find("_")
            dimension = int(snip[:end_snip])
            #Parameter
            snip_2 = snip[(end_snip + 1):]
            end_snip = snip_2.find("_")
            parameter = int(snip_2[:end_snip])
            result = {
                "type": type,
                "element_id": [dimension, parameter]
                }
            return result
        else:
            return None
            
    elif type_slug == "dimension":
        type = "dimension"
        if argument.find("new") > -1:
            #Dimension
            snip = argument[9:]
            end_snip = snip.find("_")
            dimension = int(snip[:end_snip])
            result = {
                "type": type,
                "element_id": dimension
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
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/requestbuilder', RequestBuilderPage),
    ('/buildrequestform', BuildRequestForm),
    ('/selectrequestform', SelectRequestForm),
    ('/newelement', NewElementForm),
    ('/about', AboutPage),
    ('/output', DownloadPage)
], debug=True)
