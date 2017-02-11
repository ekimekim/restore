
import os
import tempfile

from easycmd import cmd, FailedProcessError

from restore.handler import SavesFileInfo


def git(target, command, *args):
	if not os.path.isdir(target):
		target = os.path.dirname(target)
	return cmd(['git', '-C', target, command] + list(args))


def try_get_repo(filepath):
	"""For a path, try to find the repo path it is in.
	Will return either:
		(True, git dir) for a bare repository
		(False, top level dir) for a non-bare repository
		(None, None) if path is not part of a repo.
	For performance sake, we make the following assumptions:
		* Any bare repo will be called "*.git"
		* Any non-bare repo will contain a ".git" directory
	"""
	# Shortcuts to avoid needing to run git in most cases
	if filepath.endswith('.git') or os.path.isdir(os.path.join(filepath, '.git')):
		try:
			repo = git(filepath, 'rev-parse', '--show-toplevel')[:-1] # strip newline
			if repo:
				return False, os.path.abspath(repo)
			else: # bare repository
				repo = os.path.abspath(git(filepath, 'rev-parse', '--git-dir')[:-1])
				return True, repo
		except FailedProcessError:
			pass
	return None, None


class GitCloneHandler(SavesFileInfo):
	"""A handler that matches git repositories that have at least one remote.
	The restore action is to clone from that remote.
	Care must be taken with this handler! There are a number of situations where it
	may not do the right thing:
		* If you have commits that aren't pushed to the remote
		* If you have uncommitted changes
		* If you have untracked files
		* If two repos list each other as a remote (dependency cycle)
		* If you have multiple remotes, it may not clone from the one you intend.
		* You will lose per-repository hooks and config! It is literally a re-clone.

	This handler matches against the top level directory of the repo, or the git dir if bare.
	The files inside the repo and git dir will be HandledByParent.
	"""

	name = 'git-clone'
	restores_contents = True

	@classmethod
	def match(cls, manifest, filepath):
		# is it a directory?
		if not os.path.isdir(filepath):
			return
		# is it a repo?
		bare, repo = try_get_repo(filepath)
		if repo is None or repo != os.path.abspath(filepath):
			return
		# does it have a remote?
		remotes = filter(None, git(filepath, 'remote').split('\n'))
		if not remotes:
			return
		# multiple remotes: prefer 'origin' by default, otherwise pick first one
		remote_name = 'origin' if 'origin' in remotes else remotes[0]
		# get fetch url
		remote_info = git(filepath, 'remote', 'show', '-n', remote_name) # -n means don't query remote
		for line in remote_info.strip().split('\n'):
			if line.startswith('  Fetch URL: '):
				remote = line[len('  Fetch URL: '):]
				break
		else:
			raise ValueError("Bad output from git remote show {}: {!r}".format(remote_name, remote_info))
		return (remote,), {'bare': bare}

	def __init__(self, manifest, filepath, remote, bare=False):
		self.remote = remote
		self.bare = bare
		super(GitCloneHandler, self).__init__(manifest, filepath)

	def get_args(self):
		return (self.remote,), {'bare': self.bare}

	def get_depends(self):
		depends = super(GitCloneHandler, self).get_depends()
		if self.remote_is_local():
			depends.add(self.remote[len('file://'):] if self.remote.startswith('file://') else self.remote)
		return depends

	def restore(self, extra_data):
		flags = ['--bare'] if self.bare else []
		cmd(['git', 'clone'] + flags + [self.remote, self.filepath])
		super(GitCloneHandler, self).restore(extra_data)

	def remote_is_local(self):
		# git treats a url as a local path either with an explicit file:// transport
		# or if there is a '/' before the first ':'
		return self.remote.startswith('file://') or '/' in self.remote.split(':')[0]


class GitBundleHandler(SavesFileInfo):
	"""A handler that matches any git repo, and stores the git data directly.
	This should match after GitCloneHandler so any repositories with remotes can
	use that instead.
	It will not save any uncommitted changes.
	It will not save unreferenced commits.
	It will save "oddly" referenced commits, eg. stash. But it won't automatically recover them
		(you can still get them back by commit id).
	It will not save any per-repo hooks or config (eg. remotes), it is similar to a re-clone.
	
	This handler matches against the top level directory of the repo, or the git dir if bare.
	The files inside the repo and git dir will be HandledByParent.
	"""

	name = 'git-bundle'
	restores_contents = True

	@classmethod
	def match(cls, manifest, filepath):
		# is it a directory?
		if not os.path.isdir(filepath):
			return
		# is it a repo?
		bare, repo = try_get_repo(filepath)
		if repo is None or repo != os.path.abspath(filepath):
			return
		return (), {'bare': bare}

	def __init__(self, manifest, filepath, bare=False):
		self.bare = bare
		super(GitBundleHandler, self).__init__(manifest, filepath)

	def get_args(self):
		return (), {'bare': self.bare}

	def get_extra_info(self):
		extra_info = super(GitBundleHandler, self).get_extra_info()
		extra_info['bundle'] = git(self.filepath, 'bundle', 'create', '-', '--all')

	def restore(self, extra_info):
		# There seems to be no way to git clone from a bundle on stdin, so we use a tempfile
		with tempfile.NamedTemporaryFile() as f:
			f.write(extra_info['bundle'])
			f.flush()
			cmd(['git', 'clone', '-o', 'bundle', f.name, self.filepath])
		super(GitBundleHandler, self).restore(extra_info)
