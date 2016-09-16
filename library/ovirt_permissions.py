#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


try:
    import ovirtsdk4 as sdk
    import ovirtsdk4.types as otypes
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

from ovirtansible.ovirt import *


DOCUMENTATION = '''
---
module: ovirt_permissions
short_description: "Module to manage permissions of users/groups in oVirt"
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage permissions of users/groups in oVirt"
options:
    role:
        description:
            - "Name of the the role to be assigned to user/group."
        required: true
        default: UserRole
    state:
        description:
            - "Should the permission be present/absent."
        choices: ['present', 'absent']
        default: present
    object_id:
        description:
            - "ID of the object where the permissions should be managed."
        required: true
    object_name:
        description:
            - "Name of the object where the permissions should be managed."
        required: true
    object_type:
        description:
            - "The object where the permissions should be managed."
        required: true
        default: 'virtual_machine'
        choices: [
            'data_center',
            'cluster',
            'host',
            'storage',
            'network',
            'disk',
            'virtual_machine',
            'vm_pool',
            'template',
        ]
    user_name:
        description:
            - "Name of the the user to manage. In most LDAPs it's uid of the user, but in Active Directory you must specify UPN of the user."
    group_name:
        description:
            - "Name of the the group to manage."
    authz_name:
        description:
            - "Authorization provider of the user. Previously known as domain."
        required: true
    namespace:
        description:
            - "Namespace of the authorization provider, where user/group resides."
        required: false
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add user user1 from authorization provider example.com-authz
- ovirt_permissions:
    user_name: user1
    authz_name: example.com-authz
    object_type: virtual_machine
    object_name: myvm
    role: UserVmManager

# Remove permission from user
- ovirt_permissions:
    state: absent
    user_name: user1
    authz_name: example.com-authz
    object_type: cluster
    object_name: mycluster
    role: ClusterAdmin
'''


def __get_objects_service(connection, module):
    system_service = connection.system_service()
    return {
        'data_center': system_service.data_centers_service(),
        'cluster': system_service.clusters_service(),
        'host': system_service.hosts_service(),
        'storage': system_service.storage_domains_service(),
        'network': system_service.networks_service(),
        'disk': system_service.disks_service(),
        'virtual_machine': system_service.vms_service(),
        'vm_pool': system_service.vm_pools_service(),
        'template': system_service.templates_service(),
    }.get(module.params['object_type'], None)


def __get_object_service(connection, module):
    objects_service = __get_objects_service(connection, module)
    object_id = module.params['object_id']
    if object_id is None:
        object_id = getattr(search_by_name(objects_service, module.params['object_name']), 'id', None)

    object_type = module.params['object_type']
    if object_type == 'data_center':
        return objects_service.data_center_service(object_id)
    elif object_type == 'cluster':
        return objects_service.cluster_service(object_id)
    elif object_type == 'host':
        return objects_service.host_service(object_id)
    elif object_type == 'storage':
        return objects_service.storage_domain_service(object_id)
    elif object_type == 'network':
        return objects_service.network_service(object_id)
    elif object_type == 'disk':
        return objects_service.disk_service(object_id)
    elif object_type == 'virtual_machine':
        return objects_service.vm_service(object_id)
    elif object_type == 'vm_pool':
        return objects_service.vm_pool_service(object_id)
    elif object_type == 'template':
        return objects_service.template_service(object_id)
    return None


def __get_user(module, users_service):
    users = users_service.list(
        search="usrname={name}@{authz_name}".format(
            name=module.params['user_name'],
            authz_name=module.params['authz_name'],
        )
    ) or [None]

    return users[0]


def __get_group(module, groups_service):
    groups = groups_service.list(
        search="name={name}".format(
            name=module.params['group_name'],
        )
    )

    # If found more groups, filter them by namespace and authz name:
    if len(groups) > 1:
        groups = [
            g for g in groups if (
                equal(module.params['namespace'], g.namespace) and
                equal(module.params['authz_name'], g.domain.name)
            )
        ] or [None]
    return groups[0]


def __get_permission(module, permissions_service, connection):
    for permission in permissions_service.list():
        user = follow_link(connection, permission.user)
        if (
            equal(module.params['user_name'], user.principal if user else None) and
            equal(module.params['group_name'], get_link_name(connection, permission.group)) and
            equal(module.params['role'], get_link_name(connection, permission.role))
        ):
            # The permission was found:
            return permission
    return None


class PermissionsModule(BaseModule):

    def build_entity(self):
        if self._module.params['group_name'] is not None:
            entity = __get_group(self._module, self._connection.system_service().groups_service())
        else:
            entity = __get_user(self._module, self._connection.system_service().users_service())

        return otypes.Permission(
            user=otypes.User(
                id=entity.id
            ) if self._module.params['user_name'] else None,
            group=otypes.Group(
                id=entity.id
            ) if self._module.params['group_name'] else None,
            role=otypes.Role(
                name=self._module.params['role']
            ),
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        role=dict(default='UserRole'),
        object_type=dict(
            default='virtual_machine',
            choices=[
                'data_center',
                'cluster',
                'host',
                'storage',
                'network',
                'disk',
                'virtual_machine',
                'vm_pool',
                'template',
            ]
        ),
        authz_name=dict(required=True),
        object_id=dict(default=None),
        object_name=dict(default=None),
        user_name=dict(rdefault=None),
        group_name=dict(default=None),
        namespace=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    if module.params['object_name'] is None and module.params['object_id'] is None:
        module.fail_json(msg='"object_name" or "object_id" is required')

    if module.params['user_name'] is None and module.params['group_name'] is None:
        module.fail_json(msg='"user_name" or "group_name" is required')

    try:
        # Create connection to engine and clusters service:
        connection = create_connection(module.params.pop('auth'))
        permissions_service = __get_object_service(connection, module).permissions_service()

        permissions_module = PermissionsModule(
            connection=connection,
            module=module,
            service=permissions_service,
        )

        permission = __get_permission(module, permissions_service, connection)
        state = module.params['state']
        if state == 'present':
            ret = permissions_module.create(entity=permission)
        elif state == 'absent':
            ret = permissions_module.remove(entity=permission)

        module.exit_json(**ret)
    except sdk.Error as e:
        # sdk.Error returns descriptive error message, just pass it to ansible
        module.fail_json(msg=str(e))
    finally:
        # Close the connection to the server, don't revoke token:
        connection.close(logout=False)

from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()