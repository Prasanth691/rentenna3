( function( global ){
//	add array index of for old browsers (IE<9)
	if( !Array.prototype.indexOf ){
		Array.prototype.indexOf = function( obj, start ){
			var i, j;
			i = start || 0;
			j = this.length;
			while( i < j ){
				if( this[i] === obj ){
					return i;
				}
				i++;
			}
			return -1;
		};
	}

//	make a global object to store various data in
	if( !global.AddressReportObj ){ global.AddressReportObj = {}; }
	var AddressReportObj = global.AddressReportObj;

//	To keep track of which embeds we have already processed
	if( !AddressReportObj.processedScripts ){ AddressReportObj.processedScripts = []; }
	var processedScripts = AddressReportObj.processedScripts;

	if( !AddressReportObj.styleTags ){ AddressReportObj.styleTags = []; }
	var styleTags = AddressReportObj.styleTags;

//	get and cycle through any "script" tags on the page
	var scriptTags = document.getElementsByTagName('script');

//	loop the widgets passed in
	for( i = 0; i < AddressReportObj.widgets.length; i++ ){

	//	do our magic starting here!! ----------------------------------------------
	//	figure out some of the settings needed
		var settings = AddressReportObj.widgets[i].settings; 
		if( !settings.arwid ){ var error = true; }
		if( !settings.iab ){ settings.iab = 'rectangle'; }
		if( !settings.type ){ settings.type = 'simple'; }
		if( !settings.address ){ settings.address = ''; }

	//	Loop scripts in the page
		for( var j = 0; j < scriptTags.length; j++ ){
			var scriptTag = scriptTags[j];

		//	src matches the url of this request, and not processed it yet.
			if( scriptTag.src && scriptTag.src.indexOf('/widget/ar-lc-widget.js') > 0 && processedScripts.indexOf(scriptTag.src) < 0 ){

			//	add this script into the "processed" list
				processedScripts.push(scriptTag.src);

				var temp = document.createElement('a');
				temp.href = scriptTag.src;

				baseUrl = temp.protocol + "//" + temp.host;
				if (baseUrl.indexOf('cdn-addressreport') < 0) {
					baseUrl += "/resource"
				}

				if( !error ){

				//	add the style tag into the head (once only)
					if( styleTags.length === 0 ){

					//	add a style tag to the head
						var styleTag = document.createElement("link");
						styleTag.rel = "stylesheet";
						styleTag.type = "text/css";
						styleTag.href =  baseUrl + "/widget/ar-lc-widget.css?version=20160929-1742";
						styleTag.media = "all";
						document.getElementsByTagName('head')[0].appendChild(styleTag);
						styleTags.push(styleTag);
					}

				}	//	End !AddressReportObj.error 

			}	//	End condition for matching widget script

		}	//	End loop of found "scritpTags"

		if( !error ){

			var parentScript = document.getElementById( settings.elemid );
			var div = document.createElement('div');

		//	Add the cleanslate class for extreme-CSS reset.
			div.className = 'ar-lc-widget-embeddable ar-lc-widget ar-lc-widget-'+settings.type+' cleanslate iab-'+settings.iab+'';
			parentScript.parentNode.insertBefore( div, parentScript.previousSibling );
			var arDiv	= '<div class="ar-lc-innerWrap">';

		//	build the querystring to pass to the iframe
			var qs =  "?load=true";
				qs += "&arwid="+settings.arwid;
				qs += "&arwsc="+settings.arwsc;
				qs += "&type="+settings.type;
				qs += "&address="+settings.address;
				qs += "&iab="+settings.iab;
				qs += "&formbaseurl=" + settings.formbaseurl;

			if( settings.iab == 'inline' ){

				arDiv += '<iframe class="ar-lc-iframe" src="' + settings.formbaseurl + '/widget/contact-form/'+qs+'"></iframe>';

			}else{

				arDiv	+= '	<a href="#ar_lc_openModal_'+settings.elemid+'" id="ar_lc_btnModal" class="ar-lc-img-button" title="Send Me My Report">';

				//	determine the image to load
					var arImg	= '';
					if( settings.iab == 'square-pop-up' ){			//	Square Pop-up	250 x 250
						arImg	+= 'house-250x250';
					}else if( settings.iab == 'rectangle' ){		//	Rectangle		180 x 150
						arImg	+= 'house-180x150';
					}else if( settings.iab == 'full-banner' ){		//	Full-banner		468 x 60
						arImg	+= 'house-468x60';
					}else if( settings.iab == 'half-banner' ){		//	Half-banner		234 x 60
						arImg	+= 'house-234x60';
					}
				//	show image if set
					if( arImg.length > 0 ){
						arDiv	+= '	<img src="' + baseUrl + '/image/widget/lead-capture/'+arImg+'.png" />';
					}

				arDiv	+= '	</a>';

				arDiv	+= '	<div id="ar_lc_openModal_'+settings.elemid+'" class="ar-lc-modal ar-lc-modalDialog">';
				arDiv	+= '		<div class="ar-lc-modal-innerWrap">';
				arDiv	+= '			<a href="#ar_lc_close" title="Close" class="ar-lc-close">X</a>';
				arDiv	+= '		 	<iframe class="ar-lc-iframe" src="' + settings.formbaseurl + '/widget/contact-form/'+qs+'"></iframe>';
				arDiv	+= '		</div>';
				arDiv	+= '	</div>';
			}

			arDiv	+= '</div><!-- // end .ar-lc-innerWrap -->';
			div.innerHTML = arDiv;

		}	//	End !AddressReportObj.error 

	}	//	End loop of AddressReportObj.widgets

})( this );