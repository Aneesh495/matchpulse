# ADR 008: Keep learned diagnostics out of production promotion

Status: accepted for the local diagnostic profile.

A network that learns a synthetic pattern is useful numerical evidence but does not establish football predictive quality.

Decision: Train original dense and recurrent implementations from random initialization. Save exact inputs, optimizer and RNG state. Independently replay held-out inference. Serve only the declared baseline until actual-data promotion gates pass.

Consequence: The terminal does not claim to use these learned checkpoints. Three seeds are retained, including worse-than-baseline results. Full model selection and calibration remain blocked.
