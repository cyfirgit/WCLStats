function parseUser(userid) {
	username = $( "#username_" + this.value ).html(),
	email = $( "#email_" + this.value ).html(),
	level = $( "#level_" + this.value ).html(),
	user = {
		'userid': userid,
		'username': username,
		'email': email,
		'level': level,
	};
	return user;
};

function editAccount(userid) {
	$.ajax({
		dataType: 'json',
		type: 'post',
		url: '/editaccount',
		data: userid,
		success: writeRow,
	});
};

function saveAccount(userid) {
	user = parseUser(userid);
	$.ajax({
		dataType: 'json',
		type: 'post',
		url: '/saveaccount',
		data: user,
		success: writeRow,
	});
};

function writeRow(newElement) {
    $( 'tr#' + newElement.element_id ).replaceWith(newElement.template);
};

$(document).ready(function() {
	$(document).on('click', 'button#edit_account', function(){editAccount(this.value)});
	$(document).on('click', 'button#lock_account', function(){lockAccount(this.value)});
	$(document).on('click', 'button#save_account', function(){saveAccount(this.value)});
	$(document).on('click', 'button#cancel_edit', function(){cancelEdit(this.value)});
});