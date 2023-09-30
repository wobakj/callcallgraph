#!/bin/bash
python3 ./callcallgraph.py $1/cscope.out
dot -Grankdir=LR -Tpng -O $1/callgraph.dot
dot -Grankdir=LR -Tpng -O $1/filegraph.dot
dot -Grankdir=LR -Tpng -O $1/foldergraph.dot
xdg-open $1/foldergraph.dot.png
# xdg-open $1/filegraph.dot.png
# xdg-open $1/callgraph.dot.png
