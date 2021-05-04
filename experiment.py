import time
import remote

def wan_party_from_global_id(cluster, global_id):
    if global_id < cluster.num_lan_machines:
        return 1 # garbler
    else:
        return 0 # evaluator

def party_from_global_id(cluster, global_id):
    if global_id < cluster.num_lan_machines // 2:
        return 0 # evaluator
    else:
        return 1 # garbler

def clear_memory_caches(cluster, node_ids):
    cluster.for_each_concurrently(lambda machine, id: remote.exec_sync(machine.public_ip_address, "sudo swapoff -a; sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"), node_ids)

def clear_output_files(cluster, node_ids, prefix):
    cluster.for_each_concurrently(lambda machine, id: remote.exec_sync(machine.public_ip_address, "rm -f ~/work/mage/bin/{0}* ~/work/scratch/*".format(prefix)), node_ids)

def run_paired_wan_experiment(cluster, problem_name, problem_size, scenario, mem_limit, location, log_name, workers_per_node, nodes_per_party, ot_pipeline_depth, ot_num_daemons, generate_fresh_input = True, generate_fresh_memprog = True):
    protocol = "halfgates"
    program_name = "{0}_{1}".format(problem_name, problem_size)
    config_file = "~/config-{0}-paired/{1}/config_{2}_{3}_{4}_{5}.yaml".format(location, mem_limit if scenario == "mage" else "unbounded", protocol, workers_per_node * nodes_per_party, ot_pipeline_depth, ot_num_daemons)

    log_prefix = program_name + "_" + location
    if isinstance(log_name, int):
        log_name = log_prefix + "_t{1}".format(location, log_name)
    elif log_name is None:
        log_name = log_prefix
    elif not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string, int or None (got {0})".format(repr(log_name)))

    node_ids = list(range(nodes_per_party)) + list(range(cluster.location_to_id[location], cluster.location_to_id[location] + nodes_per_party))
    def copy_scripts(machine, global_id):
        for script in ("./scripts/generate_input.sh", "./scripts/generate_memprog.sh", "./scripts/run_mage.sh"):
            remote.copy_to(machine.public_ip_address, False, script)
    cluster.for_each_concurrently(copy_scripts, node_ids)

    def generate_input(machine, global_id, thread_id):
        id = ((global_id * workers_per_node) + thread_id) % (workers_per_node * nodes_per_party)
        remote.exec_sync(machine.public_ip_address, "~/generate_input.sh {0} {1} {2} {3} {4}".format(problem_name, problem_size, protocol, id, workers_per_node * nodes_per_party))
    if generate_fresh_input:
        cluster.for_each_multiple_concurrently(generate_input, workers_per_node, node_ids)

    def generate_memprog(machine, global_id):
        party = wan_party_from_global_id(cluster, global_id)
        for thread_id in range(workers_per_node):
            id = ((global_id * workers_per_node) + thread_id) % (workers_per_node * nodes_per_party)
            if scenario == "mage":
                log_name_to_use = "{0}_w{1}".format(log_name, id)
            else:
                # So we don't count this as a "planning" measurement
                log_name_to_use = ""
            remote.exec_sync(machine.public_ip_address, "~/generate_memprog.sh {0} {1} {2} {3} {4} {5} {6}".format(problem_name, problem_size, protocol, config_file, party, id, log_name_to_use))
    if generate_fresh_memprog:
        cluster.for_each_concurrently(generate_memprog, node_ids)

    def run_mage(machine, global_id, thread_id):
        party = wan_party_from_global_id(cluster, global_id)
        id = ((global_id * workers_per_node) + thread_id) % (workers_per_node * nodes_per_party)
        time.sleep(10 * id)
        if party == 1:
            time.sleep(10 * workers_per_node * nodes_per_party + 20) # Wait for all evaluator workers to start first
        log_name_to_use = "{0}_w{1}".format(log_name, id)
        remote.exec_sync(machine.public_ip_address, "~/run_mage.sh {0} {1} {2} {3} {4} {5} {6} {7} {8}".format(scenario, mem_limit, protocol, config_file, party, id, program_name, log_name_to_use, "true"))

    if protocol != "ckks":
        time.sleep(70) # Wait for TIME-WAIT state to expire
    clear_memory_caches(cluster, node_ids)
    cluster.for_each_multiple_concurrently(run_mage, workers_per_node, node_ids)
    clear_output_files(cluster, node_ids, problem_name)

