#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['clone_to_vm', 'clone_to_temp', 'convert_to_vm', 'convert_to_temp', 'remove']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            new_vm=dict(required=False), # required only for clone tasks
            host=dict(required=False), # required only for clone and convert_to_vm tasks
            resource_pool=dict(required=False),
            datastore=dict(required=False), # required only for clone tasks
            snapshot=dict(required=False), # only for clone tasks
            folder=dict(required=False), # only for clone tasks
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    host = None
    resource_pool = None
    snapshot = None

    vm_name = module.params['vm']
    new_vm = module.params['new_vm']
    host_name = module.params['host']
    resource_pool_name = module.params['resource_pool']
    datastore_name = module.params['datastore']
    snapshot_name = module.params['snapshot']
    folder_name = module.params['folder']
    operation = module.params['operation']

    si = get_service_instance(module=module)
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find virtual machine named "{0}"'.format(vm_name))

    if folder_name is None:
        folder = vm.parent
    else:
        folder = get_folder_by_name_and_type(si=si, name=folder_name, type='vm')
        if folder is None:
            module.fail_json(msg='could not find folder named "{0}"'.format(folder_name))

    if operation == 'remove':
        try:
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                WaitForTask(task=vm.PowerOffVM_Task(), si=si)
            WaitForTask(task=vm.Destroy_Task(), si=si)
            module.exit_json(changed=True, msg='entity "{0}" successfully removed'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'convert_to_temp':
        try:
            vm.MarkAsTemplate()
            module.exit_json(changed=True, msg='virtual machine "{0}" successfully converted to template'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if snapshot_name:
        snapshot = get_snaphot_from_vm_by_name(vm=vm, name=snapshot_name)
        if snapshot is None:
            module.fail_json(msg='virtual machine "{0}" does not contain snapshot named "{1}"'.format(
                vm_name, snapshot_name))

    if host_name:
        host = get_entity(si=si, name=host_name, type=vim.HostSystem)
        if host is None:
            module.fail_json(msg='could not find host named "{0}"'.format(host_name))

    if resource_pool_name:
        resource_pool = get_entity(si=si, name=resource_pool_name, type=vim.ResourcePool)
        if resource_pool is None:
            module.fail_json(msg='could not find resource pool named "{0}"'.format(resource_pool_name))

    if host_name is None and resource_pool_name is None:
        host = vm.runtime.host
        resource_pool = vm.resourcePool

    if operation == 'convert_to_vm':
        try:
            vm.MarkAsVirtualMachine(pool=resource_pool, host=host)
            module.exit_json(changed=True, msg='template "{0}" successfully converted to virtual machine'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if datastore_name is None:
        datastore = vm.datastore[0]
    else:
        datastore = get_entity(si=si, name=datastore_name, type=vim.Datastore)
        if datastore is None:
            module.fail_json(msg='could not find datastore named "{0}"'.format(datastore_name))

    if new_vm is None:
        module.fail_json(msg='required parameter "new_vm" missing for "{0}" operation'.format(operation))

    if operation == 'clone_to_vm':
        try:
            clonespec = get_clone_spec(host,resource_pool, datastore, snapshot)
            clone_task = vm.Clone(folder=folder, name=new_vm, spec=clonespec)
            WaitForTask(clone_task)
            module.exit_json(changed=True, msg='template "{0}" successfully cloned as virtual machine "{1}"'. \
                             format(vm_name, new_vm))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'clone_to_temp':
        try:
            clonespec = get_clone_spec(host,resource_pool, datastore, snapshot, True)
            clone_task = vm.Clone(folder=folder, name=new_vm, spec=clonespec)
            WaitForTask(clone_task)
            module.exit_json(changed=True, msg='virtual machine "{0}" successfully cloned as template "{1}"'. \
                             format(vm_name, new_vm))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    module.fail_json(msg='specified operation parameter "{0}" has invalid or not implemented'.format(operation))

def get_clone_spec(host, pool, store, snapshot, template=False):
    relospec = vim.vm.RelocateSpec()
    clonespec = vim.vm.CloneSpec()
    if host:
        relospec.host = host
    if pool:
        relospec.pool = pool
    relospec.datastore = store
    if snapshot:
        relospec.diskMoveType = 'createNewChildDiskBacking'
        clonespec.snapshot = snapshot
    clonespec.location = relospec
    clonespec.template = template
    return clonespec

import traceback
import sys
sys.path.append('/tmp/vsphere_utils')
reload(sys)
sys.setdefaultencoding('utf8')
from vsphere_utils import *
from pyVim.task import WaitForTask
from pyVmomi import vim, vmodl
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()