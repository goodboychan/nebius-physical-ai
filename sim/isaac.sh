#!/bin/bash
# Run a script with the Isaac Sim 6.2 venv on the GX10 (aarch64 needs libgomp preloaded). The EULA was accepted by the user on 2026-10-15.
export OMNI_KIT_ACCEPT_EULA=YES LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}/lib/aarch64-linux-gnu/libgomp.so.1"
exec ~/isaacsim-env/bin/python "$@"
