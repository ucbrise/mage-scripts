#!/usr/bin/env python3

import json
import sys
import os
import yaml

def generate_worker_config_dict(global_id, internal_port, external_port, cluster, wan = False):
    worker = {}
    worker["internal_host"] = cluster["machines"][global_id]["private_ip_address"]
    worker["internal_port"] = internal_port
    worker["external_host"] = cluster["machines"][global_id]["public_ip_address" if wan else "private_ip_address"]
    worker["external_port"] = external_port
    worker["storage_path"] = "/dev/disk/cloud/azure_resource-part1"
    return worker

def generate_config_dict(protocol, scenario, party_size, id, cluster):
    config = {}
    if protocol == "halfgates":
        config["page_shift"] = 12
        if scenario == "unbounded":
            config["num_pages"] = 524288
        elif scenario == "1gb":
            config["num_pages"] = 14848
        else:
            raise RuntimeError("Unknown scenario {0}".format(scenario))
        config["prefetch_buffer_size"] = 256
        config["prefetch_lookahead"] = 10000

        ot = {}
        ot["max_batch_size"] = 512
        ot["pipeline_depth"] = 1
        ot["num_daemons"] = 3
        config["oblivious_transfer"] = ot
    elif protocol == "ckks":
        config["page_shift"] = 21
        if scenario == "unbounded":
            config["num_pages"] = 16384
        elif scenario == "1gb":
            config["num_pages"] = 464
        else:
            raise RuntimeError("Unknown scenario {0}".format(scenario))
        config["prefetch_buffer_size"] = 16
        config["prefetch_lookahead"] = 100
    else:
        raise RuntimeError("Unknown protocol {0}".format(protocol))

    assert party_size & (party_size - 1) == 0
    first_worker_id = party_size * (id // party_size)
    allocated_workers_per_party = len(cluster["machines"]) // 2
    if first_worker_id < allocated_workers_per_party:
        evaluator_ids = range(first_worker_id, first_worker_id + party_size)
        garbler_ids = range(first_worker_id + allocated_workers_per_party, first_worker_id + allocated_workers_per_party + party_size)
    else:
        evaluator_ids = range(first_worker_id - allocated_workers_per_party, first_worker_id - allocated_workers_per_party + party_size)
        garbler_ids = range(first_worker_id, first_worker_id + party_size)
    evaluator_workers = [generate_worker_config_dict(evaluator_ids[i], 56000 + i, 57000 + i, cluster) for i in range(party_size)]
    garbler_workers = [generate_worker_config_dict(garbler_ids[i], 56000 + i, 57000 + i, cluster) for i in range(party_size)]
    config["parties"] = [{"workers": evaluator_workers}, {"workers": garbler_workers}]
    return config

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: {0} cluster.json id output_dir".format(sys.argv[0]))
        sys.exit(2)

    with open(sys.argv[1], "r") as f:
        cluster = json.load(f)

    id = int(sys.argv[2])

    creation_dir = sys.argv[3]

    unbounded_dir = os.path.join(creation_dir, "unbounded")
    bounded_dir = os.path.join(creation_dir, "1gb")

    os.makedirs(unbounded_dir, exist_ok = True)
    os.makedirs(bounded_dir, exist_ok = True)

    party_sizes = []
    party_size = 1
    while party_size < len(cluster["machines"]):
        party_sizes.append(party_size)
        party_size *= 2

    for protocol in ("halfgates", "ckks"):
        for scenario, output_dir_path in (("unbounded", unbounded_dir), ("1gb", bounded_dir)):
            for party_size in party_sizes:
                config_dict = generate_config_dict(protocol, scenario, party_size, id, cluster)
                output_path = os.path.join(output_dir_path, "config_{0}_{1}.yaml".format(protocol, party_size))
                with open(output_path, "w") as f:
                    yaml.dump(config_dict, f, sort_keys = False, default_flow_style = False)
