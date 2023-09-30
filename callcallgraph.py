#!/usr/bin/env python3
# Copyright 2010 Solomon Huang <kaichanh@gmail.com>
# Copyright 2010 Rex Tsai <chihchun@kalug.linux.org.tw>
# Copyright 2008 Jose Fonseca
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import hashlib
import json
import os
import re
import subprocess
from pathlib import PurePath

import networkx as nx
import xdot
from networkx import nx_pydot

import argparse

__author__ = 'Solomon Huang <kaichanh@gmail.com>'
__version__ = '0.0.1'

parser = argparse.ArgumentParser()


class CCGNode(object):
    ''' Represent the function call with its file name and location '''
    def __init__(self, function, file, line):
        self.func = function
        self.full_file_path = file
        self.line = int(line)
        h = hashlib.sha512()
        h.update(self.full_file_path.encode("utf-8"))
        h.update(str(self.line).encode("utf-8"))
        h.update(self.func.encode("utf-8"))
        self.hexdigest = h.hexdigest()
        self.digest = h.digest()
        self.paths = []
        self.file = os.path.basename(self.full_file_path)
        self.dir = os.path.dirname(self.full_file_path)
        dir = self.dir
        while len(dir) > 0:
            self.paths.insert(0, os.path.basename(dir))
            dir = os.path.dirname(dir)

    def __str__(self):
        return self.hexdigest[0:32]

    def __eq__(self, other):
        return self.digest == other.digest

    def __hash__(self):
        return int.from_bytes(self.digest[0:4], byteorder='big')


class CCGWindow():
    ''' CallCallGraph Window '''

    def __init__(self):
        self.base_title = "Call Call Graph"
        self.working_dir = None
        self.interest = set()
        self.filename = None
        self.config = dict()
        self.config['ignore_symbols'] = []
        self.config['ignore_header'] = True
        self.config['show_folder'] = True
        self.ignore_symbols = set()
        self.dotcode = None
        self.nodes = set()
        self.set_dotcode("digraph G {}")

    def save(self):
        with open(self.working_dir + "/callgraph.dot", "w") as file:
            file.write(self.dotcode)

    def new_project(self):
        self.working_dir = os.path.dirname(self.filename)
        p = PurePath(self.working_dir, ".callcallgraph.json")
        try:
            with open(str(p), "r") as conf:
                config = json.loads(conf.read())
                for c in config.keys():
                    if c not in self.config:
                        self.config[c] = config[c]
                    else:
                        self.config[c] = config[c]
            # write back config
            with open(str(p), "w") as conf:
                conf.write(json.dumps(self.config, indent=4))
        except FileNotFoundError:
            with open(str(p), "w") as conf:
                conf.write(json.dumps(self.config, indent=4))
        self.ignore_symbols = set(map(lambda x: re.compile(x), self.config['ignore_symbols']))

        self.update_graph()

    def is_symbol_ignored(self, symbol):
        for p in self.ignore_symbols:
            if p.match(symbol) is not None:
                return True
        return False

    def add_symbol(self, symbol):
        if(symbol == '//'):
            return

        defs, calls = self.functionDefinition(symbol)
        for file in calls.keys():
            for (func, line) in calls[file]:
                node = CCGNode(func, file, line)
                if node not in self.nodes:
                    self.nodes.add(node)
                if node not in self.interest:
                    self.interest.add(node)
        self.update_graph()

    def cscope(self, mode, func):
        # TODO: check the cscope database exists.
        cmd = "/usr/bin/cscope -d -l -L -%d %s" % (mode, func)
        # print(cmd)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                              cwd=self.working_dir) as proc:
            csoutput = str(proc.stdout.read(), encoding="utf-8")
        # print("\ncsoutput")
        # print(csoutput)
        cscope_lines = [arr.strip().split(' ') for arr in csoutput.split('\n') if len(arr.split(' ')) > 1]
        print("cscope_lines")
        print(cscope_lines)
        function_names = set(map(lambda x: x[1], cscope_lines))
        print("allFuncs")
        print(function_names)

        occurences = {}
        for l in cscope_lines:
            file = l[0]
            function = l[1]
            line = l[2]
            # print("file %s %s\n" % (file, file[-2:]))
            if self.config['ignore_header'] and file[-2:] == ".h":
                continue
            if file in occurences:
                occurences[file].add(tuple([function, line]))
            else:
                occurences[file] = set()
                occurences[file].add(tuple([function, line]))

        print("occurences")
        print(occurences)
        print("")
        return (function_names, occurences)

    def functionDefinition(self, func):
        print(f"functionDefinition for {func}:")
        return self.cscope(1, func)[1]

    def functionsCalled(self, func):
        print(f"functionsCalled for {func}:")
        # Find functions called by this function:
        return self.cscope(2, func)

    def functionsCalling(self, func):
        print(f"functionsCalling for {func}:")
        # Find functions calling this function:
        return self.cscope(3, func)

    def update_graph(self):
        """ update dot code based on the interested keys """
        if len(self.interest) <= 0:
            return

        edges = set()
        nodes_to_process = self.interest
        visited = set()
        for node in self.interest:
            if self.is_symbol_ignored(node.func):
                continue

            callees, callee_callsites = self.functionsCalled(node.func)
            for callee in callees:
                if self.is_symbol_ignored(callee):
                    continue

                declaration_site = self.functionDefinition(callee)
                print(f"for function {callee} got name {name} and call {declaration_site}")
                for file in declaration_site.keys():
                    for (func, line) in declaration_site[file]:
                        if file not in callee_callsites:
                            continue
                        called_node = CCGNode(func, file, line)
                        if called_node not in self.nodes:
                            self.nodes.add(called_node)

                        e = (node, called_node)
                        edges.add(e)

            callers, caller_callsites = self.functionsCalling(node.func)
            for caller in callers:
                if self.is_symbol_ignored(caller):
                    continue

                declaration_site = self.functionDefinition(caller)
                print(f"for function {callee} got name {name} and call {declaration_site}")
                for file in declaration_site.keys():
                    for (func, line) in declaration_site[file]:
                        if file not in caller_callsites:
                            continue
                        calling_node = CCGNode(func, file, line)
                        if calling_node not in self.nodes:
                            self.nodes.add(calling_node)

                        e = (calling_node, node)
                        edges.add(e)

        ccg_graph = nx.DiGraph()
        if self.config['show_folder']:
            for n in self.nodes:
                ccg_graph.add_node(n, label="\"%s\n%s:%d\n%s\"" % (n.dir, n.file, n.line, n.func))
        else:
            for n in self.nodes:
                ccg_graph.add_node(n, label="\"%s:%d\n%s\"" % (n.file, n.line, n.func))
        ccg_graph.add_edges_from(list(edges))
        ccg_dot = str(nx_pydot.to_pydot(ccg_graph))
        self.set_dotcode(ccg_dot)

    def set_dotcode(self, dotcode, filename=None):
        # print("\n\ndotcode:\n" + str(dotcode) + "\n\n")
        self.dotcode = dotcode

def main():
    parser.add_argument('input_file', help='path to cscope.out')
    parser.add_argument('--limited', action='store_true')
    args = parser.parse_args()

    window = CCGWindow()
    window.filename = args.input_file
    window.new_project()
    window.add_symbol("main")
    window.save()

if __name__ == '__main__':
    main()
