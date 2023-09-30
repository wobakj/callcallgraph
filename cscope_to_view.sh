#!/bin/bash
python3 ./callcallgraph.py --graph=$2 $1/cscope.out
dot -Grankdir=LR -Tpng -O $1/$2graph.dot
xdg-open $1/$2graph.dot.png
# xdg-open $1/filegraph.dot.png
# xdg-open $1/callgraph.dot.png
