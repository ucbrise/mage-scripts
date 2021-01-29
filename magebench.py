#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import time

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

def provision_machine(machine, id):
    remote.exec_script(machine.public_ip_address, "./scripts/provision.sh")
    remote.copy_to(machine.public_ip_address, False, "./cluster.json", "~")
    remote.exec_script(machine.public_ip_address, "./scripts/generate_configs.py", "~/cluster.json 0 ~/config")

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

def provision_cluster(c):
    c.for_each_concurrently(provision_machine)
    generate_ckks_keys(c)

def logs_directory(id):
    return os.path.join(".", "logs", "{0:02d}".format(id))

def fetch_logs_from(machine, id):
    directory = logs_directory(id)
    remote.copy_from(machine.public_ip_address, False, "~/logs/*", directory)

def spawn(args):
    if os.path.exists("cluster.json"):
        print("Cluster already exists!")
        print("To create a new cluster, first run \"{0} deallocate\"".format(sys.argv[0]))
        sys.exit(1)
    assert args.size > 0
    print("Spawning cluster...")
    c = cluster.spawn(args.name, args.size)
    c.save_to_file("cluster.json")
    print("Waiting three minutes for the machines to start up...")
    time.sleep(180)
    print("Provisioning the machines...")
    c.for_each_concurrently(provision_machine)
    print("Done.")

def provision(args):
    c = cluster.Cluster.load_from_file("cluster.json")
    print("Provisioning the machines...")
    provision_cluster(c)
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

def run_single(args):
    c = cluster.Cluster.load_from_file("cluster.json")
    if len(sys.argv) not in (6, 7):
        print("Usage: {0} problem_name problem_size protocol scenario [log_tag]".format(sys.argv[0]))
        sys.exit(2)
    problem_name, problem_size = parse_program(args.program)
    if problem_name.startswith("real"):
        protocol = "ckks"
        worker_ids = (0,)
    else:
        protocol = "halfgates"
        worker_ids = (0, 1)
    scenario = args.scenario
    log_name = "{0}_{1}_{2}".format(problem_name, problem_size, scenario)
    if args.tag is not None:
        log_name += "_{0}".format(args.tag)
    experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, worker_ids, log_name)

def run_nonparallel(args):
    if args.programs is None:
        args.programs = ("merge_sorted_1048576", "full_sort_1048576", "loop_join_2048", "matrix_vector_multiply_8192", "binary_fc_layer_16384", "real_sum_65536", "real_statistics_16384", "real_matrix_vector_multiply_256", "real_naive_matrix_multiply_128", "real_tiled_matrix_multiply_128")
    if args.scenarios is None:
        args.scenarios = ("mage", "unbounded", "os")

    c = cluster.Cluster.load_from_file("cluster.json")
    parsed_programs = parse_program_list(args.programs)
    for problem_name, problem_size in parsed_programs:
        if problem_name.startswith("real"):
            protocol = "ckks"
            worker_ids = (0,)
        else:
            protocol = "halfgates"
            worker_ids = (0, 1)
        for trial in range(1, args.trials + 1):
            for scenario in args.scenarios:
                log_name = "single_machine_{0}_{1}_{2}_t{3}".format(problem_name, problem_size, scenario, trial)
                experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, worker_ids, log_name)


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
                    experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, worker_ids, log_name)

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
                    experiment.run_lan_experiment(c, problem_name, problem_size, protocol, scenario, worker_ids, log_name)

def deallocate(args):
    print("Deallocating cluster...")
    cluster.deallocate(CLUSTER_NAME, CLUSTER_SIZE)
    try:
        os.remove("cluster.json")
    except os.FileNotFoundError:
        pass
    print("Done.")

def fetch_logs(args):
    print("Fetching logs...")
    c = cluster.Cluster.load_from_file("cluster.json")
    for id in range(len(c.machines)):
        os.makedirs(logs_directory(id), exist_ok = True)
    c.for_each_concurrently(fetch_logs_from)
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Run benchmark experiments on MAGE.")
    subparsers = parser.add_subparsers()

    parser_spawn = subparsers.add_parser("spawn")
    parser_spawn.add_argument("-n", "--name", default = "mage-cluster")
    parser_spawn.add_argument("-z", "--size", type = int, default = 2)
    parser_spawn.set_defaults(func = spawn)

    parser_provision = subparsers.add_parser("provision")
    parser_provision.set_defaults(func = provision)

    parser_run = subparsers.add_parser("run-single")
    parser_run.add_argument("program")
    parser_run.add_argument("scenario")
    parser_run.add_argument("--tag")
    parser_run.set_defaults(func = run_single)

    parser_run_sce = subparsers.add_parser("run-nonparallel")
    parser_run_sce.add_argument("-p", "--programs", action = "extend", nargs = "+")
    parser_run_sce.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os"))
    parser_run_sce.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_sce.set_defaults(func = run_nonparallel)

    parser_run_hgb = subparsers.add_parser("run-halfgates-baseline")
    parser_run_hgb.add_argument("-z", "--sizes", action = "extend", nargs = "+", type = int)
    parser_run_hgb.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os", "emp"))
    parser_run_hgb.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_hgb.set_defaults(func = run_halfgates_baseline)

    parser_run_ckb = subparsers.add_parser("run-ckks-baseline")
    parser_run_ckb.add_argument("-z", "--sizes", action = "extend", nargs = "+", type = int)
    parser_run_ckb.add_argument("-s", "--scenarios", action = "extend", nargs = "+", choices = ("unbounded", "mage", "os", "seal"))
    parser_run_ckb.add_argument("-t", "--trials", type = int, default = 1)
    parser_run_ckb.set_defaults(func = run_ckks_baseline)

    parser_deallocate = subparsers.add_parser("deallocate")
    parser_deallocate.set_defaults(func = deallocate)

    parser_fetch_logs = subparsers.add_parser("fetch-logs")
    parser_fetch_logs.set_defaults(func = fetch_logs)

    args = parser.parse_args()
    args.func(args)
