
import os
import stat
import time
from cStringIO import StringIO
from tarfile import TarFile, DIRTYPE, REGTYPE

from manifest import Manifest


class Archive(object):
	"""Archives are tar archives containing the manifest file, plus all the extra data
	needed to fully restore the listed files.
	As the emphasis is on not storing the whole archive in memory at once, you must pass a file
	object to the constructor to be written to/read from.
	When reading an archive, the given file object must be seekable.
	A file object need not be seekable when writing.
	Archives are gzip-compressed by default. Pass compress='bz2' to use bzip, or None to disable.
	When reading, compression is auto-detected.
	"""
	# cache for the listing of files in the archive
	# in the read case, cache means no need to re-read every time
	# in the write case, cache tracks what paths we've written since we can't read back to check later
	_names = None

	@classmethod
	def from_file(cls, filepath):
		fileobj = open(filepath)
		return cls(fileobj, 'r')

	def __init__(self, file, mode, compress='gz'):
		"""Open given file object as an archive. Mode must be one of 'r' or 'w' when reading or writing
		respectively.
		This module does not support appending to existing archives."""
		if mode == 'r':
			pass
		elif mode == 'w':
			mode = 'w|{}'.format(compress or '')
		else:
			raise ValueError("mode must be one of 'r', 'w': got {!r}".format(mode))
		self.tar = TarFile.open(fileobj=file, mode=mode)
		# we use this value to set "modified" times without doing lots of unneeded time checks
		self.create_time = time.time()

	# --- common methods ---

	def archive_path(self, path):
		"""Returns the location in the tar archive of the given path"""
		return "data/{}".format(path.lstrip('/'))

	# --- read methods ---

	def read(self, path):
		"""Returns the data for given file in the tar file"""
		return self.tar.extractfile(path).read()

	def get_names(self):
		if self._names is None:
			self._names = set(self.tar.getnames())
		return self._names

	def get_manifest(self):
		manifest = Manifest()
		manifest.load(self.read('manifest'))
		return manifest

	def get_extra_data(self, path):
		"""Returns all extra data associated with given path as a dict"""
		path = self.archive_path(path)
		data = {}
		# scan for path/KEY files
		for name in self.get_names():
			if os.path.dirname(name) != path:
				continue
			if not self.tar.getmember(name).isfile():
				continue
			key = os.path.basename(name)
			data[key] = self.read(name)
		return data

	def restore(self):
		# XXX: Future work: Restore files in order of receipt (dependencies permitting) for better behaviour
		# on a slow incoming stream instead of a random access file.
		manifest = self.get_manifest()
		manifest.restore_all(self)

	# --- write methods ---

	def build_tarinfo(self, path, isdir=False, size=None):
		# code adpated from TarFile.gettarinfo()
		# there seems to be no easy way to write a file without a matching "real" file to stat for info
		tarinfo = self.tar.tarinfo()
		tarinfo.tarfile = self.tar
		tarinfo.name = path # assumes posix relative path
		tarinfo.linkname = ''
		tarinfo.uid = os.geteuid()
		tarinfo.gid = os.getegid()
		tarinfo.mtime = self.create_time
		tarinfo.mode = 0644 | (stat.S_IFDIR if isdir else stat.S_IFREG)
		tarinfo.size = 0L if isdir else size
		tarinfo.type = DIRTYPE if isdir else REGTYPE
		if tarinfo.size is None:
			raise ValueError("Size is required for regular files")
		return tarinfo

	def write(self, path, value):
		if self._names is None:
			self._names = set()
		self.mkdir(os.path.dirname(path))
		value = str(value)

		pseudofile = StringIO(value)
		tarinfo = self.build_tarinfo(path, size=len(value))
		self.tar.addfile(tarinfo, pseudofile)

		self._names.add(path)

	def mkdir(self, path):
		"""Recursively create directories if they do not already exist"""
		if self._names is None:
			self._names = set()
		if not path or path in self._names:
			return

		parent = os.path.dirname(path)
		if path != parent: # this catches the root case
			self.mkdir(parent)

		self.tar.addfile(self.build_tarinfo(path, isdir=True))

		self._names.add(path)

	def add_extra_data(self, path, data):
		"""Add given data under the path for the given filepath"""
		path = self.archive_path(path)
		for key, value in data.items():
			self.write(os.path.join(path, key), value)

	def add_manifest(self, manifest):
		"""Add given manifest and all its contents."""
		self.write('manifest', manifest.dump())
		for path, handler in manifest.files.items():
			data = handler.get_extra_data()
			if data:
				self.add_extra_data(path, data)
