

class GraphAPI():

    def list_users(self, objectid=None, ofilter=None):
        super(GraphAPI, self).list_users(self, objectid, ofilter)

    def get_users_direct_groups(self, user_id):
        super(GraphAPI, self).get_users_direct_groups(self, user_id)

    def list_groups(self, objectid=None, ofilter=None):
        super(GraphAPI, self).list_groups(self, objectid, ofilter)

    def invalidate_all_tokens_for_user(self, user_id):
        super(GraphAPI, self).invalidate_all_tokens_for_user(self, user_id)

    def reset_user_password(self, user_id):
        super(GraphAPI, self).reset_user_password(self, user_id)

    def create_user(self, attributes):
        super(GraphAPI, self).create_user(self, attributes)

    def create_group(self, name, description=None):
        super(GraphAPI, self).create_group(self, name, description)

    def modify_user(self, object_id, modifications):
        super(GraphAPI, self).modify_user(self, object_id, modifications)

    def modify_group(self, object_id, modifications):
        super(GraphAPI, self).modify_group(self, object_id, modifications)

    def delete_user(self, object_id):
        super(GraphAPI, self).delete_user(self, object_id)

    def delete_group(self, object_id):
        super(GraphAPI, self).delete_group(self, object_id)

    def member_of_groups(self, object_id, resource_collection="users"):
        super(GraphAPI, self).member_of_groups(self, object_id, resource_collection)

    def member_of_objects(self, object_id, resource_collection="users"):
        super(GraphAPI, self).member_of_objects(self, object_id, resource_collection)

    def resolve_object_ids(self, object_ids, object_types=None):
        super(GraphAPI, self).resolve_object_ids(self, object_ids, object_types)

    def get_groups_direct_members(self, group_id):
        super(GraphAPI, self).get_groups_direct_members(self, group_id)

    def add_objects_to_azure_group(self, group_id, object_ids):
        super(GraphAPI, self).add_objects_to_azure_group(self, group_id, object_ids)

    def delete_group_member(self, group_id, member_id):
        super(GraphAPI, self).delete_group_member(self, group_id, member_id)

    def add_license(self, user_id, sku_id, deactivate_plans=None):
        super(GraphAPI, self).add_license(self, user_id, sku_id, deactivate_plans)

    def remove_license(self, user_id, sku_id):
        super(GraphAPI, self).remove_license(self, user_id, sku_id)

    def list_subscriptions(self, object_id=None, ofilter=None):
        super(GraphAPI, self).list_subscriptions(self, object_id, ofilter)

    def get_enabled_subscriptions(self):
        super(GraphAPI, self).get_enabled_subscriptions(self)

    def list_domains(self, domain_name=None):
        super(GraphAPI, self).list_domains(self, domain_name)

    def list_adconnection_details(self):
        super(GraphAPI, self).list_adconnection_details(self)

    def list_verified_domains(self):
        super(GraphAPI, self).list_verified_domains(self)

    def get_verified_domain_from_disk(self):
        super(GraphAPI, self).get_verified_domain_from_disk(self)

    def deactivate_user(self, object_id, rename=False):
        super(GraphAPI, self).deactivate_user(self, object_id, rename)

    def deactivate_group(self, object_id):
        super(GraphAPI, self).deactivate_group(self, object_id)

    def directory_object_urls_to_object_ids(self, urls):
        super(GraphAPI, self).directory_object_urls_to_object_ids(self, urls)

    def create_random_pw():
        super(GraphAPI, self).create_random_pw()

