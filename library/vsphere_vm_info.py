#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['ipv4', 'ipv6']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    vm_name = module.params['vm']
    operation = module.params['operation']

    si = get_service_instance(module=module)
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find virtual machine named "{0}"'.format(vm_name))

    tools_status = vm.guest.toolsStatus
    if (tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning'):
        module.fail_json(msg='tools not running or not installed at "{0}"'.format(vm_name))

    if 'ipv' in operation:
        try:
            ip = []
            for nic in vm.guest.net:
                adresses = nic.ipConfig.ipAddress
                for adress in adresses:
                    ip_address = adress.ipAddress
                    if operation == 'ipv6' and ':' in ip_address:
                        ip.append(ip_address)
                    elif operation == 'ipv4' and '.' in ip_address:
                        ip.append(ip_address)
                    else: continue
            module.exit_json(msg='ip addresses info successfully displayed for "{0}"'.format(vm_name),
                             ip_address=ip)
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    module.fail_json(msg='specified operation parameter "{0}" has invalid or not implemented'.format(operation))

import sys
import time
import traceback
sys.path.append('/tmp/vsphere_utils')
reload(sys)
sys.setdefaultencoding('utf8')
from vsphere_utils import *
from pyVim.task import WaitForTask
from pyVmomi import vim, vmodl
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()