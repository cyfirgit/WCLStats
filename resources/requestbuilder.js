function loadFilter() {
	var selectedFilter = $( "#selectFilter" ).val();
	var data = {
		filter: selectedFilter
	}
	$.post('/selectfilterform', data);
};

function newFilter() {
	console.log("Loading a new filter.");
	$.post('/selectfilterform', "new!");
};

$(document).ready(function() {
	$( "#selectFilter" ).change(loadFilter);
	$( "#newFilter" ).click(newFilter);
});