import json
import threading
import types

class Machine(object):
    def __init__(self):
        self.public_ip_address = None
        self.azure_public_ip_address_id = None
        self.azure_nic_id = None
        self.azure_ip_configuration_id = None
        self.private_ip_address = None
        self.vm_id = None
        self.vm_name = None
        self.disk_name = None
        self.wdisk_name = None
        self.gcp_zone = None
        self.provider = None

    def as_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        m = Machine()
        for attr in m.__dict__:
            setattr(m, attr, d.get(attr, None))
        return m

class Cluster(object):
    def __init__(self, name, size):
        self.name = name
        self.azure_rg_id = None
        self.azure_vnet_idp= None
        self.azure_nsg_id = None
        self.azure_subnet_id = None
        self.machines = tuple(Machine() for _ in range(size))
        self.num_lan_machines = size
        self.location_to_id = {}
        self.paired = False

    def local_machine_ids(self):
        return range(self.num_lan_machines)

    def machine_ids(self, *locations):
        machines = []
        for loc in locations:
            if loc == "local" or loc == "lan":
                machines.extend(self.local_machine_ids())
            else:
                machines.append(self.location_to_id[loc])
        return machines

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

    def for_each_multiple_concurrently(self, predicate, times, ids = None):
        if ids is None:
            ids = range(len(self.machines))
        threads = [[None for _ in range(times)] for _ in ids]
        for i, id in enumerate(ids):
            for j in range(times):
                t = threading.Thread(target = lambda: predicate(self.machines[id], id, j))
                threads[i][j] = t
                t.start()
        for lst in threads:
            for t in lst:
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
