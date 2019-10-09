#!/bin/bash
#
# Set a number of environmental variables and locale-related settings needed
# for Persephone to run as expected before calling the recognizer itself.
#
# It seems that recognizer processes invoked by ELAN don't inherit any regular
# environmental variables (like PATH), which makes it difficult to track down
# where both Python and ffmpeg(1) might be.  These same processes also have
# their locale set to C.  This implies a default ASCII file encoding, which
# causes Persephone to refuse to run (since it seems to assume a more Unicode-
# friendly view of the world somewhere in its code).

# **
# ** Edit the following two lines to point to the Python 3 executable and the
# ** directory in which 'ffmpeg' is found on this computer.
# **
export PYTHON3="/Library/Frameworks/Python.framework/Versions/3.6/bin/python3"
export FFMPEG_DIR="/Users/chris/Unix"

export LC_ALL="en_US.UTF-8"
export PYTHONIOENCODING="utf-8"
export PATH="$PATH:$FFMPEG_DIR"

exec $PYTHON3 ./persephone-elan.py
