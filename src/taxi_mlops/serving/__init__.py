"""Serving-side code. Owner milestones: M4 (client+parity), M7 (transformer).

- client.py: typed request builder + smoke client against the InferenceService.
- parity.py: THE test — offline model.predict vs served predictions within 1e-6.
- transformer.py (M7): KServe transformer enriching requests from Feast online
  store; imports taxi_mlops.features for any transform (skew rule).
"""
