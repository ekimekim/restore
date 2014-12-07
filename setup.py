from setuptools import setup, find_packages

setup(
	name='restore',
	description='Application to assist in backing up and restoring highly-recoverable data',
	requires=['gevent(>=1.0)', 'argh'],
	packages=find_packages(),
)
