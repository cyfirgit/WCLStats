//formID tracks what elements exist in the form by ID & assigns unique IDs
var formID = [];

//used by the html templating in a script to increment formID when loading an existing request
function setID(idType, dimension, parameter, spell_id) {
	if (idType === 'dimension') {
		formID[dimension] = [];
	} else if (idType === 'parameter') {
		formID[dimension][parameter] = [];
	} else if (idType === 'spell_id') {
		if (spell_id >= 200) {
			formID[dimension][parameter][2] = (spell_id - 200);
		} else if (spell_id >= 100) {
			formID[dimension][parameter][1] = (spell_id - 100);
		};
	};	
};

//when a request is selected from the dropdown, loads it into the request builder
function selectRequest() {
	var selectedRequest = this.id;
	$( '#requestName' ).val(selectedRequest);
	
	var data = {
		request: selectedRequest,
		request_type: 'existing',
	}
	$.post('/selectrequestform', data, buildRequest, 'html');
};

//creates a blank request
function newRequest() {
	var selectedRequest = $( '#requestName' ).val();
	if (selectedRequest !== '') {
		//If the new request has a name, process it.
		var data = {
			request: selectedRequest,
			request_type: 'new',
		};
		$.post('/selectrequestform', data, buildRequest, 'html');
	} /*else {
		//Warn that a new request needs a name  XXX ADD THIS XXX
	}*/;
};

//loads the response from POST when selecting a new/exisiting request
function buildRequest(requestForm) {
	$("#requestForm").html(requestForm);
};

//takes the html element ID and breaks it into an array that can interface with formID
function parseIdArray(element_id) {
	var idArray = []
	
	if (element_id.indexOf('dimension') > -1) {
		str = element_id.slice(10);
		cut = str.indexOf("_");
		idArray[0] = str.slice(0,cut);
	} else if (element_id.indexOf('parameter') > -1) {
		str0 = element_id.slice(10);
		cut0 = str0.indexOf("_");
		idArray[0] = str0.slice(0,cut0);
		
		str1 = str0.slice(cut0 + 1);
		cut1 = str1.indexOf("_");
		idArray[1] = str1.slice(0,cut1);
	} else if (element_id.indexOf('spell_id') > -1) {
		str0 = element_id.slice(9);
		cut0 = str0.indexOf("_");
		idArray[0] = str0.slice(0,cut0);
		
		str1 = str0.slice(cut0 + 1);
		cut1 = str1.indexOf("_");
		idArray[1] = str1.slice(0,cut1);
			
		if (element_id.indexOf('include') > -1) {
			idArray[2] = 'include';
		} else if (element_id.indexOf('exclude') > -1) {
			idArray[2] = 'exclude';
		} else {
			idArray[2] = str1.slice(cut1 + 1);
		}
	};
	return idArray;
};

//Adds a user-entered spellID to the request and creates a new input box for further spells
function addSpell(element_id) {
	if ( $.isNumeric( $( "input#" + element_id ).val() )) {
		var idArray = parseIdArray(element_id);
		/* idArray components:
			[0] = dimension index
			[1] = parameter index
			[2] = 'include' or 'exclude'
			[3] = spellID index
		*/
		if (idArray[2] === 'include') {
			idArray[3] = 1
		} else if (idArray[2] === 'exclude') {
			idArray[3] = 2
		};
		if ( typeof formID[idArray[0]][idArray[1]][idArray[3]] !== 'undefined') {
			formID[idArray[0]][idArray[1]][idArray[3]] += 1
		} else {
			formID[idArray[0]][idArray[1]][idArray[3]] = 1
		};
		idArray[4] = formID[idArray[0]][idArray[1]][idArray[3]]
		$.ajax({
			dataType: "json",
			type: "post",
			url: '/newelement',
			data: ({
				'type': 'spell',
				'id_array': String(idArray),
				'element_id': String(element_id),
				'input_value': $( "input#" + element_id ).val(),
			}),
			success: writeElement,
		});
	};
};

