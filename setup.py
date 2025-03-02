import re
from setuptools import setup, find_packages
from pathlib import Path

def get_version():
    with open('ceos_ard_cli/version.py', 'r') as file:
        content = file.read()
        return re.match(r'__version__\s*=\s*"([^"]+)"', content)[1]

def get_description():
    this_directory = Path(__file__).parent
    return (this_directory / "README.md").read_text()

setup(
    name="ceos-ard-cli",
    version=get_version(),
    license="Apache-2.0",
    description="CLI tools for CEOS-ARD",
    long_description=get_description(),
    long_description_content_type="text/markdown",
    author="Matthias Mohr",
    url="https://github.com/ceos-org/ceos-ard-cli",
    install_requires=[
        "strictyaml>=1.7.0",
        "jinja2>=3.1.0",
        "click>=8.0.0",
        "playwright>=1.50.0",
        "bibtexparser==2.0.0b8"
    ],
    extras_require={},
    packages=find_packages(),
    package_data={
        "ceos_ard_cli": []
    },
    entry_points={
        "console_scripts": [
            "ceos-ard=ceos_ard_cli:cli"
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
    ],
)
