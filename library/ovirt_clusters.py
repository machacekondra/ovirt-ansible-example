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
module: ovirt_clusters
short_description: Module to manage clusters in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage clusters in oVirt"
options:
    id:
        description:
            - "ID of the the cluster to manage."
            - "Name or ID is required."
    name:
        description:
            - "Name of the the cluster to manage."
            - "Name or ID is required."
    state:
        description:
            - "Should the cluster be present or absent"
        choices: ['present', 'absent']
        default: present
    datacenter_name:
        description:
            - "Data center name where cluster reside."
    description:
        description:
            - "Description of the cluster."
    comment:
        description:
            - "Comment of the cluster."
    network:
        description:
            - "Network of cluster."
    cpu_arch:
        description:
            - "CPU architecture of cluster."
    cpu_type:
        description:
            - "CPU type of cluster."
    switch_type:
        description:
            - "Type of the switch of the network of cluster."
    compatibility_version:
        description:
            - "Compatibility version of the cluster."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create cluster
- ovirt_clusters:
    datacenter_name: mydatacenter
    name: mycluster
    cpu_type: Intel SandyBridge Family
    description: mycluster
    compatibility_version: 4.0

# Remove cluster
- ovirt_clusters:
    state: absent
    name: mycluster
'''

class ClustersModule(BaseModule):

    def __get_major(self, full_version):
        if full_version is None:
            return None
        if isinstance(full_version, otypes.Version):
            return full_version.major
        return int(full_version.split('.')[0])

    def __get_minor(self, full_version):
        if full_version is None:
            return None
        if isinstance(full_version, otypes.Version):
            return full_version.minor
        return int(full_version.split('.')[1])

    def build_entity(self):
        return otypes.Cluster(
            name=self._module.params['name'],
            comment=self._module.params['comment'],
            description=self._module.params['description'],
            data_center=otypes.DataCenter(
                name=self._module.params['datacenter_name'],
            ) if self._module.params['datacenter_name'] else None,
            management_network=otypes.Network(
                name=self._module.params['network'],
            ) if self._module.params['network'] else None,
            cpu=otypes.Cpu(
                architecture=self._module.params['cpu_arch'],
                type=self._module.params['cpu_type'],
            ) if (
                self._module.params['cpu_arch'] or self._module.params['cpu_type']
            ) else None,
            version=otypes.Version(
                major=self.__get_major(self._module.params['compatibility_version']),
                minor=self.__get_minor(self._module.params['compatibility_version']),
            ) if self._module.params['compatibility_version'] else None,
            switch_type=otypes.SwitchType(
                self._module.params['switch_type']
            ) if self._module.params['switch_type'] else None,
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('comment'), entity.comment) and
            equal(self._module.params.get('description'), entity.description) and
            equal(self._module.params.get('switch_type'), str(entity.switch_type)) and
            equal(self._module.params.get('cpu_arch'), str(entity.cpu.architecture)) and
            equal(self._module.params.get('cpu_type'), entity.cpu.type) and
            equal(self.__get_minor(self._module.params.get('compatibility_version')), self.__get_minor(entity.version)) and
            equal(self.__get_major(self._module.params.get('compatibility_version')), self.__get_major(entity.version))
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
        network=dict(default=None),
        cpu_arch=dict(default=None),
        cpu_type=dict(default=None),
        switch_type=dict(default=None),
        compatibility_version=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    check_sdk(module)
    check_params(module)

    try:
        # Create connection to engine and clusters service:
        connection = create_connection(module.params.pop('auth'))
        clusters_service = connection.system_service().clusters_service()
        clusters_module = ClustersModule(
            connection=connection,
            module=module,
            service=clusters_service,
        )

        state = module.params['state']
        if state == 'present':
            ret = clusters_module.create()
        elif state == 'absent':
            ret = clusters_module.remove()

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
