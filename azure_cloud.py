import base64

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient

import cluster

SUBSCRIPTION_ID = "a8bdae60-f431-4620-bf0a-fad96eb36ca4"
LOCATION = "westus2"
IMAGE_ID = "/subscriptions/a8bdae60-f431-4620-bf0a-fad96eb36ca4/resourceGroups/MAGE-2/providers/Microsoft.Compute/images/mage-deps-v7"

credential = DefaultAzureCredential()

rg_name = lambda cluster_name: cluster_name + "-rg"
vnet_name = lambda cluster_name: cluster_name + "-vnet"
nsg_name = lambda cluster_name: cluster_name + "-nsg"
subnet_name = lambda cluster_name: cluster_name + "-subnet"
vm_name = lambda cluster_name, instance_id: cluster_name + "-" +  str(instance_id)
wdisk_name = lambda cluster_name, instance_id: vm_name(cluster_name, instance_id) + "-wdisk"
ip_name = lambda cluster_name, instance_id: vm_name(cluster_name, instance_id) + "-ip"
nic_name = lambda cluster_name, instance_id: vm_name(cluster_name, instance_id) + "-nic"

def spawn_cluster(c, name, count, disk_layout_name, use_large_work_disk = False, subscription_id = SUBSCRIPTION_ID, location = LOCATION, image_id = IMAGE_ID):
    cloud_init_file = "cloud-init-azure.yaml"
    if disk_layout_name == "paired-noswap":
        cloud_init_file = "cloud-init-azure-paired.yaml"

    with open(cloud_init_file, "rb") as f:
        cloud_init_bytes = f.read()
    cloud_init_encoded = base64.urlsafe_b64encode(cloud_init_bytes).decode("utf-8")

    compute_client = ComputeManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    resource_group = rg_name(name)

    if resource_client.resource_groups.check_existence(resource_group):
        raise RuntimeError("Cannot spawn cluster \"{0}\": cluster already exists".format(name))

    rg_result = resource_client.resource_groups.create_or_update(resource_group, {
        "location": location
    })
    assert rg_result.name == resource_group
    c.azure_rg_id = rg_result.id

    poller = network_client.virtual_networks.begin_create_or_update(resource_group, vnet_name(name),
    {
        "location": location,
        "address_space": {
            "address_prefixes": ["10.0.0.0/24"]
        }
    })
    vnet_result = poller.result()
    c.azure_vnet_id = vnet_result.id

    poller = network_client.network_security_groups.begin_create_or_update(resource_group, nsg_name(name),
    {
        "location": location,
        "security_rules": [
            {
                "name": name + "-ssh",
                "protocol": "Tcp",
                "source_port_range": "*",
                "source_address_prefix": "*",
                "destination_port_range": "22",
                "destination_address_prefix": "*",
                "access": "Allow",
                "priority": 300,
                "direction": "Inbound",
            },
            {
                "name": name + "-wan",
                "protocol": "Tcp",
                "source_port_range": "*",
                "source_address_prefix": "*",
                "destination_port_range": "40000-65535",
                "destination_address_prefix": "*",
                "access": "Allow",
                "priority": 301,
                "direction": "Inbound",
            },
            # Azure appears to add default rules for outbound connections and
        ]
    })
    nsg_result = poller.result()
    c.azure_nsg_id = nsg_result.id

    poller = network_client.subnets.begin_create_or_update(resource_group, vnet_name(name), subnet_name(name),
    {
        "address_prefix": "10.0.0.0/26",
        "network_security_group": {
            "id": nsg_result.id
        }
    })
    subnet_result = poller.result()
    c.azure_subnet_id = subnet_result.id

    def spawn_vm(_, id):
        poller = network_client.public_ip_addresses.begin_create_or_update(resource_group, ip_name(name, id),
        {
            "location": location,
            "sku": {
                "name": "Standard"
            },
            "public_ip_allocation_method": "Static",
            "public_ip_address_version" : "IPV4"
        })
        public_ip_result = poller.result()
        c.machines[id].azure_public_ip_address_id = public_ip_result.id
        c.machines[id].public_ip_address = public_ip_result.ip_address

        poller = network_client.network_interfaces.begin_create_or_update(resource_group, nic_name(name, id),
        {
            "location": location,
            "ip_configurations": [
                {
                    "name": name + "-ip",
                    "subnet": {
                        "id": subnet_result.id
                    },
                    "public_ip_address": {
                        "id": public_ip_result.id
                    }
                }
            ],
            "enable_accelerated_networking": True
        })
        nic_result = poller.result()
        c.machines[id].azure_nic_id = nic_result.id
        c.machines[id].azure_ip_configuration_id = nic_result.ip_configurations[0].id
        c.machines[id].private_ip_address = nic_result.ip_configurations[0].private_ip_address

        data_disks = []
        if use_large_work_disk:
            data_disks.append({
                "lun": 0,
                "name": wdisk_name(name, id),
                "create_option": "Empty",
                "disk_size_gb": 8192, # Should be at tier S70
                "managed_disk": {
                    "storage_account_type": "Standard_LRS"
                }
            })

        poller = compute_client.virtual_machines.begin_create_or_update(resource_group, vm_name(name, id),
        {
            "location": location,
            "zones": ["2"],
            "hardware_profile": {
                "vm_size": "Standard_D16d_v4"
            },
            "storage_profile": {
                "image_reference": {
                    "id": IMAGE_ID
                },
                "data_disks": data_disks
            },
            "os_profile": {
                "computer_name": vm_name(name, id),
                "admin_username": "mage",
                "linux_configuration": {
                    "disable_password_authentication": True,
                    "ssh": {
                        "public_keys": [
                            {
                                "path": "/home/mage/.ssh/authorized_keys",
                                "key_data": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDsSOuZT2UeFph4om3mjVT1C3kzkULW7+34m0Cg1F/KCBgDb+R//tpV26/BKm1uPKDm8lqz+4O9WWG+aBOjY2k1DpxY0VMxpxITRAv81TwO9Z+MpisUPvQbkphNEvLNh16T2pysrBxzYTTlvKyc0dtxs9zu7nHefIFTEZxd57vsx9tJzLBq9H7OxsGv0H6DKX7Kh4QNm7W/JyLMqZHT8ojjZugeLoHc5g/YCdUna7IsR8W0HOZ6EF3S6DE8bC4fSZo1wxVVHYYR9UQT6PSMxLKFw4Nz/kFlEG7Ae0cyGd0n2+B7+RzYEMOul1ySY9CqPxnhbXE/2TQlk57sGXNXDWBV sam@castle"
                            }
                        ]
                    }
                },
                "custom_data": cloud_init_encoded
            },
            "network_profile": {
                "network_interfaces": [
                    {
                        "id": nic_result.id
                    }
                ]
            }
        })
        vm_result = poller.result()
        c.machines[id].vm_id = vm_result.id
        c.machines[id].vm_name = vm_result.name
        c.machines[id].disk_name = vm_result.storage_profile.os_disk.name
        c.machines[id].provider = "azure"

    c.for_each_concurrently(spawn_vm, range(count))

    return c

