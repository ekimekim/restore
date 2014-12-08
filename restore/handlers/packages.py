
import gevent
from gevent import subprocess
from gevent.event import Event

from gtools import get_first

from restore.handler import Handler


class PackageHandler(Handler):
	"""A generic handler for files that are installed by package managers,
	and can be recovered by installing the package.
	Certain actions need to be implemented by a subclass for a specific package manager.
	"""

	# per-subcls dict maps files to owning package
	# if a file is not found, and indexing is not finished,
	# an event can be left to notify upon the file being set.
	package_index = None
	# holds the greenlet that is indexing
	indexer = None

	@classmethod
	def get_package(cls, filepath):
		"""Looks up what package owns the given file. Returns package name or None on no match."""
		if cls.package_index is None:
			cls.package_index = {} # by creating like this, the dict is cls specific,
			                       # instead of shared between all subclasses of PackageHandler

		if cls.indexer is None:
			# start indexing
			cls.indexer = gevent.spawn(cls.index_packages)

		result = cls.package_index.get(filepath, None)

		if not result:
			# it's not there yet - leave a marker to tell us if it's found
			result = Event()
			cls.package_index[filepath] = result

		if isinstance(result, Event):
			# wait for it to be found, or for indexing to finish
			get_first(result.wait, cls.indexer.get)
			new_result = cls.package_index.get(filepath, None)
			# if the file wasn't found, we need to clear the waiting event
			if new_result is result:
				del cls.package_index[filepath]
				result = None
			else:
				result = new_result

		# result is now either the package, or None
		return result

	@classmethod
	def set_package(cls, filepath, package):
		"""Tell the package index that filepath is owned by the given package."""
		if cls.package_index is None:
			cls.package_index = {} # just in case this is called before indexing starts
		current = cls.package_index.get(filepath, None)
		if isinstance(current, Event):
			current.set()
		cls.package_index[filepath] = package

	@classmethod
	def match(cls, manifest, filepath):
		package = cls.get_package(filepath)
		if package:
			return (package,), {}

	def __init__(self, manifest, filepath, package):
		super(PackageHandler, self).__init__(manifest, filepath)
		self.package = package

	def get_args(self):
		return (self.package,), {}

	def restore(self, extra_data):
		try:
			if self.check_package(self.package):
				return
		except subprocess.CalledProcessError:
			pass
		self.install_package(self.package)

	@classmethod
	def index_packages(cls):
		"""Actually does the work of indexing what package owns what file.
		This must be implemented by a subclass.
		The implementation should not insert values into package_index directly, but instead
		use cls.set_package(filepath, package).
		"""
		raise NotImplementedError

	def check_package(self, package):
		"""This method should return whether the given package is installed.
		To cover a common case, it will treat subprocess.CalledProcessError as False."""
		raise NotImplementedError

	def install_package(self, package):
		"""This method should do the actual package installation"""
		raise NotImplementedError


class PacmanHandler(PackageHandler):
	"""Package handler for archlinux's pacman package manager"""

	name = 'pacman'

	@classmethod
	def index_packages(cls):
		data = subprocess.check_output(['pacman', '-Ql'])
		for line in data.strip().split('\n'):
			package, filepath = line.split(' ', 1)
			cls.set_package(filepath, package)

	def check_package(self, package):
		subprocess.check_call(['pacman', '-Qq', package])

	def install_package(self, package):
		subprocess.check_call(['pacman', '-Sy', '--noconfirm', package])

