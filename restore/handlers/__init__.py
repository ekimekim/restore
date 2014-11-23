
import basics
import packages

DEFAULT_HANDLERS = [
	basics.HandledByParent,
	packages.PacmanHandler,
	basics.SymbolicLinkHandler,
	basics.DirectoryHandler,
	basics.FileHandler,
]
