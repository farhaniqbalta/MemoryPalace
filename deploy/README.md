# Deploy MemoryPalace

Target: Ubuntu 24.04, a non-root sudo-capable account, and a Git checkout owned by
that account. PostgreSQL runs in Docker; API and bot run in a virtualenv under
systemd. No domain, public API, or Telegram webhook is required for polling.

## Before deployment

1. Create the Droplet and verify SSH access. Allow inbound SSH from your own IP
   in the DigitalOcean firewall; leave ports 5432 and 8000 closed.
2. Commit and push the deployment files, then clone the repository on the server.
   Use a simple checkout path such as `/home/farhan/MemoryPalace`.
3. Create `.env` from `.env.example`. Supply the real Gemini/Anthropic keys, bot
   token, and numeric Telegram owner ID. Keep `EMBEDDING_PROVIDER=gemini`.
4. Add a randomly generated `POSTGRES_PASSWORD` and use the matching password in
   `DATABASE_URL`. URL-encode special characters in the URL password. For example:

   ```dotenv
   POSTGRES_PASSWORD=REPLACE_WITH_RANDOM_PASSWORD
   DATABASE_URL=postgresql+psycopg://postgres:REPLACE_WITH_RANDOM_PASSWORD@127.0.0.1:5432/memorypalace
   API_BASE_URL=http://127.0.0.1:8000
   ```

   Do not copy your laptop virtualenv or commit `.env`. The deployment script
   restricts `.env` to owner access and never sources it as shell code.
5. Stop the laptop's polling bot before starting the server bot. Use only one
   polling instance for a Telegram token.

## Deploy

From the server checkout, as its non-root owner:

```bash
bash scripts/deploy.sh --install-system --ingest-docs
```

`--install-system` installs Ubuntu Python/venv and Docker packages through sudo.
Omit it when those tools are already installed. `--ingest-docs` calls the selected
embedding provider and consumes API quota; omit it to keep existing chunks.

The script validates configuration, starts the database, applies migrations,
optionally ingests docs, installs two systemd units, checks API readiness, and
starts the bot. It does not create a Droplet, configure a cloud firewall, push
Git changes, or schedule backups. The readiness check verifies API startup, not
a live answer. Failed migrations/ingestion leave stopped app services for inspection.

For later updates, pull committed changes and rerun:

```bash
bash scripts/deploy.sh
```

Keep `POSTGRES_PASSWORD` unchanged for an existing database volume: changing the
Docker environment does not change an initialized PostgreSQL user's password.
The Compose project name is `memorypalace`, using its `pgdata` volume. Inspect any
existing database on the server before the first run; do not remove volumes to
resolve a credential mismatch.

## Verify and inspect

```bash
sudo systemctl status memorypalace-api memorypalace-bot
sudo journalctl -u memorypalace-api -u memorypalace-bot -f
```

Ask a known-answer question in Telegram, verify sources, then reboot the server
and repeat. Services restart automatically; the database has a restart policy.
If an existing systemd restart limit prevents startup, inspect the logs and use
`sudo systemctl reset-failed memorypalace-api memorypalace-bot` before retrying.

## Backup and restore check

Back up from the checkout (protect the backup because it contains your notes):

```bash
mkdir -p backups
chmod 700 backups
sudo docker compose --project-name memorypalace --env-file .env -f deploy/compose.yml exec -T postgres pg_dump -U postgres -Fc memorypalace > backups/memorypalace.dump
chmod 600 backups/memorypalace.dump
```

Copy backups off the Droplet. Test restoration into a separate database:

```bash
sudo docker compose --project-name memorypalace --env-file .env -f deploy/compose.yml exec -T postgres createdb -U postgres memorypalace_restore_check
sudo docker compose --project-name memorypalace --env-file .env -f deploy/compose.yml exec -T postgres pg_restore -U postgres -d memorypalace_restore_check < backups/memorypalace.dump
sudo docker compose --project-name memorypalace --env-file .env -f deploy/compose.yml exec -T postgres psql -U postgres -d memorypalace_restore_check -c 'SELECT count(*) FROM chunks;'
```

