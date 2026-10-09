"""Stand-ins for Person 1 and Person 2 modules so app.py runs before theirs land.

app.py imports the real top-level module (inspector, vision, risk, cloud) when it
exists and falls back to the one here otherwise. Delete this folder once all four
real modules are in.
"""
