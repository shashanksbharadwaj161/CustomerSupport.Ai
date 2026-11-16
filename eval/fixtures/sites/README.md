# Fake demo sites (FAKE DATA)

Fictional businesses used for the M4 knowledge tests and the M8 demo agents.
- lotus-bank: bank site; robots.txt disallows /private/ (the crawler must skip it); footer has an external link (must be ignored).
- lotus-travel: tour operator incl. one Hindi page.
- lotus-js: content rendered only by JavaScript (tests the JS rendering path).

The app serves them at /demo-sites/<name>/ (see api/knowledge.py).
