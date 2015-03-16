
import os
import string
from uuid import uuid4

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
		"""Returns (filename, title, id, (start, end), ext) if filename is formatted correctly.
		start/end may be None."""
		error = lambda msg: ValueError("Bad filename: {}".format(msg))
		filename = os.path.basename(filepath)
		start, end = None, None
		# find extension
		name, ext = os.path.splitext(filename)
		ext = ext[1:] if ext else None # splitext returns with a leading '.' normally, or '' if no ext
		# look for optional ".START:END" at end of name
		name_parts = name.split('.')
		time_info = name_parts[-1].split(':')
		if len(time_info) == 2 and all(part.isdigit() for part in time_info if part):
			start, end = [int(part) if part else None for part in time_info]
			# it's valid - assign remaining name_parts back to name
			name = '.'.join(name_parts[:-1])
		# look for id
		if len(name) < 12:
			raise error("too short")
		title, dash, id = name[:-12], name[-12], name[-11:]
		if dash != '-':
			raise error("no id")
		ALLOWED = set(string.letters + string.digits + '_-')
		if any(c not in ALLOWED for c in id):
			raise error("no id")
		return filename, title, id, (start, end), ext

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
			filename, title, id, (start, end), ext = cls.splitname(filepath)
		except ValueError:
			return
		if not cls.verify_title(id, title):
			return
		args = (id,)
		kwargs = dict(format=ext)
		if start is not None:
			kwargs['start'] = start
		if end is not None:
			kwargs['end'] = end
		return args, kwargs

	def __init__(self, manifest, filepath, id, format=None, start=None, end=None):
		super(YoutubeHandler, self).__init__(manifest, filepath)
		self.id = id
		self.format = format
		self.time_info = [int(part) if part else None for part in (start, end)]

	def get_depends(self):
		return super(YoutubeHandler, self).get_depends() | {'/usr/bin/youtube-dl'}

	def get_args(self):
		args = (self.id,)
		kwargs = dict(format=self.format)
		start, end = self.time_info
		if start is not None:
			kwargs['start'] = start
		if end is not None:
			kwargs['end'] = end
		return args, kwargs

	def restore(self, extra_data):
		if self.time_info == (None, None):
			self.download_to_path(self.filepath)
		else:
			start, end = self.time_info
			time_args = []
			if start is not None:
				time_args += ['-ss', start]
			if end is not None:
				interval = end if start is None else end - start
				time_args += ['-t', interval]
			# save to tmp file, then use ffmpeg to trim
			tmp_path = "/tmp/{}.{}".format(str(uuid4()), self.format)
			try:
				self.download_to_path(tmp_path)
				easycmd.cmd(['ffmpeg', '-y'] + time_args + ['-i', tmp_path, '-strict', '-2', self.filepath])
			finally:
				os.remove(tmp_path)
		super(YoutubeHandler, self).restore(extra_data)

	def download_to_path(self, filepath):
		args = [self.id, '--verbose', '--no-progress', '--output', filepath]
		if self.format in self.AUDIO_EXTENSIONS:
			args += ['--format', 'bestaudio', '--extract-audio', '--audio-format', self.AUDIO_EXTENSIONS[self.format]]
		elif self.format in self.VIDEO_EXTENSIONS:
			args += ['--format', 'bestvideo+bestaudio', '--recode-video', self.VIDEO_EXTENSIONS[self.format]]
		elif self.format is None:
			pass # allow default format
		else:
			raise ValueError("Unknown file extension: {}".format(self.format))
		self.youtube_dl(*args, exc=True)
		assert os.path.exists(filepath), "youtube-dl returned succesfully but file does not exist"
