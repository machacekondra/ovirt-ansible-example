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
module: ovirt_users
short_description: Module to manage users in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage users in oVirt"
options:
    name:
        description:
            - "Name of the the user to manage. In most LDAPs it's uid of the user, but in Active Directory you must specify UPN of the user."
        required: true
    state:
        description:
            - "Should the user be present/absent."
        choices: ['present', 'absent']
        default: present
    authz_name:
        description:
            - "Authorization provider of the user. Previously known as domain."
        required: true
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add user user1 from authorization provider example.com-authz
ovirt_users:
    name: user1
    domain: example.com-authz

# Add user user1 from authorization provider example.com-authz
# In case of Active Directory specify UPN:
ovirt_users:
    name: user1@ad2.example.com
    domain: example.com-authz

# Remove user user1 with authorization provider example.com-authz
ovirt_users:
    state: absent
    name: user1
    domain: example.com-authz
'''


class UsersModule(BaseModule):

    def build_entity(self):
        return otypes.User(
            domain=otypes.Domain(
                name=self._module.params['authz_name']
            ),
            user_name='{}@{}'.format(
                self._module.params['name'],
                self._module.params['authz_name']
            ),
            principal=self._module.params['name'],
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
        # Create connection to engine and users service:
        connection = create_connection(module.params.pop('auth'))
        users_service = connection.system_service().users_service()
        users_module = UsersModule(
            connection=connection,
            module=module,
            service=users_service,
        )

        state = module.params['state']
        if state == 'present':
            ret = users_module.create(
                search_params={
                    'usrname': '{}@{}'.format(
                        module.params['name'],
                        module.params['authz_name']
                    )
                }
            )
        elif state == 'absent':
            ret = users_module.remove(
                search_params={
                    'usrname': '{}@{}'.format(
                        module.params['name'],
                        module.params['authz_name']
                    )
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
