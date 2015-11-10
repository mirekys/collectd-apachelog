#!/usr/bin/env python

import subprocess

# Dictionary of functions to be mapped to each key's value
FLDMAP = {
    'response_bytes_clf': (lambda x: str(x).replace('-','0'))
}

def remap(key, value):
    """ Returns value transformed by accorging mapping table entry """
    try:
        return FLDMAP[key](value)
    except KeyError:
        return value


def tac(filename):
	""" Yields lines of the file in the reverse order """
	proc = subprocess.Popen(['tac', filename], stdout=subprocess.PIPE)
	while True:
		line = proc.stdout.readline()
		if line:
			#the real code does filtering here
			yield line.rstrip()
		else:
			break
