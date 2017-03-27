#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['create', 'rename', 'revert', 'remove', 'remove_all']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            snapshot=dict(aliases=['snap', 'snapshot_name'], required=True),
            new_snapshot=dict(aliases=['new_snap'], required=False), # required only for rename task
            description=dict(aliases=['desc'], required=False), # required only for create and rename tasks
            remove_subtree=dict(type='bool', aliases=['remove_childs'],
                                required=False, default=False), # required only for remove task
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    vm_name = module.params['vm']
    operation = module.params['operation']
    snapshot = module.params['snapshot']
    description = module.params['description']

    si = get_service_instance(module=module)
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find vm named "{0}"'.format(vm_name))

    if operation == 'create':
        try:
            creation_task = vm.CreateSnapshot(snapshot, description, False, False)
            WaitForTask(task=creation_task, si=si)
            module.exit_json(changed=True, msg='snapshot "{0}" successfully created'.format(snapshot))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'rename':
        try:
            new_snapshot = module.params['new_snapshot']

            if new_snapshot is None:
                raise Exception('required parameter "new_snapshot" missing for rename operation')

            snapshot_object = get_snaphot_from_vm_by_name(vm, snapshot)

            if snapshot_object is None:
                raise Exception('virtual machine "{0}" does not contain snapshot named "{1}"'.format(vm_name, snapshot))

            snapshot_object.RenameSnapshot(new_snapshot, description)
            module.exit_json(changed=True, msg='snapshot "{0}" successfully renamed as "{1}"'.format(
                snapshot, new_snapshot))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'revert':
        try:
            snapshot_object = get_snaphot_from_vm_by_name(vm, snapshot)

            if snapshot_object is None:
                raise Exception('virtual machine "{0}" does not contain snapshot named "{1}"'.format(vm_name, snapshot))

            reverting_task = snapshot_object.RevertToSnapshot_Task()
            WaitForTask(task=reverting_task, si=si)
            module.exit_json(changed=True, msg='snapshot "{0}" successfully reverted'.format(snapshot))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'remove':
        try:
            remove_subtree = module.params['remove_subtree']
            snapshot_object = get_snaphot_from_vm_by_name(vm, snapshot)

            if snapshot_object is None:
                raise Exception('virtual machine "{0}" does not contain snapshot named "{1}"'.format(vm_name, snapshot))

            removal_task = snapshot_object.RemoveSnapshot_Task(remove_subtree)
            WaitForTask(task=removal_task, si=si)
            module.exit_json(changed=True, msg='snapshot "{0}" successfully removed'.format(snapshot))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'remove_all':
        try:
            if vm.snapshot is None:
                raise Exception('virtual machine "{0}" does not contain snapshots'.format(vm_name))

            for snap in vm.snapshot.rootSnapshotList:
                removal_task = snap.snapshot.RemoveSnapshot_Task(True)
                WaitForTask(task=removal_task, si=si)

            module.exit_json(changed=True, msg='all snapshots at "{0}" successfully removed'.format(vm_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    module.fail_json(msg='specified operation parameter "{0}" has invalid or not implemented'.format(operation))

import sys
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