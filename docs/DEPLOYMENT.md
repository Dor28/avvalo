# Avvalo — MVP Deployment Guide (Hetzner)

> **Status:** Operational guide · 2026-06-27
> **Audience:** The operator (you) deploying the v1 build to a single Hetzner VM.
> **Scope:** Get the bot + (optional) web channel running in production, securely, on infrastructure that **starts small but scales without a rewrite.**
> **Companions:** Architecture is [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md); scope is [V1_BUILD_SCOPE.md](V1_BUILD_SCOPE.md). Safety/privacy rules in [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) **win on any conflict** — nothing in this guide may weaken the "no submitted content is ever persisted or logged" guarantee.

---

## 0. What you are deploying

One Docker host running four-or-fewer containers:

```
                Internet
                   │  443/80 (web only)
                   ▼
            ┌──────────────┐     TLS terminates here (Let's Encrypt via certbot);
            │ nginx+certbot│     security headers (skip for a bot-only deploy)
            └──────┬───────┘
                   │ http://app:8000  (private compose network)
                   ▼
            ┌──────────────┐     Telegram bot(s)  ── outbound long-poll ──▶ api.telegram.org
            │     app      │     FastAPI web        LLM  ── outbound ──▶ OpenAI-compatible host
            │ (bot + web)  │     APScheduler TTL    OCR  ── outbound ──▶ Google Cloud Vision
            └──────┬───────┘
                   │ postgresql+asyncpg (private network only)
                   ▼
            ┌──────────────┐
            │      db      │     PostgreSQL 16 — metadata only, NEVER content
            └──────┬───────┘
                   │ data dir
                   ▼
          /mnt/avvalo-data/pg   ← Hetzner Volume (resizable, snapshottable)
```

Two facts about this app shape the whole deployment:

1. **The Telegram bot uses long-polling, not webhooks.** It only makes *outbound* calls. A bot-only deployment needs **no inbound ports at all** beyond SSH — a very small attack surface.
2. **The web channel is optional** (`WEB_ENABLED`). It is the only thing that needs an inbound port, a domain, and TLS. If you only want the bots for the grant demo, skip every "web" step.

You will use two files added for production:

| File | Purpose |
|---|---|
| [`docker-compose.prod.yml`](../docker-compose.prod.yml) | Hardened, self-contained production stack (use **instead of** `docker-compose.yml`). |
| [`deploy/`](../deploy) | `nginx/` (config template + `init-letsencrypt.sh`), `env.prod.example`, `backup.sh`, `restore.sh`. |

---

## 1. Before you start — gather these

