# MS Graph specific errors =====================================================

'''
	The GraphError class is kept very generic at this point. There will
	probably be more specific error messages required in the future and for
	that this file has already been prepared. That way we can keep the
	adaptions required to introduce new error types smaller.
'''


class NoAllocatableSubscriptions(Exception):
	def __init__(self, user, adconnection_alias=None, *args, **kwargs):
		self.user = user
		self.adconnection_alias = adconnection_alias
		super(NoAllocatableSubscriptions, self).__init__(*args, **kwargs)

class GraphError(Exception):
	pass


class GraphRessourceNotFroundError(GraphError):
	pass

# vim: filetype=python expandtab tabstop=4 shiftwidth=4 softtabstop=4
