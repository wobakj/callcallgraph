# Call Call Graph

A command line utility producing a call graph on function/file/folder level from a cscope.out file.
Based on [cscope][1], [xdot][3].
Previous work is from [solomonhuang][4].
Uses `main` as the root for building the call graph.
Everything is just hacked together.

# Setup
- Create a virtual environment
- install the requirements

# Usage
- use cscope to create a cscope.out file or adapt and use `folder_to_cscope.sh <path-to-sources>` to collect files
- activate the venv
- execute cscope_to_view.sh <path-to-cscope-file> <call|file|folder>

[1]: http://cscope.sourceforge.net/
[3]: http://code.google.com/p/jrfonseca/wiki/XDot
[4]: https://github.com/solomonhuang/callcallgraph

