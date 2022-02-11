#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='sdupy',
      version='0.2',
      description='SduPy Simple Declarative Ui for Python',
      author='Tomasz Łakota',
      author_email='tomasz@lakota.pl',
      url='https://github.com/peper0/sdupy',
      install_requires=[
		'PyQt5',
		'pyqtgraph',
		'numpy',
		'matplotlib',
		'quamash',
		'asyncio_extras',
		'appdirs',
      ],
      packages=find_packages(),
      )
