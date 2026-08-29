"""Tools the agents can call.

Each module exposes a ``TOOL`` pair of ``(spec, fn)``: the JSON schema the
model sees, and the callable that runs when it asks for it. Agents compose
these into their own TOOLS mapping rather than importing a shared registry,
so what an agent can reach is visible in the agent itself.
"""
