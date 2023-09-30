#!/bin/bash
find $1 -name '*.cpp' ! -path "*/depth2/*" -prune > cscope.files
cscope -b -c -i cscope.files
