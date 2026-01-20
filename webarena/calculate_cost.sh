#!/bin/bash

PYTHON_MODULE="cost_tracker"

python3 -c "from ${PYTHON_MODULE} import calculate_total_cost; calculate_total_cost()"