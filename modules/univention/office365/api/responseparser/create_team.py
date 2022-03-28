import re

'''
    The teams API is inconsistent with the rest of the Graph API calls in that
    it does not return a JSON with the result. Instead it uses the Location
    header with a cruse url format, for which this function is there to parse
    it.
'''


def get_team_id(response):
    return re.search(r"teams\('([^']+)'\)", response['Location']).group(1) or None