| Item | Where | Notes |
|---|---|---|
| Hetzner Cloud account | console.hetzner.cloud | Project + payment method. |
| SSH keypair | your laptop | `ssh-keygen -t ed25519 -C "avvalo-deploy"` if you don't have one. **Never** put the private key on the server. |
| Telegram bot token(s) | @BotFather | One per face. Family Shield is required; Seller Guard optional. The production Family Shield bot is **[@Avvalo_official_bot](https://t.me/Avvalo_official_bot)**. |
| LLM host + API key | OpenRouter / Together / Fireworks | Pick one with a **DPA + no-retention/no-training** clause. |
| Google Cloud Vision key | console.cloud.google.com | Service-account JSON with the *Cloud Vision API* enabled. Only if OCR is on. |
| Cloudflare Turnstile keys | dash.cloudflare.com → Turnstile | **Web only** — gates image upload. |
| A domain name | any registrar | **Web only.** A subdomain like `app.yourdomain.uz` is fine. |

---

## 2. Provision the VM, Volume, and Firewall

### 2.1 Create the server

In the Hetzner Cloud Console → **Add Server**:

| Setting | Recommendation | Why |
|---|---|---|
| **Location** | **Helsinki (hel1)** | Best latency to Uzbekistan among Hetzner's EU regions; EU jurisdiction supports the privacy story. (Test Singapore `sin` if your users report lag.) |
| **Image** | **Ubuntu 24.04 LTS** | Long support window; all commands below assume it. |
| **Type** | **CX22** (2 vCPU / 4 GB) to start; **CX32** (4 vCPU / 8 GB) for headroom. ARM **`CAX11`** (4 GB) / `CAX21` (8 GB) are cheaper and work. | LLM + OCR are *external*, so the box mostly runs Python + Postgres. 4 GB is enough for the MVP; 8 GB removes all worry. See the sizing breakdown below. |
| **Volume** | Add a **10 GB Volume** now | Holds the database + backups, separate from the boot disk. Resizable later with zero downtime. |
| **Networking** | Keep public IPv4 (needed for the web). Add a **Private Network** if you plan to split the DB onto its own server later. |
| **SSH key** | Paste your **public** key | Disables password login from the start. |
| **Firewall** | Create one now (next step) | |

**Sizing — which VM, and why.** The box does **no heavy compute**: the LLM and OCR are external API calls, so it mostly runs Python (aiogram + FastAPI), Postgres, and nginx. **RAM is the constraint, not CPU**, and the main driver of RAM is *concurrent web image checks* — each holds an upload (≤10 MB) and re-encodes it with Pillow. Bot text checks are tiny.

| Profile | Hetzner type | vCPU / RAM | Good for |
|---|---|---|---|
| Bot-only | `CX22` or **`CAX11`** (ARM) | 2 / 4 GB | The grant demo + bots; smallest inbound surface. |
| **Recommended (bot + web)** | **`CX22`** / **`CAX11`** (ARM, cheaper) | 2 / 4 GB | The full MVP — comfortable into the low thousands of checks/day. |
| Headroom / bursty web | `CX32` / `CAX21` | 4 / 8 GB | Heavier concurrent image uploads, or "set and forget". |

4 GB is the practical floor (also Hetzner's smallest current shared plan). **ARM `CAX*` is cheaper and fully supported** — the stack is pure-Python with arm64 wheels.

**Where 4 GB goes (web-enabled, under MVP load):**

| Component | Typical RAM | Notes |
|---|---|---|
| Postgres | ~0.4–0.7 GB | `shared_buffers=256MB` + per-connection `work_mem`; `effective_cache_size=768MB` is only a planner hint, not an allocation. |
| `app` (Python) | ~0.3–0.6 GB | Hard-capped at **1.5 GB** in `docker-compose.prod.yml`; spikes with concurrent image processing. |
| nginx + certbot | ~30–50 MB | Negligible. |
| OS + Docker daemon | ~0.4–0.6 GB | |
| **Total** | **~1.5–2.5 GB** | Leaves roughly **1–1.5 GB headroom** on a 4 GB box. |

**Add 2 GB of swap** — cheap insurance against an OOM during `docker compose … --build` (compiling/installing wheels such as Pillow) and against traffic spikes:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl -w vm.swappiness=10        # prefer RAM; swap only under real pressure
```

**Disk:** the `CX22` boot disk (40 GB) holds the OS + Docker images/layers (~2–4 GB); the **10 GB Volume** holds the Postgres data + local backups. Watch both — `df -h /` and `df -h /mnt/avvalo-data` — and alert at ~80%.

**CPU:** 2 vCPU is ample; request handling is I/O-bound on the external LLM/OCR calls. CPU matters mainly during image builds — build on a beefier box (or push a prebuilt image) if the smallest VM feels slow. When RAM pressure does show up, that's Tier 1 in §11.4: resize in the Console and raise `shared_buffers`/`work_mem` — no rebuild.

### 2.2 Hetzner Cloud Firewall (network-level, free)

Create a firewall and attach it to the server. This filters traffic **before** it reaches the VM — defense in depth alongside the host firewall.

| Direction | Port | Source | When |
|---|---|---|---|
| Inbound | TCP 22 (or your custom SSH port) | **your IP only**, if static; else `0.0.0.0/0` + rely on key-only auth + fail2ban | always |
| Inbound | TCP 80, 443 | `0.0.0.0/0`, `::/0` | **web only** |
| Outbound | all | all | leave open (bot/LLM/OCR need 443; DNS needs 53) |

> A **bot-only** deployment opens *only SSH* inbound. Do not open 80/443 unless you run the web channel.

---

## 3. Harden the server (first 10 minutes, before anything else)

SSH in as root using your key, then:

```bash
# 3.1 — Patch everything
apt update && apt -y full-upgrade

# 3.2 — Create a non-root sudo user (you will deploy as this user)
adduser --gecos "" deploy
usermod -aG sudo deploy
install -d -m 700 /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

**3.3 — Lock down SSH.** Edit `/etc/ssh/sshd_config` (or drop a file in `/etc/ssh/sshd_config.d/`) so these are set:

```
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
AllowUsers deploy
# Optional but recommended: move off port 22 (update both firewalls if you do)
# Port 2222
```

Apply and **verify in a second terminal before closing this one**:

```bash
systemctl restart ssh
# new terminal:  ssh deploy@YOUR_SERVER_IP   (must succeed; root + password must fail)
```

**3.4 — Host firewall (UFW) + fail2ban** (belt-and-suspenders with the Hetzner firewall):

```bash
apt -y install ufw fail2ban
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH            # or 'ufw allow 2222/tcp' if you changed the port
# web only:
ufw allow 80/tcp && ufw allow 443/tcp
ufw enable
systemctl enable --now fail2ban
```

**3.5 — Automatic security updates:**

```bash
apt -y install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades   # choose "Yes"
```

From here on, **work as `deploy`** (`ssh deploy@YOUR_SERVER_IP`).

---

## 4. Install Docker

```bash
# Official Docker apt repo (Ubuntu 24.04)
sudo apt -y install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Run docker without sudo (log out/in afterwards for it to take effect)
sudo usermod -aG docker deploy
sudo systemctl enable --now docker
```

> Adding `deploy` to the `docker` group grants root-equivalent power on this host. That is acceptable for a single-admin MVP box. For stricter isolation later, evaluate **rootless Docker**.

---

## 5. Mount the data Volume (database storage)

The Volume keeps the database off the boot disk so it can be resized and snapshotted on its own. The compose stack expects it at **`/mnt/avvalo-data`** (the `db` service bind-mounts `/mnt/avvalo-data/pg`).

**First, check what state the Volume is in — this matters.** When you create a Volume in the Hetzner Console, the **"Automount"** option is on by default, and Hetzner then **formats it (ext4) and mounts it for you** at `/mnt/HC_Volume_<id>`, adding a stable by-id entry to `/etc/fstab`. So your Volume is very likely *already formatted and mounted* — in which case you must **not** run `mkfs` (it would needlessly reformat a live filesystem). Look at the `MOUNTPOINTS` column:

```bash
lsblk    # find the ~10G disk (e.g. sdb) and read its MOUNTPOINTS column
```

- **`sdb` shows a mountpoint like `/mnt/HC_Volume_106189246`** → Hetzner already formatted+mounted it. **Do NOT run `mkfs`.** Just repoint it → **Case A**.
- **`sdb` shows no mountpoint** → it's a raw, unformatted disk → format and mount it yourself → **Case B**.

### Case A — Hetzner already mounted it (the common default)

Repoint the existing mount from `/mnt/HC_Volume_<id>` to `/mnt/avvalo-data`, reusing the stable by-id device reference Hetzner already put in `/etc/fstab` (paste as a block — it uses a shell variable):

```bash
grep HC_Volume /etc/fstab                        # inspect Hetzner's entry first
HCV=$(awk '/HC_Volume/{print $2}' /etc/fstab)    # current mountpoint, e.g. /mnt/HC_Volume_106189246
sudo umount "$HCV"
sudo sed -i "s#$HCV#/mnt/avvalo-data#" /etc/fstab  # only the mountpoint changes; the by-id device path is untouched
sudo mkdir -p /mnt/avvalo-data
sudo mount -a                                    # MUST return silently — an error means the fstab edit is wrong; fix before continuing
sudo rmdir "$HCV" 2>/dev/null || true            # remove the now-empty old mountpoint
```

### Case B — raw, unformatted Volume

```bash
sudo mkfs.ext4 -F /dev/sdb            # ONLY if brand new and empty — this ERASES the disk
sudo mkdir -p /mnt/avvalo-data

# Persist the mount across reboots by UUID (safer than the /dev/sdX name, which can change)
UUID=$(sudo blkid -s UUID -o value /dev/sdb)
echo "UUID=$UUID /mnt/avvalo-data ext4 discard,nofail,defaults 0 0" | sudo tee -a /etc/fstab
sudo mount -a
```

### Both cases — create the data dirs and confirm

```bash
sudo mkdir -p /mnt/avvalo-data/pg /mnt/avvalo-data/backups
df -h /mnt/avvalo-data                # confirm the ~10G Volume is mounted here
```

> `nofail` (present in both Hetzner's entry and the Case B entry) ensures the VM still boots if the Volume is ever detached. The `db` container's entrypoint will `chown` the empty `pg/` dir on first start.
>
> **Don't end up with two fstab entries for one Volume.** In Case A you *edit* Hetzner's existing line — do not also add a UUID line, or `mount -a` will try to mount the same disk twice.

---

## 6. Get the code and secrets onto the server

```bash
sudo apt -y install git
git clone <YOUR_REPO_URL> avvalo && cd avvalo     # or scp the project up
```

**Secrets directory** (for the Cloud Vision key; skip if OCR is off):

```bash
mkdir -p secrets
# From your laptop, copy the GCV service-account JSON up:
#   scp service-account.json deploy@YOUR_SERVER_IP:~/avvalo/secrets/gcv.json
chmod 700 secrets && chmod 600 secrets/gcv.json
```

---

## 7. Configure `.env`

```bash
cp deploy/env.prod.example .env
chmod 600 .env
```

**Generate the secrets on the server** and paste them into `.env`:

```bash
openssl rand -hex 32        # -> APP_HMAC_SECRET   (generate ONCE, never rotate casually)
openssl rand -hex 32        # -> WEB_SESSION_SECRET
openssl rand -base64 36     # -> POSTGRES_PASSWORD
```

Then edit `.env` and fill in:

- `TELEGRAM_TOKEN_FAMILY_SHIELD` (+ `TELEGRAM_TOKEN_SELLER_GUARD` if used)
- `POSTGRES_PASSWORD` **and the matching password inside `DATABASE_URL`** (they must be identical)
- `APP_HMAC_SECRET`, `WEB_SESSION_SECRET`
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and the `LLM_*_RATE_PER_M` from your host's pricing
- `OPERATOR_ALERT_CHAT_ID` (get yours from @userinfobot) — **wire this up; it's how the bot tells you about safety blocks**
- **Web only:** `WEB_ENABLED=true`, `AVVALO_DOMAIN`, `ACME_EMAIL`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`
- **Bot only:** set `WEB_ENABLED=false` and leave the Turnstile/domain values blank

> ⚠️ **`APP_HMAC_SECRET` is permanent.** It derives every pseudonymous user key. Rotating it orphans all consent rows and resets every rate-limit counter. Generate it once and treat it like a database — include it in your secrets backup.

---

## 8. First boot and verification

```bash
# Bot-only deploys: edit docker-compose.prod.yml first and remove the `nginx`
# and `certbot` services and the app `healthcheck` block (the health check
# needs the web). Then bring the stack up directly:

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services Up/healthy
docker compose -f docker-compose.prod.yml logs -f app  # watch it boot
```

> **Web deploys:** don't `up -d` nginx by hand the first time — nginx won't
> start until a certificate exists. Do §9 (run `deploy/nginx/init-letsencrypt.sh`),
> which creates a temporary cert, brings the whole stack up, and issues the real
> one. A bot-only deploy has no such step.

You want to see, in order: `Avvalo booted and connected to PostgreSQL`, the retention scheduler start, and `Starting family_shield bot (polling)` (and the web line if enabled).

**Verify:**

```bash
# DB connectivity (one-shot, exits 0)
docker compose -f docker-compose.prod.yml exec app python -m app.main --check

# Schema applied, and the privacy invariant holds (no content columns):
docker compose -f docker-compose.prod.yml exec db \
  psql -U avvalo -d avvalo -c "\dt"

# Web health (web deploys only)
curl -fsS http://localhost:8000/healthz        # {"ok":true}
```

Then open Telegram, send `/start` to your bot, and complete one real check end-to-end.

---

## 9. Web channel: DNS, TLS, Turnstile

Skip this entire section for a bot-only deployment.

1. **DNS.** Create an `A` record for `AVVALO_DOMAIN` → your server's IPv4 (and `AAAA` → IPv6 if you enabled it). Start **DNS-only** (no Cloudflare proxy) so certbot can pass the Let's Encrypt HTTP-01 challenge. Set `AVVALO_DOMAIN` and `ACME_EMAIL` in `.env`.
2. **Issue the certificate.** nginx will not start until a certificate exists, so bootstrap it once with the helper script (run from the repo root, after DNS resolves and ports 80/443 are open):
   ```bash
   ./deploy/nginx/init-letsencrypt.sh           # add --staging first for a dry run
   ```
   It drops a temporary self-signed cert so nginx can start, brings the whole stack up, then obtains the real Let's Encrypt cert over HTTP-01 (webroot) and reloads nginx. Renewal is automatic afterward: the `certbot` service renews twice daily and nginx reloads every 6 hours to pick up new certs. Confirm:
   ```bash
   curl -fsS https://AVVALO_DOMAIN/healthz
   ```
   The nginx config ([`deploy/nginx/templates/avvalo.conf.template`](../deploy/nginx/templates/avvalo.conf.template)) already sets HSTS, a tight Content-Security-Policy matching the actual page (self + inline bootstrap + Turnstile), `X-Frame-Options: DENY`, and `nosniff`, and redirects all HTTP to HTTPS.
3. **Turnstile.** Put your site/secret keys in `.env`. Image upload is refused unless a Turnstile token is solved ([`abuse.py`](../app/web/abuse.py)); text checks work without it. Uploads are capped at 10 MB.
   - *Abuse-control note:* the web daily limit is keyed to the **anonymous session cookie** ([`session.py`](../app/web/session.py)), so clearing cookies resets it — Turnstile is the real gate on automated abuse. Behind nginx, the app sees the proxy's IP, not the visitor's (nginx forwards it as `X-Real-IP`/`X-Forwarded-For`). If you want the app itself to see accurate client IPs (for Turnstile's optional `remoteip` or a future IP backstop), enable uvicorn proxy headers in [`_run_web`](../app/main.py) (`proxy_headers=True, forwarded_allow_ips="*"` — safe because only nginx can reach the app). Not required for launch.
4. **(Recommended hardening) Put Cloudflare in front.** Once TLS is stable, switch the DNS record to **Proxied (orange cloud)** and set SSL mode **Full (strict)** using a Cloudflare **Origin Certificate** on nginx. This hides your origin IP, absorbs DDoS, and adds a WAF — a strong fit since you already use Turnstile. (While proxied, swap certbot's HTTP-01 for the DNS-01 challenge or just install the long-lived Cloudflare Origin Cert and stop the `certbot` service.)

---

## 10. Security hardening checklist

Most of this is already baked into the production files; this is the audit list.

**Network & host**
- [x] Key-only SSH, root login disabled, `deploy` is the only allowed user (§3.3).
- [x] Two firewalls (Hetzner Cloud + UFW); only SSH (+ 80/443 for web) inbound (§2.2, §3.4).
- [x] `fail2ban` + `unattended-upgrades` active (§3.4–3.5).
- [ ] If your IP is static, restrict inbound SSH to it in the Hetzner firewall.

**Containers & data plane**
- [x] **PostgreSQL is never published to the host/internet** — no `ports:` on `db`; reachable only on the private compose network.
- [x] `no-new-privileges:true` on every service; per-container log rotation; memory/CPU caps on `app`.
- [x] SCRAM-SHA-256 password auth forced on Postgres.
- [x] GCV key mounted **read-only**; `.env` is `chmod 600`; secrets are git-ignored ([`.gitignore`](../.gitignore) covers `.env`, `service-account*.json`).
- [ ] Run `docker scout cves` (or Trivy) against the built image before launch and periodically.

**Application-level (recommended pre-deploy checks)**
- [ ] **Mark the web session cookie `Secure`.** Set `WEB_COOKIE_SECURE=true` in `.env` (already the default in [`deploy/env.prod.example`](../deploy/env.prod.example)). nginx terminates TLS, so the anonymous session cookie should never travel over plain HTTP; leave it `false` only for local http dev. *(Web deploys only.)*
- [ ] **Confirm the privacy invariant in CI/pre-deploy:** `pytest tests/test_schema_privacy.py` asserts no content columns exist. Keep it green — it is the technical guarantee behind your privacy promise.

**Secrets management (upgrade path)**
- For the MVP, a `chmod 600 .env` owned by `deploy` is acceptable.
- To version secrets safely, adopt **SOPS + age**: encrypt `.env` into the repo and decrypt on the host at deploy time. Avoids plaintext secrets sitting on disk indefinitely.

**Operational privacy**
- The app is built to **never** write submitted text, OCR text, model output, URLs, phone numbers, or file IDs to the DB or logs ([`obs/events.py`](../app/obs/events.py) rejects content-like fields; [`data/models.py`](../app/data/models.py) has no content columns). Do not add verbose logging, request-body logging, or an APM that captures payloads. nginx access logs record metadata only.

---

## 11. The database: backups, restore, and scaling

This section is the heart of "start small but be ready to scale." The schema is small and **metadata-only**; the only table that grows with usage is `check_event` (one row per check, indexed on `ts`). That makes the scaling path clean.

### 11.1 Why it's already scale-ready

- The app reaches the DB **only through `DATABASE_URL`** — you can repoint it at a bigger box, a pooler, or a managed service with **zero code change**.
- Data lives on a **resizable Volume**, independent of the VM.
- Reads for the metrics/pitch surface are aggregate-only and can later be sent to a replica.

### 11.2 Backups (set this up on day one)

Automate the included [`backup.sh`](../deploy/backup.sh) with cron. It runs `pg_dump` inside the `db` container, compresses, optionally GPG-encrypts, rotates, and optionally copies offsite.

```bash
chmod +x deploy/backup.sh deploy/restore.sh

# Daily at 02:30 UTC, encrypted, keep 14 local copies, push offsite to a Storage Box:
crontab -e
# ┌ add:
30 2 * * *  GPG_RECIPIENT="you@example.com" STORAGE_BOX="u1234@u1234.your-storagebox.de:avvalo/" /home/deploy/avvalo/deploy/backup.sh >> /home/deploy/backup.log 2>&1
```

A **Hetzner Storage Box** (~€3.81/mo for 1 TB) is the cheapest offsite target; `rsync` over SSH is built into the script. Also enable **Volume snapshots** in the Hetzner Console for fast whole-disk rollback.

> **Practice the restore.** A backup you've never restored is a hope, not a backup. Run `deploy/restore.sh <dump>` against a throwaway VM at least once.

### 11.3 Point-in-time recovery (when downtime cost rises)

`pg_dump` gives you daily granularity. When you need minute-level recovery, switch to **continuous WAL archiving** with `pgBackRest` or `WAL-G` to object storage (the compose already sets `wal_level=replica`). This is a Tier-2 upgrade, not needed for the demo.

### 11.4 The scaling ladder

Climb only as real load demands. Each rung is a config change, not a rebuild.

| Tier | Trigger | Action |
|---|---|---|
| **0 — now** | MVP / grant demo | Postgres container on the Volume; `pg_dump` backups; default SQLAlchemy pool. Comfortably handles thousands of checks/day. |
| **1 — vertical** | CPU/RAM pressure | Power off, **resize the server** in the Console (bigger CX/CPX), power on. Resize the Volume + `sudo resize2fs /dev/sdb` (online). Raise `shared_buffers`/`work_mem`/`max_connections` in `docker-compose.prod.yml`. |
| **2 — separate the DB** | DB and app contend for resources | Move Postgres to its **own Hetzner server on a Private Network**; set `DATABASE_URL` to the private IP. The DB never touches the public internet. Add a read replica for metrics if reporting grows heavy. |
| **3 — pool + partition** | Many app workers / large `check_event` | Add **PgBouncer** (see below) and **time-partition `check_event`** by month, dropping old partitions instead of `DELETE` (cheaper TTL at scale). |
| **4 — managed** | You want HA + backups handed off | Migrate via `pg_dump`/`restore` to a managed Postgres **with a DPA and acceptable data residency** (weigh this against your in-region privacy story). |

**PgBouncer caveat (read before adding it).** This app uses **asyncpg**, which relies on prepared statements. PgBouncer in **transaction** pooling mode breaks them unless you disable statement caching. If/when you introduce PgBouncer in transaction mode, make this one change in [`app/data/db.py`](../app/data/db.py):

```python
return create_async_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},          # asyncpg
    # SQLAlchemy-side prepared-statement cache off too:
    # add ?prepared_statement_cache_size=0 or pass execution options
)
```

For the MVP, **do not add PgBouncer** — direct connections with the default pool are simpler and more than sufficient.

**Time-partitioning sketch (Tier 3).** Convert `check_event` to a `PARTITION BY RANGE (ts)` table with monthly partitions; the existing `ts` index and 90-day TTL then become a one-line `DROP TABLE check_event_2026_03` instead of a bulk `DELETE`. Introduce it with an Alembic migration when row counts reach the millions.

---

## 12. Observability & operations

**Logs** (content-free by design):
```bash
docker compose -f docker-compose.prod.yml logs -f app     # app
docker compose -f docker-compose.prod.yml logs -f nginx   # web access/errors
docker compose -f docker-compose.prod.yml logs -f certbot  # cert issuance/renewal
```

**Health:** `GET /healthz` (web). The compose `app` health check polls it every 30s; `docker compose ps` shows `healthy`.

**Metrics for the pitch** (privacy-safe aggregates — checks, completion, activation, cost/check, no-signal rate, safety blocks) come from [`app/obs/metrics.py`](../app/obs/metrics.py), exposed by the operator CLI [`app/tools/metrics.py`](../app/tools/metrics.py):
```bash
docker compose -f docker-compose.prod.yml exec app python -m app.tools.metrics
docker compose -f docker-compose.prod.yml exec app python -m app.tools.metrics --days 30
docker compose -f docker-compose.prod.yml exec app python -m app.tools.metrics --json
```
These are the numbers you'll show the grant panel. The output is aggregate-only — no user keys, check IDs, or content.

**Uptime & disk alerts (do this):**
- Point an external monitor (UptimeRobot, Better Stack — free tiers) at `https://AVVALO_DOMAIN/healthz`, or use a Telegram "dead-man's switch" for bot-only.
- Watch the Volume: `df -h /mnt/avvalo-data`. Alert at 80%. The DB is tiny, but logs and backups live here too.
- **Safety alerts:** `OPERATOR_ALERT_CHAT_ID` makes the bot message you on repeated safety blocks (per [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) §9). Don't leave it blank.

---

## 13. Routine operations

**Deploy an update:** Pushing to `main` deploys automatically via GitHub Actions — see **§18**. To deploy by hand (e.g. CI is down):
```bash
cd ~/avvalo && git pull                              # refresh compose / nginx / scripts
docker compose -f docker-compose.prod.yml pull       # pull the image CI built & pushed to GHCR
docker compose -f docker-compose.prod.yml up -d
# Migrations run automatically on app start (alembic upgrade head). Watch logs.
```

**Roll back** to a previous image — no rebuild, just repoint the tag:
```bash
cd ~/avvalo
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=sha-<previous-good>/' .env   # tags are in GHCR / the Actions run logs
docker compose -f docker-compose.prod.yml up -d
# If a migration must be undone: docker compose ... exec app alembic downgrade -1
```

**Restart / stop:**
```bash
docker compose -f docker-compose.prod.yml restart app
docker compose -f docker-compose.prod.yml down          # stop all (data persists on the Volume)
```

**Run a migration manually** (e.g., before scaling to multiple instances):
```bash
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

---

## 14. Scaling the app tier (when one VM isn't enough)

The app currently runs **bot pollers + web in one process**. Telegram allows **only one poller per bot token**, so you cannot naively run multiple `app` replicas — the extra pollers get `409 Conflict`. The codebase already supports a clean split **with no code change**, driven entirely by env:

| Service | `WEB_ENABLED` | `TELEGRAM_TOKEN_*` | Replicas | Behind nginx |
|---|---|---|---|---|
| `bot` | `false` | set | **exactly 1** | no |
| `web` | `true` | **empty** | N (scale freely) | yes |

Two services, same image, different env. The web tier becomes stateless and scales horizontally; the single bot process keeps polling.

**Two required changes when you go multi-instance:**
1. **Run migrations once**, as a separate one-shot step — not from every replica's start command (drop `alembic upgrade head &&` from the per-replica command and run it in your deploy script).
2. **Run retention in exactly one place.** `start_retention_scheduler` runs in every process today; with N web replicas you'd get N concurrent nightly cleanups. Gate it behind an env flag (e.g. only the `bot` service runs it) or extract it to a scheduled `docker compose run` job. Small change in [`app/main.py`](../app/main.py).

Beyond that: a Hetzner **Load Balancer** in front of the `web` replicas, and the DB on its own server (§11.4 Tier 2). This is post-grant territory — noted so the path is known, not because you need it now.

---

## 15. Cost estimate (approximate EUR/month — verify current Hetzner pricing)

| Component | Spec | ~Cost |
|---|---|---|
| Cloud server | CX22 (2 vCPU / 4 GB) | ~€4 |
| Volume | 10 GB | ~€0.50 |
| Snapshots | a few GB | ~€0.10 |
| Storage Box (offsite backups) | BX11, 1 TB | ~€3.80 |
| **Hetzner subtotal** | | **~€8–9/mo** |
| LLM (Qwen via host) | ≤ $0.03/check budget | usage-based |
| Cloud Vision OCR | first 1k units/mo free, then ~$1.50/1k | usage-based |
| Domain + Cloudflare | free tier works | ~€10/yr domain |

A bot-only MVP runs for **under €10/month** plus per-check LLM/OCR usage well within the ≤$0.03/check ceiling.

---

## 16. Go-live checklist

- [ ] Server hardened: key-only SSH, no root login, UFW + Hetzner firewall, fail2ban, auto-updates.
- [ ] PostgreSQL **not** exposed publicly; data on the mounted Volume; strong password.
- [ ] `.env` is `chmod 600`; `APP_HMAC_SECRET` / `WEB_SESSION_SECRET` generated and **backed up**.
- [ ] `docker compose ... ps` all healthy; `--check` passes; `\dt` shows the schema with **no content columns**.
- [ ] One full check completed in Telegram (and on the web, if enabled).
- [ ] **Web:** HTTPS valid, security headers present, Turnstile gates image upload, session cookie `Secure`.
- [ ] Backups scheduled in cron **and a test restore performed**.
- [ ] Uptime monitor + disk alert configured; `OPERATOR_ALERT_CHAT_ID` set.
- [ ] `pytest` green locally, especially `tests/test_schema_privacy.py`.
- [ ] `/privacy` and `/delete_my_data` work end-to-end.

---

## 17. Troubleshooting & command cheat-sheet

| Symptom | Likely cause | Fix |
|---|---|---|
| App exits at boot, `ValidationError` | A required env var is missing/blank | Check `.env`; `config.py` fails fast on purpose. |
| `relation "..." does not exist` | Migrations didn't run | `docker compose -f docker-compose.prod.yml exec app alembic upgrade head` |
| Bot answers, but a second instance gets `409 Conflict` | Two pollers on one token | Only one `app`/`bot` process may poll a token (§14). |
| certbot can't get a certificate | DNS not pointing at the VM, ports 80/443 closed, or proxied behind Cloudflare during HTTP-01 | Use DNS-only first; verify the `A` record and firewall; re-run `deploy/nginx/init-letsencrypt.sh` (try `--staging`); check `logs -f certbot`. |
| nginx exits at boot with `cannot load certificate` | Started before a cert existed | Run `deploy/nginx/init-letsencrypt.sh` (it bootstraps a temporary cert first), don't `up -d nginx` by hand on a fresh host. |
| Web image upload always fails | Turnstile keys missing/wrong | Set `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET`; check the browser console. |
| DB container won't start on the Volume | Permissions / non-empty dir | Ensure `/mnt/avvalo-data/pg` exists and was empty on first run. |
| Disk filling up | Logs/backups on the Volume | Log rotation is set; prune old backups (`KEEP_DAYS`); resize the Volume. |

```bash
# Cheat-sheet
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f app
docker compose -f docker-compose.prod.yml exec app python -m app.main --check
docker compose -f docker-compose.prod.yml exec db psql -U avvalo -d avvalo
./deploy/backup.sh
./deploy/restore.sh /mnt/avvalo-data/backups/avvalo_<stamp>.sql.gz
```

---

## 18. Continuous deployment (GitHub Actions)

Pushes to `main` are tested, built into an image, and deployed to this VM automatically by [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Three jobs:

1. **test** — `pip install -e ".[dev]"`, `ruff check` (non-blocking), then `pytest`. **Nothing builds or deploys unless `pytest` is green.**
2. **build-and-push** — builds the image on GitHub's runners (**not** this box) and pushes it to **GHCR** as `ghcr.io/dor28/avvalo:latest` and `:sha-<commit>`.
3. **deploy** — rsyncs repo config to the server (excluding `.env` and `secrets/`), then runs [`deploy/remote-update.sh`](../deploy/remote-update.sh): pins `IMAGE_TAG` in `.env`, `docker compose pull`, `up -d`. Migrations run on app start.

This automates **updates**. The **first** bring-up (clone, `.env`, `secrets/gcv.json`, the data Volume, and — for web — the first cert via `init-letsencrypt.sh`) is still the manual §1–§9 flow. CI takes over once the box is running.

### One-time setup

**1. A dedicated CI deploy key** (don't reuse your personal key). On your laptop:
```bash
ssh-keygen -t ed25519 -f ci_deploy -N "" -C "github-actions-deploy"
ssh-copy-id -i ci_deploy.pub -p 2222 deploy@157.180.115.209   # add the PUBLIC half to the server
```
Put the **private** half (`ci_deploy`, whole file incl. BEGIN/END lines) into the `DEPLOY_SSH_KEY` secret below.

**2. GitHub repo secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | `157.180.115.209` |
| `DEPLOY_PORT` | `2222` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the **private** `ci_deploy` key |

No GHCR secret is needed for *pushing* — the workflow's built-in `GITHUB_TOKEN` (`packages: write`) handles it.

**3. Let the server pull the private image.** The GHCR package is private, so the box needs a read token. Create a GitHub **PAT** scoped to only `read:packages`, then once on the server:
```bash
echo '<YOUR_READ_PACKAGES_PAT>' | docker login ghcr.io -u Dor28 --password-stdin
```
This persists in `~/.docker/config.json`.

**4. Ensure rsync is on the server** (usually already): `sudo apt -y install rsync`.

### A deploy, end to end
`git push origin main` → **test** → **build-and-push** → **deploy**. Watch it in the repo's **Actions** tab. You can also deploy on demand from Actions → *CI / Deploy* → **Run workflow** (`workflow_dispatch`).

### Security notes
- The deploy key is **dedicated** and only logs into this box — revoke it by deleting its line from `~deploy/.ssh/authorized_keys`.
- `GITHUB_TOKEN` is scoped to `contents: read` + `packages: write`; the server's GHCR pull PAT is `read:packages` only. Least privilege both directions.
- CI **never** sends or overwrites `.env` / `secrets/` (rsync excludes them).
- The workflow trusts the host key on first contact (`ssh-keyscan`). To close that TOFU window, capture the key (`ssh-keyscan -p 2222 157.180.115.209`) into a `DEPLOY_KNOWN_HOSTS` secret and write it to `known_hosts` instead.
- For stricter supply-chain safety, pin the `actions/*` and `docker/*` actions to commit SHAs rather than `@vN`.

---

*Deploy small, keep the privacy invariant intact, and climb the §11/§14 ladders only when real usage forces it.*
