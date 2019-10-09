#!/bin/bash
# Set the default encoding to something Unicode-friendly before starting the
# actual recognizer.  Otherwise, the default is ASCII and Persephone refuses
# to run.

# Edit the following three lines as needed.
export PYTHON3="/Library/Frameworks/Python.framework/Versions/3.6/bin/python3"
export FFMPEG_DIR="/Users/chris/Unix"
export LC_ALL="en_CA.UTF-8"

export PYTHONIOENCODING="utf-8"
export PATH="$PATH:$FFMPEG_DIR"

exec $PYTHON3 ./persephone-elan.py
