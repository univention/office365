import json
import re


def get_team_id(response):
    # raise Exception(response['Location'])
    # return re.search("teams\('([^']+)'\)", response['Location']).group(1)
    return re.search("teams\('([^']+)'\)", response['Location']).group(1) or None
