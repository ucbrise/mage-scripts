import time
import remote

def party_from_global_id(cluster, global_id):
    if global_id < len(cluster.machines) // 2:
        return 0 # evaluator
    else:
        return 1 # garbler

def clear_memory_caches(cluster, worker_ids):
    cluster.for_each_concurrently(lambda machine, id: remote.exec_sync(machine.public_ip_address, "sudo swapoff -a; sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"), worker_ids)

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
        if scenario == "mage":
            log_name_to_use = log_name
        else:
            # So we don't count this as a "planning" measurement
            log_name_to_use = ""
        remote.exec_script(machine.public_ip_address, "./scripts/generate_memprog.sh", "{0} {1} {2} {3} {4} {5} {6}".format(problem_name, problem_size, protocol, config_file, party, local_id, log_name_to_use))

    if generate_fresh_memprog:
        cluster.for_each_concurrently(generate_memprog, worker_ids)

    def run_mage(machine, global_id):
        party = party_from_global_id(cluster, global_id)
        local_id = global_id % workers_per_party
        if party == 1:
            time.sleep(30) # Wait for the evaluator to start first
        remote.exec_script(machine.public_ip_address, "./scripts/run_mage.sh", "{0} {1} {2} {3} {4} {5} {6} {7}".format(scenario, protocol, config_file, party, local_id, program_name, log_name, "true"))

    if protocol != "ckks":
        time.sleep(70) # Wait for TIME-WAIT state to expire
    clear_memory_caches(cluster, worker_ids)
    cluster.for_each_concurrently(run_mage, worker_ids)

def run_halfgates_baseline_experiment(cluster, problem_size, scenario, worker_ids, log_name = "/dev/null"):
    assert len(worker_ids) == 2
    if not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string (got {0})".format(repr(log_name)))

    def run_halfgates_baseline(machine, global_id):
        party = party_from_global_id(cluster, global_id)
        if party == 1:
            time.sleep(30)
        if global_id == worker_ids[0]:
            other_worker_id = worker_ids[1]
        else:
            assert global_id == worker_ids[1]
            other_worker_id = worker_ids[0]
        remote.exec_script(machine.public_ip_address, "./scripts/run_halfgates_baseline.sh", "{0} {1} {2} {3} {4}".format(scenario, party, problem_size, cluster.machines[other_worker_id].private_ip_address, log_name))

    time.sleep(70)
    clear_memory_caches(cluster, worker_ids)
    cluster.for_each_concurrently(run_halfgates_baseline, worker_ids)

def run_ckks_baseline_experiment(cluster, problem_size, scenario, worker_ids, log_name = "/dev/null", generate_fresh_input = True):
    if not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string (got {0})".format(repr(log_name)))

    def generate_input(machine, global_id):
        remote.exec_script(machine.public_ip_address, "./scripts/generate_input.sh", "{0} {1} {2} {3} {4}".format("real_statistics", problem_size, "ckks", 0, 1))

    if generate_fresh_input:
        cluster.for_each_concurrently(generate_input, worker_ids)

    def run_ckks_baseline(machine, global_id):
        remote.exec_script(machine.public_ip_address, "./scripts/run_ckks_baseline.sh", "{0} {1} {2}".format(scenario, problem_size, log_name))

    # time.sleep(70)
    clear_memory_caches(cluster, worker_ids)
    cluster.for_each_concurrently(run_ckks_baseline, worker_ids)