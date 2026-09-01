# Nimbus participant preflight

Do this **before** the workshop. It prevents model downloads and environment
setup from taking time away from the hands-on incident.

## What you need

- A laptop with Python 3.10 or newer, or a prepared GitHub Codespace.
- Two terminal tabs and a code editor.
- About 3 GB of free disk space for Python packages and the two small models.

## Local setup

From the `adsc-workshop` folder, run:

```bash
make setup
.venv/bin/python .devcontainer/prefetch.py
```

The second command downloads the model weights once. It can take several
minutes; wait until it prints `all weights cached.`

Nimbus then serves strictly from that local cache; it will not reach out to the
internet during the activity.

Then verify the service can start:

```bash
make serve
```

When you see `Nimbus ready`, stop it with `Ctrl-C`. You are ready. During the
workshop you will start it again, benchmark it, and edit only
`01_deploy/config.py`.

## Codespaces setup

Open the repository in a Codespace at least once before the session. Wait for
the post-create setup to finish and for the terminal to print `Nimbus workshop
ready.` Then run `make serve` once and stop it after `Nimbus ready` appears.

## If setup fails

Do not spend workshop time debugging package installation. Join a teammate or
use the paper track; it teaches the same decision process. Tell a facilitator
which command and error you saw.
