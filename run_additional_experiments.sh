#!/usr/bin/env bash

baseline_start=$(date +%s)
./magebench.py spawn -a 2
./magebench.py run-halfgates-baseline -t 1 -s os unbounded mage emp -z 1024 2048 4096 8192 16384 32768 65536 131072 262144 524288 1048576
./magebench.py run-ckks-baseline -t 1 -s os unbounded mage seal -z 64 128 256 512 1024 2048 4096 8192 16384
./magebench.py fetch-logs logs-baseline
./magebench.py deallocate
baseline_end=$(date +%s)
echo "Baseline:" $(expr $baseline_end - $baseline_start) | tee baseline_time

ten_single_start=$(date +%s)
./magebench.py spawn -a 8
./magebench.py run-lan -p merge_sorted_1048576 full_sort_1048576 loop_join_2048 matrix_vector_multiply_8192 binary_fc_layer_16384 real_sum_65536 real_statistics_16384 real_matrix_vector_multiply_256 real_naive_matrix_multiply_128 real_tiled_16_matrix_multiply_128 -s unbounded mage os -t 1 -n 1
./magebench.py fetch-logs logs-workloads-2
./magebench.py deallocate
ten_single_end=$(date +%s)
echo "Ten Single:" $(expr $ten_single_end - $ten_single_start) | tee ten_single_time

ten_single_16gib_start=$(date +%s)
./magebench.py spawn -a 16
./magebench.py run-lan -p merge_sorted_8388608 loop_join_3840 matrix_vector_multiply_20480 -s os unbounded mage -t 1 -n 1 -m 16gb
./magebench.py fetch-logs logs-16gib-workloads-2
./magebench.py deallocate

./magebench.py spawn -a 16
./magebench.py run-lan -p binary_fc_layer_57344 -s os unbounded mage -t 1 -n 1 -m 16gb
./magebench.py fetch-logs logs-16gib-workloads-2
./magebench.py deallocate

./magebench.py spawn -a 16
./magebench.py run-lan -p real_sum_458752 real_statistics_147456 real_matrix_vector_multiply_448 real_naive_matrix_multiply_256 real_tiled_64_matrix_multiply_224 -s os unbounded mage -t 1 -n 1 -m 16gb
./magebench.py fetch-logs logs-16gib-workloads-2
./magebench.py deallocate
ten_single_16gib_end=$(date +%s)
echo "Ten Single 16GiB:" $(expr $ten_single_16gib_end - $ten_single_16gib_start) | tee ten_single_16gib_time

ten_parallel_start=$(date +%s)
./magebench.py spawn -a 8
./magebench.py run-lan -p merge_sorted_4194304 full_sort_4194304 loop_join_4096 matrix_vector_multiply_16384 binary_fc_layer_32768 real_sum_262144 real_statistics_65536 real_matrix_vector_multiply_512 real_naive_matrix_multiply_256 real_tiled_16_matrix_multiply_256 -s unbounded mage os -t 1 -n 4
./magebench.py fetch-logs logs-workloads-8
./magebench.py deallocate
ten_parallel_end=$(date +%s)
echo "Ten Parallel:" $(expr $ten_parallel_end - $ten_parallel_start) | tee ten_parallel_time

wan_ot_start=$(date +%s)
./magebench.py spawn -a 1 -g oregon iowa
./magebench.py run-wan oregon -p merge_sorted_1048576 -s mage -t 15 -w 1 -o 2 4 8 16 32 64 128 256 -c 1
./magebench.py run-wan iowa -p merge_sorted_1048576 -s mage -t 15 -w 1 -o 2 4 8 16 32 64 128 256 -c 1
./magebench.py fetch-logs logs-wan-ot
./magebench.py deallocate
wan_ot_end=$(date +%s)
echo "WAN OT:" $(expr $wan_ot_end - $wan_ot_start) | tee wan_ot_time

wan_conn_start=$(date +%s)
./magebench.py spawn -a 1 -g oregon iowa
./magebench.py run-wan oregon -p merge_sorted_1048576 -s mage -t 15 -w 1 2 4 -o 128 -c 1
./magebench.py run-wan iowa -p merge_sorted_1048576 -s mage -t 15 -w 1 2 4 -o 128 -c 1
./magebench.py fetch-logs logs-wan-conn
./magebench.py deallocate
wan_conn_end=$(date +%s)
echo "WAN Conn:" $(expr $wan_conn_end - $wan_conn_start) | tee wan_conn_time

password_start=$(date +%s)
./magebench.py spawn -a 4 -g oregon -s paired-noswap
./magebench.py run-paired-wan oregon -p password_134217728 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_67108864 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_33554432 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_16777216 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_8388608 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_4194304 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_2097152 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_1048576 -s mage -t 1 -w 2 -o 128 -c 1
./magebench.py fetch-logs logs-password-4
./magebench.py deallocate

./magebench.py spawn -a 4 -g oregon -s paired-swap
./magebench.py run-paired-wan oregon -p password_67108864 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_33554432 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_16777216 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_8388608 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_4194304 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_2097152 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py run-paired-wan oregon -p password_1048576 -s os -t 1 -w 2 -o 128 -c 1
./magebench.py fetch-logs logs-password-4
./magebench.py deallocate
password_end=$(date +%s)
echo "Password Reuse:" $(expr $password_end - $password_start) | tee password_time

cpir_start=$(date +%s)
./magebench.py spawn -a 8 -s paired-noswap
./magebench.py run-lan -p real_cpir_256 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_384 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_512 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_640 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_768 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_896 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1024 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1158 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1280 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1408 -s mage -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1536 -s mage -m max -t 1 -n 1
./magebench.py fetch-logs logs-cpir
./magebench.py deallocate

./magebench.py spawn -a 8 -s paired-swap
./magebench.py run-lan -p real_cpir_256 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_384 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_512 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_640 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_768 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_896 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1024 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1158 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1280 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1408 -s os -m max -t 1 -n 1
./magebench.py run-lan -p real_cpir_1536 -s os -m max -t 1 -n 1
./magebench.py fetch-logs logs-cpir
./magebench.py deallocate
cpir_end=$(date +%s)
echo "Computational PIR:" $(expr $cpir_end - $cpir_start) | tee password_time
