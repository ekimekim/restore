
import os

from restore import SavesFileInfo


class BasicDirectoryHandler(SavesFileInfo):
	"""Fallback default handler for directories - simply recreates them, empty."""

	name = 'basic-directory'

	@classmethod
	def match(cls, filepath):
		# match all directories
		if os.path.isdir(filepath):
			return cls(filepath)

	def restore(self, extra_data):
		os.mkdir(self.filepath)
		super(BasicDirectoryHandler, self).restore(extra_data)
