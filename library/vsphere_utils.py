#!/usr/bin/python
# -*- coding: utf-8 -*-
from ansible.module_utils.six import iteritems
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import atexit
import ssl
import traceback

try:
    import requests
    from pyVim import connect
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

class TaskError(Exception):
    pass

def get_connection_argument_spec():
    return dict(
        hostname=dict(required=True),
        port=dict(default='443', required=False),
        username=dict(aliases=['user', 'uname'], required=True),
        password=dict(aliases=['pass', 'pwd'], required=True, no_log=True),
        validate_certs=dict(type='bool', required=False, default=False),
    )

def get_connection_info(module):
    hostname = module.params['hostname']
    port = module.params['port']
    username = module.params['username']
    password = module.params['password']
    validate_certs = module.params['validate_certs']
    return hostname, port, username, password, validate_certs

def get_service_instance(module):
    hostname, port, username, password, validate_certs = get_connection_info(module)

    if validate_certs and not hasattr(ssl, 'SSLContext'):
        module.fail_json(msg='pyVim does not support changing verification mode with python < 2.7.9.'
                             'Either update python or use validate_certs=false')
    try:
        if validate_certs:
            service_instance = connect.SmartConnect(host=hostname, user=username, pwd=password)
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            context.verify_mode = ssl.CERT_NONE
            service_instance = connect.SmartConnect(host=hostname, user=username,
                                                    pwd=password, sslContext=context)
    except Exception as e:
        module.fail_json(msg=e.message, exception=traceback.format_exc())
    finally:
        if not service_instance:
            module.fail_json(msg='could not connect to "{0}"'.format(hostname))
        atexit.register(connect.Disconnect, service_instance)
        return service_instance

def collect_objects_properties(si, type, props_list=None, include_object=True):
    """
    Collect properties for managed objects from a view ref

    Args:
        si (ServiceInstance): ServiceInstance connection
        object_type pyVmomi.vim.*): Type of managed object
        props_list list): List of properties to retrieve
        include_object (bool): If True include the managed objects

    Returns:
        A list of properties for the managed objects
    """

    # Create object specification to define the starting point of
    # inventory navigation
    root_folder = si.content.rootFolder
    view_container = si.content.viewManager.CreateContainerView(
        container=root_folder, type=[type], recursive=True)
    object_spec = vmodl.query.PropertyCollector.ObjectSpec()
    object_spec.obj = view_container
    object_spec.skip = True

    # Create a traversal specification to identify the path for collection
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec()
    traversal_spec.name = 'traverseEntities'
    traversal_spec.path = 'view'
    traversal_spec.skip = False
    traversal_spec.type = view_container.__class__
    object_spec.selectSet = [traversal_spec]

    # Identify the properties to the retrieved
    property_spec = vmodl.query.PropertyCollector.PropertySpec()
    property_spec.type = type

    if not props_list:
        property_spec.all = True

    property_spec.pathSet = props_list

    # Add the object and property specification to the
    # property filter specification
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = [object_spec]
    filter_spec.propSet = [property_spec]

    # Retrieve properties
    collector = si.content.propertyCollector
    managed_objects = collector.RetrieveContents([filter_spec])

    data = []
    for object in managed_objects:
        properties = {}
        for property in object.propSet:
            properties[property.name] = property.val

        if include_object:
            properties['obj'] = object.obj

        data.append(properties)
    return data

def get_entity(si, name, type=vim.VirtualMachine):
    entity_data = collect_objects_properties(si, type=type, props_list=['name'])
    entity = next((entity for entity in entity_data if entity['name'].lower() == name.lower()), None)
    if entity is None: return None
    return entity['obj']

def get_entity_by_name_and_type(si, name, type):
    properties = ['name']
    type = type.lower()

    if type == 'host':
        vim_type = vim.HostSystem
    elif type == 'vm':
        vim_type = vim.VirtualMachine
    elif type == 'datastore':
        vim_type = vim.Datastore
    elif type == 'network':
        vim_type = vim.Network
    else:
        vim_type = vim.VirtualMachine

    entity_data = collect_objects_properties(si, type=vim_type, props_list=properties)
    entity = next((entity for entity in entity_data if entity['name'] == name), None)

    if entity is None:
        return entity

    return entity['obj']

def get_folder_type(type):
    type = type.lower()
    if type == 'host':
        return 'ComputeResource'
    if type == 'vm':
        return 'VirtualMachine'
    if type == 'datastore':
        return 'Datastore'
    if type == 'network':
        return 'Network'
    return None

def are_folder_contain_type(folder, type):
    result = next((folder_type for folder_type in folder.childType if folder_type.lower() == type.lower()), None)
    if result is None:
        return False
    else:
        return True

def get_folder_by_name_and_type(si, name, type):
    folder_data = collect_objects_properties(si, type=vim.Folder, props_list=['name'])
    filtered_folders = [folder for folder in folder_data if folder['name'].lower() == name.lower()]

    if len(filtered_folders) == 0:
        return None

    if type is None:
        return filtered_folders[0]['obj']

    folder_type = get_folder_type(type)
    folder = next((folder for folder in filtered_folders if are_folder_contain_type(folder['obj'], folder_type)), None)
    if folder is None: return folder
    return folder['obj']

def get_all_snapshots_info(snapshot_tree):
    snapshots = []

    if snapshot_tree is None:
        return snapshots

    for snapshot in snapshot_tree:
        snapshots.append(snapshot)
        child_snapshot = snapshot.childSnapshotList
        snapshots.extend(get_all_snapshots_info(child_snapshot))

    return snapshots

def get_snaphot_from_vm_by_name(vm, name):
    snapshots = get_all_snapshots_info(vm.snapshot.rootSnapshotList)
    snapshot = next((snap for snap in snapshots if snap is not None and snap.name.lower() == name.lower()), None)

    if snapshot is None:
        return snapshot

    return snapshot.snapshot