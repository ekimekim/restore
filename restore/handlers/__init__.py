
import basics
import packages
import example

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

DEFAULT_HANDLERS = [
	packages.PacmanHandler,
]
DEFAULT_HANDLERS = FIRST_HANDLERS + DEFAULT_HANDLERS + LAST_HANDLERS
