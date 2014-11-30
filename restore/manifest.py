
import os

import simplejson as json

from handler import Handler
from handlers import DEFAULT_HANDLERS


class Manifest(object):
	"""A Manifest contains the list of files and their associated handlers.
	Manifests can contain absolute or relative paths, but not both.
	If unspecified, a manifest will adopt the absolute/relative mode depending on the first added path.
	"""

	def __init__(self, filepath=None, absolute=None):
		"""Filepath arg provides a shortcut to load a manifest from a file"""
		self.files = {}
		self.absolute = absolute
		if filepath:
			self.loadfile(filepath)

	def add_file_tree(self, root):
		"""Load files and folders recursively, if not already loaded"""
		for path, dirs, files in os.walk(root):
			for filename in files:
				self.add_file(os.path.join(path, filename), overwrite=False)
			self.add_file(path, overwrite=False)

	def add_file(self, path, handler=None, overwrite=True):
		if self.absolute is None:
			self.absolute = path.startswith('/')
		if self.absolute:
			path = os.path.abspath(path)
		elif path.startswith('/'):
			raise ValueError("Cannot add absolute path to relative path manifest")
		path = os.path.normpath(path)
		if overwrite or path not in self.files:
			self.files[path] = handler

	def dump(self):
		"""Returns the string data representing the on-disk format.
		On-disk format is one line per handler as follows:
			"{path!r}\t{handler_name}\t{args}"
		where args are a comma-seperated list of either positional args
		or key=value args. All args are strings. Internal whitespace is preserved but leading
		and trailing whitespace is not. eg. "hello world , foo =bar" would resolve to:
			("hello world",), {"foo": "bar"}
		If no handler is set, the name 'none' is used.
		The purpose of this format is to be easily hand-editable.
		"""
		output = ''
		for path, handler in sorted(self.files.items()):
			if handler:
				args, kwargs = handler.get_args()
				argstr = ", ".join(map(str, args) + ["{}={}".format(k, v) for k, v in kwargs.items()])
				name = handler.name
			else:
				name, argstr = 'none', ''
			output += "{}\t{}\t{}\n".format(json.dumps(path), name, argstr)
		return output

	def load(self, data, overwrite=True):
		"""Takes the string data for the on-disk format and loads it into the object.
		See dump() for a description of the on-disk format."""
		for line in filter(None, data.split('\n')):
			parts = line.split('\t')
			parts = list(parts) + [''] * max(3 - len(parts), 0) # pad to length 3 with ''
			path, name, args = parts[:3]

			path = json.loads(path)

			args = filter(None, args.split(','))
			posargs, kwargs = [], {}
			for arg in args:
				if '=' in args:
					k, v = args.split('=', 1)
					kwargs[k.strip()] = v.strip()
				else:
					posargs.append(arg.split())

			if name == 'none' or not name:
				handler = None
			else:
				handler = Handler.from_name(name)(self, path, *posargs, **kwargs)

			self.add_file(path, handler, overwrite=overwrite)

	def savefile(self, filepath):
		"""Save manifest to a file"""
		s = self.dump()
		with open(filepath, 'w') as f:
			f.write(s)

	def loadfile(self, filepath):
		"""Load data from file and add it to manifest"""
		with open(filepath) as f:
			self.load(f.read())

	def find_matches(self, handlers=DEFAULT_HANDLERS):
		"""Search handler classes for matches for files.
		Order in the handlers list determines priority."""
		for path in sorted(self.files):
			if self.files[path]: continue # only look for unhandled files
			for cls in handlers:
				match = cls.match(self, path)
				if not match: continue
				args, kwargs = match
				self.files[path] = cls(self, path, *args, **kwargs)
				break


class edit_manifest(object):
	"""Helper context manager to load a manifest from disk, modify it, and save it if there's no errors.
	On enter, returns a manifest object loaded from the passed in filename.
	On exit without errors, saves the manifest object under the same filename.

	This context manager is re-usable but NOT re-enterant.
	"""

	def __init__(self, filepath):
		self.filepath = filepath

	def __enter__(self):
		self.manifest = Manifest(self.filepath)
		return self.manifest

	def __exit__(self, *exc_info):
		if exc_info == (None, None, None):
			self.manifest.savefile(self.filepath)
