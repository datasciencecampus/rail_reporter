#!/bin/bash

# Add this to PATH, makes source, direnv available
export PATH="/usr/local/bin:$PATH"

# Change to project directory
cd ~/GitHub/rail_reporter

# Activate venv
source env/bin/activate

# direnv doesn't play nice with automation, load manually instead
source ~/GitHub/rail_reporter/.envrc
source ~/GitHub/rail_reporter/.secrets

# Run process
python run.py