def run_wan_experiment(cluster, problem_name, problem_size, scenario, mem_limit, location, log_name, workers_per_node, ot_pipeline_depth, ot_num_daemons, generate_fresh_input = True, generate_fresh_memprog = True):
    protocol = "halfgates"
    program_name = "{0}_{1}".format(problem_name, problem_size)
    config_file = "~/config-{0}/{1}/config_{2}_{3}_{4}_{5}.yaml".format(location, "1gb" if scenario == "mage" else "unbounded", protocol, workers_per_node, ot_pipeline_depth, ot_num_daemons)

    log_prefix = program_name + "_" + location
    if isinstance(log_name, int):
        log_name = log_prefix + "_t{1}".format(location, log_name)
    elif log_name is None:
        log_name = log_prefix
    elif not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string, int or None (got {0})".format(repr(log_name)))

    node_ids = (0, cluster.location_to_id[location])
    def copy_scripts(machine, global_id):
        for script in ("./scripts/generate_input.sh", "./scripts/generate_memprog.sh", "./scripts/run_mage.sh"):
            remote.copy_to(machine.public_ip_address, False, script)
    cluster.for_each_concurrently(copy_scripts, node_ids)

    def generate_input(machine, global_id, thread_id):
        remote.exec_sync(machine.public_ip_address, "~/generate_input.sh {0} {1} {2} {3} {4}".format(problem_name, problem_size, protocol, thread_id, workers_per_node))
    if generate_fresh_input:
        cluster.for_each_multiple_concurrently(generate_input, workers_per_node, node_ids)

    def generate_memprog(machine, global_id, thread_id):
        party = wan_party_from_global_id(cluster, global_id)
        if scenario == "mage":
            log_name_to_use = "{0}_w{1}".format(log_name, thread_id)
        else:
            # So we don't count this as a "planning" measurement
            log_name_to_use = ""
        remote.exec_sync(machine.public_ip_address, "~/generate_memprog.sh {0} {1} {2} {3} {4} {5} {6}".format(problem_name, problem_size, protocol, config_file, party, thread_id, log_name_to_use))
    if generate_fresh_memprog:
        cluster.for_each_multiple_concurrently(generate_memprog, workers_per_node, node_ids)

    def run_mage(machine, global_id, thread_id):
        party = wan_party_from_global_id(cluster, global_id)
        time.sleep(10 * thread_id)
        if party == 1:
            time.sleep(10 * workers_per_node + 20) # Wait for all evaluator workers to start first
        log_name_to_use = "{0}_w{1}".format(log_name, thread_id)
        remote.exec_sync(machine.public_ip_address, "~/run_mage.sh {0} {1} {2} {3} {4} {5} {6} {7} {8}".format(scenario, mem_limit, protocol, config_file, party, thread_id, program_name, log_name_to_use, "true"))

    if protocol != "ckks":
        time.sleep(70) # Wait for TIME-WAIT state to expire
    clear_memory_caches(cluster, node_ids)
    cluster.for_each_multiple_concurrently(run_mage, workers_per_node, node_ids)

