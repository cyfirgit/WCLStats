# coding: utf-8

#PROJECT TODO:

#For prototype:
    #Build web interface for pull requests
        #Add trinket dimension to resquestform.html
        #Add/Remove item functions
        #New reqest option
        #submit form processing code
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

from google.appengine.ext import ndb

import apirequests
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
    def post(self):
        pass
    
    
class SelectRequestForm(webapp2.RequestHandler):
    def post(self):
        #Query NDB for the request and its dimensions and parameters.
        selected_request = self.request.get('request')
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
                    "exlcude": parameter.exclude
                    })
            dimensions.append({
                "name": dimension.name,
                "parameters": parameters
                })
                
        #Pass class and spec data to the form for dropdowns.
        classes = Reference.get_by_id("wcl_classes").json
        for class_ in classes:
            if class_['id'] == request_complete.character_class:
                class_index = classes.index(class_)
                
        template_values = {
            'request': {
                'selected_request': selected_request,
                'character_class': request_complete.character_class,
                'specializations': request_complete.specialization,
                'dimensions': dimensions,
                'class_index': class_index,
                },
            'classes': classes,
            }
        
        template = JINJA_ENVIRONMENT.get_template("templates/requestform.html")
        self.response.write(template.render(template_values))
		
		
class AboutPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("templates/about.html")
        self.response.write(template.render({}))

		
class DownloadPage(webapp2.RequestHandler):
    def post(self):
        logging.info("***Beginning Frost Pull***")
        pull = apirequests.rankings_pull_filtered(boss, frost_parameters, frost_dimensions)
        logging.info("***Compiling frost.csv data***")
        output = exportdata.csv_output(pull, frost_dimensions)
        self.response.headers["Content-Type"] = "application/csv"
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s' % "output.csv"
        self.response.write(output)    
    
        
def initialize():
    class_data = apirequests.static_request("WCL", "classes")
    zone_data = apirequests.static_request("WCL", "zones")
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
        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/requestbuilder', RequestBuilderPage),
    ('/buildrequestform', BuildRequestForm),
    ('/selectrequestform', SelectRequestForm),
    ('/about', AboutPage),
    ('/output', DownloadPage)
], debug=True)
