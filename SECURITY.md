# Security Policy

## Supported versions

Security fixes are applied to the latest release on PyPI. Please make sure you are
running the most recent release before reporting an issue.

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.0     | :x:                |
| < 1.0   | :x:                |

1.0 remains on PyPI because it is the version the JOSS paper describes and because 2.0
is a deliberate API break. It is not maintained.

## Reporting a vulnerability

If you believe you have found a security vulnerability, please report it privately
rather than opening a public issue.

- Use GitHub's [private vulnerability reporting](https://github.com/tresoldi/dafsa/security/advisories/new)
  (Security → Report a vulnerability), or
- Email the maintainer at tiago.tresoldi@lingfil.uu.se.

Please include a description of the issue, the affected version(s), and, if possible, a
minimal reproduction. You can expect an initial acknowledgement within a reasonable
timeframe, and you will be kept informed as the report is investigated and resolved.

## Where the surface is

`dafsa` has no network and no authentication surface, and it has no required
dependencies. Two areas are worth pointing at:

- **Untrusted input.** Sequences and tokens come from the caller and may be adversarial:
  very long sequences, very large alphabets, tokens whose `__hash__` or `__eq__`
  misbehave. Traversal is iterative and the representation is flat, so deep input does
  not exhaust the stack, but a report of unbounded memory or non-terminating behaviour on
  a specific input is welcome.
- **Export output.** `to_dot` produces source that a caller may feed to Graphviz, and
  `write_figure` invokes `dot` itself. Token text is escaped before it reaches the DOT
  source; an input that escapes that quoting, or that injects an attribute or a shell
  argument, is a genuine vulnerability and should be reported here rather than in an
  issue.

Reports outside those areas are still welcome — this is a description of where problems
are most plausible, not a limit on what will be looked at.
