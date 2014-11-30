
import os
import pwd
import grp
import weakref
from stat import S_IMODE

from classtricks import get_all_subclasses


class Handler(object):
	"""Handlers handle a particular file. Handlers have a unique name, used to look them up.
	A handler needs to be able to perform the following actions:
		Collect all data nessecary to restore a file
		Restore the file given the saved data
	Optionally, it may also specify conditions where it determines a file should be governed by it.
	For example, a package manager handler could automatically apply itself to files which the package
	manager reports as owned by a package.

	Data stored by a handler falls into two categories:
		arguments, which are passed into init, and are user-facing. These should be human-readable
			and small. When passed to init, may be in string form (eg. "0" instead of 0).
		extra data, which is gathered at backup time. These can be as large as you like.

	If a restore handler depends on another file being restored first (for example, if it uses the contents of that
	file to re-constitute the target file), it should return that filepath in get_depends().
	Note that filepaths outside the scope of the manifest are assumed to be already present.
	"""

	name = NotImplemented

	@classmethod
	def from_name(cls, name):
		for subcls in get_all_subclasses(cls):
			if subcls.name == name:
				return subcls
		raise KeyError(name)

	@classmethod
	def match(cls, manifest, filepath):
		"""Investigate file and establish if this handler should apply.
		Return None to reject, or (args, kwargs) to pass to the handler's constructor.
		Defaults to not matching anything.
		"""
		return None

	def __init__(self, manifest, filepath):
		self.filepath = filepath
		# we use a weakref for manifest to break the circular reference, and handlers shouldn't be
		# called once the manifest object is dead anyway.
		self.manifest = weakref.proxy(manifest)

	def get_args(self):
		"""Return the arguments that, if passed to __init__, would re-create an identical handler.
		Format is (args, kwargs). Note that this may be used for display, so use your judgement
		on what should be args and what should be kwargs.
		Note that all args will be converted to string."""
		return (), {}

	def get_extra_data(self):
		"""Generate or retrieve the extra data needed to restore the target file using this handler.
		Unlike args, which often describe WHAT needs saving, this is the part that acually saves the big data,
		whole files, etc.
		Returned data should be a dict {key: data}.
		"""
		return {}

	def get_depends(self):
		"""Return a set of paths that must be fully restored before this restore action can occur.
		Don't forget to include super()'s results too.
		A handler will always depend on its parent directory.
		"""
		return {os.path.dirname(self.filepath)}

	def restore(self, extra_data):
		"""Restore the target file from given saved data."""
		raise NotImplementedError


class SavesFileInfo(Handler):
	"""A handler which automatically takes care of file mode and ownership.
	Remember to call super() for get_extra_data() and restore().
	Owner and group are saved by name, not by id, since this is likely to be incorrect across machines.
	If no user exists for a file's UID, the file's owner is not saved.
	"""

	def get_extra_data(self):
		stat = os.stat(self.filepath)
		try:
			owner = pwd.getpwuid(stat.st_uid).pw_name
		except KeyError:
			owner = None
		try:
			group = grp.getgrgid(stat.st_gid).gr_name
		except KeyError:
			group = None
		return {
			'mode': S_IMODE(stat.st_mode),
			'owner': owner,
			'group': group,
		}

	def restore(self, extra_data):
		stat = os.stat(self.filepath)
		if S_IMODE(stat.st_mode) != extra_data['mode']:
			os.chmod(self.filepath, extra_data['mode'])
		uid = stat.st_uid if extra_data['owner'] is None else pwd.getpwnam(extra_data['owner'])
		gid = stat.st_gid if extra_data['group'] is None else grp.getgrnam(extra_data['group'])
		if uid != stat.st_uid or gid != stat.st_gid:
			os.chown(self.filepath, uid, gid)
