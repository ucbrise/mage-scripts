#!/usr/bin/env python3
import argparse
import os
import shutil
import socket
import sys
import time

import cloud
import cluster
import experiment
import remote

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

def copy_ckks_keys(machine, id):
    remote.copy_to(machine.public_ip_address, True, "./ckks_keys", "~")
    remote.exec_sync(machine.public_ip_address, "cp ~/ckks_keys/* ~/work/mage/bin")

def generate_ckks_keys(c):
    shutil.rmtree("./ckks_keys", ignore_errors = True)
    remote.exec_sync(c.machines[0].public_ip_address, "cd ~/work/mage/bin; ./ckks_utils keygen; mkdir -p ~/ckks_keys; cp *.ckks ~/ckks_keys")
    try:
        remote.copy_from(c.machines[0].public_ip_address, True, "~/ckks_keys", ".")
        c.for_each_concurrently(copy_ckks_keys, range(1, len(c.machines)))
    finally:
        shutil.rmtree("./ckks_keys")

def provision_cluster(c, repository, checkout):
    def provision_machine(machine, id):
        if machine.image_name != "mage":
            remote.exec_script(machine.public_ip_address, "./scripts/install_deps.sh", "--install-mage-deps --install-utils --setup-wan-tcp")
        remote.exec_script(machine.public_ip_address, "./scripts/provision.sh", "{0} {1}".format(machine.provider, c.setup))
        remote.exec_script(machine.public_ip_address, "./scripts/setup_code.sh", "{0} {1} {2}".format(machine.image_name, repository, checkout))
        remote.copy_to(machine.public_ip_address, False, "./cluster.json", "~")
        if id < c.num_lan_machines:
            remote.exec_script(machine.public_ip_address, "./scripts/generate_configs.py", "~/cluster.json {0} lan ~/config {1}".format(id, "true" if c.setup.startswith("paired") else "false"))
        if c.setup in ("paired-noswap", "paired-swap"):
            for location, loc_id in c.location_to_id.items():
                if id in range(c.num_lan_machines) or id in range(loc_id, loc_id + c.num_lan_machines):
                    remote.exec_script(machine.public_ip_address, "./scripts/generate_configs.py", "~/cluster.json {0} {1}-paired ~/config-{1}-paired".format(id, location))
        else:
            for location, loc_id in c.location_to_id.items():
                if id == 0 or id == loc_id:
                    remote.exec_script(machine.public_ip_address, "./scripts/generate_configs.py", "~/cluster.json 0 {0} ~/config-{0}".format(location))
    c.for_each_concurrently(provision_machine)
    generate_ckks_keys(c)

def spawn(args):
    if os.path.exists("cluster.json"):
        print("Cluster already exists!")
        print("To create a new cluster, first run \"{0} deallocate\"".format(sys.argv[0]))
        sys.exit(1)
    assert args.azure_machine_count > 0
    if args.gcloud_machine_locations is None:
        args.gcloud_machine_locations = tuple()
    elif args.large_work_disk:
        print("Do NOT use \"large work disk\" in the WAN.")
        print("The swapfile won't be on the temp disk anymore.")
        print("This can be fixed by changing the code.")
        sys.exit(1)
    if args.name == "":
        args.name = "mage-{0}".format(socket.gethostname())
    print("Spawning cluster...")
    c = cloud.spawn_cluster(args.name, args.azure_machine_count, "mage" if args.image else "ubuntu", args.large_work_disk, args.wan_setup, args.project_gcloud, *args.gcloud_machine_locations)
    c.save_to_file("cluster.json")
    print("Waiting three minutes for the machines to start up...")
    time.sleep(180)
    print("Provisioning the machines...")
    provision_cluster(c, args.repository, args.checkout)
    print("Done.")

def provision(args):
    c = cluster.Cluster.load_from_file("cluster.json")
    print("Provisioning the machines...")
    provision_cluster(c, args.repository, args.checkout)
    print("Done.")

def parse_program(program):
    try:
        index = program.rfind("_")
        if index == -1:
            raise ValueError
        problem_name = program[:index]
        problem_size = program[index + 1:]
        return (problem_name, problem_size)
    except ValueError:
        print("Invalid program name (must be of the form <problem name>_<problem size>): {0}".format(program))
        sys.exit(2)

