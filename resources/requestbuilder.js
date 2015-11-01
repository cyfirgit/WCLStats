function selectRequest() {
	var selectedRequest = this.id;
	console.log("Firing selectRequest");
	console.log(selectedRequest);
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