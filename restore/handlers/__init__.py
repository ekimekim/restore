
import basics
import packages
import example
import git
import ignore

# first and last handlers that should always be in those positions to ensure proper operation
# these cover things like restoring whole directories and fallback "just back up the file" stuff
FIRST_HANDLERS = [
	basics.HandledByParent,
]

LAST_HANDLERS = [
	basics.SymbolicLinkHandler,
	basics.BasicDirectoryHandler,
	basics.BasicFileHandler,
]

_DEFAULT_HANDLERS = [
	packages.PacmanHandler,
	ignore.IgnoreHandler,
	git.GitContentHandler,
	git.GitCloneHandler,
	git.GitBundleHandler,
]
DEFAULT_HANDLERS = FIRST_HANDLERS + _DEFAULT_HANDLERS + LAST_HANDLERS
