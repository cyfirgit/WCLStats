function validatePull() {
	var difficulties = $("input[type=checkbox][name='difficulty']:checked").length
	var encounters = $("input[type=checkbox][name='encounter']:checked").length
	var metrics = $("input[type=radio][name='metric']:checked").length
	errorMessage = "";
	
	if(difficulties < 1) {
		errorMessage += "At least one difficulty must be selected.<br>";
	};
	if(encounters < 1) {
		errorMessage += "At least one encounter must be selected.<br>";
	};
	if(metrics < 1) {
		errorMessage += "You must select the metric to measure.<br>";
	};
	
	if (errorMessage === "") {
		console.log("You done good!")
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
		$(e.currentTarget).find('h4[id="buildPullModalLabel"]').html('Request: ' + requestName);
		
	});
	$('[data-toggle="tooltip"]').tooltip();
    $('[data-toggle="popover"]').popover();
	$(document).on('click', '#startPull', function(){validatePull()});
});