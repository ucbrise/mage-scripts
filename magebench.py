#!/usr/bin/env python3
import os
import sys
import time

import cluster
import remote

CLUSTER_NAME = "mage-cluster"
CLUSTER_SIZE = 2

def party_from_global_id(cluster, global_id):
    if global_id < len(cluster.machines) // 2:
        return 0 # evaluator
    else:
        return 1 # garbler

def validate_protocol(protocol):
    protocol = protocol.lower()
    if protocol not in ("halfgates", "ckks"):
        print("Protocol must be halfgates or ckks (got {0})".format(protocol))
        sys.exit(2)
    return protocol

def validate_scenario(scenario):
    scenario = scenario.lower()
    if scenario not in ("unbounded", "os", "mage"):
        print("Scenario must be unbounded, os, or mage (got {0})".format(scenario))
    return scenario

def provision(machine, id):
    remote.exec_script(machine.public_ip_address, "./scripts/provision.sh")
    remote.copy_to(machine.public_ip_address, False, "./cluster.json", "~")
    remote.exec_script(machine.public_ip_address, "./scripts/generate_configs.py", "~/cluster.json 0 ~/config")

def run_lan_experiment(cluster, problem_name, problem_size, protocol, scenario, worker_ids, log_name = "/dev/null", generate_fresh_input = True, generate_fresh_memprog = True):
    if protocol == "halfgates":
        assert len(worker_ids) % 2 == 0
        workers_per_party = len(worker_ids) // 2
    elif protocol == "ckks":
        workers_per_party = len(worker_ids)
    else:
        raise RuntimeError("Unknown protocol {0}".format(protocol))

    program_name = "{0}_{1}".format(problem_name, problem_size)
    config_file = "~/config/{0}/config_{1}_{2}.yaml".format("1gb" if scenario == "mage" else "unbounded", protocol, workers_per_party)

    if isinstance(log_name, int):
        log_name = program_name + "_t{0}".format(log_name)
    elif log_name is None:
        log_name = program_name
    elif not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string (got {0})".format(repr(log_name)))

    def generate_input(machine, global_id):
        remote.exec_script(machine.public_ip_address, "./scripts/generate_input.sh", "{0} {1} {2} {3} {4}".format(problem_name, problem_size, protocol, global_id % workers_per_party, workers_per_party))

    if generate_fresh_input:
        cluster.for_each_concurrently(generate_input, worker_ids)

    def generate_memprog(machine, global_id):
        party = party_from_global_id(cluster, global_id)
        local_id = global_id % workers_per_party
        remote.exec_script(machine.public_ip_address, "./scripts/generate_memprog.sh", "{0} {1} {2} {3} {4} {5} {6}".format(problem_name, problem_size, protocol, config_file, party, local_id, log_name))

    if generate_fresh_memprog:
        cluster.for_each_concurrently(generate_memprog, worker_ids)

    def run_mage(machine, global_id):
        party = party_from_global_id(cluster, global_id)
        local_id = global_id % workers_per_party
        if party == 1:
            time.sleep(30) # Wait for the evaluator to start first
        remote.exec_script(machine.public_ip_address, "./scripts/run_mage.sh", "{0} {1} {2} {3} {4} {5} {6} {7}".format(scenario, protocol, config_file, party, local_id, program_name, log_name, "true"))

    time.sleep(70) # Wait for TIME-WAIT state to expire
    cluster.for_each_concurrently(run_mage, worker_ids)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: {0} spawn/provision/run/deallocate".format(sys.argv[0]))
        sys.exit(2)

    if sys.argv[1] == "spawn":
        if os.path.exists("cluster.json"):
            print("Cluster already exists!")
            print("To create a new cluster, first run \"{0} deallocate\"".format(sys.argv[0]))
            sys.exit(1)
        print("Spawning cluster...")
        c = cluster.spawn(CLUSTER_NAME, CLUSTER_SIZE)
        c.save_to_file("cluster.json")
        print("Waiting three minutes for the machines to start up...")
        time.sleep(180)
        print("Provisioning the machines...")
        c.for_each_concurrently(provision)
        print("Done.")
    elif sys.argv[1] == "provision":
        c = cluster.Cluster.load_from_file("cluster.json")
        print("Provisioning the machines...")
        c.for_each_concurrently(provision)
        print("Done.")
    elif sys.argv[1] == "run":
        c = cluster.Cluster.load_from_file("cluster.json")
        if len(sys.argv) not in (6, 7):
            print("Usage: {0} problem_name problem_size protocol scenario [log_tag]".format(sys.argv[0]))
            sys.exit(2)
        problem_name = sys.argv[2]
        problem_size = int(sys.argv[3])
        protocol = validate_protocol(sys.argv[4])
        scenario = validate_scenario(sys.argv[5])
        worker_ids = (0, 1)
        log_name = "{0}_{1}_{2}".format(problem_name, problem_size, scenario)
        if len(sys.argv) >= 7:
            log_name += "_{0}".format(sys.argv[6])
        run_lan_experiment(c, problem_name, problem_size, protocol, scenario, worker_ids, log_name)
    elif sys.argv[1] == "deallocate":
        print("Deallocating cluster...")
        cluster.deallocate(CLUSTER_NAME, CLUSTER_SIZE)
        try:
            os.remove("cluster.json")
        except os.FileNotFoundError:
            pass
        print("Done.")
    else:
        print("Unknown command \"{0}\"".format(sys.argv[1]))
        sys.exit(2)
