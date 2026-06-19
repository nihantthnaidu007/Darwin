"""Darwin: a verified code-optimization engine.

Single namespace package for the engine modules. Importing the package has no side
effects (no logging configured, no environment mutated); see logsetup and generator.
Data directories (cases/, mcases/, runs/, reports/, seeds/) live at the checkout root,
outside the package; darwin.paths resolves that root. See CONTEXT.md.
"""
