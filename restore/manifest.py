

import simplejson as json


class Manifest(object):
	"""A Manifest contains the list of files and their associated handlers."""

	def __init__(self):
		self.files = {}

	def load(self, filepath):
		"""Load manifest from file, overwriting anything already present"""
		with open(filepath) as f:
			data = f.read()
		data = json.loads(data)
		for path, handler in data.items():
			name = handler['name']
			handler_data = handler['data']
			handler = Handler.from_name(name)(self, path, **handler_data)
			self.add_file(path, handler)

	def add_file_tree(self, root):
		"""Load files and folders recursively, if not already loaded"""
		for path, dirs, files in os.walk(root):
			for filename in files:
				self.add_file(filename, overwrite=False)
			self.add_file(path, overwrite=False)

	def add_file(self, path, handler=None, overwrite=True):
		self.files[path] = handler

	def save(self, filepath):
		data = {path: (handler if handler is None else dict(name=handler.name, data=handler.get_data()))
		        for path, handler in self.files}
		data = json.dumps(data)
		with open(filepath, 'w') as f:
			f.write(data)
