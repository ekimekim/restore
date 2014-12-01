
import random
from uuid import uuid4

from restore.handler import Handler


class ExampleHandler(Handler):
	"""This handler DOES NOT RESTORE YOUR FILE.
	It is merely an example handler for demonstration and testing purposes.
	In fact, it completely ignores the target file, instead storing some random values,
	and printing them on "restore".
	The two random values are designated "arg" and "data" and serve to demonstrate the difference
	between handler arg data and handler data.
	"""
	name = 'example'

	@classmethod
	def match(cls, manifest, filepath):
		return (random.randrange(10),), {}

	def __init__(self, manifest, filepath, value):
		super(ExampleHandler, self).__init__(manifest, filepath)
		self.value = value

	def get_args(self):
		return (self.value,), {}

	def get_extra_data(self):
		data = str(uuid4())
		print "Example handler: Storing random value {}".format(data)
		return {"random": data}

	def restore(self, extra_data):
		print "Example handler: Restoring {} with arg {} and data {}".format(self.filepath, self.value, extra_data['random'])