def parse_program_list(program_list):
    result = []
    for program in program_list:
        result.append(parse_program(program))
    return result

def run_lan(args):
    c = cluster.Cluster.load_from_file("cluster.json")
    if args.programs is None:
        if len(c.machines) == 2:
            args.programs = ("merge_sorted_1048576", "full_sort_1048576", "loop_join_2048", "matrix_vector_multiply_8192", "binary_fc_layer_16384", "real_sum_65536", "real_statistics_16384", "real_matrix_vector_multiply_256", "real_naive_matrix_multiply_128", "real_tiled_matrix_multiply_128")
        elif len(c.machines) == 8:
            args.programs = ("merge_sorted_4194304", "full_sort_4194304", "loop_join_4096", "matrix_vector_multiply_16384", "binary_fc_layer_32768", "real_sum_262144", "real_statistics_65536", "real_matrix_vector_multiply_512", "real_naive_matrix_multiply_256", "real_tiled_matrix_multiply_256")
        else:
            print("Could not infer default list of programs for {0}-machine cluster".format(len(c.machines)))
            args.programs = tuple()
    if args.scenarios is None:
        args.scenarios = ("mage", "unbounded", "os")

    parsed_programs = parse_program_list(args.programs)
    for problem_name, problem_size in parsed_programs:
        if problem_name.startswith("real"):
            protocol = "ckks"
            worker_ids = range(len(c.machines) // 2)
        else:
            protocol = "halfgates"
            worker_ids = range(len(c.machines))
        for trial in range(1, args.trials + 1):
            for scenario in args.scenarios:
                num_nodes_per_party = (len(c.machines) // 2) if args.num_nodes is None else args.num_nodes
                log_name = "workers_{0}_{1}_{2}_{3}_t{4}".format(num_nodes_per_party, problem_name, problem_size, scenario, trial)
                experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, args.mem_limit, worker_ids, log_name, args.num_nodes)


def make_run_wan(paired):
    def run_wan(args):
        c = cluster.Cluster.load_from_file("cluster.json")
        if args.programs is None:
            args.programs = ("merge_sorted_1048576",)
        if args.scenarios is None:
            args.scenarios = ("mage",)
        if args.workers_per_node is None:
            args.workers_per_node = (1,)
        if args.ot_num_connections is None:
            args.ot_num_connections = (3,)
        if args.ot_concurrency is None:
            args.ot_concurrency = (3,)

        parsed_programs = parse_program_list(args.programs)
        for problem_name, problem_size in parsed_programs:
            if problem_name.startswith("real"):
                print("Skipping {0} (only halfgates supported over WAN)".format(problem_name))
                continue
            else:
                protocol = "halfgates"
            for trial in range(1, args.trials + 1):
                for scenario in args.scenarios:
                    for workers_per_node in args.workers_per_node:
                        for ot_num_daemons in args.ot_num_connections:
                            for ot_concurrency in args.ot_concurrency:
                                ot_pipeline_depth = max(ot_concurrency // (ot_num_daemons * workers_per_node), 1)
                                log_name = "wan_{0}_{1}_{2}_{3}_{4}_{5}_{6}_t{7}".format(args.location, workers_per_node, ot_pipeline_depth, ot_num_daemons, problem_name, problem_size, scenario, trial)
                                if paired:
                                    log_name = "paired" + log_name
                                    experiment.run_paired_wan_experiment(c, problem_name, problem_size, scenario, args.mem_limit, args.location, log_name, workers_per_node, c.num_lan_machines, ot_pipeline_depth, ot_num_daemons)
                                else:
                                    experiment.run_wan_experiment(c, problem_name, problem_size, scenario, args.mem_limit, args.location, log_name, workers_per_node, 1, ot_pipeline_depth, ot_num_daemons)
    return run_wan

def run_halfgates_baseline(args):
    if args.sizes is None:
        args.sizes = tuple(2 ** i for i in range(10, 21))
    if args.scenarios is None:
        args.scenarios = ("mage", "unbounded", "os", "emp")

    c = cluster.Cluster.load_from_file("cluster.json")
    assert len(c.machines) == 2

    problem_name = "merge_sorted"
    protocol = "halfgates"
    worker_ids = (0, 1)

    for problem_size in args.sizes:
        for trial in range(1, args.trials + 1):
            for scenario in args.scenarios:
                log_name = "halfgates_baseline_{0}_{1}_{2}_t{3}".format(problem_name, problem_size, scenario, trial)
                if scenario == "emp":
                    experiment.run_halfgates_baseline_experiment(c, problem_size, "os", worker_ids, log_name)
                else:
                    experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, args.mem_limit, worker_ids, log_name)

def run_ckks_baseline(args):
    if args.sizes is None:
        args.sizes = tuple(2 ** i for i in range(6, 15))
    if args.scenarios is None:
        args.scenarios = ("mage", "unbounded", "os", "seal")

    c = cluster.Cluster.load_from_file("cluster.json")
    assert len(c.machines) == 1 or len(c.machines) == 2

    problem_name = "real_statistics"
    protocol = "ckks"
    worker_ids = (0,)

    for problem_size in args.sizes:
        for trial in range(1, args.trials + 1):
            for scenario in args.scenarios:
                log_name = "ckks_baseline_{0}_{1}_{2}_t{3}".format(problem_name, problem_size, scenario, trial)
                if scenario == "seal":
                    experiment.run_ckks_baseline_experiment(c, problem_size, "os", worker_ids, log_name)
                else:
                    experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, args.mem_limit, worker_ids, log_name)

