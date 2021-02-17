import json
import re


def get_team_id(response):
    return re.search(
        r'/teams/(?P<teamId>[^/]*)/operations/(?P<operationId>.*)',
        response['location']
    )['teamId']
