#!/bin/bash

# Script to setup a virtual CAN interface (vcan0)
# Requirements: sudo privileges

echo "Setting up vcan0..."

# Load the vcan kernel module
sudo modprobe vcan

# Create the vcan0 interface
sudo ip link add dev vcan0 type vcan || echo "vcan0 already exists or failed to create"

# Bring the interface up
sudo ip link set up vcan0

echo "vcan0 is up and running."
ip link show vcan0
