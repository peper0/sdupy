#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='sdupy',
      version='0.7',
      description='SduPy Simple Declarative Ui for Python',
      author='Tomasz Łakota',
      author_email='tomasz@lakota.pl',
      url='https://github.com/peper0/sdupy',
      install_requires=[
		'PyQt5',
		'pyqtgraph>=0.12.3',
		'numpy',
		'matplotlib>=3.5',
        'qasync',
		'asyncio_extras',
		'appdirs'
      ],
      packages=find_packages(),
      )
