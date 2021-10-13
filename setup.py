import setuptools
from jfc import __version__

with open('README.md', 'r') as readme_file:
    long_description = readme_file.read()

with open('requirements.txt', 'r') as requirements:
    install_requires = [
        line[:line.find('==')]
        for line in requirements.readlines()]

setuptools.setup(
    name='jfc',
    version=__version__,
    author='Miguel Murça',
    author_email='miguelmurca+jfc@gmail.com',
    description='Making Journal Club easier.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/mikeevmm/jfc',
    project_urls = {
        'Bug Tracker': 'https://github.com/mikeevmm/jfc/issues'
    },
    license='GPLv3',
    packages=['jfc'],
    entry_points = {
        'console_scripts': [
            'jfc=jfc.jfc:main'
        ]
    },
    install_requires=install_requires,
)
