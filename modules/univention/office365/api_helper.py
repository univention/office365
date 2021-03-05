import os
import re


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
