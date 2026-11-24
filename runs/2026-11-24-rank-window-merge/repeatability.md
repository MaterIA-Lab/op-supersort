# Repeatability check

The registered development run missed the gate on every primary input.
Single-call times varied substantially in some cells. Before closing,
rerun the same complete six-case schedule once in a fresh process with
the same inputs, source digests, flags and affinity. Build the executable
again and log its digest. Compare the separate medians for each case.

This repeat checks the decision under timing variability using the same
development inputs. The original stopping rule and the holdout seeds
stay as registered. If a repeat clears the threshold in any primary
cell, report the discrepancy with the first run.
