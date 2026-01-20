import os
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

def run_task(tid):
    """Run a single task: inference + evaluation"""
    TASK_TIMEOUT = 1800  # 30 minutes
    start_time = time.time()

    # step 1: run inference
    cmd = [
        "python", "run.py",
        "--task", f"webarena.{tid}",
    ]

    try:
        # Use subprocess.run with proper output handling
        process = Popen(cmd, start_new_session=True)
        process.wait(timeout=TASK_TIMEOUT)

        # Check if inference succeeded
        if process.returncode != 0:
            print(f"❌ Task {tid} inference failed with exit code {process.returncode}")
            return tid, False

        print(f"✅ Task {tid} inference completed")

    except TimeoutExpired:
        print(f"Task {tid} timed out during inference after {TASK_TIMEOUT} seconds. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass # process already terminated
        process.wait()  # Clean up the zombie process
        return tid, False
    except KeyboardInterrupt:
        print(f"\n⚠️  Task {tid} interrupted by user")
        raise  # Re-raise to propagate to main
    except Exception as e:
        print(f"❌ Task {tid} inference failed with exception: {e}")
        return tid, False

    time_left = TASK_TIMEOUT - (time.time() - start_time)
    if time_left <= 0:
        print(f"Task {tid} ran out of time after inference step.")
        _log_timeout_task(tid)
        return tid, False

    # step 2: run evaluation (only if inference succeeded)
    try:
        process = Popen([
            "python", "-m", "autoeval.evaluate_trajectory",
             "--result_dir", f"results/webarena.{tid}"],
            start_new_session=True
        )
        process.wait(timeout=time_left)

        if process.returncode != 0:
            print(f"❌ Task {tid} evaluation failed with exit code {process.returncode}")
            return tid, False

        print(f"✅ Task {tid} evaluation completed")

    except TimeoutExpired:
        print(f"Task {tid} timed out during evaluation. Terminating process group.")
        _log_timeout_task(tid)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass # process already terminated
        process.wait()
        return tid, False
    except KeyboardInterrupt:
        print(f"\n⚠️  Task {tid} interrupted by user")
        raise  # Re-raise to propagate to main
    except Exception as e:
        print(f"❌ Task {tid} evaluation failed with exception: {e}")
        return tid, False

    print(f"################## Task {tid} Finished ##################")
    return tid, True

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

    if args.parallel > 1:
        # Run tasks in parallel
        print(f"Running {len(task_ids)} tasks with parallelism={args.parallel}")
        successful = 0
        failed = 0

        try:
            with ProcessPoolExecutor(max_workers=args.parallel) as executor:
                futures = {executor.submit(run_task, tid): tid for tid in task_ids}
                for future in as_completed(futures):
                    tid = futures[future]
                    try:
                        task_id, success = future.result()
                        if success:
                            successful += 1
                            print(f"✅ Task {task_id} completed successfully")
                        else:
                            failed += 1
                            print(f"❌ Task {task_id} failed")
                    except Exception as e:
                        failed += 1
                        print(f"❌ Task {tid} failed with error: {e}")
        except KeyboardInterrupt:
            print(f"\n\n🛑 Interrupted by user! Shutting down gracefully...")
            print(f"Summary: {successful} successful, {failed} failed (interrupted)")
            return

        print(f"\n{'='*60}")
        print(f"Summary: {successful} successful, {failed} failed out of {len(task_ids)} tasks")
        print(f"{'='*60}\n")

        # Calculate total cost after all tasks
        calculate_total_cost()
    else:
        # Run tasks sequentially (original behavior)
        successful = 0
        failed = 0

        try:
            for tid in task_ids:
                task_id, success = run_task(tid)
                if success:
                    successful += 1
                else:
                    failed += 1
                calculate_total_cost()
        except KeyboardInterrupt:
            print(f"\n\n🛑 Interrupted by user! Shutting down gracefully...")
            print(f"Summary: {successful} successful, {failed} failed (interrupted)")
            return

        print(f"\n{'='*60}")
        print(f"Summary: {successful} successful, {failed} failed out of {len(task_ids)} tasks")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "shopping_admin", "gitlab", "reddit", "map", "wikipedia"])
    parser.add_argument("--start_index", type=int, default=0)
    parser.add_argument("--end_index", type=int, default=None)
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel tasks to run (default: 1)")
    args = parser.parse_args()

    main()
