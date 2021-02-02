from abc import ABC

class Base(ABC):
    """
    This abstract base class lists all functions required by udm.
    """

    def list_users(self, objectid=None, ofilter=None):
        super(APIBase, self).list_users(self, objectid, ofilter)
        pass

    def get_users_direct_groups(self, user_id):
        super(APIBase, self).get_users_direct_groups(self, user_id)
        pass

    def list_groups(self, objectid=None, ofilter=None):
        super(APIBase, self).list_groups(self, objectid, ofilter)
        pass

    def invalidate_all_tokens_for_user(self, user_id):
        super(APIBase, self).invalidate_all_tokens_for_user(self, user_id)
        pass

    def reset_user_password(self, user_id):
        super(APIBase, self).reset_user_password(self, user_id)
        pass

    def create_user(self, attributes):
        super(APIBase, self).create_user(self, attributes)
        pass

    def create_group(self, name, description=None):
        super(APIBase, self).create_group(self, name, description)
        pass

    def modify_user(self, object_id, modifications):
        super(APIBase, self).modify_user(self, object_id, modifications)
        pass

    def modify_group(self, object_id, modifications):
        super(APIBase, self).modify_group(self, object_id, modifications)
        pass

    def delete_user(self, object_id):
        super(APIBase, self).delete_user(self, object_id)
        pass

    def delete_group(self, object_id):
        super(APIBase, self).delete_group(self, object_id)
        pass

    def member_of_groups(self, object_id, resource_collection="users"):
        super(APIBase, self).member_of_groups(self, object_id, resource_collection)
        pass

    def member_of_objects(self, object_id, resource_collection="users"):
        super(APIBase, self).member_of_objects(self, object_id, resource_collection)
        pass

    def resolve_object_ids(self, object_ids, object_types=None):
        super(APIBase, self).resolve_object_ids(self, object_ids, object_types)
        pass

    def get_groups_direct_members(self, group_id):
        super(APIBase, self).get_groups_direct_members(self, group_id)
        pass

    def add_objects_to_azure_group(self, group_id, object_ids):
        super(APIBase, self).add_objects_to_azure_group(self, group_id, object_ids)
        pass

    def delete_group_member(self, group_id, member_id):
        super(APIBase, self).delete_group_member(self, group_id, member_id)
        pass

    def add_license(self, user_id, sku_id, deactivate_plans=None):
        super(APIBase, self).add_license(self, user_id, sku_id, deactivate_plans)
        pass

    def remove_license(self, user_id, sku_id):
        super(APIBase, self).remove_license(self, user_id, sku_id)
        pass

    def list_subscriptions(self, object_id=None, ofilter=None):
        super(APIBase, self).list_subscriptions(self, object_id, ofilter)
        pass

    def get_enabled_subscriptions(self):
        super(APIBase, self).get_enabled_subscriptions(self)
        pass

    def list_domains(self, domain_name=None):
        super(APIBase, self).list_domains(self, domain_name)
        pass

    def list_adconnection_details(self):
        super(APIBase, self).list_adconnection_details(self)
        pass

    def list_verified_domains(self):
        super(APIBase, self).list_verified_domains(self)
        pass

    def get_verified_domain_from_disk(self):
        super(APIBase, self).get_verified_domain_from_disk(self)
        pass

    def deactivate_user(self, object_id, rename=False):
        super(APIBase, self).deactivate_user(self, object_id, rename)
        pass

    def deactivate_group(self, object_id):
        super(APIBase, self).deactivate_group(self, object_id)
        pass

    def directory_object_urls_to_object_ids(self, urls):
        super(APIBase, self).directory_object_urls_to_object_ids(self, urls)
        pass

    def create_random_pw():
        super(APIBase, self).create_random_pw()
        pass

