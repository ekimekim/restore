
import os

import argh

from manifest import Manifest, edit_manifest


cli = argh.EntryPoint("restore")

@cli
def add(manifest, *path, **kwargs):
	"""Add files or folders to a manifest file, or create a new manifest if it doesn't exist"""
	manifest_path = manifest
	manifest = Manifest(manifest_path) if os.path.isfile(manifest_path) else Manifest()
	for p in path:
		manifest.add_file_tree(p)
	manifest.savefile(manifest_path)

@cli
def prune(manifest):
	"""Remove files from manifest that no longer exist"""
	with edit_manifest(manifest) as m:
		for path in m.files.keys():
			if not os.path.exists(path):
				del m.files[path]

@cli
def match(manifest):
	"""Automatically find matching handlers for all unhandled files in manifest"""
	with edit_manifest(manifest) as m:
		m.find_matches()


if __name__ == '__main__':
	cli()
