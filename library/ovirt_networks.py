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
module: ovirt_networks
short_description: Module to create/delete networks in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to create/delete networks in oVirt"
options:
    name:
        description:
            - "Name of the the network to manage."
        required: true
    state:
        description:
            - "Should the network be present or absent"
        choices: ['present', 'absent']
        default: present
    datacenter_name:
        description:
            - "Datacenter name where network reside."
    description:
        description:
            - "Description of the network."
    comment:
        description:
            - "Comment of the network."
    vlan_tag:
        description:
            - "Specify VLAN tag."
    vm_network:
        description:
            - "If I(True) network will be marked as network for VM."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create network
- ovirt_networks:
    auth: "{{ ovirt_auth }}"
    datacenter_name: mydatacenter
    name: mynetwork
    vlan_tag: 1
    vm_network: true

# Remove network
- ovirt_networks:
    state: absent
    name: mynetwork
'''

class NetworksModule(BaseModule):

    def build_entity(self):
        return otypes.Network(
            name=self._module.params['name'],
            comment=self._module.params['comment'],
            description=self._module.params['description'],
            data_center=otypes.DataCenter(
                name=self._module.params['datacenter_name'],
            ) if self._module.params['datacenter_name'] else None,
            vlan=otypes.Vlan(
                self._module.params['vlan_tag'],
            ) if self._module.params['vlan_tag'] else None,
            usages=(
                ['vm'] if self._module.params['vm_network'] else ['']
            ) if self._module.params['vm_network'] is not None else None,
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('comment'), entity.comment) and
            equal(self._module.params.get('description'), entity.description) and
            equal(self._module.params.get('vlan_tag'), getattr(entity.vlan, 'id', None)) and
            equal(self._module.params.get('vm_network'), True if entity.usages else False)
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        datacenter_name=dict(default=None),
        name=dict(default=None),
        description=dict(default=None),
        comment=dict(default=None),
        vlan_tag=dict(default=None, type='int'),
        vm_network=dict(default=None, type='bool'),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        connection = create_connection(module.params.pop('auth'))
        networks_service = connection.system_service().networks_service()
        networks_module = NetworksModule(
            connection=connection,
            module=module,
            service=networks_service,
        )
        state = module.params['state']
        if state == 'present':
            ret = networks_module.create(
                search_params={
                    'name': module.params['name'],
                    'datacenter': module.params['datacenter_name'],
                }
            )
        elif state == 'absent':
            ret = networks_module.remove(
                search_params={
                    'name': module.params['name'],
                    'datacenter': module.params['datacenter_name'],
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
