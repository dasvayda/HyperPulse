---
name: hyperpulse-local-server
description: Start or restart HyperPulse local servers on Windows when the user asks, either the full site or the backend-only whale alert observer.
---

From the HyperPulse repository root, choose a mode and run the project PowerShell script:

- Full site (backend on 8100, frontend on 3100): `powershell -NoProfile -ExecutionPolicy Bypass -File backend/scripts/restart_local.ps1 -Mode Full`
- Backend-only monitoring: use `-Mode Monitor` in the same command. It starts the non-sending observer for 24 hours, sampling 30 wallets every two minutes.

Use `-Plan` to inspect identified processes and port conflicts without changing server state. The script replaces both existing HyperPulse services when switching modes. If a listener's ownership cannot be established, identify it before taking any action; a port alone is insufficient. If the sandbox denies CIM or persistent process launch, use the shell's escalation mechanism.

Report the verified URLs and log paths. Use the reported observation JSONL for subsequent monitoring. Both modes disable Telegram delivery by default; for an explicitly requested live Telegram test, pass `-SendTelegram` with `-Mode Full`.
