# References

The algorithms `dafsa` implements, and where to read about them.

!!! note "DOIs pending verification"

    Bibliographic details below are recorded from the literature; the DOI/link pass has not
    been done yet, so only URLs verified against this repository are included. Adding
    resolvable identifiers is part of the documentation milestone.

## Minimal acyclic DFA construction

The incremental construction used by `Trie` and `Dafsa` — insert sorted sequences, minimize
the suffix behind you, keep a register of already-minimized states — is Daciuk's:

- Daciuk, Jan; Mihov, Stoyan; Watson, Bruce W.; Watson, Richard E. (2000).
  "Incremental Construction of Minimal Acyclic Finite-State Automata."
  *Computational Linguistics* 26(1): 3–16.
- Daciuk, Jan (1998). *Incremental Construction of Finite-State Automata and Transducers, and
  their Use in the Natural Language Processing.* PhD thesis, Technical University of Gdańsk.
- Ciura, Marcin G.; Deorowicz, Sebastian (2001). "How to squeeze a lexicon."
  *Software: Practice and Experience* 31(11): 1077–1090.

`dafsa` 1.0 was based on Steve Hanov's public-domain Python sketch of the same algorithm:

- Hanov, Steve (2011). "Succinct Data Structures: Cramming 80,000 words into a Javascript
  file." <http://stevehanov.ca/blog/?id=115>

### Daciuk's reference implementations

Jan Daciuk published C and C++ implementations of these algorithms (`fsa`, `adfa`, `fadd`,
`ccip`, `utr`, `minim`). They were originally at

> `http://galaxy.eti.pg.gda.pl/katedry/kiw/pracownicy/Jan.Daciuk/personal/minim.html`

which is no longer reachable. The [archive.org
snapshot](https://web.archive.org/web/20160531133017/http://galaxy.eti.pg.gda.pl/katedry/kiw/pracownicy/Jan.Daciuk/personal/minim.html)
preserves the page but not the archives themselves. Daciuk's personal page is at
<http://www.jandaciuk.pl/>.

Copies of those tarballs were vendored in this repository under `daciuk/` from version 0.5
until the 2.0 rewrite, when they were removed: they are GPL-2 licensed while this project is
MIT, and 896 KB of third-party C source is not something a Python library should carry. They
remain in the git history and can be recovered with:

```bash
git log --all --oneline -- daciuk/            # find a revision that still has them
git show <revision>:daciuk/fsa_0.51.tar.gz > fsa_0.51.tar.gz
```

## Suffix automata and CDAWGs

`SuffixAutomaton` and `Cdawg` index every substring of a sequence, which is a different
problem from storing a dictionary of whole sequences:

- Blumer, Anselm; Blumer, Janet; Haussler, David; Ehrenfeucht, Andrzej; Chen, M. T.;
  Seiferas, Joel (1985). "The smallest automaton recognizing the subwords of a text."
  *Theoretical Computer Science* 40: 31–55.
- Blumer, Anselm; Blumer, Janet; Haussler, David; McConnell, Ross; Ehrenfeucht, Andrzej
  (1987). "Complete inverted files for efficient text retrieval and analysis."
  *Journal of the ACM* 34(3): 578–595.
- Inenaga, Shunsuke; Hoshino, Hiromasa; Shinohara, Ayumi; Takeda, Masayuki; Arikawa, Setsuo;
  Mauri, Giancarlo; Pavesi, Giulio (2005). "On-line construction of compact directed acyclic
  word graphs." *Discrete Applied Mathematics* 146(2): 156–179.

## Weighted automata and semirings

The semiring layer, weight-aware minimization, weight pushing, and transducer composition
follow the weighted finite-state transducer literature:

- Mohri, Mehryar (1997). "Finite-State Transducers in Language and Speech Processing."
  *Computational Linguistics* 23(2): 269–311.
- Mohri, Mehryar (2009). "Weighted Automata Algorithms." In *Handbook of Weighted Automata*,
  edited by Manfred Droste, Werner Kuich, and Heiko Vogler, 213–254. Springer.
- Mohri, Mehryar; Pereira, Fernando; Riley, Michael (2002). "Weighted finite-state transducers
  in speech recognition." *Computer Speech & Language* 16(1): 69–88.
- Allauzen, Cyril; Riley, Michael; Schalkwyk, Johan; Skut, Wojciech; Mohri, Mehryar (2007).
  "OpenFst: A General and Efficient Weighted Finite-State Transducer Library."
  In *Implementation and Application of Automata (CIAA 2007)*, 11–23. Springer.

## This library

- Tresoldi, Tiago (2020). *DAFSA, a library for computing Deterministic Acyclic Finite State
  Automata.* Version 1.0. Jena.
  DOI: [10.5281/zenodo.3668870](https://doi.org/10.5281/zenodo.3668870)
- Tresoldi, Tiago (2020). "DAFSA: a Python library for Deterministic Acyclic Finite State
  Automata." Submitted to the *Journal of Open Source Software*;
  [review thread](https://joss.theoj.org/papers/10d826c5b26e5222beb1b3780d606725). The
  manuscript source is kept in `manuscript/` in this repository.
