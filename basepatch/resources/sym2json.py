#!/usr/bin/env python
import sys
import os
import glob
import re
import json

symbolsdict = {}
for arg in sys.argv[1:]:
    for filename in glob.glob(arg):
        if (os.path.splitext(filename)[1] == '.sym'):
            regex = re.compile(r'^(?P<bankregexmatch>[A-Fa-f0-9]{2}):(?P<addrregexmatch>[A-Fa-f0-9]{4}) (?P<symregexmatch>[a-zA-Z_][a-zA-Z0-9_]*)')
        elif (os.path.splitext(filename)[1] == '.asm'):
            regex = re.compile(r'^!(?P<symregexmatch>[a-zA-Z_][a-zA-Z0-9_]*) *= *\$(?P<bankregexmatch>[A-Fa-f0-9]{2})(?P<addrregexmatch>[A-Fa-f0-9]{4})')
        else:
            print(f'Warning: ignoring file with unrecognized extension: {filename}', file=sys.stderr)
            continue
        with open(filename) as file:
            for line in file.readlines():
                match = re.search(regex, line)
                if match:
                    symbolsdict[match.groupdict()['symregexmatch']] = match.groupdict()['bankregexmatch'] + ":" + match.groupdict()['addrregexmatch']
json.dump(symbolsdict, sys.stdout, indent=4)
