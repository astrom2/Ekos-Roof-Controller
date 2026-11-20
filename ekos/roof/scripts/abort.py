#!/usr/bin/env python3
# INDI Dome Scripting Gateway -> abort
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from roof_actions import run
sys.exit(run("abort"))
