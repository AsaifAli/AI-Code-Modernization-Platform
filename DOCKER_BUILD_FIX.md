# Docker build fix

The agent image installs Universal Ctags inside the container. The dependency installation is also configured for slow/large ARM64 wheels:

- pip timeout: 600 seconds
- pip retries: 10
- binary wheels preferred
- BuildKit pip cache enabled

Build with:

```bash
docker compose build agent_service
```

If a previous partial download timed out, simply rerun the same command; the BuildKit cache can reuse completed downloads.