The restore-check database name must not already exist. These commands do not
replace your application database. Set up a recurring backup after the manual
restore check succeeds.

## Validation status

The shell script has passed Bash syntax and help checks locally. Actual Ubuntu
package installation, systemd startup, reboot persistence, and backup restoration
must be verified on the Droplet. No server deployment has been performed yet.

## Automatic deployment from GitHub

Workflow: local commit → push to `main` → GitHub Actions → SSH to Droplet →
fetch the pushed commit → dependencies/migrations → restart API and bot.
See `.github/workflows/deploy.yml`. No server-side polling timer is required.
Other branches do not deploy. A manual run is also available from Actions on `main`.

### One-time setup

1. Finish the initial server setup above and run the deployment script manually.
   The non-root deployment account must own the checkout and have noninteractive
   sudo access for the script's Docker/systemd/service-installation commands.
   The workflow fails rather than asking for a sudo password. This account can
   install services with administrator privileges: only trusted maintainers
   should be able to push deployment code to `main`.
2. Create a dedicated SSH key for GitHub Actions to connect to the Droplet.
   Add its public key to the deployment account's `~/.ssh/authorized_keys`.
   Save the private key as `DEPLOY_SSH_KEY` in GitHub, not in the repository.
3. Configure the Droplet to fetch this repository without prompts. For a private
   repository, use a separate read-only GitHub deploy key on the Droplet and an
   SSH `origin` URL. The Actions-to-Droplet key and Droplet-to-GitHub key serve
   different purposes. Verify `git fetch origin main` as the deployment user.
4. Create a GitHub environment named `production`. Add these environment secrets:

   | Secret | Value |
   | --- | --- |
   | `DEPLOY_HOST` | Droplet IPv4 address or DNS name (SSH port 22). |
   | `DEPLOY_USER` | Non-root deployment account. |
   | `DEPLOY_PATH` | Absolute checkout path, e.g. `/home/farhan/MemoryPalace`. |
   | `DEPLOY_SSH_KEY` | Dedicated SSH private key for the Droplet. |
   | `DEPLOY_KNOWN_HOSTS` | Verified SSH known_hosts line for the Droplet. |

   Get the host key through a trusted server console or compare its fingerprint
   before saving the known_hosts line. The workflow requires host verification.
   Leave required deployment reviewers disabled if you want fully automatic runs.
5. Permit the GitHub runner to reach SSH. A firewall limited to your laptop IP
   will block hosted runners; choose a network arrangement that admits them.
   Keep PostgreSQL and API ports private. If fixed-source SSH access is required,
   use a runner with a fixed outbound IP and adjust `runs-on` accordingly.
6. Stop the laptop bot, commit/push these files, and inspect the Actions run.

App/provider credentials stay in the server's `.env`. They are not transferred
through GitHub Actions. An automatic redeploy keeps the database volume and does
not re-ingest notes or re-embed on every code push. Run those scripts deliberately
when documents or embedding configuration change.

### Deployment behavior

- GitHub and a server-side lock serialize deployments; a running deploy is not
  cancelled by a later push. Superseded commits are skipped before checkout.
- The checkout uses the exact pushed commit in detached-HEAD mode. Do not edit
  tracked files on the server; push changes from your PC instead. `.env` stays local.
- This workflow runs deployment without a separate CI test gate. Keep local tests
  passing before pushing; a CI test job can be added later.
- Updates have a short service interruption. There is no automatic rollback of
  code, dependencies, or database migrations. A failed deployment needs log review
  before retrying. GitHub shows failure in the Actions run.
- The workflow and script are prepared locally; the SSH connection and actual
  automatic deployment still need verification after server/secrets setup.
