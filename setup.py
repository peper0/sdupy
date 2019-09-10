#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='sdupy',
      version='0.1',
      description='SduPy Simple Declarative Ui for Python',
      author='Tomasz Łakota',
      author_email='tomasz@lakota.pl',
      url='https://github.com/peper0/sdupy/tree/master',
      install_requires=[
		'PyQt5',
		'pyqtgraph',
		'numpy',
		'matplotlib',
		'quamash',
		'asyncio_extras',
      ],
      packages=find_packages(),
      )
