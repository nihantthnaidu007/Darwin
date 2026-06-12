# 0005 Version numbering: 0.x until production-grade

Decision: Versions stay 0.x until the engine is genuinely production-grade, then 1.0.

Context: The project ships honest milestones, not finished products. The git tags are v0.1.0 (verified single-function simplifier, untrusted-code isolation deferred) and v0.2.0 (OS-level container isolation, in-process forgery and native-Linux verification still open). The README frames each as an honest milestone, not a finished product.

Alternatives rejected:
- Tag 1.0 at the first working milestone: would overclaim relative to the open boundaries.
- No versioning: loses the honest milestone record the tags provide.

Consequences: The version number itself carries the honesty signal. 1.0 is reserved until the open boundaries (the forgery residual, native-Linux isolation, a real benchmark) are closed.
