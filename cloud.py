import threading
import cluster
import azure_cloud
import google_cloud

def spawn_cluster(name, num_lan_machines, use_large_work_disk, paired, *wan_machine_locations):
    num_wan_machines = len(set(wan_machine_locations))
    if len(wan_machine_locations) != num_wan_machines:
        print("Some WAN locations are repeated")
        return None

    if num_lan_machines < 0:
        print("The number of LAN machines must be nonnegative")
        return None

    if paired:
        num_wan_machines *= num_lan_machines

    c = cluster.Cluster(name, num_lan_machines + num_wan_machines)

    gcp_locations = []
    for wan_location in wan_machine_locations:
        region_zone = google_cloud.location_to_region_zone(wan_location)
        if region_zone is None:
            print("Unknown location {0}".format(wan_location))
            return None
        gcp_locations.append(region_zone)

    gcp_lock = threading.Lock()

    def init(_, id):
        if id == 0 and num_lan_machines > 0:
            # Initializes all machines from indices 0 to num_lan_machines - 1
            azure_cloud.spawn_cluster(c, name, num_lan_machines, "paired-noswap" if paired else "regular", use_large_work_disk)
        elif id >= num_lan_machines:
            if paired:
                wan_index = (id // num_lan_machines) - 1
                wan_location = wan_machine_locations[wan_index]
                region_zone = gcp_locations[wan_index]
                with gcp_lock:
                    location_id = (id % num_lan_machines)
                    gcp_instance_name = "{0}-{1}-{2}".format(name, wan_location, location_id)
                    if (id % num_lan_machines) == 0:
                        c.location_to_id[wan_location] = id
                    google_cloud.spawn_instance(c.machines[id], gcp_instance_name, "n2-highmem-4", 2, "paired-noswap", *region_zone)
            else:
                wan_index = id - num_lan_machines
                wan_location = wan_machine_locations[wan_index]
                region_zone = gcp_locations[wan_index]
                with gcp_lock:
                    gcp_instance_name = "{0}-{1}".format(name, wan_location)
                    c.location_to_id[wan_location] = id
                    google_cloud.spawn_instance(c.machines[id], gcp_instance_name, "n2-highcpu-2", 1, "regular", *region_zone)

    c.for_each_concurrently(init)
    c.num_lan_machines = num_lan_machines
    c.paired = paired
    return c

def deallocate_cluster(c):
    gcp_lock = threading.Lock()

    def deallocate(m, id):
        if id == 0:
            azure_cloud.deallocate_cluster(c.name)
        elif id >= c.num_lan_machines:
            with gcp_lock:
                google_cloud.deallocate_instance(m)

    c.for_each_concurrently(deallocate)

def deallocate_cluster_by_info(name, num_lan_machines, paired, *wan_machine_locations):
    gcp_locations = []
    for wan_location in wan_machine_locations:
        region_zone = google_cloud.location_to_region_zone(wan_location)
        if region_zone is None:
            print("Unknown location {0}".format(wan_location))
            return None
        gcp_locations.append(region_zone)

    azure_cloud.deallocate_cluster(name, False)
    for i, region_zone in enumerate(gcp_locations):
        target_zone = "-".join(region_zone)
        if paired:
            for id in range(num_lan_machines):
                vm_name = "-".join((name, wan_machine_locations[i], str(id)))
                google_cloud.deallocate_instance_by_info(target_zone, vm_name)
        else:
            vm_name = "-".join((name, wan_machine_locations[i]))
            google_cloud.deallocate_instance_by_info(target_zone, vm_name)
