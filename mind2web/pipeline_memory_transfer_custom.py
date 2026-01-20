"Online Induction and Workflow Utilization Pipeline."
import os
import argparse
import subprocess
import json
from utils.data import load_json

def offline():
    # workflow induction
    process = subprocess.Popen([
        'python', 'offline_induction.py',
        '--mode', 'auto', '--website', args.website,
        '--domain', args.domain, '--subdomain', args.subdomain,
        '--model', args.model, '--output_dir', "workflow",
        '--instruction_path', args.instruction_path,
        '--one_shot_path', args.one_shot_path,
    ])
    exit_code = process.wait()
    if exit_code != 0:
        print(f"Error: Offline induction failed for {args.website} with exit code {exit_code}")
        return

    # test inference
    process = subprocess.Popen([
        'python', 'run_mind2web.py',
        '--website', args.website,
        '--workflow_path', f"workflow/{args.website}.txt",
        '--temperature', str(args.temperature),
    ])
    process.wait()

def baseline():
    """Run baseline inference without workflow induction (empty memory)."""
    # Ensure a workflow file exists, even if empty
    if not os.path.exists(args.workflow_path):
        os.makedirs(os.path.dirname(args.workflow_path), exist_ok=True)
        with open(args.workflow_path, 'w') as f:
            f.write("")  # Create empty file

    print(f"Running BASELINE inference on all examples for {args.website}...")
    
    cmd =[
        'python', 'run_mind2web.py',
        '--benchmark', args.benchmark,
        '--workflow_path', args.workflow_path,
        '--website', args.website,
        '--model', args.model,
        '--log_dir', args.results_dir,
        '--temperature', str(args.temperature),
        '--enable_reasoning_bank', str(args.enable_reasoning_bank),
        '--private_memory_path', args.private_memory_path, # Changed from reasoning_bank_path
        '--private_memory_embeddings_path', args.private_memory_embeddings_path, # Changed from reasoning_bank_embeddings_path
        '--retrieve_type', args.retrieve_type,
    ]

    if args.domain:
        cmd.extend(['--domain', args.domain])

    if args.subdomain:
        cmd.extend(['--subdomain', args.subdomain])

    process = subprocess.Popen(cmd)
    exit_code = process.wait()
    if exit_code != 0:
        print(f"Error: Baseline inference failed for {args.website} with exit code {exit_code}")
    else:
        print(f"Finished BASELINE inference for {args.website}!\n")


def online():
    # load all examples for streaming
    samples = load_json(args.data_dir, args.benchmark)
    print(f"Loaded #{len(samples)} test examples")
    if args.website is not None:
        samples = [s for s in samples if s["website"] == args.website]
        print(f"Filtering down to #{len(samples)} examples on website [{args.website}]")
    n = len(samples)
    
    for i in range(0, n, args.induce_steps):
        j = min(n, i + args.induce_steps)

        print(f"Running inference on {i}-{j} th example..")

        cmd =[
            'python', 'run_mind2web.py',
            '--benchmark', args.benchmark,
            '--workflow_path', args.workflow_path,
            '--website', args.website,
            '--start_idx', f'{i}', '--end_idx', f'{j}',
            '--model', args.model,
            '--log_dir', args.results_dir, # Pass the flat results_dir as log_dir
            '--temperature', str(args.temperature),
            '--enable_reasoning_bank', str(args.enable_reasoning_bank),
            '--private_memory_path', args.private_memory_path, # Changed from reasoning_bank_path
            '--private_memory_embeddings_path', args.private_memory_embeddings_path, # Changed from reasoning_bank_embeddings_path
            '--retrieve_type', args.retrieve_type,
        ]

        if args.domain:
            cmd.extend(['--domain', args.domain])

        if args.subdomain:
            cmd.extend(['--subdomain', args.subdomain])

        process = subprocess.Popen(cmd)
        exit_code = process.wait()
        
        if exit_code != 0:
            print(f"Error: Inference failed for {args.website} ({i}-{j}) with exit code {exit_code}. Skipping induction.")
            continue  # Skip induction if inference failed

        print(f"Finished inference on {i}-{j} th example!\n")

        if j < len(samples):
            print(f"Starting workflow induction with 0-{j} th examples...")
            process = subprocess.Popen([
                'python', 'online_induction.py',
                '--benchmark', args.benchmark,
                '--website', args.website,
                '--results_dir', args.results_dir,
                '--output_path', args.workflow_path,
                '--model_name', args.model,
                '--temperature', str(args.temperature),
            ])
            exit_code = process.wait()
            
            if exit_code != 0:
                print(f"Error: Workflow induction failed for {args.website} with exit code {exit_code}.")
            else:
                print(f"Finished workflow induction with 0-{j} th examples!\n")


