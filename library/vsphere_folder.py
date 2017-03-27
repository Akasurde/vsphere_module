#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    type_choices = ['host', 'vm', 'datastore', 'network']
    operation_choices = ['create', 'rename', 'remove', 'move']
    argument_spec.update(
        dict(
            folder=dict(required=True),
            new_folder=dict(required=False), # required only for rename task
            datacenter=dict(required=False), # required only for create task
            parent_folder=dict(required=False), # required only for create task
            entity=dict(required=False), # required only for move task
            entity_type=dict(required=False, default='vm', choices=type_choices),  # required only for move task
            operation=dict(required=True, choices=operation_choices),
            folder_type=dict(required=False, default='vm', choices=type_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for vsphere_folder module')

    folder_name = module.params['folder']
    datacenter_name = module.params['datacenter']
    parent_folder_name = module.params['parent_folder']
    operation = module.params['operation']
    folder_type = module.params['folder_type']

    si = get_service_instance(module=module)

    if operation == 'create':
        try:
            if datacenter_name:
                datacenter = get_entity(si=si, name=datacenter_name, type=vim.Datacenter)

                if datacenter:
                    if folder_type == 'host':
                        datacenter.hostFolder.CreateFolder(folder_name)
                    elif folder_type == 'vm':
                        datacenter.vmFolder.CreateFolder(folder_name)
                    elif folder_type == 'datastore':
                        datacenter.datastoreFolder.CreateFolder(folder_name)
                    elif folder_type == 'network':
                        datacenter.networkFolder.CreateFolder(folder_name)

                    module.exit_json(changed=True, msg='folder "{0}" successfully created'.format(folder_name))
                else:
                    raise Exception('could not find datacenter named "{0}"'.format(datacenter_name))
            elif parent_folder_name:
                parent_folder = get_folder_by_name_and_type(
                    si=si, name=parent_folder_name, type=folder_type)

                if parent_folder is None:
                    raise Exception('could not find parent folder named "{0}"'.format(parent_folder_name))

                parent_folder.CreateFolder(folder_name)
                module.exit_json(changed=True, msg='folder "{0}" successfully created'.format(folder_name))
            else:
                raise Exception('for the create operation at least one of the following parameters must be specified' +
                                ' "datacenter", "parent_folder"')
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    folder = get_folder_by_name_and_type( si=si, name=folder_name, type=folder_type)

    if folder is None:
        module.fail_json(msg='could not find folder named "{0}"'.format(folder_name))

    if operation == 'rename':
        try:
            new_folder_name = module.params['new_folder']

            if new_folder_name is None:
                raise Exception('required parameter "new_folder" missing for rename operation')

            WaitForTask(folder.Rename(new_folder_name), si=si)
            module.exit_json(changed=True, msg='folder "{0}" successfully renamed as "{1}"'.format(
                folder_name, new_folder_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'remove':
        try:
            WaitForTask(folder.UnregisterAndDestroy(), si=si)
            module.exit_json(changed=True, msg='folder "{0}" successfully removed'.format(folder_name))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'move':
        try:
            entity_name = module.params['entity']
            entity_type = module.params['entity_type']

            if entity_name is None:
                raise Exception('required parameter "entity" missing for move operation')

            if entity_type is None:
                raise Exception('required parameter "entity_type" missing for move operation')

            entity = get_entity_by_name_and_type(si=si, name=entity_name, type=entity_type)

            if entity is None:
                raise Exception('could not find entity named "{0}"'.format(entity_name))

            WaitForTask(folder.MoveIntoFolder_Task([entity]), si=si)
            module.exit_json(changed=True, msg='entity "{0}" successfully moved into folder "{1}"'.format(
                entity_name, folder_name))
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