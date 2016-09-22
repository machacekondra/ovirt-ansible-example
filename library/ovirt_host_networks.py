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
module: ovirt_host_networks
short_description: Module to manage host networks in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage host networks in oVirt"
options:
    name:
        description:
            - "Name of the the host to manage networks."
        required: true
    state:
        description:
            - "Should the host be present/absent"
        choices: ['present', 'absent']
        default: present
    bond:
        description:
            - "Dictionary describing network bond:"
            - "C(name) - Bond name."
            - "C(mode) - Bonding mode."
            - "C(interfaces) - List of interfaces to create a bond."
    interface:
        description:
            - "Name of the network interface where logical network should be attached."
    networks:
        description:
            - "List of dictionary describing networks to be attached to interface or bond:"
            - "C(name) - Name of the logical network to be assigned to bond or interface."
            - "C(boot_protocol) - Boot protocol one of the I(none), I(static) or I(dhcp)."
            - "C(address) - IP address in case of I(static) boot protocol is used."
            - "C(prefix) - Routing prefix in case of I(static) boot protocol is used."
            - "C(version) - IP version. Either v4 or v3."
    labels:
        description:
            - "List of names of the network label to be assigned to bond or interface."
    check:
        description:
            - "If I(true) verify connectivity between host and engine."
            - "If after changing the networks configuration the connectivity from host to the engine
               is lost changes are rolled back."
    save:
        description:
            - "If I(true) network configuration will be persistent, by default they are temporary."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create bond on eth0 and eth1 interface, and put myvlan network on top of it:
- ovirt_host_networks:
    name: myhost
    bond:
      name: bond0
      mode: 2
      interfaces:
        - eth0
        - eth1
    network: myvlan

# Assign network to host interface
- ovirt_host_networks:
    name: myhost
    interface: eth0
    network: ovirtmgmt

# Detach network from host
- ovirt_host_networks:
    state: absent
    name: myhost
    network: myvlan
'''


class HostNetworksModule(BaseModule):

    def build_entity(self):
        return otypes.Host()

    def _action_save_configuration(self, entity):
        if self._module.params['save']:
            if not self._module.check_mode:
                self._service.service(entity.id).commit_net_config()
            self.changed = True


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent', 'maintenance', 'upgraded'],
            default='present',
        ),
        name=dict(default=None, aliases=['host']),
        bond=dict(default=None, type='dict'),
        interface=dict(default=None),
        networks=dict(default=None, type='list'),
        labels=dict(default=None, type='list'),
        check=dict(default=None, type='bool'),
        save=dict(default=None, type='bool'),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        # Create connection to engine and clusters service:
        connection = create_connection(module.params.pop('auth'))
        hosts_service = connection.system_service().hosts_service()
        host_networks_module = HostNetworksModule(
            connection=connection,
            module=module,
            service=hosts_service,
        )

        state = module.params['state']
        if state == 'present':
            bond = module.params['bond']
            networks = module.params['networks']
            interface = module.params['interface']

            ret = host_networks_module.action(
                action='setup_networks',
                post_action=host_networks_module._action_save_configuration,
                check_connectivity=module.params['check'],
                modified_bonds=[
                    otypes.HostNic(
                        name=bond.get('name'),
                        bonding=otypes.Bonding(
                            options=[
                                otypes.Option(
                                    name="mode",
                                    value=str(bond.get('mode')),
                                )
                            ],
                            slaves=[
                                otypes.HostNic(name=i) for i in bond.get('interfaces', [])
                            ],
                        ),
                    ),
                ] if bond else None,
                modified_labels=[
                    otypes.NetworkLabel(
                        name=str(name),
                        host_nic=otypes.HostNic(
                            name=bond.get('name') if bond else interface
                        ),
                    ) for name in module.params['labels']
                ] if module.params['labels'] else None,
                modified_network_attachments=[
                    otypes.NetworkAttachment(
                        network=otypes.Network(
                            name=network['name']
                        ) if network['name'] else None,
                        host_nic=otypes.HostNic(
                            name=bond.get('name') if bond else interface
                        ),
                        ip_address_assignments=[
                            otypes.IpAddressAssignment(
                                assignment_method=otypes.BootProtocol(
                                    network.get('boot_protocol', 'none')
                                ),
                                ip=otypes.Ip(
                                    address=network.get('address'),
                                    gateway=network.get('gateway'),
                                    netmask=network.get('netmask'),
                                    version=otypes.IpVersion(
                                        network.get('version')
                                    ),
                                ),
                            ),
                        ],
                    ) for network in networks
                ] if networks else None,
            )
        elif state == 'absent':
            bond = module.params['bond']
            nic_name = bond.get('name') if bond else module.params['interface']

            host = host_networks_module.search_entity()
            nics_service = hosts_service.host_service(host.id).nics_service()
            nic = search_by_name(nics_service, nic_name)
            attachments = nics_service.nic_service(nic.id).network_attachments_service().list() if nic else []

            ret = host_networks_module.action(
                entity=host,
                action='setup_networks',
                post_action=host_networks_module._action_save_configuration,
                check_connectivity=module.params['check'],
                removed_bonds=[
                    otypes.HostNic(
                        name=bond.get('name'),
                    ),
                ] if bond else None,
                removed_labels=[
                    otypes.NetworkLabel(
                        name=str(name),
                    ) for name in module.params['labels']
                ] if module.params['labels'] else None,
                removed_network_attachments=list(attachments),
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
