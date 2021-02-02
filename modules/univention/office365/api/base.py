from abc import ABC

class Base(ABC):
    """
    This abstract base class lists all functions required by udm.
    """
    def __init__(self, ucr, name, adconnection_alias=None):
        pass

    def list_users(self, objectid=None, ofilter=None):
        pass

    def get_users_direct_groups(self, user_id):
        pass

    def list_groups(self, objectid=None, ofilter=None):
        pass

    def invalidate_all_tokens_for_user(self, user_id):
        pass

    def reset_user_password(self, user_id):
        pass

    def create_user(self, attributes):
        pass

    def create_group(self, name, description=None):
        pass

    def modify_user(self, object_id, modifications):
        pass

    def modify_group(self, object_id, modifications):
        pass

    def delete_user(self, object_id):
        pass

    def delete_group(self, object_id):
        pass

    def member_of_groups(self, object_id, resource_collection="users"):
        pass

    def member_of_objects(self, object_id, resource_collection="users"):
        pass

    def resolve_object_ids(self, object_ids, object_types=None):
        pass

    def get_groups_direct_members(self, group_id):
        pass

    def add_objects_to_azure_group(self, group_id, object_ids):
        pass

    def delete_group_member(self, group_id, member_id):
        pass

    def add_license(self, user_id, sku_id, deactivate_plans=None):
        pass

    def remove_license(self, user_id, sku_id):
        pass

    def list_subscriptions(self, object_id=None, ofilter=None):
        pass

    def get_enabled_subscriptions(self):
        pass

    def list_domains(self, domain_name=None):
        pass

    def list_adconnection_details(self):
        pass

    def list_verified_domains(self):
        pass

    def get_verified_domain_from_disk(self):
        pass

    def deactivate_user(self, object_id, rename=False):
        pass

    def deactivate_group(self, object_id):
        pass

    def directory_object_urls_to_object_ids(self, urls):
        pass

    def create_random_pw():
        pass

