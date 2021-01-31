import base64
import json
import threading
import types
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient

SUBSCRIPTION_ID = "a8bdae60-f431-4620-bf0a-fad96eb36ca4"
LOCATION = "westus2"
#IMAGE_ID = "/subscriptions/a8bdae60-f431-4620-bf0a-fad96eb36ca4/resourceGroups/MAGE-2/providers/Microsoft.Compute/images/mage-deps"
#IMAGE_ID = "/subscriptions/a8bdae60-f431-4620-bf0a-fad96eb36ca4/resourceGroups/MAGE-2/providers/Microsoft.Compute/images/mage-prereqs"
IMAGE_ID = "/subscriptions/a8bdae60-f431-4620-bf0a-fad96eb36ca4/resourceGroups/MAGE-2/providers/Microsoft.Compute/images/mage-deps"
RESOURCE_GROUP = "MAGE-2"

credential = DefaultAzureCredential()

class Machine(object):
    def __init__(self):
        self.public_ip_address = None
        self.public_ip_address_id = None
        self.nic_id = None
        self.ip_configuration_id = None
        self.private_ip_address = None
        self.vm_id = None
        self.disk_name = None

    def as_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        m = Machine()
        for attr in m.__dict__:
            setattr(m, attr, d[attr])
        return m

class Cluster(object):
    def __init__(self, name, size):
        self.name = name
        self.rg_id = None
        self.vnet_id = None
        self.nsg_id = None
        self.subnet_id = None
        self.machines = tuple(Machine() for _ in range(size))

    def for_each_concurrently(self, predicate, ids = None):
        if ids is None:
            ids = range(len(self.machines))
        threads = [None for _ in ids]
        def iteration(i, id):
            threads[i] = threading.Thread(target = lambda: predicate(self.machines[id], id))
            threads[i].start()
        for i, id in enumerate(ids):
            iteration(i, id)
        for t in threads:
            t.join()

    def as_dict(self):
        d = dict(self.__dict__)
        d["machines"] = tuple(m.as_dict() for m in d["machines"])
        return d

    @staticmethod
    def from_dict(d):
        c = Cluster("", 0)
        for attr in c.__dict__:
            if attr == "machines":
                c.machines = tuple(Machine.from_dict(m) for m in d[attr])
            else:
                setattr(c, attr, d[attr])
        return c

    def save_to_file(self, filename):
        with open(filename, "w") as f:
            json.dump(self.as_dict(), f)

    @staticmethod
    def load_from_file(filename):
        with open(filename, "r") as f:
            d = json.load(f)
            return Cluster.from_dict(d)

rg_name = lambda cluster_name: cluster_name + "-rg"
vnet_name = lambda cluster_name: cluster_name + "-vnet"
nsg_name = lambda cluster_name: cluster_name + "-nsg"
subnet_name = lambda cluster_name: cluster_name + "-subnet"
vm_name = lambda cluster_name, instance_id: cluster_name + "-" +  str(instance_id)
disk_name = lambda clsuter_name, instance_id: vm_name(cluster_name, instance_id) + "-disk"
ip_name = lambda cluster_name, instance_id: vm_name(cluster_name, instance_id) + "-ip"
nic_name = lambda cluster_name, instance_id: vm_name(cluster_name, instance_id) + "-nic"

def spawn(name, count, subscription_id = SUBSCRIPTION_ID, location = LOCATION, image_id = IMAGE_ID):
    with open("cloud-init.yaml", "rb") as f:
        cloud_init_bytes = f.read()
    cloud_init_encoded = base64.urlsafe_b64encode(cloud_init_bytes).decode("utf-8")

    c = Cluster(name, count)

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
    c.rg_id = rg_result.id

    poller = network_client.virtual_networks.begin_create_or_update(resource_group, vnet_name(name),
    {
        "location": location,
        "address_space": {
            "address_prefixes": ["10.0.0.0/24"]
        }
    })
    vnet_result = poller.result()
    c.vnet_id = vnet_result.id

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
    c.nsg_id = nsg_result.id

    poller = network_client.subnets.begin_create_or_update(resource_group, vnet_name(name), subnet_name(name),
    {
        "address_prefix": "10.0.0.0/28",
        "network_security_group": {
            "id": nsg_result.id
        }
    })
    subnet_result = poller.result()
    c.subnet_id = subnet_result.id

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
        c.machines[id].public_ip_address_id = public_ip_result.id
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
        c.machines[id].nic_id = nic_result.id
        c.machines[id].ip_configuration_id = nic_result.ip_configurations[0].id
        c.machines[id].private_ip_address = nic_result.ip_configurations[0].private_ip_address

        poller = compute_client.virtual_machines.begin_create_or_update(resource_group, vm_name(name, id),
        {
            "location": location,
            "zones": ["2"],
            "hardware_profile": {
                "vm_size": "Standard_D16d_v4"
            },
            "storage_profile": {
                "image_reference": {
                    "id": image_id
                }
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
        c.machines[id].disk_name = vm_result.storage_profile.os_disk.name

    c.for_each_concurrently(spawn_vm)

    return c

def deallocate(name, subscription_id = SUBSCRIPTION_ID):
    resource_client = ResourceManagementClient(credential, subscription_id)

    resource_group = rg_name(name)

    if not resource_client.resource_groups.check_existence(resource_group):
        raise RuntimeError("Cannot deallocate cluster \"{0}\": cluster does not exist".format(name))

    poller = resource_client.resource_groups.begin_delete(resource_group)
    rg_delete_result = poller.result()

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
