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
module: ovirt_vmpools
short_description: Module to manage VM pools in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage VM pools in oVirt."
options:
    name:
        description:
            - "Name of the the VM pool to manage."
        required: true
    state:
        description:
            - "Should the VM pool be present/absent"
        choices: ['present', 'absent']
        default: present
    template:
        description:
            - "Name of the template, which will be used to create VM pool."
    description:
        description:
            - "Description of the VM pool."
    cluster:
        description:
            - "Name of the cluster, where VM pool should be created."
    type:
        description:
            - "Type of the VM pool. Either manual or automatic."
            - "C(manual) - The administrator is responsible for explicitly returning the virtual machine to the pool.
               The virtual machine reverts to the original base image after the administrator returns it to the pool."
            - "C(Automatic) - When the virtual machine is shut down, it automatically reverts to its base image and
               is returned to the virtual machine pool."
            - "Default value is set by engine."
        choices: ['manual', 'automatic']
    vm_per_user:
        description:
            - "Maximum number of VMs a single user can attach to from this pool."
            - "Default value is set by engine."
    prestarted:
        description:
            - "Number of pre-started VMs defines the number of VMs in run state, that are waiting
               to be attached to Users."
            - "Default value is set by engine."
    vm_count:
        description:
            - "Number of VMs in the pool."
            - "Default value is set by engine."
    delete_protected:
        description:
            - "If I(True) VM pool will be set as delete protected."
            - "If I(False) VM pool won't be set as delete protected."
            - "If no value is passed, default value is set by oVirt engine."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create VM pool from template
- ovirt_vmpools:
    cluster: mycluster
    name: myvmpool
    template: rhel7
    vm_count: 2
    prestarted: 2
    vm_per_user: 1

# Remove vmpool
- ovirt_vmpools:
    state: absent
    name: myvmpool
    force: true
'''


class VmPoolsModule(BaseModule):

    def build_entity(self):
        return otypes.VmPool(
            name=self._module.params['name'],
            description=self._module.params['description'],
            comment=self._module.params['comment'],
            cluster=otypes.Cluster(
                name=self._module.params['cluster']
            ) if self._module.params['cluster'] else None,
            template=otypes.Template(
                name=self._module.params['template']
            ) if self._module.params['template'] else None,
            max_user_vms=self._module.params['vm_per_user'],
            prestarted_vms=self._module.params['prestarted'],
            size=self._module.params['vm_count'],
            delete_protected=self._module.params['delete_protected'],
            type=otypes.VmPoolType(
                self._module.params['type']
            ) if self._module.params['type'] else None,
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('cluster'), get_link_name(self._connection, entity.cluster)) and
            equal(self._module.params.get('description'), entity.description) and
            equal(self._module.params.get('comment'), entity.comment) and
            equal(self._module.params.get('vm_per_user'), entity.max_user_vms) and
            equal(self._module.params.get('prestarted'), entity.prestarted_vms) and
            equal(self._module.params.get('vm_count'), entity.size) and
            equal(self._module.params.get('delete_protected'), entity.delete_protected)
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        name=dict(default=None),
        template=dict(default=None),
        cluster=dict(default=None),
        description=dict(default=None),
        comment=dict(default=None),
        vm_per_user=dict(default=None, type='int'),
        prestarted=dict(default=None, type='int'),
        vm_count=dict(default=None, type='int'),
        type=dict(default=None, choices=['automatic', 'manual']),
        delete_protected=dict(type='bool'),
        force=dict(type='bool'),
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
        vm_pools_service = connection.system_service().vm_pools_service()
        vm_pools_module = VmPoolsModule(
            connection=connection,
            module=module,
            service=vm_pools_service,
        )

        state = module.params['state']
        if state == 'present':
            ret = vm_pools_module.create()
        elif state == 'absent':
            ret = vm_pools_module.remove()

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
