#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo 'usage: bash run.sh NEW_OUTPUT_DIRECTORY [--candidate|--disjoint-batches] [--smoke]' >&2
    exit 2
fi
variant=pilot
smoke=()
for option in "${@:2}"; do
    case "$option" in
        --candidate) variant=candidate ;;
        --disjoint-batches) variant=disjoint ;;
        --smoke) smoke=(--smoke) ;;
        *) printf 'unknown option: %s\n' "$option" >&2; exit 2 ;;
    esac
done

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build=$(mktemp -d)
trap 'rm -f -- "$build/bench"; rmdir -- "$build"' EXIT
mkdir -- "$1"
output=$(cd -- "$1" && pwd)
compiler=${CXX:-g++}
cpu=${PAGE_MERGE_CPU:-4}
flags=(-O3 -DNDEBUG -std=c++20 -march=native -Wall -Wextra -Wpedantic)
"$compiler" "${flags[@]}" "$source_dir/bench.cpp" -o "$build/bench"

{
    echo "source_commit=$(git -C "$source_dir" rev-parse HEAD)"
    echo "utc_started=$(date -u +%FT%TZ)"
    echo "kernel=$(uname -r)"
    awk -F= '/^PRETTY_NAME=/{print "os=" $2}' /etc/os-release
    awk -F': *' '/^model name/{print "processor=" $2; exit}' /proc/cpuinfo
    awk '/^MemTotal:|^MemAvailable:/{print $1 " " $2 " " $3}' /proc/meminfo
    echo "logical_cpu_count=$(getconf _NPROCESSORS_ONLN)"
    echo "page_bytes=$(getconf PAGESIZE)"
    echo "affinity_logical_cpu=$cpu"
    echo "thread_count=1"
    echo "compiler=$("$compiler" -dumpfullversion -dumpversion)"
    echo "flags=${flags[*]}"
    echo "variant=$variant"
    getconf GNU_LIBC_VERSION
    for setting in enabled shmem_enabled; do
        path="/sys/kernel/mm/transparent_hugepage/$setting"
        if [[ -r $path ]]; then
            printf 'thp_%s=' "$setting"
            cat -- "$path"
        fi
    done
    echo "max_map_count=$(cat /proc/sys/vm/max_map_count)"
    echo "load_before=$(cut -d ' ' -f 1-3 /proc/loadavg)"
} > "$output/metadata.txt"

if [[ $variant == pilot ]]; then
    taskset -c "$cpu" "$build/bench" calibrate "${smoke[@]}" > "$output/calibration.csv" 2>> "$output/metadata.txt"
    taskset -c "$cpu" "$build/bench" merge "${smoke[@]}" > "$output/merge.csv" 2>> "$output/metadata.txt"
elif [[ $variant == candidate ]]; then
    taskset -c "$cpu" "$build/bench" candidate "${smoke[@]}" > "$output/candidate.csv" 2>> "$output/metadata.txt"
else
    taskset -c "$cpu" "$build/bench" disjoint "${smoke[@]}" > "$output/disjoint.csv" 2>> "$output/metadata.txt"
fi
echo "utc_finished=$(date -u +%FT%TZ)" >> "$output/metadata.txt"
