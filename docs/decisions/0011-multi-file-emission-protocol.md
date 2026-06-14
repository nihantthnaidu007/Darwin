# 0011 Multi-file emission protocol and static-only candidate validation

Decision: The multi-file generator asks the model to emit each file as a "### FILE: <relative path>" marker immediately followed by a fenced code block. The parser extracts those files and validates them statically only: every file parses, a root __init__.py is present, the entry class is statically exposed in __init__.py, and every path is relative, inside the candidate directory, and ends in .py. Candidate code is never imported or executed on the host.

Context: A stateful multi-file candidate has no single fenced block and must load as a package with the entry class exposed. The candidate is untrusted model output, so confirming loadability by importing it on the host would execute untrusted code outside the container and break the v2.0 isolation boundary (decision 0007). Static validation catches the obvious malformed cases and feeds them back; true loadability is confirmed safely inside the container by the correctness gate.

Alternatives rejected:
- A single JSON object mapping path to code: fragile under large code bodies and escaping.
- Importing the candidate on the host to confirm the entry loads: executes untrusted code outside the container.

Consequences: The protocol is backtick-fence-only and explicit-re-export-only. A tilde fence, an indented fence, or an entry exposed only via import-star or __all__ is conservatively rejected as invalid and surfaced as feedback, not a crash. Duplicate paths are last-write-wins. A missing subpackage __init__.py passes static validation but fails to import, which surfaces in the container correctness gate rather than the generator. These are the known edges of the format.
