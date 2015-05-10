
import os
import re

from restore.handler import Handler


class IgnoreHandler(Handler):
	"""A handler that does not re-create the file, for temporary files and others you do not wish to save.
	Automatically matches on certain file extensions and hard-coded paths.
	Specify additional paths to match using env var MATCH_IGNORE (seperate paths with : and escape : as \: )
	"""

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
	if 'MATCH_IGNORE' in os.environ:
		_paths = re.split(r'(?<!\\):', os.environ['MATCH_IGNORE'])
		_paths = [_path.replace(r"\:", ":") for _path in _paths]
		MATCH_PATHS |= set(_paths)

	@classmethod
	def match(cls, manifest, filepath):
		if (any(filepath.endswith(ext) for ext in cls.MATCH_EXTENSIONS) or
		    os.path.abspath(filepath) in cls.MATCH_PATHS):
			return (), {}

	def restore(self):
		pass
