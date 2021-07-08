import os
import re
import json
import time
import shutil

ASYNC_DATA_DIR = '/var/lib/univention-office365/async'
ASYNC_FAILED_DIR = os.path.join(ASYNC_DATA_DIR, 'failed')


def get_http_proxies(ucr, logger):
    res = dict()
    # 1. proxy settings from environment
    for req_key, env_key in [
        ('http', 'HTTP_PROXY'), ('http', 'http_proxy'), ('https', 'HTTPS_PROXY'), ('https', 'https_proxy')
    ]:
        try:
            res[req_key] = os.environ[env_key]
        except KeyError:
            pass
    # 2. settings from system wide UCR proxy settings
    for req_key, ucrv in [('http', 'proxy/http'), ('https', 'proxy/https')]:
        if ucr[ucrv]:
            res[req_key] = ucr[ucrv]

    # 3. settings from office365 UCR proxy settings
    for req_key, ucrv in [('http', 'office365/proxy/http'), ('https', 'office365/proxy/https')]:
        if ucr[ucrv] and ucr[ucrv] == 'ignore':
            try:
                del res[req_key]
            except KeyError:
                pass
        elif ucr[ucrv]:
            res[req_key] = ucr[ucrv]
    # remove password from log output
    res_redacted = res.copy()
    for k, v in res_redacted.items():
        password = re.findall(r'http.?://\w+:(\w+)@.*', v)
        if password:
            res_redacted[k] = v.replace(password[0], '*****', 1)

    logger.info('proxy settings: %r', res_redacted)
    return res


def write_async_json(data):
    filename = os.path.join(ASYNC_DATA_DIR, '{time:f}.json'.format(time=time.time()))
    filename_tmp = filename + '.tmp'
    with open(filename_tmp, 'wb') as fd:
        json.dump(data, fd, sort_keys=True, indent=4)
    shutil.move(filename_tmp, filename)


def write_async_job(a_api_version=1, a_function_name=None, a_ad_connection_alias=None, a_logger=None, **kwargs):

    success = False

    # api_version 1
    # {
    #   "function_name": "convert_from_group_to_team",
    #   "ad_connection_alias": "alias1",
    #   "api_version": 1,
    #   "parameters": {
    #     "param1": "value1",
    #     "param2": "value2"
    #   }
    # }
    if a_api_version == 1:
        if a_function_name and a_ad_connection_alias:
            data = {
                "function_name": a_function_name,
                "ad_connection_alias": a_ad_connection_alias,
                "api_version": 1,
            }
            if kwargs:
                data['parameters'] = kwargs
            write_async_json(data)
            success = True

    return success
