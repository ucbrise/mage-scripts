import googleapiclient.discovery

# Q: perhaps just integrate this into cluster.py?
GCP_PROJECT = "rise-mage"

oregon = ("us-west1", "b")
iowa = ("us-central1", "b")

compute = googleapiclient.discovery.build("compute", "v1")

# Reference: https://cloud.google.com/compute/docs/reference/rest/v1/instances/insert

def spawn_gcp_instance(name, region, zone_id):
    target_zone = "{0}-{1}".format(region, zone_id)
    # Based on https://cloud.google.com/compute/docs/tutorials/python-guide

    image_response = compute.images().getFromFamily(project = "ubuntu-os-cloud", family = "ubuntu-2004-lts").execute()

    request_body = {
        "kind": "compute#instance",
        "name": name,
        "zone": "projects/{0}/zones/{1}".format(GCP_PROJECT, target_zone),
        "machineType": "projects/{0}/zones/{1}/machineTypes/n2-highcpu-2".format(GCP_PROJECT, target_zone),
        "displayDevice": {
            "enableDisplay": False,
        },
        "metadata": {
            "kind": "compute#metadata",
            "items": [
                {
                    "key": "ssh-keys",
                    "value": "mage:ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDsSOuZT2UeFph4om3mjVT1C3kzkULW7+34m0Cg1F/KCBgDb+R//tpV26/BKm1uPKDm8lqz+4O9WWG+aBOjY2k1DpxY0VMxpxITRAv81TwO9Z+MpisUPvQbkphNEvLNh16T2pysrBxzYTTlvKyc0dtxs9zu7nHefIFTEZxd57vsx9tJzLBq9H7OxsGv0H6DKX7Kh4QNm7W/JyLMqZHT8ojjZugeLoHc5g/YCdUna7IsR8W0HOZ6EF3S6DE8bC4fSZo1wxVVHYYR9UQT6PSMxLKFw4Nz/kFlEG7Ae0cyGd0n2+B7+RzYEMOul1ySY9CqPxnhbXE/2TQlk57sGXNXDWBV mage@castle"
                }
            ]
        },
        "tags": {
            "items": []
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
                    "sourceImage": image_response["selfLink"],
                    "diskType": "projects/{0}/zones/{1}/diskTypes/pd-standard".format(GCP_PROJECT, target_zone),
                    "diskSizeGb": "10",
                },
                "diskEncryptionKey": {}
            },
            {
                "kind": "compute#attachedDisk",
                "mode": "READ_WRITE",
                "autoDelete": True,
                "deviceName": "local-ssd-0",
                "type": "SCRATCH",
                "interface": "NVME",
                "initializeParams": {
                    "diskType": "projects/{0}/zones/{1}/diskTypes/local-ssd".format(GCP_PROJECT, target_zone),
                }
            }
        ],
        "canIpForward": False,
        "networkInterfaces": [
            {
                "kind": "compute#networkInterface",
                "subnetwork": "projects/{0}/regions/{1}/subnetworks/default".format(GCP_PROJECT, region),
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
        "serviceAccounts": [
            {
                "email": "832515717505-compute@developer.gserviceaccount.com",
                "scopes": [
                    "https://www.googleapis.com/auth/devstorage.read_only",
                    "https://www.googleapis.com/auth/logging.write",
                    "https://www.googleapis.com/auth/monitoring.write",
                    "https://www.googleapis.com/auth/servicecontrol",
                    "https://www.googleapis.com/auth/service.management.readonly",
                    "https://www.googleapis.com/auth/trace.append"
                ]
            }
        ],
        "shieldedInstanceConfig": {
            "enableSecureBoot": False,
            "enableVtpm": True,
            "enableIntegrityMonitoring": True
        },
        "confidentialInstanceConfig": {
            "enableConfidentialCompute": False
        }
    }

    result = compute.instances().insert(project = GCP_PROJECT, zone = target_zone, body = request_body).execute()
    return result
