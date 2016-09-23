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
module: ovirt_datacenters
short_description: Module to manage data centers in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage data centers in oVirt"
options:
    name:
        description:
            - "Name of the the data center to manage."
        required: true
    state:
        description:
            - "Should the data center be present or absent"
        choices: ['present', 'absent']
        default: present
    description:
        description:
            - "Description of the data center."
    comment:
        description:
            - "Comment of the data center."
    local:
        description:
            - "I(True) if the data center should be local, I(False) if should be shared."
            - "Default value is set by engine."
    compatibility_version:
        description:
            - "Compatibility version of the data center."
    quota_mode:
        description:
            - "Quota mode of the data center. One of I(disabled), I(audit) or I(enabled)"
        choices: ['disabled', 'audit', 'enabled']
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

# Create datacenter
- ovirt_datacenters:
    name: mydatacenter
    local: True
    compatibility_version: 4.1
    quota_mode: enabled

# Remove datacenter
- ovirt_datacenters:
    state: absent
    name: mydatacenter
'''

class DatacentersModule(BaseModule):

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
        return otypes.DataCenter(
            name=self._module.params['name'],
            comment=self._module.params['comment'],
            description=self._module.params['description'],
            quota_mode=otypes.QuotaModeType(
                self._module.params['quota_mode']
            ) if self._module.params['quota_mode'] else None,
            local=self._module.params['local'],
            version=otypes.Version(
                major=self.__get_major(self._module.params['compatibility_version']),
                minor=self.__get_minor(self._module.params['compatibility_version']),
            ) if self._module.params['compatibility_version'] else None,
        )

    def update_check(self, entity):
        return (
            equal(self._module.params.get('comment'), entity.comment) and
            equal(self._module.params.get('description'), entity.description) and
            equal(self._module.params.get('quota_mode'), str(entity.quota_mode)) and
            equal(self._module.params.get('local'), entity.local) and
            equal(self.__get_minor(self._module.params.get('compatibility_version')), self.__get_minor(entity.version)) and
            equal(self.__get_major(self._module.params.get('compatibility_version')), self.__get_major(entity.version))
        )


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        name=dict(default=None),
        description=dict(default=None),
        local=dict(type='bool'),
        compatibility_version=dict(default=None),
        quota_mode=dict(choices=['disabled', 'audit', 'enabled']),
        comment=dict(default=None),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        # Create connection to engine and data centers service:
        connection = create_connection(module.params.pop('auth'))
        data_centers_service = connection.system_service().data_centers_service()
        clusters_module = DatacentersModule(
            connection=connection,
            module=module,
            service=data_centers_service,
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
