
import os
import sys

import escapes
import argh

from restore.manifest import Manifest, edit_manifest
from restore.handlers import _DEFAULT_HANDLERS, FIRST_HANDLERS, LAST_HANDLERS
from restore.handler import Handler
from restore.archive import Archive


cli = argh.EntryPoint("restore")

@cli
@argh.arg('-L', '--follow-symlinks', help='Follow any symbolic links, instead of adding the links themselves')
def add(manifest, follow_symlinks=False, *path):
	"""Add files or folders to a manifest file, or create a new manifest if it doesn't exist"""
	manifest_path = manifest
	manifest = Manifest(manifest_path) if os.path.isfile(manifest_path) else Manifest()
	for p in path:
		manifest.add_file_tree(p, follow_symlinks=follow_symlinks)
	manifest.savefile(manifest_path)

@cli
def prune(manifest):
	"""Remove files from manifest that no longer exist"""
	with edit_manifest(manifest) as m:
		for path in m.files.keys():
			if not os.path.exists(path):
				del m.files[path]

@cli
@argh.arg('handlers', nargs='*', default=[h.name for h in _DEFAULT_HANDLERS], type=str,
          help='Specific handler names to match on. If none given, the default list is used.')
@argh.arg('--no-common', help='Disable the common handlers that provide basic default functionality')
@argh.arg('--exclude', help='A comma-seperated list of handlers not to use')
@argh.arg('--overwrite', help='Ignore existing handlers and attempt to re-match everything')
def match(manifest, no_common=False, exclude='', overwrite=False, *handlers):
	"""Automatically find matching handlers for all unhandled files in manifest"""
	try:
		handlers = [Handler.from_name(name) for name in handlers]
	except KeyError as ex:
		raise argh.CommandError("No such handler: {}".format(ex))
	if not no_common:
		handlers = FIRST_HANDLERS + handlers + LAST_HANDLERS
	if exclude:
		exclude = exclude.split(',')
		for name in exclude:
			handler = Handler.from_name(name)
			if handler in handlers:
				handlers.remove(handler)

	def print_progress(done, total):
		if not total:
			return
		sys.stdout.write('{}{}Matching...{} of {} complete ({:.2f}%){}'.format(
			escapes.CLEAR_LINE, escapes.SAVE_CURSOR,
			done, total, (100. * done)/total,
			escapes.LOAD_CURSOR,
		))
		sys.stdout.flush()

	with edit_manifest(manifest) as m:
		m.find_matches(handlers, progress_callback=print_progress, overwrite=overwrite)
	print # end the partial line left by print_progress

@cli
@argh.arg('--quiet', help='List names only, no descriptions')
def list_handlers(quiet=False):
	"""Print a list of handler names and descriptions"""
	for handler in Handler.get_all():
		if quiet:
			print handler.name
			continue
		# We use the first line of the docstring as a "description"
		try:
			description = handler.__doc__.strip().split('\n')[0]
		except (AttributeError, IndexError):
			description = 'No description'
		if handler in FIRST_HANDLERS:
			description = '(common: runs first) ' + description
		if handler in LAST_HANDLERS:
			description = '(common: runs last) ' + description
		if handler in _DEFAULT_HANDLERS:
			description = '(default) ' + description
		print "{}: {}".format(handler.name, description)

@cli
def restore(archive):
	"""Restore all contents of the given archive. WARNING: May overwrite existing files."""
	archive_path = archive
	archive = Archive.from_file(archive_path)
	archive.restore()

@cli
@argh.arg('--compress', choices=['gz', 'bz2', 'none'], help='Compression algorithm to use for the archive')
def archive(manifest, archive, compress='gz'):
	"""Store backup info for manifest into an archive, which can be used to later restore the data.
	If archive path is '-', output to stdout.
	"""
	manifest = Manifest(manifest)
	if compress == 'none':
		compress = None
	if archive == '-':
		manifest.archive(sys.stdout, compress=compress)
	else:
		with open(archive, 'w') as f:
			manifest.archive(f, compress=compress)

if __name__ == '__main__':
	cli()
