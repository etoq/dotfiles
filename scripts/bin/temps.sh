#!/bin/bash
while true; do
  clear
  echo "=== CPU (hwmon7) ==="
  for i in 1 2 3 4 5; do
    val=$(cat /sys/class/hwmon/hwmon7/temp${i}_input 2>/dev/null)
    echo "  Core $i: $((val/1000))°C"
  done
  echo "=== ThinkPad EC (hwmon4) ==="
  for i in 1 2; do
    val=$(cat /sys/class/hwmon/hwmon4/temp${i}_input 2>/dev/null)
    echo "  EC $i: $((val/1000))°C"
  done
  echo "=== NVMe (hwmon3) ==="
  val=$(cat /sys/class/hwmon/hwmon3/temp1_input 2>/dev/null)
  echo "  SSD: $((val/1000))°C"
  echo "=== Fan ==="
  cat /proc/acpi/ibm/fan | grep -E 'status|speed|level'
  sleep 2
done
