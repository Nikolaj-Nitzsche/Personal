#!/usr/bin/env bash
# Soft “unplug/re‑plug” Attocube on Bus 001 Device 018

echo "Looking for Bus 001 Device 018 under /sys/bus/usb/devices/…"
for d in /sys/bus/usb/devices/*; do
  if [ -f "$d/busnum" ] && [ -f "$d/devnum" ]; then
    BUS=$(cat "$d/busnum")
    DEV=$(cat "$d/devnum")
    if [ "$BUS" = "1" ] && [ "$DEV" = "18" ]; then
      echo "→ Found device at $d"
      echo "   Un‑authorizing (simulated unplug)…"
      echo 0 | sudo tee "$d/authorized" >/dev/null
      sleep 1
      echo "   Re‑authorizing (simulated re‑plug)…"
      echo 1 | sudo tee "$d/authorized" >/dev/null
      echo "✅ Device reset complete."
      exit 0
    fi
  fi
done

echo "❌ Could not find Bus 001 Device 018 under /sys/bus/usb/devices."
exit 1
