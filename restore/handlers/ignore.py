
from restore.handler import Handler


class IgnoreHandler(Handler):
	"""A handler that does not re-create the file, for temporary files and others you do not wish to save."""

	name = 'ignore'
	restores_contents = True

	# match on any file with these extensions
	MATCH_EXTENSIONS = {'.pyc', '.swp'}
	# match on these hard-coded paths which are places that 'temporary files' lie
	MATCH_PATHS = {
		'/dev', '/proc', '/sys',
		'/tmp', '/run', '/var/tmp', '/var/run', '/var/lock',
		'/var/cache',
	}

	@classmethod
	def match(cls, manifest, filepath):
		if (any(filepath.endswith(ext) for ext in cls.MATCH_EXTENSIONS) or
		    os.path.abspath(filepath) in MATCH_PATHS):
			return (), {}

	def restore(self):
		pass
