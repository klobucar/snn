if (typeof S3BL_IGNORE_PATH == 'undefined' || S3BL_IGNORE_PATH!=true) {
	var S3BL_IGNORE_PATH = false;
}

if (typeof BUCKET_URL == 'undefined') {
	var BUCKET_URL = location.protocol + '//' + location.hostname;
}

if (typeof BUCKET_NAME != 'undefined') {
		// if bucket_url does not start with bucket_name,
		// assume path-style url
		if (!~BUCKET_URL.indexOf(location.protocol + '//' + BUCKET_NAME)) {
				BUCKET_URL += '/' + BUCKET_NAME;
		}
}

if (typeof S3B_ROOT_DIR == 'undefined') {
	var S3B_ROOT_DIR = '';
}

jQuery(function($) {
	getS3Data();
});

function getS3Data(marker, html) {
	var s3_rest_url = createS3QueryUrl(marker);
	// set loading notice
	$('#listing').html('<img src="ajaxload-circle.gif" />');
	$.get(s3_rest_url)
		.done(function (data) {
			// clear loading notice
			$('#listing').html('');
			var xml = $(data);
			var info = getInfoFromS3Data(xml);
			html = typeof html !== 'undefined' ? html + prepareTable(info) : prepareTable(info);
			if (info.nextMarker != "null") {
				getS3Data(info.nextMarker, html);
			} else {
				document.getElementById('listing').innerHTML = '<pre>' + html + '</pre>';
			}
		})
		.fail(function(error) {
			console.error(error);
			$('#listing').html('<strong>Error: ' + error + '</strong>');
		});
}

function createS3QueryUrl(marker) {
	var s3_rest_url = BUCKET_URL;
	s3_rest_url += '?delimiter=/';

	//
	// Handling paths and prefixes:
	//
	// 1. S3BL_IGNORE_PATH = false
	// Uses the pathname
	// {bucket}/{path} => prefix = {path}
	//
	// 2. S3BL_IGNORE_PATH = true
	// Uses ?prefix={prefix}
	//
	// Why both? Because we want classic directory style listing in normal
	// buckets but also allow deploying to non-buckets
	//

	var rx = '.*[?&]prefix=' + S3B_ROOT_DIR + '([^&]+)(&.*)?$';
	var prefix = '';
	if (S3BL_IGNORE_PATH==false) {
		var prefix = location.pathname.replace(/^\//, S3B_ROOT_DIR);
	}
	var match = location.search.match(rx);
	if (match) {
		prefix = S3B_ROOT_DIR + match[1];
	} else {
		if (S3BL_IGNORE_PATH) {
			var prefix = S3B_ROOT_DIR;
		}
	}
	if (prefix) {
		// make sure we end in /
		var prefix = prefix.replace(/\/$/, '') + '/';
		s3_rest_url += '&prefix=' + prefix;
	}
	if (marker) {
		s3_rest_url += '&marker=' + marker;
	}
	return s3_rest_url;
}

function getInfoFromS3Data(xml) {
	var files = $.map(xml.find('Contents'), function(item) {
		item = $(item);
		return {
			Key: item.find('Key').text(),
			LastModified: dateToHumanReadable(item.find('LastModified').text()),
			Size: bytesToHumanReadable(item.find('Size').text()),
			Type: 'file'
		}
	});
	files.sort(nameSort);
	var directories = $.map(xml.find('CommonPrefixes'), function(item) {
		item = $(item);
		return {
			Key: item.find('Prefix').text(),
			LastModified: '',
			Size: '',
			Type: 'directory'
		}
	});
	directories.sort(nameSort);
	if ($(xml.find('IsTruncated')[0]).text() == 'true') {
		var nextMarker = $(xml.find('NextMarker')[0]).text();
	} else {
		var nextMarker = null;
	}
	return {
		files: files,
		directories: directories,
		prefix: $(xml.find('Prefix')[0]).text(),
		nextMarker: encodeURIComponent(nextMarker)
	}
}

// info is object like:
// {
//		files: ..
//		directories: ..
//		prefix: ...
// } 
function prepareTable(info) {
	var files = info.directories.concat(info.files)
		, prefix = info.prefix
		;
	var cols = [ 45, 30, 15 ];
	var content = [];
	content.push(padRight('NCSBE File', cols[0]) + padRight('Size', cols[2]) + 'Last Modified' + ' \n');
	content.push(new Array(cols[0] + cols[1] + cols[2] + 4).join('-') + '\n');

	// add the ../ at the start of the directory listing
	if (prefix) {
		var up = prefix.replace(/\/$/, '').split('/').slice(0, -1).concat('').join('/'), // one directory up
			item = {
				Key: up,
				LastModified: '',
				Size: '',
				keyText: '../',
				href: S3BL_IGNORE_PATH ? '?prefix=' + up : '../'
			},
			row = renderRow(item, cols);
		content.push(row + '\n');
	}

	jQuery.each(files, function(idx, item) {
		// strip off the prefix
		item.keyText = item.Key.substring(prefix.length);

		//skip files to not show
		switch (item.keyText) {
			case 'index.html':
				return true;
				break;
			case 'jquery.min.js':
				return true;
				break;
			case 'list.js':
				return true;
				break;
			case 'ajaxload-circle.gif':
				return true;
				break;
			case 'Thumbs.db':
				return true;
				break;
		}

		if (item.Type === 'directory') {
			if (S3BL_IGNORE_PATH) {
				item.href = location.protocol + '//' + location.hostname + location.pathname + '?prefix=' + item.Key;
			} else {
				item.href = item.keyText;
			}
		} else {
			item.href = BUCKET_URL + '/' + encodeURIComponent(item.Key);
			item.href = item.href.replace(/%2F/g, '/');
		}
		var row = renderRow(item, cols);
		content.push(row + '\n');
	});

	return content.join('');
}

function renderRow(item, cols) {
	var row = '';
	//shorten item text if too long
	var itemtext = (item.keyText.length > cols[0] ? item.keyText.slice(0, cols[0] - 3) + '...' : item.keyText);
	row += '<a href="' + item.href + '"' + (~itemtext.indexOf('...') ? ' title="' + item.keyText + '" ' : '') + '>' + itemtext + '</a>' + padRight('', cols[0] - item.keyText.length, true);
	row += padRight(item.Size, cols[2]);
	row += item.LastModified;
	return row;
}

function padRight(padString, length, spaceonly) {
	var str = padString.slice(0, length - 3);
	if (padString.length > str.length) {
		str += '...';
	}
	while (str.length < length) {
		str = str + ' ';
	}
	if (spaceonly == true) {
		str = str.replace(padString.slice(0, length - 3), '');
	}
	return str;
}

function bytesToHumanReadable(sizeInBytes) {
	var i = -1;
	var units = [' KB', ' MB', ' GB'];
	do {
		sizeInBytes = sizeInBytes / 1024;
		i++;
	} while (sizeInBytes > 1024);
	return Math.max(sizeInBytes, 0.1).toFixed(1) + units[i];
}

function dateToHumanReadable(fileDate) {
	var newDate = new Date(fileDate).toLocaleString();
	if (newDate == 'Invalid Date') {
		newDate = '';
	}
	return newDate;
}

function nameSort(a, b) {
	var valA = a.Key.toUpperCase(),
		valB = b.Key.toUpperCase();

	return valA < valB ? -1 : valA == valB ? 0 : 1;
}
