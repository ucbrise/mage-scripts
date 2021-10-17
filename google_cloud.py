import time
import googleapiclient.discovery
import cluster

GCP_PROJECT = "rise-mage"
GCP_FIREWALL_RULE = "mage-wan"

oregon = ("us-west1", "b")
iowa = ("us-central1", "b")
virginia = ("us-east4", "b")

def location_to_region_zone(loc):
    if loc == "oregon":
        return oregon
    elif loc == "iowa":
        return iowa
    elif loc == "virginia":
        return virginia
    else:
        return None

compute = googleapiclient.discovery.build("compute", "v1")

# This is based on code given here: https://cloud.google.com/compute/docs/tutorials/python-guide
def wait_for_operation(compute, project, zone, operation):
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result['status'] == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)

# Reference: https://cloud.google.com/compute/docs/reference/rest/v1/instances/insert
def spawn_instance(m, name, instance_type, num_local_ssds, image_name, disk_layout_name, region, zone_letter, project_name = GCP_PROJECT):
    cloud_init_file = "cloud-init-gcp.yaml"
    if disk_layout_name == "paired-noswap":
        cloud_init_file = "cloud-init-gcp-paired.yaml"
    elif disk_layout_name == "paired-swap":
        cloud_init_file = "cloud-init-gcp-paired-swap.yaml"

    with open(cloud_init_file, "rb") as f:
        cloud_init_bytes = f.read()

    target_zone = "{0}-{1}".format(region, zone_letter)
    # Based on https://cloud.google.com/compute/docs/tutorials/python-guide

    if image_name == "mage":
        image_response = compute.images().getFromFamily(project = project_name, family = "mage-deps").execute()
        image_link = image_response["selfLink"]
    else:
        image_response = compute.images().getFromFamily(project = "ubuntu-os-cloud", family = "ubuntu-2004-lts").execute()
        image_link = image_response["selfLink"]
        #image_link = "projects/ubuntu-os-cloud/global/images/ubuntu-2004-focal-v20210623"

    # Create firewall rule for inbound WAN traffic if it does not already exist
    prev_firewalls = compute.firewalls().list(project = GCP_PROJECT, filter = "name = {0}".format(GCP_FIREWALL_RULE)).execute()
    if "items" not in prev_firewalls or len(prev_firewalls["items"]) == 0:
        compute.firewalls().insert(project = GCP_PROJECT, body = {
            "name": GCP_FIREWALL_RULE,
            "description": "Allow inbound TCP connections for wide-are network experiments to benchmark MAGE.",
            "targetTags": [GCP_FIREWALL_RULE],
            "allowed": [{"IPProtocol": "tcp", "ports": ["57000-57999"]}]
        }).execute()

    local_ssds = []
    for i in range(num_local_ssds):
        local_ssds.append({
            "kind": "compute#attachedDisk",
            "mode": "READ_WRITE",
            "autoDelete": True,
            "deviceName": "local-ssd-{0}".format(i),
            "type": "SCRATCH",
            "interface": "NVME",
            "initializeParams": {
                "diskType": "projects/{0}/zones/{1}/diskTypes/local-ssd".format(project_name, target_zone),
            }
        })

    request_body = {
        "kind": "compute#instance",
        "name": name,
        "zone": "projects/{0}/zones/{1}".format(project_name, target_zone),
        "machineType": "projects/{0}/zones/{1}/machineTypes/{2}".format(project_name, target_zone, instance_type),
        "displayDevice": {
            "enableDisplay": False,
        },
        "metadata": {
            "kind": "compute#metadata",
            "items": [
                {
                    "key": "ssh-keys",
                    "value": "mage:ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDsSOuZT2UeFph4om3mjVT1C3kzkULW7+34m0Cg1F/KCBgDb+R//tpV26/BKm1uPKDm8lqz+4O9WWG+aBOjY2k1DpxY0VMxpxITRAv81TwO9Z+MpisUPvQbkphNEvLNh16T2pysrBxzYTTlvKyc0dtxs9zu7nHefIFTEZxd57vsx9tJzLBq9H7OxsGv0H6DKX7Kh4QNm7W/JyLMqZHT8ojjZugeLoHc5g/YCdUna7IsR8W0HOZ6EF3S6DE8bC4fSZo1wxVVHYYR9UQT6PSMxLKFw4Nz/kFlEG7Ae0cyGd0n2+B7+RzYEMOul1ySY9CqPxnhbXE/2TQlk57sGXNXDWBV mage@castle"
                },
                {
                    "key": "user-data",
                    "value": cloud_init_bytes.decode("ascii")
                }
            ]
        },
        "tags": {
            "items": [
                GCP_FIREWALL_RULE # Associates this instance with the firewall rule created above
            ]
        },
        "disks": [
            {
                "kind": "compute#attachedDisk",
                "type": "PERSISTENT",
                "boot": True,
                "mode": "READ_WRITE",
                "autoDelete": True,
                "deviceName": name,
                "initializeParams": {
                    "sourceImage": image_link,
                    "diskType": "projects/{0}/zones/{1}/diskTypes/pd-standard".format(project_name, target_zone),
                    "diskSizeGb": "10",
                },
                "diskEncryptionKey": {}
            },
            *local_ssds
        ],
        "canIpForward": False,
        "networkInterfaces": [
            {
                "kind": "compute#networkInterface",
                "subnetwork": "projects/{0}/regions/{1}/subnetworks/default".format(project_name, region),
                "accessConfigs": [
                    {
                        "kind": "compute#accessConfig",
                        "name": "External NAT",
                        "type": "ONE_TO_ONE_NAT",
                        "networkTier": "PREMIUM",
                    }
                ],
                "aliasIpRanges": []
            }
        ],
        "description": "",
        "labels": {},
        "scheduling": {
            "preemptible": False,
            "onHostMaintenance": "MIGRATE",
            "automaticRestart": True,
            "nodeAffinities": []
        },
        "deletionProtection": False,
        "reservationAffinity": {
            "consumeReservationType": "ANY_RESERVATION",
        },
        "shieldedInstanceConfig": {
            "enableSecureBoot": False,
            "enableVtpm": True,
            "enableIntegrityMonitoring": True
        },
        "confidentialInstanceConfig": {
            "enableConfidentialCompute": False
        }
    }

    operation = compute.instances().insert(project = project_name, zone = target_zone, body = request_body).execute()
    wait_for_operation(compute, project_name, target_zone, operation["name"])

    info = compute.instances().get(project = project_name, zone = target_zone, instance = name).execute()

    m.public_ip_address = info["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
    m.private_ip_address = info["networkInterfaces"][0]["networkIP"]
    m.vm_id = info["id"]
    m.vm_name = info["name"]
    m.disk_name = info["disks"][0]["deviceName"]
    m.gcp_zone = target_zone
    m.provider = "gcloud"
    m.image = image_name

def deallocate_instance(m, project_name = GCP_PROJECT):
    deallocate_instance_by_info(m.gcp_zone, m.vm_name, project_name)

def deallocate_instance_by_info(target_zone, instance_name, project_name = GCP_PROJECT):
    operation = compute.instances().delete(project = project_name, zone = target_zone, instance = instance_name).execute()
    wait_for_operation(compute, project_name, target_zone, operation["name"])
