"""Build and run the registered host-to-host GPU sort probe on Windows."""

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from itertools import product
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = ROOT / "runs/2026-11-24-gpu-sort-return/protocol.md"
FLAGS = ["-O3", "--std=c++17", "-arch=sm_86", "--expt-relaxed-constexpr", "--use-local-env",
         "-Xcompiler=/O2,/arch:AVX2,/EHsc"]
METHODS = {"raw", "raw_tiles", "prefix_serial", "prefix_overlap", "frame_serial", "frame_overlap"}
PRIMARY = ((16777216, "uniform"), (67108864, "uniform"))
CONTROL = (16777216, "edge_clusters")
SEEDS = {"development": (59021, 91457), "holdout": (133241, 177463)}


def output(command):
    return subprocess.check_output(command, encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command_executable(name):
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"missing {name}")
    return Path(path).resolve()


def vcvars_path(cl):
    for parent in cl.parents:
        candidate = parent / "VC/Auxiliary/Build/vcvars64.bat"
        if candidate.is_file():
            return candidate
    raise SystemExit("could not locate the Visual Studio x64 environment setup")


def batch_quote(value):
    value = str(value)
    if any(character in value for character in ('"', '%', '!', '\r', '\n')):
        raise ValueError("unsupported character in a build path")
    return '"' + value + '"'


def build(executable, nvcc):
    cl = command_executable("cl")
    setup = vcvars_path(cl)
    toolset = next((p.name for p in cl.parents if p.parent.name == "MSVC"), None)
    if not toolset:
        raise SystemExit("could not determine the installed MSVC toolset")
    version_selector = ".".join(toolset.split(".")[:2])
    compile_arguments = [nvcc, *FLAGS, HERE / "bench.cu", "-o", executable]
    lines = [
        "@echo off",
        f"call {batch_quote(setup)} -vcvars_ver={version_selector} >nul",
        "if errorlevel 1 exit /b %errorlevel%",
        " ".join(batch_quote(arg) for arg in compile_arguments),
        "exit /b %errorlevel%",
    ]
    script = executable.parent / "build.bat"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")
    compiler_scratch = executable.parent / "compiler-scratch"
    compiler_scratch.mkdir(exist_ok=True)
    build_env = {**os.environ, "TEMP": str(compiler_scratch), "TMP": str(compiler_scratch)}
    subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "build.bat"],
                   cwd=executable.parent, env=build_env, check=True)
    result = output([str(executable), "--verify"])
    (executable.parent / "verification.txt").write_text(result, encoding="utf-8", newline="\n")
    print(result, end="", flush=True)


def host_processor():
    import winreg

    path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("work", type=Path)
    parser.add_argument("--cpu", default=8, type=int)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    raw = work / f"{args.stage}.csv"
    metadata = work / f"{args.stage}-metadata.json"
    if raw.exists() or metadata.exists():
        raise SystemExit("measurements already exist")
    executable = work / "bench.exe"
    nvcc = command_executable("nvcc")
    source_hashes = {p.relative_to(ROOT).as_posix(): digest(p)
                     for p in (PROTOCOL, HERE / "bench.cu", HERE / "run.py")}
    if args.stage == "development":
        build(executable, nvcc)
    else:
        prior = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if digest(executable) != prior["binary_sha256"] or source_hashes != prior["source_sha256"]:
            raise SystemExit("holdout requires the unchanged development build")
    names = ("name", "compute_capability", "device_bytes", "driver_api", "runtime", "cub", "msvc")
    gpu = dict(zip(names, output([str(executable), "--version"]).splitlines(), strict=True))
    for name in ("device_bytes", "driver_api", "runtime", "cub", "msvc"):
        gpu[name] = int(gpu[name])
    gpu["nvidia_driver"] = output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]).splitlines()[0]

    shapes = (*PRIMARY, CONTROL) if args.stage == "development" else PRIMARY
    header = None
    lines = []
    count = 0
    started = datetime.now(timezone.utc)
    for (rows, distribution), seed in product(shapes, SEEDS[args.stage]):
        result = output([str(executable), str(rows), distribution, str(seed), str(args.cpu)])
        current = result.splitlines(keepends=True)
        if header is None:
            header = current[0]
            lines.append(header)
        samples = list(csv.DictReader(io.StringIO(result)))
        expected = set(product(METHODS, range(9)))
        actual = {(s["method"], int(s["round"])) for s in samples}
        if (current[0] != header or len(samples) != len(expected) or actual != expected
                or any(s["verified"] != "true" or int(s["total_ns"]) <= 0 for s in samples)):
            raise RuntimeError(f"incomplete or unverified case {rows} {distribution} {seed}")
        count += len(samples)
        lines.extend(current[1:])
        print(f"{rows} {distribution} seed {seed}: {len(samples)} calls verified", flush=True)
    finished = datetime.now(timezone.utc)
    with raw.open("x", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    data = {
        "stage": args.stage,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "gpu": gpu,
        "host_processor": host_processor(),
        "platform": platform.platform(),
        "logical_cpu": args.cpu,
        "host_threads": 1,
        "streams": 1,
        "nvcc_version": output([str(nvcc), "--version"]).splitlines(),
        "flags": FLAGS,
        "source_sha256": source_hashes,
        "binary_sha256": digest(executable),
        "raw_sha256": digest(raw),
        "verified_calls": count,
        "warmups": 2,
        "measured_calls_per_method": 7,
        "model": "gpt-6.2-sol",
        "tokens": "not captured",
        "reasoning_setting": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"Verified {count} complete host-to-host sorts", flush=True)


if __name__ == "__main__":
    main()
