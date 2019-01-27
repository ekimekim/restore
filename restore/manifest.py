
import os

from gevent.event import Event
from gevent.lock import Semaphore, DummySemaphore, RLock
from gevent.pool import Group
import gevent

import gtools

from handler import Handler
from handlers import DEFAULT_HANDLERS


class StopMatching(Exception):
	"""Raise in a match confirmation callback to gracefully stop all matching
	and return."""


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

	def add_file_tree(self, root, follow_symlinks=False):
		"""Load files and folders recursively, if not already loaded"""
		# os.walk doesn't handle trivial case of a non-directory
		if not os.path.isdir(root):
			self.add_file(root, overwrite=False, follow_symlinks=follow_symlinks)
		for path, dirs, files in os.walk(root, followlinks=follow_symlinks):
			for filename in files:
				self.add_file(os.path.join(path, filename), overwrite=False)
			self.add_file(path, overwrite=False, follow_symlinks=follow_symlinks)

	def add_file(self, path, handler=None, overwrite=True, follow_symlinks=False):
		"""Add path and associate with handler (if any).
		If path already present and overwrite=False, do nothing.
		If follow_symlinks=False, the link itself will be added.
		If follow_symlinks=True, both the link and the path it points to will be added.
		Returns added paths.
		"""
		if self.absolute is None:
			self.absolute = path.startswith('/')

		path = os.path.normpath(path)

		if self.absolute:
			path = os.path.abspath(path)
		else:
			path = os.path.relpath(path)

		ret = []

		if follow_symlinks and os.path.islink(path):
			linked_path = os.path.join(path, os.readlink(path))
			if os.path.exists(linked_path) or os.path.islink(linked_path):
				ret += self.add_file(linked_path, overwrite=False, follow_symlinks=follow_symlinks)

		if overwrite or path not in self.files:
			self.files[path] = handler
			ret.append(path)

		return ret

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
			output += "{}\t{}\t{}\n".format(path.encode('string-escape'), name, argstr)
		return output

	def load(self, data, overwrite=True):
		"""Takes the string data for the on-disk format and loads it into the object.
		See dump() for a description of the on-disk format."""
		for line in filter(None, data.split('\n')):
			parts = line.split('\t')
			parts = list(parts) + [''] * max(3 - len(parts), 0) # pad to length 3 with ''
			path, name, args = parts[:3]

			path = path.decode('string-escape')

			args = filter(None, args.split(','))
			posargs, kwargs = [], {}
			for arg in args:
				if '=' in arg:
					k, v = arg.split('=', 1)
					kwargs[k.strip()] = v.strip()
				else:
					posargs.append(arg.strip())

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

	def find_matches(self,
		handlers=DEFAULT_HANDLERS,
		progress_callback=None,
		confirm_callback=None,
		overwrite=False,
		add_root=None,
		follow_symlinks=False,
	):
		"""Search handler classes for matches for files that already exist in manifest,
		as well as given root path recurively (if given).
		Order in the handlers list determines priority.
		Parent directories are matched before children (to allow HandledByParent to work)
		but otherwise matching is done in parallel.
		Children are not added if they would be HandledByParent.
		If given, progress_callback will be called some number of times,
		with args (number finished, total). The final call will always be (total, total).
		Calls will not overlap.
		If given, confirm_callback will be called for each match, with args (path, matched handler).
		It should return either the same handler or a new one. The intent is to let a user interactively
		confirm a handler before moving on.
		Calls to confirm callback may overlap (called from different greenlets).
		Total may rise as files are added."""
		unmatched = [path for path, handler in self.files.items() if overwrite or not handler]
		unadded = [] if add_root is None or os.path.normpath(add_root) in self.files else [os.path.normpath(add_root)]
		unmatched += unadded
		ready = {path: Event() for path in unmatched}

		if progress_callback is None:
			progress_callback = lambda done, total: None

		# a manifest might contain a huge number of files, we can't try to do everything at once
		# or we will OOM/run out of fds/cause timeouts/etc.
		# however, we need to be able to proceed with whichever is next in the dependency graph,
		# so we can only limit concurrency after that check.
		MAX_CONCURRENCY = int(os.environ.get('MATCH_CONCURRENCY_MAX', 100))
		semaphore = Semaphore(MAX_CONCURRENCY)

		done = [0] # putting a number inside a list allows us to assign to it from inside a closure
		           # (since py2 doesn't have a nonlocal keyword)
		callback_lock = RLock()

		pool = Group()

		def match_path(path):
			added_paths = []
			if path in unadded:
				unadded.remove(path)
				added_paths = self.add_file(path, follow_symlinks=follow_symlinks, overwrite=False)
			self.find_match(path, handlers, _ready=ready, _lock=semaphore, _confirm_callback=confirm_callback)
			for added_path in added_paths:
				if path in self.files and self.files[path].restores_contents:
					continue # don't add subpaths of path that restores contents
				if not os.path.isdir(path):
					continue
				for filename in sorted(os.listdir(path)):
					sub_path = os.path.normpath(os.path.join(path, filename))
					# add new path if it doesn't already exist
					if sub_path not in self.files and sub_path not in unadded:
						unmatched.append(sub_path)
						unadded.append(sub_path)
						ready[sub_path] = Event()
						pool.spawn(match_path, sub_path)
			done[0] += 1
			with callback_lock:
				progress_callback(done[0], len(unmatched))

		progress_callback(0, len(unmatched))
		for path in unmatched:
			pool.spawn(match_path, path)
		unready = [e for e in ready.values() if not e.ready()]
		try:
			while unready:
				ready = gevent.wait(unready, count=1)
				for g in ready:
					g.get() # re-raise if failed
				unready = [e for e in ready.values() if not e.ready()]
		except StopMatching:
			pass
		progress_callback(len(unmatched), len(unmatched))

	def find_match(self, path, handlers=DEFAULT_HANDLERS, _ready=None, _lock=DummySemaphore(), _confirm_callback=None):
		"""Find handler from given list which matches against path and set that handler for that path in manifest.
		Other args are for internal use only (see find_matches)
		"""
		parent = os.path.dirname(path)
		if _ready and parent in _ready:
			_ready[parent].wait()
		with _lock:
			for cls in handlers:
				match = cls.match(self, path)
				if not match: continue
				args, kwargs = match
				handler = cls(self, path, *args, **kwargs)
				if _confirm_callback:
					handler = _confirm_callback(path, handler)
				self.files[path] = handler
				break
		if _ready:
			_ready[path].set()

	def restore(self, archive, path):
		"""Restore target path from given archive. Note this assumes the path's dependencies are already
		correct."""
		extra_data = archive.get_extra_data(path)
		handler = self.files[path]
		if handler:
			handler.restore(extra_data)

	def restore_all(self, archive):
		"""Restore all files in manifest, using given archive.
		NOTE: Unexpected results may happen if archive was not constructed using the exact same manifest.
		Generally, you should call archive.restore() instead, as this will force it to use the manifest
		from the archive itself.
		"""
		restored = {path: Event() for path in self.files}

		def wait_and_restore(path):
			handler = self.files[path]
			if not handler:
				return
			for dependency in handler.get_depends():
				dependency = os.path.normpath(dependency)
				if dependency in restored:
					restored[dependency].wait()
				else:
					# try to find a parent that we do know of, and depend on that instead,
					# assuming it will provide the child.
					dependency_parent = dependency
					while dependency_parent not in ['/', '.']:
						dependency_parent = os.path.dirname(dependency_parent)
						if dependency_parent in restored:
							restored[dependency_parent].wait()
							break
			self.restore(archive, path)
			restored[path].set()

		self.check_cycles()
		gtools.gmap(wait_and_restore, self.files)

	def archive(self, fileobj, compress='gz'):
		"""Write archive to given fileobj (common use cases include a file on disk, a pipe to a storage service).
		The archive contains all the info needed for a later restore operation, including the manifest itself.
		compress enables compression on the output archive and may be one of "gz", "bz2" or None.
		"""
		# late import breaks cyclic dependency
		from archive import Archive
		with Archive(fileobj, 'w', compress=compress) as archive:
			archive.add_manifest(self)

	def check_cycles(self, path=None, chain=()):
		"""Check for cycles originating from path, or all paths if path=None"""
		if path is None:
			for path in self.files:
				self.check_cycles(path)
			return

		if path not in self.files:
			return

		if path in chain:
			chain_text = " -> ".join(map(repr, chain + (path,)))
			raise ValueError("Dependency cycle: {}".format(chain_text))

		for dependency in self.files[path].get_depends():
			dependency = os.path.normpath(dependency)
			self.check_cycles(dependency, chain + (path,))


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
