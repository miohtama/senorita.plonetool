from setuptools import setup, find_packages
import os

version = '1.0'

long_description = (
    open('README.rst').read()
    + '\n' +
    'Contributors\n'
    '============\n'
    + '\n' +
    open('CONTRIBUTORS.txt').read()
    + '\n' +
    open('CHANGES.txt').read()
    + '\n')

setup(name='senorita.plonetool',
      version=version,
      description="Sysadmin helper tools to create and manage Plone sites",
      long_description=long_description,
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='',
      author='Mikko Ohtamaa',
      author_email='mikko@opensourcehacker.com',
      url='https://github.com/miohtama/senorita.plonetool',
      license='GPL2',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      namespace_packages=['senorita'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'plac',
          'sh'
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      plonetool = senorita.plonetool.main:entry_point
      """,
      )
