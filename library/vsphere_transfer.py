#!/usr/bin/python
# -*- coding: utf-8 -*-

def main():
    argument_spec = get_connection_argument_spec()
    operation_choices = ['upload', 'download']
    argument_spec.update(
        dict(
            vm=dict(required=True),
            source=dict(required=True),
            destination=dict(required=True),
            guest_username=dict(required=True),
            guest_password=dict(required=True),
            operation=dict(required=True, choices=operation_choices)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    vm_name = module.params['vm']
    operation = module.params['operation']
    source = module.params['source']
    destination = module.params['destination']
    guest_username = module.params['guest_username']
    guest_password = module.params['guest_password']

    si = get_service_instance(module=module)
    content = si.RetrieveContent()
    vm = get_entity(si=si, name=vm_name)

    if not vm:
        module.fail_json(msg='could not find virtual machine named "{0}"'.format(vm_name))

    tools_status = vm.guest.toolsStatus
    if (tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning'):
        module.fail_json(msg='tools not running or not installed at "{0}"'.format(vm_name))

    credentials = vim.vm.guest.NamePasswordAuthentication(
        username=guest_username, password=guest_password)

    if operation == 'upload':
        try:
            if os.path.isfile(source):
                result = upload_file(content, vm, credentials, destination, source)
                if not result:
                    raise Exception('upload operation error for file "{0}"'.format(source))
                module.exit_json(changed=True, msg='file "{0}" successfully uploaded into "{1}"'.format(
                    source, destination))
            elif os.path.isdir(source):
                upload_folder(content, vm, credentials, destination, source)
                module.exit_json(changed=True, msg='folder "{0}" successfully uploaded into "{1}"'.format(
                    source, destination))
            else:
                raise Exception('source path "{0}" not exist or not supported'.format(source))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    if operation == 'download':
        try:
            is_file, is_dir, error = get_remote_path_info(content, vm, credentials, source)

            if is_file:
                result = download_file(content, vm, credentials, destination, source)
                if not result:
                    raise Exception('download operation error for file "{0}"'.format(source))
                module.exit_json(changed=True, msg='file "{0}" successfully downloaded into "{1}"'.format(
                    source, destination))

            if is_dir:
                download_folder(content, vm, credentials, destination, source)
                module.exit_json(changed=True, msg='folder "{0}" successfully downloaded into "{1}"'.format(
                    source, destination))

            if error:
                raise Exception('could not find remote file by path "{0}"'.format(source))
        except Exception as e:
            module.fail_json(msg=e.message, exception=traceback.format_exc())

    module.fail_json(msg='specified operation parameter "{0}" has invalid or not implemented'.format(operation))

def upload_folder(content, vm, credentials, destination, source):
    source_file_list = []
    partial_source_file_list = []
    dest_file_list = []

    for root, sub_dirs, files in os.walk(source):
        for file in files:
            file_full_path = path_combine(root, file)
            source_file_list.append(file_full_path)

            if '\\' in file_full_path:
                symbol = '\\'
            else:
                symbol = '/'

            file_partial_path = file_full_path.replace(source + symbol, '')
            partial_source_file_list.append(file_partial_path)

    for file in partial_source_file_list:
        if '\\' in destination:
            file.replace('/', '\\')
        dest_file_list.append(path_combine(destination, file))

    for source_file, destination_file in itertools.izip(source_file_list, dest_file_list):
        result = upload_file(content, vm, credentials, destination_file, source_file)
        if not result:
            raise Exception('upload operation error for file "{0}"'.format(source_file))

def upload_file(content, vm, credentials, destination, source):
    try:
        file_attribute = vim.vm.guest.FileManager.FileAttributes()
        dest_path = get_directory_path(destination)
        try_create_folder(content, vm, credentials, dest_path)
        with open(source, 'rb') as file:
            file = file.read()
        url = content.guestOperationsManager.fileManager. \
            InitiateFileTransferToGuest(vm, credentials, destination, file_attribute, len(file), True)
        response = requests.put(url=url, data=file, verify=False)

        if response.status_code == 200:
            return True
        else:
            return False
    except:
        return False

def get_remote_folder_structure(content, vm, credentials, path):
    remote_fs = []
    list_file_info = content.guestOperationsManager.fileManager.ListFilesInGuest(
        vm, credentials, path)

    for file in list_file_info.files:
        if file.path == '.' or file.path == '..':
            continue
        if not file.type == 'directory':
            file_path = path_combine(path, file.path)
            remote_fs.append(file_path)
        else:
            folder_path = path_combine(path, file.path)
            remote_fs.extend(get_remote_folder_structure(content, vm, credentials, folder_path))

    return remote_fs

def download_folder(content, vm, credentials, destination, source):
    source_file_list = get_remote_folder_structure(content, vm, credentials, source)
    dest_file_list = []

    if '\\' in source:
        symbol = '\\'
    else:
        symbol = '/'
    for file in source_file_list:
        file_partial_path = file.replace(source + symbol, '')
        if '\\' in destination:
            file_partial_path = file_partial_path.replace('/', '\\')
        else:
            file_partial_path = file_partial_path.replace('\\', '/')
        dest_file_list.append(path_combine(destination, file_partial_path))

    for source_file, destination_file in itertools.izip(source_file_list, dest_file_list):
        result = download_file(content, vm, credentials, destination_file, source_file)
        if not result:
            raise Exception('download operation error for file "{0}"'.format(source_file))

def download_file(content, vm, credentials, destination, source):
    try:
        dest_path = get_directory_path(destination)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        file_attribute = content.guestOperationsManager.fileManager. \
            InitiateFileTransferFromGuest(vm, credentials, source)
        response = requests.get(url=file_attribute.url, stream=True, verify=False)

        if response.status_code == 200:
            with open(destination, 'wb') as file:
                file.write(response.content)
            return True
        else:
            return False
    except:
        return False

def try_create_folder(content, vm, credentials, folder):
    try:
        content.guestOperationsManager.fileManager.MakeDirectoryInGuest(vm, credentials, folder, True)
    except: None

def get_directory_path(path):
    if '\\' in path:
        return '\\'.join(path.split('\\')[0:-1])
    else:
        return '/'.join(path.split('/')[0:-1])

def get_remote_path_info(content, vm, credentials, path):
    is_file = is_dir = error = False
    try:
        list_file_info = content.guestOperationsManager.fileManager.ListFilesInGuest(
            vm, credentials, path)

        if list_file_info.files[0].type == 'file':
            is_file = True
        else:
            is_dir = True
    except:
        error = True
    finally:
        return is_file, is_dir, error

def path_combine(path, file):
    if '\\' in path:
        return path + '\\' + file
    else:
        return os.path.join(path, file)

import itertools
import glob
import os
import requests
import sys
import traceback
sys.path.append('/tmp/vsphere_utils')
reload(sys)
sys.setdefaultencoding('utf8')
from vsphere_utils import *
from pyVmomi import vim, vmodl
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()