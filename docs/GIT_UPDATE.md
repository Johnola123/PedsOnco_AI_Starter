# Updating your existing GitHub repository

If your local repository is `~/PedsOnco_AI_Starter`, unzip the final package somewhere temporary, then copy its **contents** into the repository.

Example on macOS:

```bash
cd ~/Downloads
unzip PedsOnco_AI_Final_Direct_Upload.zip
rsync -av --exclude='.git' PedsOnco_AI_Starter/ ~/PedsOnco_AI_Starter/
cd ~/PedsOnco_AI_Starter
cp .env.example .env   # only if you do not already have a local .env
git status
git add .
git commit -m "Add direct MinIO S3 uploads and external URL API ingestion"
git push origin main
```

If GitHub CLI/terminal authentication is still unavailable, the source files can be uploaded through the GitHub web interface. Never upload `.env`, access tokens, patient data, or local Docker volumes.

For a disposable development deployment created from an older starter schema:

```bash
docker compose down -v
docker compose up --build -d
```

Do not remove volumes if they contain data you need. Use a proper database migration plan before upgrading a non-disposable deployment.
