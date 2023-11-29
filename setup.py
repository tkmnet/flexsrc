from setuptools import find_packages
from setuptools import setup
import flexsrc


def load_description():
    with open('README.md', 'r') as file:
        line = file.readline()
        prev = ''
        while line:
            if prev == '# FlexSrc\n':
                return line.rstrip()
            prev = line
            line = file.readline()
    return ''


def load_long_description():
    with open('README.md', 'r') as file:
        return file.read()


setup(
    name='flexsrc',
    version=flexsrc.__version__,
    description=load_description(),
    long_description=load_long_description(),
    long_description_content_type='text/markdown',  
    author='tkms',
    author_email='tkmnet@users.noreply.github.com',
    url='https://github.com/tkmnet/flexsrc',
    packages=find_packages(),
    install_requires=['pyyaml', 'xxhash', 'pandas', 'cfcf'],
)
