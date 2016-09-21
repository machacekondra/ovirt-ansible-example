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
module: ovirt_nics
short_description: Module to manage network interfaces of Virtual Machines in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage network interfaces of Virtual Machines in oVirt"
options:
    name:
        description:
            - "Name of the network interface to manage."
        required: true
    vm_name:
        description:
            - "Name of the Virtual Machine to manage."
        required: true
    state:
        description:
            - "Should the Virtual Machine NIC be present/absent/plugged/unplugged."
        choices: ['present', 'absent', 'plugged', 'unplugged']
        default: present
    profile:
        description:
            - "Virtual network interface profile to be attached to VM network interface,
               by default Empty network is used if profile is not specified."
    interface:
        description:
            - "Type of the network interface."
        choices: ['virtio', 'e1000', 'rtl8139', 'pci_passthrough', 'rtl8139_virtio', 'spapr_vlan']
        default: 'virtio'
    mac_address:
        description:
            - "Custom MAC address of the network interface, by default it's obtained from MAC pool."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add NIC to VM
- ovirt_nics:
    state: present
    vm_name: myvm
    name: mynic
    interface: e1000
    mac_address: 00:1a:4a:16:01:56
    profile: ovirtmgmt

# Plug NIC to VM
- ovirt_nics:
    auth: "{{ ovirt_auth }}"
    state: plugged
    vm_name: myvm
    name: mynic

# Unplug NIC from VM
- ovirt_nics:
    auth: "{{ ovirt_auth }}"
    state: unplugged
    vm_name: myvm
    name: mynic

# Remove NIC from VM
- ovirt_nics:
    state: absent
    vm_name: myvm
    name: mynic
'''


class VmNicsModule(BaseModule):

    def build_entity(self):
        profile = self._module.params.get('profile')
        return otypes.Nic(
            name=self._module.params.get('name'),
            interface=otypes.NicInterface(
                self._module.params.get('interface')
            ) if self._module.params.get('interface') else None,
            vnic_profile=otypes.VnicProfile(
                id=search_by_name(
                    self._connection.system_service().vnic_profiles_service(),
                    profile,
                ).id
            ) if profile else None,
            mac=otypes.Mac(
                address=self._module.params.get('mac_address')
            ) if self._module.params.get('mac_address') else None,
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('interface'), str(entity.interface)) and
            equal(self._module.params.get('profile'), get_link_name(self._connection, entity.vnic_profile)) and
            equal(self._module.params.get('mac_address'), entity.mac.address)
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent', 'plugged', 'unplugged'],
            default='present'
        ),
        vm_name=dict(required=True),
        name=dict(required=True),
        interface=dict(default=None),
        profile=dict(default=None),
        mac_address=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        # Locate the service that manages the virtual machines and use it to
        # search for the NIC:
        connection = create_connection(module.params.pop('auth'))
        vms_service = connection.system_service().vms_service()

        # Locate the VM, where we will manage NICs:
        vm_name = module.params.get('vm_name')
        vm = search_by_name(vms_service, vm_name)

        # Locate the service that manages the virtual machines NICs:
        nics_service = vms_service.vm_service(vm.id).nics_service()
        vmnics_module = VmNicsModule(
            connection=connection,
            module=module,
            service=nics_service,
        )

        # Handle appropriate action:
        state = module.params['state']
        if state == 'present':
            ret = vmnics_module.create()
        elif state == 'absent':
            ret = vmnics_module.remove()
        elif state == 'plugged':
            vmnics_module.create()
            ret = vmnics_module.action(
                action='activate',
                action_condition=lambda nic: not nic.plugged,
                wait_condition=lambda nic: nic.plugged,
            )
        elif state == 'unplugged':
            vmnics_module.create()
            ret = vmnics_module.action(
                action='deactivate',
                action_condition=lambda nic: nic.plugged,
                wait_condition=lambda nic: not nic.plugged,
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
