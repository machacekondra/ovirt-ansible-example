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


DOCUMENTATION = '''
---
module: ovirt_snapshots
short_description: "Module to create/delete/manage Virtual Machine Snapshots in oVirt"
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to create/delete/manage Virtual Machine Snapshots in oVirt"
options:
    snapshot_id:
        description:
            - "ID of the snapshot to manage."
    vm_name:
        description:
            - "Name of the Virtual Machine to manage."
        required: true
    state:
        description:
            - "Should the Virtual Machine snapshot be inpreview/present/absent."
        choices: ['inpreview', 'present', 'absent']
        default: present
    description:
        description:
            - "Description of the snapshot."
'''


EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create snapshot of the VM
- ovirt_snapshots:
    vm_name: rhel7
    description: MySnapshot
register: snapshot

# Preview snapshot of the VM
- ovirt_snapshots:
    state: inpreview
    vm_name: rhel7
    snapshot_id: "{{ snapshot.id }}"

# Undo snapshot of the VM
# In case snapshot is in preview state,
# state=absent will run undo operation
- ovirt_snapshots:
    state: absent
    vm_name: rhel7
    snapshot_id: "{{ snapshot.id }}"

# Remove snapshot of the VM
- ovirt_snapshots:
    state: absent
    vm_name: rhel7
    snapshot_id: "{{ snapshot.id }}"
'''


def create_snapshot(module, vm_service, snapshots_service):
    changed = False
    # Get the snapshot:
    snapshot =  snapshots_service.snapshot_service(module.params['snapshot_id']).get()

    # If snapshot exists, check if it should be updated:
    if snapshot:
        if snapshot.snapshot_status != otypes.SnapshotStatus.IN_PREVIEW:
            if not module.check_mode:
                vm_service.commit_snapshot()
            changed = True
    else:
        # Create snapshot of VM:
        if not module.check_mode:
            snapshot = snapshots_service.add(
                otypes.Snapshot(
                    description=module.params.get('description'),
                )
            )
        changed = True

    # Wait for the snapshot to be created:
    if changed:
        wait(
            snapshots_service.snapshot_service(snapshot.id),
            lambda snapshot: snapshot.snapshot_status == otypes.SnapshotStatus.OK,
        )
    return {
        'changed': changed,
        'id': snapshot.id,
        'snapshot': get_dict_of_struct(snapshot),
    }


def remove_snapshot(module, vm_service, snapshots_service):
    changed = False
    # Get the snapshot:
    snapshot = snapshots_service.snapshot_service(module.params['snapshot_id']).get()

    # If snapshot exists, remove it:
    if snapshot:
        snapshot_service = snapshots_service.snapshot_service(snapshot.id)
        if snapshot.snapshot_status == otypes.SnapshotStatus.IN_PREVIEW:
            if not module.check_mode:
                vm_service.undo_snapshot()
            changed = True
            wait(
                snapshots_service.snapshot_service(snapshot.id),
                lambda snapshot: snapshot.snapshot_status == otypes.SnapshotStatus.OK,
            )
        else:
            if not module.check_mode:
                snapshot_service.remove()
            changed = True
            wait(
                snapshots_service.snapshot_service(snapshot.id),
                lambda snapshot: snapshot is None,
            )


    return {
        'changed': changed,
        'id': snapshot.id if snapshot else None,
        'snapshot': get_dict_of_struct(snapshot),
    }


def preview_snapshot(module, vm_service, snapshots_service):
    changed = False
    # Get the snapshot:
    snapshot = snapshots_service.snapshot_service(module.params['snapshot_id']).get()

    if snapshot is None:
        # Create snapshot:
        if not module.check_mode:
            snapshot = create_snapshot(module, snapshots_service)
        changed = True

    if snapshot.snapshot_status != otypes.SnapshotStatus.IN_PREVIEW:
        if not module.check_mode:
            vm_service.preview_snapshot(
                snapshot=otypes.Snapshot(id=snapshot.id),
                restore_memory=None,
                disks=None,
            )
        changed = True

    # Wait for the disk to be detached:
    if changed:
        wait(
            snapshots_service.snapshot_service(snapshot.id),
            lambda snapshot: snapshot.snapshot_status == otypes.SnapshotStatus.IN_PREVIEW,
        )
    return {
        'changed': changed,
        'id': snapshot.id if snapshot else None,
        'snapshot': get_dict_of_struct(snapshot),
    }


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['inpreview', 'present', 'absent'],
            default='present',
        ),
        vm_name=dict(required=True),
        snapshot_id=dict(default=None),
        description=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'absent', ['snapshot_id']),
            ('state', 'inpreview', ['snapshot_id']),
        ]
    )
    check_sdk(module)

    vm_name = module.params.get('vm_name')
    connection = create_connection(module.params.pop('auth'))
    vms_service = connection.system_service().vms_service()
    vm = search_by_name(vms_service, vm_name)
    if not vm:
        module.exit_json(
            changed=False,
            msg="Vm '{name}' doesn't exist.".format(name=vm_name),
        )

    vm_service = vms_service.vm_service(vm.id)
    snapshots_service = vms_service.vm_service(vm.id).snapshots_service()
    try:
        state = module.params['state']
        if state == 'present':
            ret = create_snapshot(module, vm_service, snapshots_service)
        elif state == 'inpreview':
            ret = preview_snapshot(module, vm_service, snapshots_service)
        elif state == 'absent':
            ret = remove_snapshot(module, vm_service, snapshots_service)
        module.exit_json(**ret)
    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        # Close the connection to the server, don't revoke token:
        connection.close(logout=False)


from ansible.module_utils.basic import *
from ansible.module_utils.ovirt import *
if __name__ == "__main__":
    main()
