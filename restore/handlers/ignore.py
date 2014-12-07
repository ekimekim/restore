
from restore.handler import Handler


class IgnoreHandler(Handler):
	"""A handler that does not re-create the file, for temporary files and others you do not wish to save."""

	name = 'ignore'
	MATCH_EXTENSIONS = {'.pyc', '.swp'}

	@classmethod
	def match(cls, manifest, filepath):
		if any(filepath.endswith(ext) for ext in cls.MATCH_EXTENSIONS):
			return (), {}

	def restore(self):
		pass
