# coding: utf-8
import csv


def csv_output(ranks, dimensions):
	csvfile = ""
	fieldnames = ["name", "class", "spec", "itemLevel", "total",
				  "duration", "size", "link", "guild", "server"]
	for dimension in dimensions:
		fieldnames.append(dimension)
	
	for field in fieldnames:
		csvfile += field + ","
	csvfile = new_line(csvfile)
	
	for rank in ranks:
		for item in fieldnames:
			if item == "link":
				csvfile += "https://www.warcraftlogs.com/reports/" + \
							rank["reportID"] + "#fight=" + \
							str(rank["fightID"]) + ","
			else:
				csvfile += unicode(rank[item]) + ","
		csvfile = new_line(csvfile)
	return csvfile
	
			
def new_line(string):
	index = len(string)
	s = string[:(index - 1)]
	string = s + "\n"
	return string