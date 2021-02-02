import textwrap
from univention.lib.i18n import Translation
from cgi import parse_qs
_ = Translation('univention-management-console-module-office365').translate

try:
	from html import escape
	from urllib.parse import parse_qs
except ImportError: # Python 2
	from cgi import escape, parse_qs


def application(environ, start_response):
	status = '200 OK'
	response_header = [('Content-type', 'text/html; charset=UTF-8')]
	start_response(status, response_header)
	try:
		request_body_size = int(environ.get('CONTENT_LENGTH', 0))
	except (ValueError):
		request_body_size = 0

	request_body = environ['wsgi.input'].read(request_body_size)
	request_body = parse_qs(request_body)

	content = textwrap.dedent(u"""\
	<!DOCTYPE html>
	<html>
		<head>
			<title>%(title)s</title>
		</head>
		<body>
			<form action="/univention/command/office365/authorize_internal" id="form_auth" method="post">
	""" % {'title': _('Microsoft 365 Configuration finished')})

	for name, value in request_body.items():
		content += u'\t<input type="hidden" name="%s" value="%s" />\n' % (escape(name), escape(value[0]))

	content += textwrap.dedent(u"""\
				<button type="submit">...</button>
			</form>
			<script type="application/javascript">//<!--
				document.getElementById("form_auth").submit();
			//--></script>
		</body>
	</html>
	""")
	return [content.encode('UTF-8')]