//Adds a user-entered parameter to the request and creates a new input box for further parameters
function addParameter(element_id) {
	if ( $( "input#" + element_id ).val() !== "") {
		var idArray = parseIdArray(element_id);
		/* idArray components:
			[0] = dimension index
			[1] = parameter index (This should be 'new' after parseIdArray())
		*/
		formID[idArray[0]].push([]);
		idArray[1] = formID[idArray[0]].length;
		$.ajax({
			dataType: "json",
			type: "post",
			url: '/newelement',
			data: ({
				'type': 'parameter',
				'id_array': String(idArray),
				'element_id': String(element_id),
				'input_value': $( "input#" + element_id ).val(),
			}),
			success: writeElement,
		});
	};
};

//Adds a user-entered dimension to the request and creates a new input box for further dimensions
function addDimension(element_id) {
	if ( $( "input#" + element_id ).val() !== "") {
		var idArray = []
		formID.push([]);
		idArray[0] = formID.length;
		$.ajax({
			dataType: "json",
			type: "post",
			url: '/newelement',
			data: ({
				'type': 'dimension',
				'id_array': String(idArray),
				'element_id': String(element_id),
				'input_value': $( "input#" + element_id ).val(),
			}),
			success: writeElement,
		});
	};
};

function addTrinkets() {
	$.ajax({
		dataType: "json",
		type: "post",
		url: '/newelement',
		data: ({
			'type': 'trinkets',
			'id_array': '',
			'element_id': 'trinketsContainer',
			'input_value': '',
		}),
		success: writeElement,
	});
};

function writeElement(newElement) {
	$( "div#" + newElement.element_id ).replaceWith(newElement.template);
};

function removeElement(element) {
	$( "div#" + element).hide('slow', function(){ $(this).remove(); });
};

function removeTrinkets() {
	$.ajax({
		dataType: "json",
		type: "post",
		url: '/newelement',
		data: ({
			'type': 'no_trinkets',
			'id_array': '',
			'element_id': 'trinketsContainer',
			'input_value': '',
		}),
		success: writeElement,
	});
};

function chevronToggle(element) {
	if( $( element ).find('span.glyphicon-chevron-down').length != 0) {
		$( element ).html('<span class="glyphicon glyphicon-chevron-right" aria-hidden="true"></span>')
	} else if( $( element ).find('span.glyphicon-chevron-right').length != 0) {
		$( element ).html('<span class="glyphicon glyphicon-chevron-down" aria-hidden="true"></span>')
	};
};

function changeClass(characterClass) {
	$.ajax({
		dataType: "json",
		type: "post",
		url: '/newelement',
		data: ({
			'type': 'specializations',
			'id_array': '',
			'element_id': 'specializationsContainer',
			'input_value': characterClass,
		}),
		success: writeElement,
	});
}

$(document).ready(function() {
	$( "#selectRequest li a" ).click(selectRequest);
	$( "#newRequest" ).click(newRequest);
	$(document).on('change', 'select#characterClass', function(){changeClass(this.value)});
	$(document).on('click', 'button#addTrinkets', function(){addTrinkets()});
	$(document).on('click', 'button#removeTrinkets', function(){removeTrinkets()});
	$(document).on('click', 'button#spell_id_plus', function(){addSpell(this.value)});
	$(document).on('click', 'button#parameter_plus', function(){addParameter(this.value)}); 
	$(document).on('click', 'button#dimension_plus', function(){addDimension(this.value)}); 
	$(document).on('click', 'button#spell_id_minus', function(){removeElement(this.value)});
	$(document).on('click', 'button#parameter_minus', function(){removeElement(this.value)});
	$(document).on('click', 'button#dimension_minus', function(){removeElement(this.value)});
	$(document).on('click', 'button#chevron-toggle', function(){chevronToggle(this)});
});