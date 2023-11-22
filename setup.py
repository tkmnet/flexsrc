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


setup(
    name='flexsrc',
    version=flexsrc.__version__,
    description=load_description(),
    author='tkms',
    author_email='tkmnet@users.noreply.github.com',
    url='https://github.com/tkmnet/flexsrc',
    packages=find_packages(),
    install_requires=['pyyaml', 'xxhash', 'pandas', 'cfcf'],
)
