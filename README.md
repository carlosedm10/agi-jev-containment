# HackSpain 2026

Local product stack for the HackSpain 2026 hackathon: FastAPI, React/Vite, and Postgres. The participant CLI is a separate binary.

- **How the system is built:** [docs/README.md](docs/README.md)
- **CLI commands:** [docs/cli.md](docs/cli.md) · official page [hackspain.app/cli](https://hackspain.app/cli)
- **Agent rules:** [AGENTS.md](AGENTS.md)

```bash
cp .env_template .env
make build
make up
```

API: http://localhost:8000/ · OpenAPI: http://localhost:8000/docs · UI: http://localhost:3000/

CLI install (macOS/Linux):

```bash
curl -fsSL https://hackspain.com/install.sh | sh
hackspain
```
