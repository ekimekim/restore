
import os

import argh

from manifest import Manifest


cli = argh.EntryPoint("restore")

@cli
def add(manifest, *path, **kwargs):
	"""Add files or folders to a manifest file, or create a new manifest if it doesn't exist"""
	manifest_path = manifest
	manifest = Manifest(manifest_path) if os.path.isfile(manifest_path) else Manifest()
	for p in path:
		manifest.add_file_tree(p)
	manifest.savefile(manifest_path)


if __name__ == '__main__':
	cli()
