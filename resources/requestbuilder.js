var formID = [];

function setID(idType, dimension, parameter, spell_id) {
	if (idType === 'dimension') {
		console.log('Adding index [' + dimension + ']');
		formID[dimension] = [];
	} else if (idType === 'parameter') {
		console.log('Adding index [' + dimension + '][' + parameter + ']');
		formID[dimension][parameter] = [];
	} else if (idType === 'spell_id') {
		if (spell_id >= 200) {
		console.log('Adding index [' + dimension + '][' + parameter + '][2][' + spell_id + ']');
			formID[dimension][parameter][2] = (spell_id - 200);
		} else if (spell_id >= 100) {
		console.log('Adding index [' + dimension + '][' + parameter + '][1][' + spell_id + ']');
			formID[dimension][parameter][1] = (spell_id - 100);
		};
	};	
};

function selectRequest() {
	var selectedRequest = this.id;
	$( '#requestName' ).val(selectedRequest);
	
	var data = {
		request: selectedRequest
	}
	$.post('/selectrequestform', data, buildRequest, 'html');
};

function newRequest() {
	$.post('/selectrequestform', {request:"new"}, buildRequest, 'html');
};

function buildRequest(requestForm) {
	$("#requestForm").html(requestForm);
};

$(document).ready(function() {
	$( "#selectRequest li a" ).click(selectRequest);
	$( "#newRequest" ).click(newRequest);
});