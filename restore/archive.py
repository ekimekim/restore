
import os
from tarfile import TarFile

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
	_names = None

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
			if name == path or not name.startswith(path):
				continue
			if not self.tar.getmember(name).isfile():
				continue
			key = os.path.basename(name)
			data[key] = self.read(name)
		return data

	def restore(self):
		manifest = self.get_manifest()
		manifest.restore_all(self)

	# --- write methods ---

	# TODO