def run_multiworker_lan_experiment(cluster, problem_name, problem_size, protocol, scenario, mem_limit, node_ids, log_name = "/dev/null", workers_per_node = 1, nodes_per_party = None, generate_fresh_input = True, generate_fresh_memprog = True):
    if nodes_per_party is None:
        if protocol == "halfgates":
            assert len(node_ids) % 2 == 0
            nodes_per_party = len(node_ids) // 2
        elif protocol == "ckks":
            nodes_per_party = len(node_ids)
        else:
            raise RuntimeError("Unknown protocol {0}".format(protocol))

    assert len(cluster.machines) == cluster.num_lan_machines

    program_name = "{0}_{1}".format(problem_name, problem_size)
    config_file = "~/config/{0}/config_{1}_{2}_{3}.yaml".format(mem_limit if scenario == "mage" else "unbounded", protocol, nodes_per_party, workers_per_node)

    if isinstance(log_name, int):
        log_name = program_name + "_t{0}".format(log_name)
    elif log_name is None:
        log_name = program_name
    elif not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string, int, or None (got {0})".format(repr(log_name)))

    def generate_input(machine, global_id, thread_id):
        local_id = ((global_id % nodes_per_party) * workers_per_node) + thread_id
        remote.exec_script(machine.public_ip_address, "./scripts/generate_input.sh", "{0} {1} {2} {3} {4}".format(problem_name, problem_size, protocol, local_id, workers_per_node * nodes_per_party))

    if generate_fresh_input:
        cluster.for_each_multiple_concurrently(generate_input, workers_per_node, node_ids)

    def generate_memprog(machine, global_id):
        party = party_from_global_id(cluster, global_id)
        for thread_id in range(workers_per_node):
            local_id = ((global_id % nodes_per_party) * workers_per_node) + thread_id
            if scenario == "mage":
                log_name_to_use = "{0}_w{1}".format(log_name, local_id)
            else:
                # So we don't count this as a "planning" measurement
                log_name_to_use = ""
            remote.exec_script(machine.public_ip_address, "./scripts/generate_memprog.sh", "{0} {1} {2} {3} {4} {5} {6}".format(problem_name, problem_size, protocol, config_file, party, local_id, log_name_to_use))

    if generate_fresh_memprog:
        cluster.for_each_concurrently(generate_memprog, node_ids)

    def run_mage(machine, global_id, thread_id):
        party = party_from_global_id(cluster, global_id)
        local_id = ((global_id % nodes_per_party) * workers_per_node) + thread_id
        time.sleep(10 * local_id)
        if party == 1:
            time.sleep(10 * workers_per_node * nodes_per_party + 20) # Wait for all evaluator workers to start first
        log_name_to_use = "{0}_w{1}".format(log_name, local_id)
        remote.exec_script(machine.public_ip_address, "./scripts/run_mage.sh", "{0} {1} {2} {3} {4} {5} {6} {7} {8}".format(scenario, mem_limit, protocol, config_file, party, local_id, program_name, log_name_to_use, "true"))

    if protocol != "ckks":
        time.sleep(70) # Wait for TIME-WAIT state to expire
    clear_memory_caches(cluster, node_ids)
    cluster.for_each_multiple_concurrently(run_mage, workers_per_node, node_ids)

def run_lan_experiment(cluster, problem_name, problem_size, protocol, scenario, mem_limit, worker_ids, log_name = "/dev/null", workers_per_party = None, generate_fresh_input = True, generate_fresh_memprog = True):
    if workers_per_party is None:
        if protocol == "halfgates":
            assert len(worker_ids) % 2 == 0
            workers_per_party = len(worker_ids) // 2
        elif protocol == "ckks":
            workers_per_party = len(worker_ids)
        else:
            raise RuntimeError("Unknown protocol {0}".format(protocol))

    assert len(cluster.machines) == cluster.num_lan_machines

    program_name = "{0}_{1}".format(problem_name, problem_size)
    config_file = "~/config/{0}/config_{1}_{2}_{3}.yaml".format(mem_limit if scenario == "mage" else "unbounded", protocol, workers_per_party, 1)

    if isinstance(log_name, int):
        log_name = program_name + "_t{0}".format(log_name)
    elif log_name is None:
        log_name = program_name
    elif not isinstance(log_name, str):
        raise RuntimeError("log_name must be a string, int, or None (got {0})".format(repr(log_name)))

    def generate_input(machine, global_id):
        local_id = global_id % workers_per_party
        remote.exec_script(machine.public_ip_address, "./scripts/generate_input.sh", "{0} {1} {2} {3} {4}".format(problem_name, problem_size, protocol, local_id, workers_per_party))

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
        time.sleep(10 * local_id)
        if party == 1:
            time.sleep(10 * workers_per_party + 20) # Wait for all evaluator workers to start first
        remote.exec_script(machine.public_ip_address, "./scripts/run_mage.sh", "{0} {1} {2} {3} {4} {5} {6} {7} {8}".format(scenario, mem_limit, protocol, config_file, party, local_id, program_name, log_name, "true"))

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
