import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


HERE = Path(__file__).resolve().parent
HIGHWAY = "a3f6f68fcc368e5e3025ca25805eabda9d8a456f"
X86_SIMD_SORT = "6e059b14975df2e3c74260ec905167a1be5a34ca"
PDQ_SHA256 = "1916aff237fc7ecc638dec6397662334552a1b6f823fa65011a8dfe831237fc0"
FLAGS = ["-O3", "-DNDEBUG", "-std=c++17", "-march=native"]


def capture(*command, cwd=HERE):
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def verify_checkout(path, revision):
    actual = capture("git", "rev-parse", "HEAD", cwd=path)
    changed = capture("git", "status", "--porcelain", "--untracked-files=no", cwd=path)
    if actual != revision or changed:
        raise ValueError(f"{path.name} must have clean tracked files at {revision}")


def processor_name():
    if os.name == "nt":
        import winreg

        key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as registry:
            return winreg.QueryValueEx(registry, "ProcessorNameString")[0].strip()
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        name, _, value = line.partition(":")
        if name.strip() == "model name":
            return value.strip()
    return platform.machine()


def run(args):
    vendor = args.vendor.resolve()
    verify_checkout(vendor / "highway", HIGHWAY)
    verify_checkout(vendor / "x86-simd-sort", X86_SIMD_SORT)
    if hashlib.sha256((vendor / "pdqsort.h").read_bytes()).hexdigest() != PDQ_SHA256:
        raise ValueError("pdqsort.h does not match the registered source")

    output = args.output.resolve()
    output.mkdir(parents=True)
    binary = output / "record-bench.exe"
    link_flags = ["-lpsapi"] if os.name == "nt" else []
    subprocess.run(
        [args.compiler, *FLAGS, "-I", vendor, "-I", vendor / "x86-simd-sort" / "src",
         "-I", vendor / "highway", "bench.cpp", "vq_bridge.cpp",
         vendor / "highway" / "hwy" / "abort.cc", *link_flags, "-o", binary],
        cwd=HERE, check=True,
    )

    metadata = {
        "utc_started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_commit": capture("git", "rev-parse", "HEAD"),
        "cpu": processor_name(),
        "logical_cpu_count": os.cpu_count(),
        "affinity_logical_cpu": args.cpu,
        "thread_count": 1,
        "os": {"name": platform.system(), "release": platform.release(), "version": platform.version()},
        "compiler": capture(args.compiler, "--version").splitlines()[0],
        "flags": FLAGS + link_flags,
        "references": {"highway": HIGHWAY, "x86-simd-sort": X86_SIMD_SORT, "pdqsort_sha256": PDQ_SHA256},
        "cache_eviction_buffer_bytes": 64 * 1024 * 1024,
        "smoke": args.smoke,
    }
    command = [binary, str(args.cpu)]
    if args.smoke:
        command.append("--smoke")
    with (output / "raw.csv").open("w", encoding="utf-8", newline="") as raw:
        process = subprocess.run(command, stdout=raw, stderr=subprocess.PIPE, text=True)
    if process.returncode:
        raise RuntimeError(f"benchmark exited with {process.returncode}: {process.stderr.strip()}")
    metadata["peak_process_resident_bytes"] = int(process.stderr.strip())
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and run the preregistered record-permutation pilot.")
    parser.add_argument("--vendor", type=Path, required=True, help="directory containing the pinned sources")
    parser.add_argument("--output", type=Path, required=True, help="new directory for the binary and results")
    parser.add_argument("--cpu", type=int, default=4, help="logical CPU on which to pin the benchmark thread")
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--smoke", action="store_true", help="check the four paths on small development inputs")
    arguments = parser.parse_args()
    if arguments.cpu < 0:
        parser.error("--cpu must be nonnegative")
    run(arguments)
