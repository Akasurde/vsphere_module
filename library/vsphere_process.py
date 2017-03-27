#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['start', 'stop']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            guest_username=dict(required=True),
            guest_password=dict(required=True),
            wait=dict(type='bool', required=False, default=True),
            program=dict(required=False), # required only for start operation
            arguments=dict(required=False),
            work_dir=dict(required=False),
            pid=dict(required=False), # required only for stop operation
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    vm_name = module.params['vm']
    operation = module.params['operation']
    guest_username = module.params['guest_username']
    guest_password = module.params['guest_password']
    wait = module.params['wait']
    program = module.params['program']
    arguments = module.params['arguments']
    work_dir = module.params['work_dir']
    pid = module.params['pid']

    si = get_service_instance(module=module)
    content = si.RetrieveContent()
    pm = content.guestOperationsManager.processManager
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find virtual machine named "{0}"'.format(vm_name))

    tools_status = vm.guest.toolsStatus
    if (tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning'):
        module.fail_json(msg='tools not running or not installed at "{0}"'.format(vm_name))

    credentials = vim.vm.guest.NamePasswordAuthentication(
        username=guest_username, password=guest_password)

    if operation == 'start':
        try:
            if program is None:
                raise Exception('required parameter "program" missing for start operation')

            if arguments is None:
                arguments = ''

            program_spec = vim.vm.guest.ProcessManager.ProgramSpec(
                programPath=program, arguments=arguments, workingDirectory=work_dir)

            pid = pm.StartProgramInGuest(vm=vm, auth=credentials, spec=program_spec)
            process = get_process_info(pm, vm, credentials, pid)
            if wait:
                while True:
                    process = get_process_info(pm, vm, credentials, pid)
                    if process is None: break
                    if process.endTime: break

            if process:
                module.exit_json(msg='start operation successful',
                    process_name=process.name, process_pid=pid, process_owner=process.owner,
                    process_start_time=process.startTime, process_end_time=process.endTime,
                    process_exit_code=process.exitCode)

            module.exit_json(msg='start operation successful', process_pid=pid)
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'stop':
        try:
            if pid is None:
                raise Exception('required parameter "pid" missing for stop operation')

            pm.TerminateProcessInGuest(vm=vm, auth=credentials, pid=long(pid))
            module.exit_json(msg='process with pid "{0}" successfully terminated'.format(pid))
        except Exception as e:
            module.fail_json(msg='stop operation failed for pid "{0}"'.format(pid),
                             exception_message=e.message, exception=traceback.format_exc())

    module.fail_json(msg='specified operation parameter "{0}" has invalid or not implemented'.format(operation))

def get_process_info(pm, vm, cred, pid):
    processes = pm.ListProcessesInGuest(vm=vm, auth=cred, pids=[pid])
    if (len(processes) > 0):
        return processes[0]
    else:
        return None

import sys
import traceback
sys.path.append('/tmp/vsphere_utils')
reload(sys)
sys.setdefaultencoding('utf8')
from time import sleep
from vsphere_utils import *
from pyVmomi import vim, vmodl
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()