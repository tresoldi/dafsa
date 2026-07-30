# Contributing

When contributing to this library, please first discuss the change you wish to
make via a GitHub issue or, if necessary, email to the author.

Please note that we have a code of conduct. Be sure to follow it in all your
interactions with the project.

## Development setup

The library targets Python 3.10 and later.

```bash
git clone https://github.com/tresoldi/dafsa.git
cd dafsa
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Before opening a pull request, run what CI runs:

```bash
ruff check .              # lint
ruff format .             # format
mypy                      # type-check
pytest                    # tests
mkdocs build --strict     # documentation
```

All five must pass, and `make quality` runs the first three. `mypy` covers `src/`, `tests/`
and `benchmarks/`, so new code needs type annotations. Docstrings are Google style, checked
by ruff's pydocstyle rules and rendered by mkdocstrings.

`master` is the 2.0 development line, and 2.0 is a deliberate break from the released 1.0.
Before proposing a change, please read [`ARCHITECTURE.md`](ARCHITECTURE.md): it records the
package structure, the API contract, the audit of 1.0 that motivated the rewrite, and the
decisions taken along the way. A change that cuts against a decision recorded there is worth
discussing in an issue first — the decision may well be wrong, but it should be revised
deliberately rather than by accident.

## Pull Request Process

1. Try to follow best practices for good commit messages; when in doubt,
   err in favour of verbosity. Remember that a commit message should
   explain *what* and *why*, not *how*. Our informal reference
   to best practices
   [is the one by Chris Beams](https://chris.beams.io/posts/git-commit/).
2. Add tests for the behaviour you are changing. For anything touching the automata
   themselves, prefer a test that checks the result against an independent reference (a plain
   Python `set`, a brute-force computation) over one that asserts the current output.
3. Update the documentation under `docs/` when you change the interface, and note user-visible
   changes for the changelog.
4. The versioning scheme is [SemVer](https://semver.org/).
5. Pull requests are merged once another contributor has signed off; if you lack permission to
   merge, ask a maintainer to do it for you.

## Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as
contributors and maintainers pledge to making participation in our project and
our community a harassment-free experience for everyone, regardless of age,
body size, disability, ethnicity, gender identity and expression, level of
experience, nationality, personal appearance, race, religion, or sexual
identity and orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment
include:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behavior by participants include:

* The use of sexualized language or imagery and unwelcome sexual attention or
advances
* Trolling, insulting/derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or electronic
  address, without explicit permission
* Other conduct which could reasonably be considered inappropriate in a
  professional setting

### Our Responsibilities

Project maintainers are responsible for clarifying the standards of acceptable
behavior and are expected to take appropriate and fair corrective action in
response to any instances of unacceptable behavior.

Project maintainers have the right and responsibility to remove, edit, or
reject comments, commits, code, wiki edits, issues, and other contributions
that are not aligned to this Code of Conduct, or to ban temporarily or
permanently any contributor for other behaviors that they deem inappropriate,
threatening, offensive, or harmful.

### Scope

This Code of Conduct applies both within project spaces and in public spaces
when an individual is representing the project or its community. Examples of
representing a project or community include using an official project e-mail
address, posting via an official social media account, or acting as an
appointed representative at an online or offline event. Representation of a
project may be further defined and clarified by project maintainers.

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported by contacting the lead developer at
<tresoldi@shh.mpg.de>. All
complaints will be reviewed and investigated and will result in a response that
is deemed necessary and appropriate to the circumstances. The project team is
obligated to maintain confidentiality with regard to the reporter of an
incident. Further details of specific enforcement policies may be posted
separately.

Project maintainers who do not follow or enforce the Code of Conduct in good
faith may face temporary or permanent repercussions as determined by other
members of the project's leadership.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage],
version 1.4, available at
[http://contributor-covenant.org/version/1/4][version]

[homepage]: http://contributor-covenant.org
[version]: http://contributor-covenant.org/version/1/4/
