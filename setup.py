#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='Flask-RESTful-Fieldsets',
    version='0.1.0',
    url='https://www.github.com/janlo/flask-restful-fieldsets/',
    author='Jan Losinski',
    description='Extension to Flask-RESTful to create fieldsets',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    test_suite = 'nose.collector',
    install_requires=[
        'Flask-RESTful>=0.1.5',
        'Flask>=0.8',
    ],
)