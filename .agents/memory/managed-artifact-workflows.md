---
name: Managed artifact workflow behavior
description: Working-directory and stale-process behavior when changing a managed artifact's development service.
---

Managed artifact development commands run from that artifact's directory, not necessarily from the repository root. Root-level Django commands must set their working directory explicitly. A service process may also remain alive after its workflow is removed or replaced.

**Why:** During the Django app setup, the root-level management command first searched in the artifact directory, and the removed starter service later continued to occupy the port.

**How to apply:** Check the workflow working directory before writing run commands. If a port remains busy after replacing a workflow, inspect the process and stop only the stale service before restarting.