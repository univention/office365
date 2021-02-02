class AzureError(Exception):
    def __init__(self, msg, chained_exc=None, adconnection_alias=None, *args, **kwargs):
        self.chained_exc = chained_exc
                self.adconnection_alias = adconnection_alias
                super(AzureError, self).__init__(msg, *args, **kwargs)


class TokenError(AzureError):
    def __init__(self, msg, response=None, *args, **kwargs):
        self.response = response
        if response and hasattr(response, "json"):
            j = response.json
        if callable(response.json):  # requests version compatibility
            j = j()
        self.error_description = j["error_description"]
        super(TokenError, self).__init__(msg, *args, **kwargs)


class IDTokenError(AzureError):
    pass


class TokenValidationError(AzureError):
    pass


class NoIDsStored(AzureError):
    pass


class ManifestError(AzureError):
    pass


class WriteScriptError(AzureError):
    pass


class ADConnectionIDError(AzureError):
    pass


# MS Graph specific errors =====================================================

class GraphError(Exception):
    pass


class GroupAlreadyExists(GraphError):
    pass

class UserAlreadyExists(GraphError):
    pass

class TokenFileNotFound(GraphError):
    pass

class TokenFileInvalid(GraphError):
    pass

