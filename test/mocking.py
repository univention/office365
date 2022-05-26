import mock
import os
import sys

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

# Mocking pwd.getpwnam("listener").pw_uid
pwd_module = mock.MagicMock()
m = mock.Mock()
m.pw_uid = 1000
pwd_module.getpwnam.return_value = m
sys.modules['pwd'] = pwd_module

# Mocking grp.getgrnam("nogroup").gr_gid
grp_module = mock.MagicMock()
m = mock.Mock()
m.gr_gid = 1000
grp_module.getgrnam.return_value = m
sys.modules['grp'] = grp_module
sys.modules['univention.debug'] = mock.MagicMock()
sys.modules['univention.admin'] = mock.MagicMock()
sys.modules['univention.admin'].uldap.getAdminConnection.return_value = mock.MagicMock(), mock.MagicMock()
sys.modules['univention.config_registry'] = mock.MagicMock()
sys.modules['univention.ldap_cache.cache'] = mock.MagicMock()
sys.modules['univention.ldap_cache.frontend'] = mock.MagicMock()
sys.modules['ldap'] = mock.MagicMock()
sys.modules['ldap.filter'] = mock.MagicMock()
sys.modules['unidecode'] = mock.MagicMock()
sys.modules['listener'] = mock.MagicMock()
sys.modules['univention.lib.i18n'] = mock.MagicMock()
sys.modules['univention.config_registry.frontend'] = mock.MagicMock()
