
import os

from restore.handler import SavesFileInfo, Handler


class BasicDirectoryHandler(SavesFileInfo):
	"""Fallback default handler for directories - simply recreates them, empty."""

	name = 'basic-directory'

	@classmethod
	def match(cls, manifest, filepath):
		# match all directories
		if os.path.isdir(filepath):
			return (), {}

	def restore(self, extra_data):
		if not os.path.isdir(self.filepath):
			os.mkdir(self.filepath)
		super(BasicDirectoryHandler, self).restore(extra_data)


class BasicFileHandler(SavesFileInfo):
	"""Fallback default handler for files - saves entire file contents as data"""

	name = 'basic-file'

	@classmethod
	def match(cls, manifest, filepath):
		# match all regular files
		if os.path.isfile(filepath):
			return (), {}

	def get_extra_data(self):
		extra_data = super(BasicFileHandler, self).get_extra_data()
		with open(self.filepath) as f:
			extra_data['content'] = f.read()
		return extra_data

	def restore(self, extra_data):
		with open(self.filepath, 'w') as f:
			f.write(extra_data['content'])
		super(BasicFileHandler, self).restore(extra_data)


class SymbolicLinkHandler(Handler):
	"""Handler to re-create symbolic links"""

	name = 'symbolic-link'

	@classmethod
	def match(cls, manifest, filepath):
		if os.path.islink(filepath):
			return (), {}

	def get_extra_data(self):
		return {'target': os.readlink(self.filepath)}

	def restore(self, extra_data):
		os.symlink(extra_data['target'], self.filepath)


class HandledByParent(Handler):
	"""A special handler that indicates the file will be restored in the process of restoring its parent directory.
	To facilitate auto-matching, handlers can implement an attribute restores_contents = True.
	Any handler with this attribute will cause all subfiles to match to this handler.
	"""
	name = 'parent'
	restores_contents = True

	@classmethod
	def match(cls, manifest, filepath):
		parent = os.path.dirname(filepath)
		parent_handler = manifest.files.get(parent, None)
		if parent_handler and getattr(parent_handler, 'restores_contents', False):
			return (), {}

	def restore(self):
		pass
