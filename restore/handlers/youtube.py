
import os
import string

import easycmd

from restore.handler import SavesFileInfo


class YoutubeHandler(SavesFileInfo):
	"""Handles files that have been downloaded from youtube, if named in the right format.

	Expects files in format "{title}-{id}.{ext}"
	Requires youtube-dl and ffmpeg.
	"""
	name = 'youtube'

	# we map file extensions to args as understood by the --audio-format and --recode-video options
	AUDIO_EXTENSIONS = {
		'aac': 'aac',
		'ogg': 'vorbis',
		'mp3': 'mp3',
		'm4a': 'm4a',
		'wav': 'wav',
	}
	VIDEO_EXTENSIONS = {
		'mp4': 'mp4',
		'flv': 'flv',
		'webm': 'webm',
		'mkv': 'mkv',
	}

	@classmethod
	def splitname(cls, filepath):
		"""Returns (filename, title, id, ext) if filename is formatted correctly."""
		error = lambda msg: ValueError("Bad filename: {}".format(msg))
		filename = os.path.basename(filepath)
		name, ext = os.path.splitext(filename)
		ext = ext[1:] if ext else None # splitext returns with a leading '.' normally, or '' if no ext
		if len(name) < 12:
			raise error("too short")
		title, dash, id = name[:-12], name[-12], name[-11:]
		if dash != '-':
			raise error("no id")
		ALLOWED = set(string.letters + string.digits + '_-')
		if any(c not in ALLOWED for c in id):
			raise error("no id")
		return filename, title, id, ext

	@classmethod
	def verify_title(cls, id, title):
		"""Verify with youtube that the video of given id exists and has the given title.
		Returns boolean."""
		# "title" as understood here and the real title are somewhat different, as youtube-dl munges the
		# title when creating filenames to avoid "weird" characters
		return cls.youtube_dl('--get-filename', '-o', '%(title)s', id, exc=False) == title

	@classmethod
	def youtube_dl(cls, *args, **kwargs):
		"""Run youtube-dl and return stdout
		If kwarg exc=False, return None on error, else raise FailedProcessError as normal."""
		exc = kwargs.pop('exc', True)
		if kwargs:
			raise TypeError("Unexpected keyword args: {}".format(kwargs))
		try:
			return easycmd.cmd(['youtube-dl'] + list(args)).strip()
		except easycmd.FailedProcessError:
			if exc:
				raise
			return None

	@classmethod
	def match(cls, manifest, filepath):
		try:
			filename, title, id, ext = cls.splitname(filepath)
		except ValueError:
			return
		if not cls.verify_title(id, title):
			return
		return (id,), {'format': ext}

	def __init__(self, manifest, filepath, id, format=None):
		super(YoutubeHandler, self).__init__(manifest, filepath)
		self.id = id
		self.format = format

	def get_depends(self):
		return super(YoutubeHandler, self).get_depends() | {'/usr/bin/youtube-dl'}

	def get_args(self):
		return (self.id,), {'format': self.format}

	def restore(self, extra_data):
		args = [self.id, '--verbose', '--no-progress', '--output', self.filepath]
		if self.format in self.AUDIO_EXTENSIONS:
			args += ['--format', 'bestaudio', '--extract-audio', '--audio-format', self.AUDIO_EXTENSIONS[self.format]]
		elif self.format in self.VIDEO_EXTENSIONS:
			args += ['--format', 'bestvideo+bestaudio', '--recode-video', self.VIDEO_EXTENSIONS[self.format]]
		elif self.format is None:
			pass # allow default format
		else:
			raise ValueError("Unknown file extension: {}".format(self.format))
		self.youtube_dl(*args, exc=True)
		assert os.path.exists(self.filepath), "youtube-dl returned succesfully but file does not exist"
		super(YoutubeHandler, self).restore(extra_data)
