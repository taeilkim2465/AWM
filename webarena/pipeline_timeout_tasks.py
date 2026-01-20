"""
Pipeline for running specific timeout tasks with reasoning bank
Based on pipeline_reasoning_bank.py but accepts specific task IDs
"""
import os
import shutil
import json
import argparse
import time
import signal
from subprocess import Popen, TimeoutExpired
from cost_tracker import calculate_total_cost, LOG_FILE

def _log_timeout_task(tid):
    with open("./timeout_tasks.jsonl", "a") as f:
        f.write(json.dumps({"task_id": tid}) + "\n")

def run_task(tid, reasoning_bank_path, website, retrieve_type):
    """Run a single task: inference + evaluation with reasoning bank"""
    TASK_TIMEOUT = 1800  # 30 minutes
    start_time = time.time()

    # step 1: run inference
    cmd = [
        "python", "run.py",
        "--task_name", f"webarena.{tid}",
        "--enable_reasoning_bank", "True"
    ]

    if reasoning_bank_path:
        cmd.extend(["--reasoning_bank_path", reasoning_bank_path])

    if retrieve_type:
        cmd.extend(["--retrieve_type", retrieve_type])

    # Ensure environment variables are set
    env = os.environ.copy()
    env.update({
        'WA_SHOPPING': 'http://10.10.0.120:7770',
        'WA_SHOPPING_ADMIN': 'http://10.10.0.120:7780/admin',
        'WA_REDDIT': 'http://10.10.0.120:9999',
        'WA_GITLAB': 'http://10.10.0.120:8023',
        'WA_WIKIPEDIA': 'http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing',
        'WA_MAP': 'http://10.10.0.120:3000',
        'WA_HOMEPAGE': 'http://10.10.0.120:4399',
        'SHOPPING': 'http://10.10.0.120:7770',
        'SHOPPING_ADMIN': 'http://10.10.0.120:7780/admin',
        'REDDIT': 'http://10.10.0.120:9999',
        'GITLAB': 'http://10.10.0.120:8023',
        'WIKIPEDIA': 'http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing',
        'MAP': 'http://10.10.0.120:3000',
        'HOMEPAGE': 'http://10.10.0.120:4399',
    })

    process = Popen(cmd, start_new_session=True, env=env)

    try:
        process.wait(timeout=TASK_TIMEOUT)
    except TimeoutExpired:
        print(f"Task {tid} timed out during inference after {TASK_TIMEOUT} seconds. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        return tid

    time_left = TASK_TIMEOUT - (time.time() - start_time)
    if time_left <= 0:
        print(f"Task {tid} ran out of time after inference step.")
        _log_timeout_task(tid)
        return tid

    # step 2: run evaluation
    process = Popen([
        "python", "-m", "autoeval.evaluate_trajectory",
        "--result_dir", f"results/webarena.{tid}"
    ], start_new_session=True, env=env)

    try:
        process.wait(timeout=time_left)
    except TimeoutExpired:
        print(f"Task {tid} timed out during evaluation. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        return tid

    # step 3: update reasoning bank
    if reasoning_bank_path:
        time_left = TASK_TIMEOUT - (time.time() - start_time)
        if time_left <= 0:
            print(f"Task {tid} ran out of time before reasoning bank update.")
            _log_timeout_task(tid)
            return tid

        cmd = [
            "python", "-m", "utils.reasoning_bank",
            "--result_dir", f"results/webarena.{tid}",
            "--reasoning_bank_path", reasoning_bank_path
        ]
        process = Popen(cmd, start_new_session=True, env=env)

        try:
            process.wait(timeout=time_left)
        except TimeoutExpired:
            print(f"Task {tid} timed out during reasoning bank update. Terminating process group.")
            _log_timeout_task(tid)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            return tid

    # Move the result directory
    source_dir = f"results/webarena.{tid}"
    dest_dir = f"results/{website}"

    try:
        if os.path.exists(source_dir):
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(source_dir, dest_dir)
            print(f"Moved result for task {tid} to {dest_dir}")
        else:
            print(f"Source directory {source_dir} not found for moving.")
    except (IOError, os.error, shutil.Error) as e:
        print(f"Error moving directory for task {tid}: {e}")

    print(f"################## Task {tid} Finished ##################")
    return tid

def main():
    # Get task IDs from arguments
    task_ids = args.task_ids

    print(f"Running {len(task_ids)} tasks with reasoning_bank={args.reasoning_bank_path}")

    # Ensure reasoning bank directory exists
    if args.reasoning_bank_path:
        os.makedirs(os.path.dirname(args.reasoning_bank_path), exist_ok=True)

    # Run tasks sequentially
    for tid in task_ids:
        run_task(tid, args.reasoning_bank_path, args.website, args.retrieve_type)
        calculate_total_cost()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "shopping_admin", "gitlab", "reddit", "map", "wikipedia"])
    parser.add_argument("--task_ids", type=int, nargs='+', required=True,
                        help="List of task IDs to run")
    parser.add_argument("--reasoning_bank_path", type=str, default="data/reasoning_bank.json",
                        help="Path to Reasoning Bank JSON file")
    parser.add_argument("--retrieve_type", type=str, default="bm25", choices=["embedding", "bm25"],
                        help="Type of retrieval method for reasoning bank")
    args = parser.parse_args()

    main()
