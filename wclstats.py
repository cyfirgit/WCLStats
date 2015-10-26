# coding: utf-8

#PROJECT TODO:
#Implement storage of requests/dimensions/parameters
#Build web interface for pull requests
#Implement decremental request size to respond to timeout issues.

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

	
class RequestFilter(ndb.Model):
    name = ndb.StringProperty()
	
	
class MainPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("templates/wclstats.html")
        self.response.write(template.render({}))
		
		
class RequestBuilderPage(webapp2.RequestHandler):
    selected_filter = []
    
    def post(self):
        selected_filter = self.request.get("selectFilter")
    
    def get(self):
        filters = RequestFilter.query().fetch()
        template_values = {
            'filters': filters,
            'selected_filter': selected_filter,
        }
        template = JINJA_ENVIRONMENT.get_template("templates/requestbuilder.html")
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
		
		
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/requestbuilder', RequestBuilderPage),
    ('/about', AboutPage),
    ('/output', DownloadPage)
], debug=True)

# dl = webapp2.WSGIApplication([
    # ('/output/', DownloadPage)
# ], debug=True)

boss = 1799

unholy_parameters = {
    "metric":"dps",
    "difficulty":5,
    "class":1,
    "spec":3,
    }
	
unholy_trinkets = [
    {
        "name": "Unending Hunger",
        "include": [183941],
        "exclude": None
        },
    {
        "name": "Discordant Chorus",
        "include": [184248],
        "exclude": None
        },
    {
        "name": "Empty Drinking Horn",
        "include": [184256],
        "exclude": None
        },
    {
        "name": "Both Other Trinkets",
		"include": None,
		"exclude": None
		},
	{
		"name": "Reaper's Harvest",
		"include": [184899],
		"exclude": None
		},
	{
		"name": "Vial of Convulsive Shadows",
		"include": [176874],
		"exclude": None
		},
	{
		"name": "Other Trinkets",
		"include": None,
		"exclude": None
		}
	]
		
unholy_dimensions = {
	"T7/T4 Pair": {
		"NP|BT": {
			"include": [155159, 114851],
			"exclude": None
			},
		"Def|BT": {
			"include": [152280, 114851],
			"exclude": None
			},
		"BoS|BT": {
			"include": [152279, 114851],
			"exclude": None
			},
		"NP|RC": {
			"include": [155159, 51460],
			"exclude": None
			}
		},
	"Trinkets": apirequests.build_trinket_dimensions(unholy_trinkets)
	}
	
frost_parameters = {
	"metric":"dps",
	"difficulty":5,
	"class":1,
	"spec":2,
	}
	
frost_trinkets = [
	{
		"name": "Unending Hunger",
		"include": [183941],
		"exclude": None
		},
	{
		"name": "Discordant Chorus",
		"include": [184248],
		"exclude": None
		},
	{
		"name": "Empty Drinking Horn",
		"include": [184256],
		"exclude": None
		},
	{
		"name": "Both Other Trinkets",
		"include": None,
		"exclude": None
		},
	{
		"name": "Reaper's Harvest",
		"include": [184982],
		"exclude": None
		},
	{
		"name": "Other Trinkets",
		"include": None,
		"exclude": None
		}
	]
		
frost_dimensions = {
	"T7/T4 Pair": {
		"NP|BT": {
			"include": [155159, 114851],
			"exclude": None
			},
		"Def|BT": {
			"include": [152280, 114851],
			"exclude": None
			},
		"NP|RC": {
			"include": [155159, 51460],
			"exclude": None
			}
		},
	"Trinkets": apirequests.build_trinket_dimensions(frost_trinkets)
	}
	


