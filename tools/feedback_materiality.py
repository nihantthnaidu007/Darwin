"""The materiality floor for crediting the directed-feedback loop (decision 0021).

`feedback_load_bearing` in the benchmark aggregates is true only when some case's
later-generation gain CLEARS this floor. A case can reach its best at generation
2+ yet add only a fraction of a percentage point over generation 1 -- within LLM
run-to-run noise, not evidence the loop did real work. The single-file
(benchmark.py) and multi-file (mbenchmark.py) orchestrators both reference the
constant below, so the threshold cannot drift between the two paths.
"""

# Percentage-point gain a later generation must EXCEED (strictly) for the feedback
# loop to count as load-bearing. Gains at or below this are run-to-run noise. The
# committed single-file data (gains 0.37 and 0.40) sits below it -> not load-bearing.
FEEDBACK_MATERIALITY_EPSILON_PP = 0.5
