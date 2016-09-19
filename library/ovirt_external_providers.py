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
module: ovirt_external_providers
short_description: Module to manage external providers in oVirt
version_added: "2.2"
author: "Ondra Machacek (@machacekondra)"
description:
    - "Module to manage external providers in oVirt"
options:
    name:
        description:
            - "Name of the the external provider to manage. Required if C(state) is not I(imported) storage."
    state:
        description:
            - "Should the external be present or absent"
        choices: ['present', 'absent']
        default: present
    description:
        description:
            - "Description of the external provider."
    type:
        description:
            - "Description of the external provider."
        choices: ['os_image', 'os_network', 'os_volume',  'foreman']
    url:
        description:
            - "URL where external provider is hosted."
            - "Applicable for those types: I(os_image), I(os_volume), I(os_network) and I(foreman)."
    username:
        description:
            - "Username to be used for login to external provider."
            - "Applicable for all types."
    password:
        description::
            - "Password of the user specified in C(username) parameter."
            - "Applicable for all types."
    tenant_name:
        description:
            - "Name of the tenant."
            - "Applicable for those types: I(os_image), I(os_volume) and I(os_network)."
        aliases: ['tenant']
    authentication_url:
        description:
            - "Keystone authentication URL of the openstack provider."
            - "Applicable for those types: I(os_image), I(os_volume) and I(os_network)."
        aliases: ['auth_url']
    data_center:
        description:
            - "Name of the data center where provider should be attached."
            - "Applicable for those type: I(os_volume)."
'''

EXAMPLES = '''
# Examples don't contain auth parameter for simplicity,
# look at ovirt_auth module to see how to reuse authentication:

- name: Add image external provider:
  ovirt_external_providers:
    name: image_provider
    type: os_image
    url: http://10.34.63.71:9292
    username: admin
    password: 123456
    tenant: admin
    auth_url: http://10.34.63.71:35357/v2.0/

# Remove image external provider:
- ovirt_external_providers:
    state: absent
    name: image_provider
    type: os_image
'''

class ExternalProviderModule(BaseModule):

    def provider_type(self, provider_type):
        self._provider_type = provider_type

    def build_entity(self):
        provider_type = self._provider_type(
            requires_authentication='username' in self._module.params,
        )
        for key, value in self._module.params.items():
            if hasattr(provider_type, key):
                setattr(provider_type, key, value)

        return provider_type


def get_external_provider_service(provider_type, system_service):
    if provider_type == 'os_image':
        return otypes.OpenStackImageProvider, system_service.openstack_image_providers_service()
    elif provider_type == 'os_network':
        return otypes.OpenStackNetworkProvider, system_service.openstack_network_providers_service()
    elif provider_type == 'os_volume':
        return otypes.OpenStackVolumeProvider, system_service.openstack_volume_providers_service()
    elif provider_type == 'foreman':
        return otypes.ExternalHostProvider, system_service.external_host_providers_service()


def main():
    argument_spec = ovirt_full_argument_spec(
        state=dict(
            choices=['present', 'absent'],
            default='present',
        ),
        name=dict(default=None),
        description=dict(default=None),
        type=dict(
            default=None,
            required=True,
            choices=[
                'os_image', 'os_network', 'os_volume',  'foreman',
            ],
            aliases=['provider'],
        ),
        url=dict(default=None),
        username=dict(default=None),
        password=dict(default=None),
        tenant_name=dict(default=None, aliases=['tenant']),
        authentication_url=dict(default=None, aliases=['auth_url']),
        data_center=dict(default=None, aliases=['data_center']),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='ovirtsdk4 is required for this module')

    try:
        connection = create_connection(module.params.pop('auth'))
        provider_type, external_providers_service = get_external_provider_service(
            provider_type=module.params.pop('type'),
            system_service=connection.system_service(),
        )
        external_providers_module = ExternalProviderModule(
            connection=connection,
            module=module,
            service=external_providers_service,
        )
        external_providers_module.provider_type(provider_type)

        state = module.params.pop('state')
        if state == 'absent':
            ret = external_providers_module.remove()
        elif state == 'present':
            ret = external_providers_module.create()

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
