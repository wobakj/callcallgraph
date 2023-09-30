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
    def __init__(self, function, file, line, label = None):
        self.func = function
        self.full_file_path = file
        self.line = int(line)
        h = hashlib.sha512()
        h.update(self.full_file_path.encode("utf-8"))
        h.update(str(self.line).encode("utf-8"))
        h.update(self.func.encode("utf-8"))
        self.hexdigest = h.hexdigest()
        self.digest = h.digest()
        self.file = os.path.basename(self.full_file_path)
        self.dir = os.path.dirname(self.full_file_path)
        self.label = label

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
        self.filename = None
        self.config = dict()
        self.config['ignore_symbols'] = []
        self.config['ignore_header'] = True
        self.config['show_folder'] = True
        self.ignore_symbols = set()

    def save(self, graph, filename):
        with open(self.working_dir + "/" + filename + ".dot", "w") as file:
            file.write(str(nx_pydot.to_pydot(graph)))

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

    def is_symbol_ignored(self, symbol):
        for p in self.ignore_symbols:
            if p.match(symbol) is not None:
                return True
        return False

    def cscope(self, mode, func):
        # TODO: check the cscope database exists.
        cmd = "/usr/bin/cscope -d -l -L -%d %s" % (mode, func)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                              cwd=self.working_dir) as proc:
            csoutput = str(proc.stdout.read(), encoding="utf-8")
        # print("\ncsoutput")
        # print(csoutput)
        cscope_lines = [arr.strip().split(' ') for arr in csoutput.split('\n') if len(arr.split(' ')) > 1]
        # print("cscope_lines")
        # print(cscope_lines)
        function_names = set(map(lambda x: x[1], cscope_lines))
        # print("allFuncs")
        # print(function_names)

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

        # print("occurences")
        # print(occurences)
        # print("")
        return (function_names, occurences)

    def functionDefinition(self, func):
        # print(f"functionDefinition for {func}:")
        # we dont need the name of this function - we aleady know it
        definition = self.cscope(1, func)[1]
        if not definition:
            return None
        assert len(definition) == 1
        file, occurence = next(iter(definition.items()))
        assert len(occurence) == 1
        _, line = next(iter(occurence))
        return (file, line)

    def functionsCalled(self, func):
        # print(f"functionsCalled for {func}:")
        # Find functions called by this function:
        return self.cscope(2, func)

    def functionsCalling(self, func):
        # print(f"functionsCalling for {func}:")
        # Find functions calling this function:
        return self.cscope(3, func)

    def produce_graphs(self, root,calls, files, folders):
        to_visit = list()
        visited = set()
        call_graph = nx.DiGraph()
        folder_graph = nx.MultiDiGraph()
        file_graph = nx.MultiDiGraph()

        root_node = self.create_function_node(root)
        if not root_node:
            return

        to_visit.append(root_node)

        if (calls):
            call_graph.add_node(root_node, label="\"%s\n%s:%d\n%s\"" % (root_node.dir, root_node.file, root_node.line, root_node.func))

        if (files):
            root_file_node = self.add_file(root_node.full_file_path)
            file_graph.add_node(root_file_node, label="\"%s\n%s\"" % (root_node.dir, root_node.file))

        if (folders):
            root_folder_node = self.add_file(root_node.dir)
            folder_graph.add_node(root_folder_node, label="\"%s\"" % root_node.dir)


        while to_visit:
            function_node = to_visit.pop()
            if function_node in visited:
                continue

            if self.is_symbol_ignored(function_node.func):
                continue

            visited.add(function_node)
            file_node = self.add_file(function_node.full_file_path)
            folder_node = self.add_file(function_node.dir)

            _, callee_callsites = self.functionsCalled(function_node.func)
            for _, calls in callee_callsites.items():
                for callee, line in calls:
                    if self.is_symbol_ignored(callee):
                        continue

                    callee_node = self.create_function_node(callee)
                    if not callee_node:
                        continue

                    if (calls):
                        call_graph.add_node(callee_node, label="\"%s\n%s:%d\n%s\"" % (callee_node.dir, callee_node.file, callee_node.line, callee_node.func))
                        call_graph.add_edge(function_node, callee_node)

                    if (files):
                        callee_file_node = self.add_file(callee_node.full_file_path)
                        file_graph.add_node(callee_file_node, label="\"%s\n%s\"" % (callee_file_node.dir, callee_file_node.file))
                        file_graph.add_edge(file_node, callee_file_node, label="\"%s\"" % callee)

                    if (folders):
                        callee_folder_node = self.add_file(callee_node.dir)
                        folder_graph.add_node(callee_folder_node, label="\"%s\n%s\"" % (callee_folder_node.dir, callee_folder_node.file))
                        folder_graph.add_edge(folder_node, callee_folder_node, label="\"%s:%s\"" % (function_node.file, callee))


                    if callee_node not in visited:
                        to_visit.append(callee_node)

        if (calls):
            self.save(call_graph, "callgraph")
        if (files):
            self.save(file_graph, "filegraph")
        if (folders):
            self.save(folder_graph, "foldergraph")

    def add_file(self, file_path):
        node = CCGNode(file_path, file_path, 0)
        return node

    def create_function_node(self, symbol):
        declaration_site = self.functionDefinition(symbol)
        # skip functions whose declaration could not be found
        if not declaration_site:
            return None

        # print(f"for callee {callee} got call {declaration_site}")
        file, line = declaration_site
        return  CCGNode(symbol, file, line)

def main():
    parser.add_argument('input_file', help='path to cscope.out')
    parser.add_argument('--graph', choices=['call', 'file', 'folder'], required=True)
    args = parser.parse_args()
    window = CCGWindow()
    window.filename = args.input_file
    window.new_project()
    window.produce_graphs("main", args.graph == "call", args.graph == "file", args.graph == "folder")
    return 0

if __name__ == '__main__':
    main()
