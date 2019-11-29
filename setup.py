import pathlib
from setuptools import setup

# The directory containing this file
LOCAL_PATH = pathlib.Path(__file__).parent

# The text of the README file
README_FILE = (LOCAL_PATH / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="dafsa",
    version="0.3",
    description="Library for computing Deterministic Acyclic Finite State Automata (DAFSA)",
    long_description=README_FILE,
    long_description_content_type="text/markdown",
    url="https://github.com/tresoldi/dafsa",
    author="Tiago Tresoldi",
    author_email="tresoldi@shh.mpg.de",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
    ],
    packages=["dafsa", "resources"],
    keywords=[
        "dafsa",
        "dawg",
        "finite state",
        "deterministic acyclic finite state automaton",
        "directed acyclic word graph",
    ],
    include_package_data=True,
    install_requires=["networkx"],
    entry_points={"console_scripts": ["dafsa=dafsa.__main__:main"]},
    test_suite="tests",
    tests_require=[],
    zip_safe=False,
)
