#!/usr/bin/env python3

import json
import sys
import os
import yaml

def generate_worker_config_dict(global_id, internal_port, external_port, cluster, wan = False, worker_id = None):
    worker = {}
    worker["internal_host"] = cluster["machines"][global_id]["private_ip_address"]
    worker["internal_port"] = internal_port
    worker["external_host"] = cluster["machines"][global_id]["public_ip_address" if wan else "private_ip_address"]
    worker["external_port"] = external_port
    if wan:
        worker["storage_path"] = "worker{0}_swapfile".format(worker_id)
    else:
        worker["storage_path"] = "/dev/disk/cloud/azure_resource-part1"
    return worker

def populate_top_level_params(protocol, scenario, split_factor, config, ot_pipeline_depth = 1, ot_num_daemons = 3):
    if protocol == "halfgates":
        config["page_shift"] = 12
        if scenario == "unbounded":
            config["num_pages"] = 1048576
        elif scenario.endswith("gb"):
            num_gb = int(scenario[:-2])
            num_bytes = num_gb << 30
            total_ideal_num_pages = num_bytes >> (config["page_shift"] + 4)
            config["num_pages"] = (total_ideal_num_pages // split_factor) - 1536
        else:
            raise RuntimeError("Unknown scenario {0}".format(scenario))
        config["prefetch_buffer_size"] = 256
        config["prefetch_lookahead"] = 10000

        ot = {}
        ot["max_batch_size"] = 512
        ot["pipeline_depth"] = ot_pipeline_depth
        ot["num_daemons"] = ot_num_daemons
        config["oblivious_transfer"] = ot
    elif protocol == "ckks":
        config["page_shift"] = 21
        if scenario == "unbounded":
            config["num_pages"] = 32768
        elif scenario.endswith("gb"):
            num_gb = int(scenario[:-2])
            num_bytes = num_gb << 30
            total_ideal_num_pages = num_bytes >> config["page_shift"]
            config["num_pages"] = (total_ideal_num_pages // split_factor) - 48
        else:
            raise RuntimeError("Unknown scenario {0}".format(scenario))
        config["prefetch_buffer_size"] = 16
        config["prefetch_lookahead"] = 100
    else:
        raise RuntimeError("Unknown protocol {0}".format(protocol))

def generate_config_dict(protocol, scenario, party_size, id, cluster):
    config = {}
    populate_top_level_params(protocol, scenario, 1, config)

    assert party_size & (party_size - 1) == 0
    first_worker_id = party_size * (id // party_size)
    allocated_workers_per_party = len(cluster["machines"]) // 2
    if first_worker_id < allocated_workers_per_party:
        evaluator_ids = range(first_worker_id, first_worker_id + party_size)
        garbler_ids = range(first_worker_id + allocated_workers_per_party, first_worker_id + allocated_workers_per_party + party_size)
    else:
        evaluator_ids = range(first_worker_id - allocated_workers_per_party, first_worker_id - allocated_workers_per_party + party_size)
        garbler_ids = range(first_worker_id, first_worker_id + party_size)
    evaluator_workers = [generate_worker_config_dict(evaluator_ids[i], 56000 + i, 57000 + i, cluster, False) for i in range(party_size)]
    garbler_workers = [generate_worker_config_dict(garbler_ids[i], 56000 + i, 57000 + i, cluster, False) for i in range(party_size)]
    config["parties"] = [{"workers": evaluator_workers}, {"workers": garbler_workers}]
    return config

def generate_wan_config_dict(scenario, num_workers_per_party, azure_id, gcloud_id, cluster, ot_pipeline_depth = 1, ot_num_daemons = 3):
    config = {}
    populate_top_level_params("halfgates", scenario, num_workers_per_party, config, ot_pipeline_depth, ot_num_daemons)

    evaluator_workers = [generate_worker_config_dict(gcloud_id, 56000 + i, 57000 + i, cluster, True, i) for i in range(party_size)]
    garbler_workers = [generate_worker_config_dict(azure_id, 56000 + i, 57000 + i, cluster, True, i) for i in range(party_size)]
    config["parties"] = [{"workers": evaluator_workers}, {"workers": garbler_workers}]
    return config

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: {0} cluster.json id lan/location output_dir".format(sys.argv[0]))
        sys.exit(2)

    with open(sys.argv[1], "r") as f:
        cluster = json.load(f)

    id = int(sys.argv[2])

    location = sys.argv[3]

    creation_dir = sys.argv[4]

    memory_bounds = ("unbounded", "1gb", "2gb", "4gb", "8gb", "16gb", "32gb", "62gb")
    dir_paths = tuple(os.path.join(creation_dir, mem_bound) for mem_bound in memory_bounds)
    for dir in dir_paths:
        os.makedirs(dir, exist_ok = True)

    if location == "lan" or location == "local":
        party_sizes = []
        party_size = 1
        while party_size < cluster["num_lan_machines"]:
            party_sizes.append(party_size)
            party_size *= 2

        for protocol in ("halfgates", "ckks"):
            for scenario, output_dir_path in zip(memory_bounds, dir_paths):
                for party_size in party_sizes:
                    config_dict = generate_config_dict(protocol, scenario, party_size, id, cluster)
                    output_path = os.path.join(output_dir_path, "config_{0}_{1}.yaml".format(protocol, party_size))
                    with open(output_path, "w") as f:
                        yaml.dump(config_dict, f, sort_keys = False, default_flow_style = False)
    else:
        azure_id = id
        gcloud_id = cluster["location_to_id"][location]
        for scenario, output_dir_path in (("unbounded", unbounded_dir), ("1gb", bounded_dir)):
            for party_size in (1, 2, 4, 8, 16):
                for ot_pipeline_depth in tuple(2 ** i for i in range(9)):
                    for ot_num_daemons in tuple(2 ** i for i in range(9)):
                        ot_params = (ot_pipeline_depth, ot_num_daemons)
                        config_dict = generate_wan_config_dict(scenario, party_size, azure_id, gcloud_id, cluster, *ot_params)
                        output_path = os.path.join(output_dir_path, "config_halfgates_{0}_{1}_{2}.yaml".format(party_size, ot_pipeline_depth, ot_num_daemons))
                        with open(output_path, "w") as f:
                            yaml.dump(config_dict, f, sort_keys = False, default_flow_style = False)
