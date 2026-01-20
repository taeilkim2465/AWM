import os
import shutil
import json
import argparse
import time
import signal
from subprocess import Popen, TimeoutExpired
from cost_tracker import calculate_total_cost, LOG_FILE
from concurrent.futures import ProcessPoolExecutor, as_completed

def _log_timeout_task(tid):
    with open("./timeout_tasks.jsonl", "a") as f:
        f.write(json.dumps({"task_id": tid}) + "\n")

def run_task(tid, reasoning_bank_path, website, retrieve_type):
    """Run a single task: inference + evaluation with reasoning bank"""
    TASK_TIMEOUT = 1000  # 16 minutes
    start_time = time.time()

    # step 1: run inference
    cmd = [
        "python", "run.py",
        "--task", f"webarena.{tid}",
        "--enable_reasoning_bank", "True"
    ]

    if reasoning_bank_path:
        cmd.extend(["--reasoning_bank_path", reasoning_bank_path])
    
    if retrieve_type:
        cmd.extend(["--retrieve_type", retrieve_type])

    # Using start_new_session=True to create a new process group
    # This allows us to kill the process and all its children.
    process = Popen(cmd, start_new_session=True)

    try:
        process.wait(timeout=TASK_TIMEOUT)
    except TimeoutExpired:
        print(f"Task {tid} timed out during inference after {TASK_TIMEOUT} seconds. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass # process already terminated
        process.wait()  # Clean up the zombie process
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
    ], start_new_session=True)
    
    try:
        process.wait(timeout=time_left)
    except TimeoutExpired:
        print(f"Task {tid} timed out during evaluation. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass # process already terminated
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
        process = Popen(cmd, start_new_session=True)
        
        try:
            process.wait(timeout=time_left)
        except TimeoutExpired:
            print(f"Task {tid} timed out during reasoning bank update. Terminating process group.")
            _log_timeout_task(tid)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass # process already terminated
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
    except (IOError, os.Error) as e:
        print(f"Error moving directory for task {tid}: {e}")
        
    print(f"################## Task {tid} Finished ##################")
    return tid

def main():
    # collect examples
    config_files = [
        os.path.join("config_files", f) for f in os.listdir("config_files")
        if f.endswith(".json") and f.split(".")[0].isdigit()
    ]
    config_files = sorted(config_files, key=lambda x: int(x.split("/")[-1].split(".")[0]))
    config_list = [json.load(open(f)) for f in config_files]
    config_flags = [config["sites"][0] == args.website for config in config_list]
    task_ids = [config["task_id"] for config, flag in zip(config_list, config_flags) if flag]

    if args.end_index == None: args.end_index = len(task_ids)
    task_ids = task_ids[args.start_index: args.end_index]

    # Ensure reasoning bank directory exists
    if args.reasoning_bank_path:
        os.makedirs(os.path.dirname(args.reasoning_bank_path), exist_ok=True)

    if args.parallel > 1:
        # Run tasks in parallel
        print(f"Running {len(task_ids)} tasks with parallelism={args.parallel} and reasoning_bank={args.reasoning_bank_path}")
        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(run_task, tid, args.reasoning_bank_path, args.website, args.retrieve_type): tid for tid in task_ids}
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                    print(f"✅ Task {result} completed successfully")
                except Exception as e:
                    print(f"❌ Task {tid} failed with error: {e}")

        # Calculate total cost after all tasks
        calculate_total_cost()
    else:
        # Run tasks sequentially (original behavior)
        for tid in task_ids:
            run_task(tid, args.reasoning_bank_path, args.website, args.retrieve_type)
            calculate_total_cost()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "shopping_admin", "gitlab", "reddit", "map", "wikipedia"])
    parser.add_argument("--start_index", type=int, default=0)
    parser.add_argument("--end_index", type=int, default=None)
    parser.add_argument("--reasoning_bank_path", type=str, default="data/reasoning_bank.json",
                        help="Path to Reasoning Bank JSON file")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel tasks to run (default: 1)")
    parser.add_argument("--retrieve_type", type=str, default="embedding", choices=["embedding", "bm25"],
                        help="Type of retrieval method for reasoning bank")
    args = parser.parse_args()

    main()
