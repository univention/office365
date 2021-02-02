import json
import re


def get_team_id(response):
    return re.search("teams\('([^']+)'\)", response['Location']).group(1) or None
