from setuptools import setup

with open('README', 'r') as f:
    long_description = f.read()

setup(
   name='metadatamagic',
   version='0.1',
   description='Automagically enhance your documents in Mayan EDMS with metadata',
   license='tbd',
   long_description=long_description,
   author='Thomas Lauterbach',
   author_email='drrsatzteil@web.de',
   url='http://www.tbd.de/',
   packages=['metadatamagic'],
   python_requires='>=3.10.0',
   install_requires=[
        'wheel',
        'requests',
        'pypdfium2==3.21.0',
        'numpy',
        'uharfbuzz',
        'python-doctr[torch]',
        'dateparser',
        'price-parser',
        'Babel',
        'thefuzz[speedup]',
        'mgzip'
    ]
)