def memory_transfer_custom():
    """
    Run inference with a custom mix of private and transfer memories.
    This function now delegates the memory handling logic to run_mind2web.py.
    """
    
    # Ensure an empty workflow file exists, similar to the baseline setup.
    if not os.path.exists(args.workflow_path):
        os.makedirs(os.path.dirname(args.workflow_path), exist_ok=True)
        with open(args.workflow_path, 'w') as f:
            f.write("")
    
    print(f"Running MEMORY-TRANSFER-CUSTOM inference for {args.website}...")
    
    cmd = [
        'python', 'run_mind2web.py',
        '--benchmark', args.benchmark,
        '--workflow_path', args.workflow_path, # Path to an empty file
        '--website', args.website,
        '--model', args.model,
        '--log_dir', args.results_dir,
        '--temperature', str(args.temperature),
        '--enable_reasoning_bank', "True", # Must be enabled for this mode
        '--is_memory_transfer_custom', "True", # Flag to trigger custom logic in run_mind2web
        '--retrieve_type', args.retrieve_type,
        '--private_memory_path', args.private_memory_path,
        '--private_memory_embeddings_path', args.private_memory_embeddings_path,
        '--transfer_memory_path', args.transfer_memory_path,
        '--transfer_memory_embeddings_path', args.transfer_memory_embeddings_path,
    ]

    if args.domain:
        cmd.extend(['--domain', args.domain])
    if args.subdomain:
        cmd.extend(['--subdomain', args.subdomain])

    process = subprocess.Popen(cmd)
    exit_code = process.wait()

    if exit_code != 0:
        print(f"Error: Custom memory transfer inference failed for {args.website} with exit code {exit_code}")
    else:
        print(f"Finished Custom memory transfer inference for {args.website}!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # examples
    parser.add_argument("--data_dir", type=str, default="data")
    parser.add_argument("--benchmark", type=str, default="test_task",
        choices=["test_task", "test_website", "test_domain", "train"])
    parser.add_argument("--website", type=str, required=False, default=None)
    parser.add_argument("--domain", type=str, default=None)
    parser.add_argument("--subdomain", type=str, default=None)

    # results and workflows
    parser.add_argument("--results_dir", type=str, default=None)
    parser.add_argument("--workflow_path", type=str, default=None)

    # prompt
    parser.add_argument("--instruction_path", type=str, default="prompt/instruction_action.txt")
    parser.add_argument("--one_shot_path", type=str, default="prompt/one_shot_action.txt")
    parser.add_argument("--prefix", type=str, default=None)
    parser.add_argument("--suffix", type=str, default="# Summary Workflows")

    # gpt
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--temperature", type=str, default="0.0")

    # induction frequency
    parser.add_argument("--induce_steps", type=int, default=1)

    # setup
    parser.add_argument("--setup", type=str, required=True,
                        choices=["online", "offline", "baseline", "memory_transfer_custom"])

    def str2bool(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    parser.add_argument("--enable_reasoning_bank", type=str2bool, default=False, help="Enable Reasoning Bank usage")
    
    # Arguments for memory_transfer_custom setup and baseline/online
    parser.add_argument("--private_memory_path", type=str, default="data/reasoning_bank.json", help="Path to the private memory file.")
    parser.add_argument("--private_memory_embeddings_path", type=str, default="data/reasoning_bank_embeddings.json", help="Path to the private memory embeddings file.")
    parser.add_argument("--transfer_memory_path", type=str, default="data/reasoning_bank_mt.json", help="Path to the transfer memory file.")
    parser.add_argument("--transfer_memory_embeddings_path", type=str, help="Path to the transfer memory embeddings file.")

    # Retrieve type
    parser.add_argument("--retrieve_type", type=str, default="embedding", choices=["bm25", "embedding"], help="Type of retrieval method to use")

    args = parser.parse_args()

    # Capture original paths to prevent them from being overwritten in the loop
    original_results_dir = args.results_dir
    original_workflow_path = args.workflow_path

    if args.website is None:
        # Auto-detect websites from data
        all_samples = load_json(args.data_dir, args.benchmark)
        website_info = {}
        for s in all_samples:
            w = s.get("website")
            if w and w not in website_info:
                website_info[w] = {
                    "domain": s.get("domain"),
                    "subdomain": s.get("subdomain")
                }
        
        sorted_websites = sorted(list(website_info.keys()))
        print(f"Automated Mode: Found {len(sorted_websites)} websites. Starting execution...")

        for w in sorted_websites:
            print(f"\n{'='*20}\nRunning for website: {w}\n{'='*20}")
            args.website = w
            
            # Auto-configure paths
            if original_results_dir is not None:
                args.results_dir = f"{original_results_dir}/{w}"
            else:
                if args.setup == "baseline":
                    args.results_dir = f"results_baseline/{w}"
                elif args.setup == "memory_transfer_custom":
                    args.results_dir = f"results_memory_transfer_custom/{w}"
                else:
                    args.results_dir = f"results/{w}"
                
            if original_workflow_path is not None:
                # If it's a file path, we might want to append website name before extension or use it as a dir
                if original_workflow_path.endswith('.txt'):
                    args.workflow_path = original_workflow_path.replace('.txt', f'_{w}.txt')
                else:
                    args.workflow_path = f"{original_workflow_path}/{w}.txt"
            else:
                if args.setup == "baseline":
                    args.workflow_path = f"workflow/baseline/{w}_empty.txt"
                else:
                    args.workflow_path = f"workflow/{w}.txt"
            
            info = website_info[w]
            if args.domain is None: args.domain = info.get("domain")
            if args.subdomain is None: args.subdomain = info.get("subdomain")

            if args.setup == "online":
                online()
            elif args.setup == "offline":
                offline()
            elif args.setup == "baseline":
                baseline()
            elif args.setup == "memory_transfer_custom":
                memory_transfer_custom()

    else:
        # If website is provided, ensure results_dir is also set if not given
        if args.results_dir is None:
            if args.setup == "baseline":
                args.results_dir = f"results_baseline/{args.website}"
            elif args.setup == "memory_transfer_custom":
                args.results_dir = f"results_memory_transfer_custom/{args.website}"
            else:
                args.results_dir = f"results/{args.website}"
                
        if args.workflow_path is None:
            if args.setup == "baseline":
                args.workflow_path = f"workflow/baseline/{args.website}_empty.txt"
            else:
                args.workflow_path = f"workflow/{args.website}.txt"
            
        if args.setup == "online":
            assert (args.results_dir is not None) and (args.workflow_path is not None)
            online()
        elif args.setup == "offline":
            assert (args.domain is not None) and (args.subdomain is not None)
            offline()
        elif args.setup == "baseline":
            baseline()
        elif args.setup == "memory_transfer_custom":
            memory_transfer_custom()
