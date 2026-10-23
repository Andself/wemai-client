# Bound-account, group-only experimental build

This branch extends taskmemz/wemai-client pure-uia. Upstream licenses are retained.

## Changes
- Local group allowlist is authoritative; remote config cannot expand scope.
- No private chat forwarding or sending, friend handling, moment commands, global session discovery or group-member enumeration.
- Explicit main HWND + PID + process creation time; no title-only account fallback.
- Desktop and popup selectors are scoped to the bound PID; ambiguous account roots are rejected.
- Startup and every outgoing item verify the visible nickname and stable WeChat ID.
- No binding or failed identity check means no sending. Default main entry exits without starting the bridge.
- Binding, real group names, and local configs are ignored by Git.

## Local preparation
Use Python 3.12+ and install requirements.txt into a dedicated virtual environment. Copy safety.example.toml to safety.toml, configure an exact allowed group, and keep send_enabled=false. The separate adapter must also remain disabled.

Use diagnose.py --handle <reviewed main HWND> --nickname <bot nickname> --account-id <stable WeChat ID> to create a session-local binding. These values must come from the selected small account, not the primary account. The command only validates process/window metadata. Add --verify-account to open the selected profile and check its identity; this does not send a message or connect to MaiBot. UI compatibility is NOT proven by metadata validation.

After successful profile and UI compatibility checks, set WEMAI_BINDING_FILE to the local binding path. Only after reviewing and testing the exact group may send_enabled be set to true and the adapter enabled. Restarting WeChat requires a new binding. Never rebind automatically to a different window.

## Verification
python -m unittest -v test_safety

## Limits
This build has offline policy tests, not a completed live integration test on WeChat 4.1.15.56. Upstream UI selectors and keyboard/mouse automation remain version-dependent. Foreground focus can change during automation; process-scoped selectors do not provide OS-level input isolation. Do not interact with the primary account while validating automated input. Account verification and sending are not an atomic operation. A separate Windows session/device is stronger isolation than same-desktop multi-open.

No automatic messages have been sent by this development workflow.
