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
        self.interest = set()
        self.filename = None
        self.config = dict()
        self.config['ignore_symbols'] = []
        self.config['ignore_header'] = True
        self.config['show_folder'] = True
        self.ignore_symbols = set()
        self.dotcode = None
        self.nodes = set()
        self.edges = set()
        self.set_dotcode("digraph G {}")

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

    def add_symbol(self, symbol):
        if(symbol == '//'):
            return

        node = self.create_function_node(symbol)
        if not node:
            return

        self.nodes.add(node)
        if node not in self.interest:
            self.interest.add(node)

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

    def call_graph(self, root):
        to_visit = list()
        visited = set()
        root_node = self.create_function_node(root)
        if root_node:
            to_visit.append(root_node)
            self.nodes.add(root_node)

        while to_visit:
            node = to_visit.pop()
            if node in visited:
                continue

            if self.is_symbol_ignored(node.func):
                continue

            visited.add(node)

            _, callee_callsites = self.functionsCalled(node.func)
            for file, calls in callee_callsites.items():
                for callee, line in calls:
                    if self.is_symbol_ignored(callee):
                        continue

                    callee_node = self.create_function_node(callee)
                    if not callee_node:
                        continue

                    self.nodes.add(callee_node)
                    self.edges.add((node, callee_node))

                    if callee_node not in visited:
                        to_visit.append(callee_node)

        ccg_graph = nx.DiGraph()
        for n in self.nodes:
            if self.config['show_folder']:
                ccg_graph.add_node(n, label="\"%s\n%s:%d\n%s\"" % (n.dir, n.file, n.line, n.func))
            else:
                ccg_graph.add_node(n, label="\"%s:%d\n%s\"" % (n.file, n.line, n.func))

        ccg_graph.add_edges_from(list(self.edges))
        return ccg_graph

    def file_graph(self, root, folders = False):
        self.nodes = set()
        self.edges = set()
        to_visit = list()
        visited = set()
        root_node = self.create_function_node(root)
        folder_graph = nx.MultiDiGraph()
        if root_node:
            to_visit.append(root_node)
            root_file_node = self.add_file(root_node.dir if folders else root_node.full_file_path)
            if self.config['show_folder']:
                folder_graph.add_node(root_file_node, label="\"%s\n%s\"" % (root_node.dir, root_node.file))
            else:
                folder_graph.add_node(root_file_node, label="\"%s\"" % (root_node.file))

        while to_visit:
            function_node = to_visit.pop()
            if function_node in visited:
                continue

            if self.is_symbol_ignored(function_node.func):
                continue

            visited.add(function_node)
            file_node = self.add_file(function_node.dir if folders else function_node.full_file_path)

            _, callee_callsites = self.functionsCalled(function_node.func)
            for _, calls in callee_callsites.items():
                for callee, line in calls:
                    if self.is_symbol_ignored(callee):
                        continue

                    callee_node = self.create_function_node(callee)
                    if not callee_node:
                        continue

                    callee_file_node = self.add_file(callee_node.dir if folders else callee_node.full_file_path)
                    if self.config['show_folder']:
                        folder_graph.add_node(callee_file_node, label="\"%s\n%s\"" % (callee_file_node.dir, callee_file_node.file))
                    else:
                        folder_graph.add_node(callee_file_node, label="\"%s\"" % (callee_file_node.file))
                    # self.edges.add((file_node, callee_file_node, callee, function_node.file))
                    if folders:
                        folder_graph.add_edge(file_node, callee_file_node, label="\"%s:%s\"" % (function_node.file, callee))
                    else:
                        folder_graph.add_edge(file_node, callee_file_node, label="\"%s\"" % callee)

                    if callee_node not in visited:
                        to_visit.append(callee_node)


        return folder_graph

    def add_file(self, file_path):
        node = CCGNode(file_path, file_path, 0)
        return node

    def add_folder(self, file_path):

        node = CCGNode(file_path, file_path, 0)
        # if node not in self.nodes:
        self.nodes.add(node)
        return node

    def create_function_node(self, symbol):
        declaration_site = self.functionDefinition(symbol)
        # skip functions whose declaration could not be found
        if not declaration_site:
            return None

        # print(f"for callee {callee} got call {declaration_site}")
        file, line = declaration_site

        node = CCGNode(symbol, file, line)
        # if node not in self.nodes:
        return node

    # def add_call(self, caller, callee, info = None):
    #     self.edges.add((caller, callee, info))

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
    call_graph = window.call_graph("main")
    window.save(call_graph, "callgraph")
    file_graph = window.file_graph("main")
    window.save(file_graph, "filegraph")
    folder_graph = window.file_graph("main", True)
    window.save(folder_graph, "foldergraph")

if __name__ == '__main__':
    main()
