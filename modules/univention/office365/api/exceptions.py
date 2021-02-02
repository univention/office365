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

# vim: filetype=python expandtab tabstop=4 shiftwidth=4 softtabstop=4
