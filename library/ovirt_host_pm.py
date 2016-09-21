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

from ansible.module_utils.ovirt import *


DOCUMENTATION = '''
---
module: ovirt_host_pm
short_description: Module to manage power management of hosts in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage power management of hosts in oVirt."
options:
    name:
        description:
            - "Name of the the host to manage."
        required: true
        aliases: ['host']
    state:
        description:
            - "Should the host be present/absent/started/stopped/restarted"
        choices: ['present', 'absent', 'started', 'stopped', 'restarted']
        default: present
    address:
        description:
            - "Address of the power management interface."
    username:
        description:
            - "Username to be used to connect to power management interface."
    password:
        description:
            - "Password of the user specified in C(username) parameter."
    type:
        description:
            - "Type of the power management. oVirt predefined values are I(drac5), I(ilo), I(ipmilan), I(rsa),
               I(bladecenter), I(alom), I(apc), I(eps), I(wti), I(rsb), but user can have defined custom type."
    port:
        description:
            - "Power management interface port."
    slot:
        description:
            - "Power management slot."
    options:
        description:
            - "Dictionary of additional fence agent options."
            - "Additional information about options can be found at U(https://fedorahosted.org/cluster/wiki/FenceArguments)."
    encrypt_options:
        description:
            - "If (true) options will be encrypted when send to agent."
        aliases: ['encrypt']
    order:
        description:
            - "Integer value specifying, by default it's added at the end."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add fence agent to host 'myhost'
- ovirt_host_pm:
    name: myhost
    address: 1.2.3.4
    options:
      myoption1: x
      myoption2: y
    username: admin
    password: admin
    port: 3333
    type: ipmilan

# Remove ipmilan fence agent with address 1.2.3.4 on host 'myhost'
- ovirt_host_pm:
    state: absent
    name: myhost
    address: 1.2.3.4
    type: ipmilan
'''


class HostModule(BaseModule):
    def build_entity(self):
        return otypes.Host(
            power_management=otypes.PowerManagement(
                enabled=True,
            ),
        )

    def update_check(self, entity):
        return equal(True, entity.power_management.enabled)


class HostPmModule(BaseModule):

    def build_entity(self):
        return otypes.Agent(
            address=self._module.params['address'],
            encrypt_options=self._module.params['encrypt_options'],
            options=[
                otypes.Option(
                    name=name,
                    value=value,
                ) for name, value in self._module.params['options'].items()
            ] if self._module.params['options'] else None,
            password=self._module.params['password'],
            port=self._module.params['port'],
            type=self._module.params['type'],
            username=self._module.params['username'],
            order=self._module.params.get('order', 100),
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('address'), entity.address) and
            equal(self._module.params.get('encrypt_options'), entity.encrypt_options) and
            equal(self._module.params.get('password'), entity.password) and
            equal(self._module.params.get('username'), entity.username) and
            equal(self._module.params.get('port'), entity.port) and
            equal(self._module.params.get('type'), entity.type)
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent', 'started', 'stopped', 'restarted'],
            default='present',
        ),
        name=dict(default=None, required=True, aliases=['host']),
        address=dict(default=None),
        username=dict(default=None),
        password=dict(default=None),
        type=dict(default=None),
        port=dict(default=None, type='int'),
        slot=dict(default=None),
        options=dict(default=None, type='dict'),
        encrypt_options=dict(default=None, type='bool', aliases=['encrypt']),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        connection = create_connection(module.params.pop('auth'))
        hosts_service = connection.system_service().hosts_service()
        host = search_by_name(hosts_service, module.params['name'])
        fence_agents_service = hosts_service.host_service(host.id).fence_agents_service()

        host_pm_module = HostPmModule(
            connection=connection,
            module=module,
            service=fence_agents_service,
        )
        host_module = HostModule(
            connection=connection,
            module=module,
            service=hosts_service,
        )

        state = module.params['state']
        if state == 'present':
            agent = host_pm_module.search_entity(
                search_params={
                    'address': module.params['address'],
                    'type': module.params['type'],
                }
            )
            ret = host_pm_module.create(entity=agent)
            host_module.create(entity=host)
        elif state == 'absent':
            agent = host_pm_module.search_entity(
                search_params={
                    'address': module.params['address'],
                    'type': module.params['type'],
                }
            )
            ret = host_pm_module.remove(entity=agent)
        elif state == 'started':
            ret = host_module.action(
                action='fence',
                action_condition=lambda h: h.status == otypes.HostStatus.DOWN,
                wait_condition=lambda h: h.status in [otypes.HostStatus.UP, otypes.HostStatus.MAINTENANCE],
                fence_type='start',
            )
        elif state == 'stopped':
            host_module.action(
                action='deactivate',
                action_condition=lambda h: h.status not in [otypes.HostStatus.MAINTENANCE, otypes.HostStatus.DOWN],
                wait_condition=lambda h: h.status == otypes.HostStatus.MAINTENANCE,
            )
            ret = host_module.action(
                action='fence',
                action_condition=lambda h: h.status != otypes.HostStatus.DOWN,
                wait_condition=lambda h: h.status == otypes.HostStatus.DOWN,
                fence_type='stop',
            )
        elif state == 'restarted':
            ret = host_module.action(
                action='fence',
                wait_condition=lambda h: h.status == otypes.HostStatus.UP,
                fence_type='restart',
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
