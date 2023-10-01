# Call Call Graph

A command line utility producing a call graph on function/file/folder level from a cscope.out file.
Based on [cscope][1].
Previous work is from [solomonhuang][2].
Everything is just hacked together.

# Setup
- install cscope `sudo apt install cscope`
- if you want to generate an image from the .dot output, install graphviz `sudo apt install graphviz`
- create a virtual environment
- install the requirements

# Usage
- use cscope to create a cscope.out file or adapt and use `folder_to_cscope.sh <path-to-sources>` to collect files
- activate the venv
- execute cscope_to_view.sh <path-to-cscope-file> <call|file|folder>

[1]: http://cscope.sourceforge.net/
[2]: https://github.com/solomonhuang/callcallgraph
