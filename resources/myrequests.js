function validatePull() {
	//Checks that the pull parameters are valid before POSTing to /buildpull.
	//Start by collecting all the selected difficulties and encounters, as well
	//as the selected metric.
	var difficulties = $("input[type=checkbox][name='difficulty']:checked")
	var encounters = $("input[type=checkbox][name='encounter']:checked")
	var metric = $("input[type=radio][name='metric']:checked")
	//Create an empty error message to begin with.
	errorMessage = "";
	
	//Check difficulties/encounters/metric for how many are selected.  If any
	//of them have no options selected, add this to the error message.
	if(difficulties.length < 1) {
		errorMessage += "At least one difficulty must be selected.<br>";
	};
	if(encounters.length < 1) {
		errorMessage += "At least one encounter must be selected.<br>";
	};
	if(metric.length < 1) {
		errorMessage += "You must select the metric to measure.<br>";
	};
	
	//If the error message is still blank, everything validated, so start the
	//buildPull POST.
	if (errorMessage === "") {
		$( "#buildPullForm" ).submit();
	//Otherwise, add a bootstrap alert with all the error messages to the modal.
	} else {
		$( '#modalError' ).html('<div class="alert alert-warning" role="alert">' + errorMessage	+ '</div>');
	}
};


$(document).ready(function() {
	$('#buildPullModal').on('show.bs.modal', function(e) {
		//Get the name and id of the current request from the button clicked.
		var requestName = $(e.relatedTarget).data('request-name');
		var requestID = $(e.relatedTarget).val();
		
		//Add the request name to the modal title.
		$(e.currentTarget).find('h4[id="buildPullModalLabel"]').html('<div id="modalHeader" data-request-id="' + requestID + '">Request: ' + requestName +'</div>');
		
		//Add the request ID as the value for a hidden form input to pass to the handler.
		$(e.currentTarget).find('input[id="requestID"]').val(requestID)
		
	});
	$('[data-toggle="tooltip"]').tooltip();
    $('[data-toggle="popover"]').popover();
	$(document).on('click', '#startPull', function(){validatePull()});
});