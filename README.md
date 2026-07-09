# shp-engine

SHP Engine is the clean core for Orhan's safe AI video automation system.

This first version is intentionally conservative: it creates dry-run video job manifests and keeps YouTube privacy set to `private` by default.

## What is included

- Python project skeleton
- Environment/secrets template
- Health check command
- Safe dry-run pipeline
- Output manifest generation
- YouTube privacy default: `private`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
cp .env.example .env
```

## Health check

```bash
shp-engine health
```

## Create a safe dry-run job

```bash
shp-engine run "mycelium"
```

The command writes:

```text
output/latest_job.json
```

## Next build steps

1. Script generator agent
2. Voiceover agent
3. Scene prompt/image/video agent
4. Render assembly layer
5. YouTube uploader with `privacyStatus=private`
6. Health supervisor that blocks unsafe publishing

## Safety rule

Real API keys must only live in local `.env`, Vercel secrets, or GitHub secrets. Never commit real secrets to the repo.
