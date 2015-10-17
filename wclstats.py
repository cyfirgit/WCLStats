# coding: utf-8

import webapp2
import apirequests
import json
import csv
import exportdata

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        self.response.write(output)

test_parameters = {
	"metric":"dps",
	"difficulty":4,
	"class":1,
	"spec":3,
	}
	
test_trinkets = [
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
		"include": [184983],
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
		},
	{
		"name": "Forgemaster's Insignia",
		"include": [177096],
		"exclude": None
		},
	{
		"name": "Horn of Screaming Spirits",
		"include": [177042],
		"exclude": None
		},
	]
		
test_dimensions = {
	"T7 Talent": {
		"NP": {
			"include": [155159],
			"exclude": None
			},
		"Def": {
			"include": [152280],
			"exclude": None
			},
		"BoS": {
			"include": [152279],
			"exclude": None
			}
		},
	"T4 Talent": {
		"BT": {
			"include": [114851],
			"exclude": None
			},
		"RC": {
			"include": [51460],
			"exclude": None
			},
		"RE": {
			"include": None,
			"exclude": [114851, 51460]
			}
		},
	"Trinkets": apirequests.build_trinket_dimensions(test_trinkets)
	}
	
pull = apirequests.rankings_pull_filtered(1799, test_parameters, test_dimensions)
output = exportdata.csv_output(pull, test_dimensions)

		
app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)