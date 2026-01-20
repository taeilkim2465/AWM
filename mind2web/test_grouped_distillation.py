#!/usr/bin/env python3
"""
Test script for grouped step-level distillation.
This tests the new success/failure step separation logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.distiller import MemoryDistiller

def test_distiller():
    """Test the distiller with different prompt types."""

    print("=" * 80)
    print("Testing Grouped Step-Level Distillation")
    print("=" * 80)

    # Initialize distiller
    distiller = MemoryDistiller()

    # Test data
    task = "Find a vacation home in Orlando with a private pool, at least three bedrooms, and availability for the first week of December."
    domain = "expedia"

    # Success steps (mocked)
    success_trajectory = """Step 2:
Observation: `<html> <div main> <div tabpanel> <form> <div going to> <ul> <button id=7535 button orlando florida, united states /> <button id=8025 button orlando (mco - orlando intl.) /> </ul> </div> </form> </div> </div> </html>`
Action: `CLICK [7535]` ([button]  Orlando Florida, United States -> CLICK)

Step 3:
Observation: `<html> <div main> <div tabpanel> <form> <button id=11413 button 1 room, 2 travelers> 1 room, 2 travelers </button> </form> </div> </html>`
Action: `CLICK [11413]` ([button] 1 room, 2 travelers -> CLICK)
"""

    # Failure steps (mocked)
    failure_trajectory = """Step 1:
Observation: `<html> <div main> <div tabpanel> <form> <div> <div going to> <div> <label> Going to </label> <input id=3820 text where are you going? /> </div> </div> </form> </div> </div> </html>`
Action: `TYPE 3820 Orlando`

Step 4:
Observation: `<html> <div main> <div> <svg icon /> <button id=12345 search /> </div> </html>`
Action: `CLICK [12340]` (wrong ID, decorative icon)
"""

    # Test 1: Success step distillation
    print("\n[TEST 1] Testing SUCCESS step distillation...")
    print("-" * 80)
    try:
        success_items = distiller.distill(
            task=task,
            trajectory=success_trajectory,
            outcome="SUCCESS",
            domain=domain,
            prompt_type="success"
        )
        print(f"✓ Success distillation completed: {len(success_items)} items extracted")
        for i, item in enumerate(success_items):
            print(f"\n  Item {i+1}:")
            print(f"    Title: {item.get('title', 'N/A')}")
            print(f"    Description: {item.get('description', 'N/A')}")
            print(f"    Content: {item.get('content', 'N/A')[:100]}...")
    except Exception as e:
        print(f"✗ Success distillation failed: {e}")

    # Test 2: Failure step distillation
    print("\n[TEST 2] Testing FAILURE step distillation...")
    print("-" * 80)
    try:
        failure_items = distiller.distill(
            task=task,
            trajectory=failure_trajectory,
            outcome="FAILURE",
            domain=domain,
            prompt_type="failure"
        )
        print(f"✓ Failure distillation completed: {len(failure_items)} items extracted")
        for i, item in enumerate(failure_items):
            print(f"\n  Item {i+1}:")
            print(f"    Title: {item.get('title', 'N/A')}")
            print(f"    Description: {item.get('description', 'N/A')}")
            print(f"    Content: {item.get('content', 'N/A')[:100]}...")
    except Exception as e:
        print(f"✗ Failure distillation failed: {e}")

    # Test 3: Default (task-level) distillation still works
    print("\n[TEST 3] Testing DEFAULT task-level distillation (backward compatibility)...")
    print("-" * 80)
    try:
        combined_trajectory = success_trajectory + "\n\n" + failure_trajectory
        default_items = distiller.distill(
            task=task,
            trajectory=combined_trajectory,
            outcome="FAILURE",
            domain=domain,
            prompt_type="default"
        )
        print(f"✓ Default distillation completed: {len(default_items)} items extracted")
        for i, item in enumerate(default_items):
            print(f"\n  Item {i+1}:")
            print(f"    Title: {item.get('title', 'N/A')}")
    except Exception as e:
        print(f"✗ Default distillation failed: {e}")

    print("\n" + "=" * 80)
    print("Testing completed!")
    print("=" * 80)

if __name__ == "__main__":
    # Check if prompt files exist
    prompt_dir = "prompt/reasoning_bank"
    required_files = ["distill_system.txt", "distill_user.txt", "success_step.txt", "failure_step.txt"]

    print("Checking prompt files...")
    for filename in required_files:
        filepath = os.path.join(prompt_dir, filename)
        if os.path.exists(filepath):
            print(f"  ✓ {filename} exists")
        else:
            print(f"  ✗ {filename} NOT FOUND")
            sys.exit(1)

    print("\nAll prompt files found. Starting tests...\n")
    test_distiller()
