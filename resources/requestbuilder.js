var formID = [];

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
			idArray[2] = element_id.slice(cut + 1);
		}
	};
	return idArray;
};

function addSpell(element_id) {
	if ( typeof $( "input#" + element_id ).val() !== 'undefined') {
		var idArray = parseIdArray(element_id);
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
	};
	$.ajax({
		dataType: "json",
		type: "post",
		url: '/newelement',
		data: ({
			'type': 'spell',
			'id_array': String(idArray),
			'element_id': String(element_id),
			'spell_id': $( "input#" + element_id ).val(),
		}),
		success: writeElement,
	})
};

function writeElement(newElement) {
	$( "div#" + newElement.element_id ).replaceWith(newElement.template);
}

function removeElement(element) {
	$( "div#" + element).hide('slow', function(){ $this.remove(); });
}

$(document).ready(function() {
	$( "#selectRequest li a" ).click(selectRequest);
	$( "#newRequest" ).click(newRequest);
	$(document).on('click', 'button#spell_id_plus', function(){addSpell(this.value)}); 
	$(document).on('click', 'button#spell_id_minus', function(){removeElement(this.value)});
	$(document).on('click', 'button#parameter_minus', function(){removeElement(this.value)});
	$(document).on('click', 'button#dimension_minus', function(){removeElement(this.value)});
});