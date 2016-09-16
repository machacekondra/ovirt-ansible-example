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
module: ovirt_groups
short_description: Module to manage groups in oVirt/RHV
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage groups in oVirt/RHV"
options:
    name:
        description:
            - "Name of the the group to manage."
        required: true
    state:
        description:
            - "Should the group be present/absent."
        choices: ['present', 'absent']
        default: present
    authz_name:
        description:
            - "Authorization provider of the group. Previously known as domain."
        required: true
    namespace:
        description:
            - "Namespace of the authorization provider, where group resides."
        required: false
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add group group1 from authorization provider example.com-authz
ovirt_groups:
    name: group1
    domain: example.com-authz

# Add group group1 from authorization provider example.com-authz
# In case of multi-domain Active Directory setup, you should pass
# also namespace, so it adds correct group:
ovirt_groups:
    name: group1
    namespace: dc=ad2,dc=example,dc=com
    domain: example.com-authz

# Remove group group1 with authorization provider example.com-authz
ovirt_groups:
    state: absent
    name: group1
    domain: example.com-authz
'''


class GroupsModule(BaseModule):

    def build_entity(self):
        return otypes.Group(
            domain=otypes.Domain(
                name=self._module.params['authz_name']
            ),
            name=self._module.params['name'],
            namespace=self._module.params['namespace'],
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        name=dict(required=True),
        authz_name=dict(required=True),
        namespace=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        connection = create_connection(module.params.pop('auth'))
        groups_service = connection.system_service().groups_service()
        groups_module = GroupsModule(
            connection=connection,
            module=module,
            service=groups_service,
        )

        group = None
        if 'id' in module.params:
            group = search_by_name(
                service=groups_service,
                name=module.params['name'],
                namespace=module.params['namespace'],
            )

        state = module.params['state']
        if state == 'present':
            # Passing `search_params` along with entity is hack here,
            # because it's not possible to find group by it's namespace,
            # and if group is not found by `search_by_name` method, by
            # filtering object attributes, it should be found even,
            # byt `create` method, that's why we need to pass everything
            # here and not empty `search_params` otherwise only `name`
            # would be used. In future if oVirt backend will support search
            # by namespace, we can remove it:
            ret = groups_module.create(
                entity=group,
                search_params={
                    'name': module.params['name'],
                    'namespace': module.params['namespace'],
                }
            )
        elif state == 'absent':
            ret = groups_module.remove(
                entity=group,
                search_params={
                    'name': module.params['name'],
                    'namespace': module.params['namespace'],
                }
            )

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
