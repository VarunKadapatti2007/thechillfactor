"""PRISM 800 m daily: skipped.

The Phase 0 spike showed one CONUS day of one variable is a 43 MB zip that
takes about 15 s, so point extraction over 45 winters would need roughly
33,000 such files. BUILD.md 3.4 says to use PRISM only if point extraction is
fast, so estimator E6 is not built. See DATA_SOURCES.md.
"""

AVAILABLE = False