def deallocate_cluster(name, exception_if_not_exist = True, subscription_id = SUBSCRIPTION_ID):
    resource_client = ResourceManagementClient(credential, subscription_id)

    resource_group = rg_name(name)

    if not resource_client.resource_groups.check_existence(resource_group):
        if exception_if_not_exist:
            raise RuntimeError("Cannot deallocate cluster \"{0}\": cluster does not exist".format(name))
        return False

    poller = resource_client.resource_groups.begin_delete(resource_group)
    rg_delete_result = poller.result()
    return True

    # compute_client = ComputeManagementClient(credential, subscription_id)
    # network_client = NetworkManagementClient(credential, subscription_id)
    # for id in range(count):
    #     vm_info = compute_client.virtual_machines.get(resource_group, vm_name(name, id))
    #
    #     poller = compute_client.virtual_machines.begin_delete(resource_group, vm_name(name, id))
    #     vm_delete_result = poller.result()
    #
    #     poller = compute_client.disks.begin_delete(resource_group, vm_info.storage_profile.os_disk.name)
    #     disk_delete_result = poller.result()
    #
    #     poller = network_client.network_interfaces.begin_delete(resource_group, nic_name(name, id))
    #     nic_delete_result = poller.result()
    #
    #     poller = network_client.public_ip_addresses.begin_delete(resource_group, ip_name(name, id))
    #     ip_delete_result = poller.result()
    #
    # poller = network_client.subnets.begin_delete(resource_group, vnet_name(name), subnet_name(name))
    # subnet_delete_result = poller.result()
    #
    # poller = network_client.network_security_groups.begin_delete(resource_group, nsg_name(name))
    # nsg_delete_result = poller.result()
    #
    # poller = network_client.virtual_networks.begin_delete(resource_group, vnet_name(name))
    # vnet_delete_result = poller.result()