def deallocate(args):
    print("Deallocating cluster...")
    c = cluster.Cluster.load_from_file("cluster.json")
    cloud.deallocate_cluster(c)
    try:
        os.remove("cluster.json")
    except FileNotFoundError:
        pass
    print("Done.")

def purge(args):
    print("Purging cluster...")
    if args.gcloud_machine_locations is None:
        args.gcloud_machine_locations = tuple()
    if args.name == "":
        args.name = "mage-{0}".format(socket.gethostname())
    cloud.deallocate_cluster_by_info(args.name, args.azure_machine_count, args.wan_setup, *args.gcloud_machine_locations)
    try:
        os.remove("cluster.json")
    except FileNotFoundError:
        pass
    print("Done.")

def logs_directory(c, id, logs_directory):
    if id < c.num_lan_machines:
        directory_name = "{0:02d}".format(id)
    elif c.setup in ("paired-noswap", "paired-swap"):
        for location, loc_id in c.location_to_id.items():
            if id in range(loc_id, loc_id + c.num_lan_machines):
                directory_name = "{0}-{1:02d}".format(location, id)
                break
    else:
        for location, loc_id in c.location_to_id.items():
            if id == loc_id:
                directory_name = location
                break
    return os.path.join(".", logs_directory, directory_name)

def fetch_logs(args):
    print("Fetching logs...")
    c = cluster.Cluster.load_from_file("cluster.json")
    for id in range(len(c.machines)):
        os.makedirs(logs_directory(c, id, args.directory), exist_ok = True)

    def fetch_logs_from(machine, id):
        directory = logs_directory(c, id, args.directory)
        remote.copy_from(machine.public_ip_address, False, "~/logs/*", directory)

    c.for_each_concurrently(fetch_logs_from)
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Run benchmark experiments on MAGE.")
    subparsers = parser.add_subparsers()

    parser_spawn = subparsers.add_parser("spawn")
    parser_spawn.add_argument("-n", "--name", default = "")
    parser_spawn.add_argument("-a", "--azure-machine-count", type = int, default = 2)
    parser_spawn.add_argument("-d", "--large-work-disk", action = "store_true")
    parser_spawn.add_argument("-g", "--gcloud-machine-locations", action = "extend", nargs = "+", choices = ("oregon", "iowa", "virginia"))
    parser_spawn.add_argument("-s", "--wan-setup", default = "regular")
    parser_spawn.add_argument("-r", "--repository", default = "https://github.com/ucbrise/mage")
    parser_spawn.add_argument("-c", "--checkout", default = "main")
    parser_spawn.add_argument("-i", "--image", action = "store_true")
    parser_spawn.add_argument("-p", "--project-gcloud", default = "rise-mage")
    parser_spawn.set_defaults(func = spawn)

    parser_provision = subparsers.add_parser("provision")
    parser_provision.set_defaults(func = provision)

    parser_run_lan = subparsers.add_parser("run-lan")
    parser_run_lan.add_argument("-p", "--programs", action = "extend", nargs = "+")
    parser_run_lan.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os"))
    parser_run_lan.add_argument("-m", "--mem-limit", type=str, default = "1gb")
    parser_run_lan.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_lan.add_argument("-n", "--num-nodes", type = int)
    parser_run_lan.set_defaults(func = run_lan)

    parser_run_wan = subparsers.add_parser("run-wan")
    parser_run_wan.add_argument("location", choices = ("oregon", "iowa", "virginia"))
    parser_run_wan.add_argument("-p", "--programs", action = "extend", nargs = "+")
    parser_run_wan.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os"))
    parser_run_wan.add_argument("-m", "--mem-limit", type=str, default = "1gb")
    parser_run_wan.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_wan.add_argument("-w", "--workers-per-node", type = int, action = "extend", nargs = "+")
    parser_run_wan.add_argument("-o", "--ot-concurrency", type = int, action = "extend", nargs = "+")
    parser_run_wan.add_argument("-c", "--ot-num-connections", type = int, action = "extend", nargs = "+")
    parser_run_wan.set_defaults(func = make_run_wan(False))

    parser_run_paired_wan = subparsers.add_parser("run-paired-wan")
    parser_run_paired_wan.add_argument("location", choices = ("oregon", "iowa", "virginia"))
    parser_run_paired_wan.add_argument("-p", "--programs", action = "extend", nargs = "+")
    parser_run_paired_wan.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os"))
    parser_run_paired_wan.add_argument("-m", "--mem-limit", type=str, default = "max")
    parser_run_paired_wan.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_paired_wan.add_argument("-w", "--workers-per-node", type = int, action = "extend", nargs = "+")
    parser_run_paired_wan.add_argument("-o", "--ot-concurrency", type = int, action = "extend", nargs = "+")
    parser_run_paired_wan.add_argument("-c", "--ot-num-connections", type = int, action = "extend", nargs = "+")
    parser_run_paired_wan.set_defaults(func = make_run_wan(True))

    parser_run_hgb = subparsers.add_parser("run-halfgates-baseline")
    parser_run_hgb.add_argument("-z", "--sizes", action = "extend", nargs = "+", type = int)
    parser_run_hgb.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os", "emp"))
    parser_run_hgb.add_argument("-m", "--mem-limit", type=str, default = "1gb")
    parser_run_hgb.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_hgb.set_defaults(func = run_halfgates_baseline)

    parser_run_ckb = subparsers.add_parser("run-ckks-baseline")
    parser_run_ckb.add_argument("-z", "--sizes", action = "extend", nargs = "+", type = int)
    parser_run_ckb.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os", "seal"))
    parser_run_ckb.add_argument("-m", "--mem-limit", type=str, default = "1gb")
    parser_run_ckb.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_ckb.set_defaults(func = run_ckks_baseline)

    parser_deallocate = subparsers.add_parser("deallocate")
    parser_deallocate.set_defaults(func = deallocate)

    parser_purge = subparsers.add_parser("purge")
    parser_purge.add_argument("-n", "--name", default = "")
    parser_purge.add_argument("-a", "--azure-machine-count", type = int, default = 2)
    parser_purge.add_argument("-d", "--large-work-disk", action = "store_true")
    parser_purge.add_argument("-g", "--gcloud-machine-locations", action = "extend", nargs = "+", choices = ("oregon", "iowa", "virginia"))
    parser_purge.add_argument("-s", "--wan-setup", default = "regular")
    parser_purge.add_argument("-r", "--repository", default = "https://github.com/ucbrise/mage")
    parser_purge.add_argument("-c", "--checkout", default = "main")
    parser_purge.set_defaults(func = purge)

    parser_fetch_logs = subparsers.add_parser("fetch-logs")
    parser_fetch_logs.add_argument("directory")
    parser_fetch_logs.set_defaults(func = fetch_logs)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Nothing to do!")
        print("Try: {0} -h".format(sys.argv[0]))
