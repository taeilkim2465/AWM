import os
import json
import argparse
import time
import signal
from subprocess import Popen, TimeoutExpired
from cost_tracker import calculate_total_cost, LOG_FILE

def _log_timeout_task(tid):
    with open("./timeout_tasks.jsonl", "a") as f:
        f.write(json.dumps({"task_id": tid}) + "\n")


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
    for tid in task_ids[args.start_index: args.end_index]:
        TASK_TIMEOUT = 1800  # 30 minutes
        start_time = time.time()

        # step 1: run inference
        cmd = [
            "python", "run.py", 
            "--task", f"webarena.{tid}",
            "--workflow_path", f"workflow/{args.website}.txt"
        ]
        if args.enable_reasoning_bank:
            cmd.extend(["--enable_reasoning_bank", "True"])
        if args.reasoning_bank_path:
            cmd.extend(["--reasoning_bank_path", args.reasoning_bank_path])

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
            continue

        time_left = TASK_TIMEOUT - (time.time() - start_time)
        if time_left <= 0:
            print(f"Task {tid} ran out of time after inference step.")
            _log_timeout_task(tid)
            continue

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
            process.wait()  # Clean up the zombie process
            continue

        time_left = TASK_TIMEOUT - (time.time() - start_time)
        if time_left <= 0:
            print(f"Task {tid} ran out of time after evaluation step.")
            _log_timeout_task(tid)
            continue

        # step 3: update workflow
        process = Popen([
            "python", "induce_prompt.py",
            "--result_dir", f"results/webarena.{tid}",
            "--output_path", f"workflow/{args.website}.txt",
        ], start_new_session=True)
        try:
            process.wait(timeout=time_left)
        except TimeoutExpired:
            print(f"Task {tid} timed out during workflow update. Terminating process group.")
            _log_timeout_task(tid)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass # process already terminated
            process.wait()  # Clean up the zombie process
            continue

        print(f"################## Task {tid} Finished ##################")
        calculate_total_cost()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "shopping_admin", "gitlab", "reddit", "map", "wikipedia"])
    parser.add_argument("--start_index", type=int, default=0)
    parser.add_argument("--end_index", type=int, default=None)
    parser.add_argument("--enable_reasoning_bank", action='store_true', help="Enable Reasoning Bank")
    parser.add_argument("--reasoning_bank_path", type=str, default=None, help="Path to Reasoning Bank")
    args = parser.parse_args()

    main()
