#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
from time import sleep


def main():
    parser = argparse.ArgumentParser(
        description="Run EMUSES with a range of dynamic optim_dict configurations as separate processes."
    )
    parser.add_argument(
        '--num_configs', type=int, default=50,
        help="Number of dynamic optim_dict configurations to try (e.g., if 10, will try dynamic_optim_dict_0 to dynamic_optim_dict_9)."
    )
    parser.add_argument(
        '--base_optim_dict', type=str, default='dynamic_optim_dict',
        help="Base name of the optim_dict variable in optim_configs.py (e.g., 'dynamic_optim_dict')."
    )
    parser.add_argument(
        '--max_concurrent', type=int, default=20,
        help="Maximum number of concurrent processes. A machine with 72 cores might handle around 20 heavy processes concurrently."
    )
    # All remaining arguments will be passed to the EMUSES command.
    parser.add_argument(
        'emuses_args', nargs=argparse.REMAINDER,
        help="The command-line arguments for the EMUSES tool. For example: 'full /path/to/output mnist -inorm min-max --correlation_method pointbiserial --test_size 0.2 --interactive_plot --classification'"
    )

    args = parser.parse_args()

    # Get the EMUSES executable. Adjust if necessary.
    emuses_executable = "emuses"  # Ensure this is in your PATH

    # We assume that the command follows the format:
    # emuses <subcommand> <output_folder> ...
    # So, the output folder is the second argument in emuses_args.
    if len(args.emuses_args) < 2:
        print("Error: At least two arguments are required for EMUSES (subcommand and output folder).")
        sys.exit(1)
    base_output_folder = args.emuses_args[1]

    processes = []
    max_concurrent = args.max_concurrent

    for idx in range(args.num_configs):
        optim_dict_name = f"{args.base_optim_dict}_{idx}"
        # Modify the output folder to be a subfolder of the base output folder.
        new_output_folder = os.path.join(base_output_folder, optim_dict_name)
        # Ensure the new output folder exists.
        os.makedirs(new_output_folder, exist_ok=True)

        # Build the command:
        # We need to replace the original output folder (argument 1) with new_output_folder.
        # We'll create a copy of the argument list.
        cmd_args = list(args.emuses_args)
        cmd_args[1] = new_output_folder

        # Append the --optim_dict parameter at the end.
        cmd_args.extend(["--optim_dict", optim_dict_name])

        cmd = [emuses_executable] + cmd_args
        print(f"Launching command for optim_dict '{optim_dict_name}': {' '.join(cmd)}")

        proc = subprocess.Popen(cmd)
        processes.append(proc)

        # Limit concurrency: wait if we've launched max_concurrent processes.
        while len(processes) >= max_concurrent:
            for p in processes:
                ret = p.poll()
                if ret is not None:
                    processes.remove(p)
                    break
            else:
                sleep(1)

    # Wait for remaining processes to finish.
    for p in processes:
        p.wait()

    print("All processes completed.")


if __name__ == "__main__":
    main()
