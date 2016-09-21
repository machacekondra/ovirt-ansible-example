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
module: ovirt_hosts
short_description: Module to create/delete/manage hosts in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to create/delete/manage hosts in oVirt"
options:
    name:
        description:
            - "Name of the the host to manage."
        required: true
    state:
        description:
            - "Should the host be present/absent/maintenance/upgraded"
        choices: ['present', 'absent', 'maintenance', 'upgraded']
        default: present
    comment:
        description:
            - "Description of the host."
    cluster:
        description:
            - "Name of the cluster, where host should be created."
    address:
        description:
            - "Host address. Can be IP address or FQDN."
    password:
        description:
            - "Password of the root. It's required in case C(public_key) is set to I(False)."
    public_key:
        description:
            - "I(True) if the public key should be used to authenticate to host."
            - "It's required in case C(password) is not set."
        default: False
        aliases: ['ssh_public_key']
    kdump_integration:
        description:
            - "Specify if host will have enabled Kdump integration."
        choices: ['enabled', 'disabled']
        default: enabled
    spm_priority:
        description:
            - "SPM priority of the host. Integer value from 1 to 10, where higher number means higher priority."
    override_iptables:
        description:
            - "If True host iptables will be overridden by host deploy script."
    force:
        description:
            - "If True host will be forcibly moved to desired state."
        default: False
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Add host with username/password
- ovirt_hosts:
    cluster: Default
    name: myhost
    address: 10.34.61.145
    password: secret

# Add host using public key
- ovirt_hosts:
    public_key: true
    cluster: Default
    name: myhost2
    address: 10.34.61.145

# Maintenance
- ovirt_hosts:
    state: maintenance
    name: myhost

# Upgrade host
- ovirt_hosts:
    state: upgraded
    name: myhost

# Remove host
- ovirt_hosts:
    state: absent
    name: myhost
    force: True
'''


class HostsModule(BaseModule):

    def build_entity(self):
        return otypes.Host(
            name=self._module.params['name'],
            cluster=otypes.Cluster(
                name=self._module.params['cluster']
            ) if self._module.params['cluster'] else None,
            comment=self._module.params['comment'],
            address=self._module.params['address'],
            root_password=self._module.params['password'],
            ssh=otypes.Ssh(
                authentication_method='publickey',
            ) if self._module.params['public_key'] else None,
            kdump_status=otypes.KdumpStatus(
                self._module.params['kdump_integration']
            ) if self._module.params['kdump_integration'] else None,
            spm=otypes.Spm(
                priority=self._module.params['spm_priority'],
            ) if self._module.params['spm_priority'] else None,
            override_iptables=self._module.params['override_iptables'],
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('comment'), entity.comment) and
            equal(self._module.params.get('kdump_integration'), entity.kdump_status) and
            equal(self._module.params.get('spm_priority'), entity.spm.priority)
        )

    def pre_remove(self, entity):
        self.action(
            entity=entity,
            action='deactivate',
            action_condition=lambda h: h.status != otypes.HostStatus.MAINTENANCE,
            wait_condition=lambda h: h.status == otypes.HostStatus.MAINTENANCE,
        )

    def post_update(self, entity):
        if entity.status != otypes.HostStatus.UP:
            if not self._module.check_mode:
                self._service.host_service(entity.id).activate()
            self.changed = True


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent', 'maintenance', 'upgraded'],
            default='present',
        ),
        name=dict(default=None),
        comment=dict(default=None),
        cluster=dict(default=None),
        address=dict(default=None),
        password=dict(default=None),
        public_key=dict(default=False, type='bool', aliases=['ssh_public_key']),
        kdump_integration=dict(default=None, choices=['enabled', 'disabled']),
        spm_priority=dict(default=None, type='int'),
        override_iptables=dict(default=None, type='bool'),
        force=dict(default=False, type='bool'),
        timeout=dict(default=600, type='int'),
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
        hosts_module = HostsModule(
            connection=connection,
            module=module,
            service=hosts_service,
        )

        state = module.params['state']
        if state == 'present':
            # FIXME: Handle states properly, ( ie. what if host is in maintanence)
            ret = hosts_module.create(result_state=otypes.HostStatus.UP)
        elif state == 'absent':
            ret = hosts_module.remove()
        elif state == 'maintenance':
            ret = hosts_module.action(
                action='deactivate',
                action_condition=lambda h: h.status != otypes.HostStatus.MAINTENANCE,
                wait_condition=lambda h: h.status == otypes.HostStatus.MAINTENANCE,
            )
        elif state == 'upgraded':
            ret = hosts_module.action(
                action='upgrade',
                action_condition=lambda h: h.update_available,
                wait_condition=lambda h: h.status == otypes.HostStatus.UP,
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
