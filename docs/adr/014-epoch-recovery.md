# ADR 014: Exact epoch-boundary recovery

Status: accepted.

Saving final weights alone cannot resume a stochastic optimizer. Reinitializing Adam moments or shuffling from a new RNG state changes the trajectory. Regenerating missing inputs during recovery would also replace the frozen experiment.

Freeze all input bytes before fitting. Save model parameters, optimizer moments and step, sampler RNG, completed epoch count, initial random parameters, losses and numerical-source fingerprints atomically after each epoch. Resume only an incomplete run, preserving completed outputs. Temporary writes use unique owned paths, so an orphaned uncommitted file does not block the next atomic replacement.

Exact artifact equality with an uninterrupted run is the recovery endpoint. This leaves training objectives, seed identities, splits and thresholds unchanged. Recovering in the middle of an epoch deliberately repeats its uncommitted partial work; completed epochs are not replayed.
