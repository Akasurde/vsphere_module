#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['poweron', 'poweroff', 'reboot', 'suspend']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            wait=dict(type='bool', required=False, default=True),
            guest=dict(type='bool', required=False, default=False), # required only for poweron and poweroff tasks
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    vm_name = module.params['vm']
    operation = module.params['operation']
    guest = module.params['guest']
    wait = module.params['wait']

    si = get_service_instance(module=module)
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find virtual machine named "{0}"'.format(vm_name))

    if operation == 'poweron':
        try:
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                WaitForTask(vm.PowerOn(), si=si)
            if wait:
                while not vm.guest.interactiveGuestOperationsReady:
                    time.sleep(1)

            module.exit_json(msg='power on operation successful for "{0}"'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'poweroff':
        try:
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                if guest:
                    vm.ShutdownGuest()
                    if wait:
                        while vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                            time.sleep(1)
                else:
                    WaitForTask(vm.PowerOff(), si=si)

            module.exit_json(msg='power off operation successful for "{0}"'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'reboot':
        try:
            if guest:
                vm.RebootGuest()
                if wait:
                    while vm.guest.interactiveGuestOperationsReady:
                        time.sleep(1)
                    while not vm.guest.interactiveGuestOperationsReady:
                        time.sleep(1)
            else:
                WaitForTask(vm.ResetVM_Task(), si=si)
                if wait:
                    while not vm.guest.interactiveGuestOperationsReady:
                        time.sleep(1)

            module.exit_json(msg='reboot operation successful for "{0}"'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'suspend':
        try:
            if vm.runtime.powerState != vim.VirtualMachinePowerState.suspended:
                WaitForTask(vm.Suspend(), si=si)

            module.exit_json(msg='suspend operation successful for "{0}"'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message)

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