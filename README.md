# Tuya Local Dashboard

A one-page, TasmoAdmin-style dashboard for finding and controlling local
Tuya switches — built for people using the **Tuya Local** integration in
Home Assistant who want an easy way to discover device IPs and local keys.

It combines two discovery methods:

- **LAN scan** — listens for the UDP broadcasts Tuya devices send on
  your local network (ports 6666/6667/7000) to find IP, device ID and
  protocol version.
- **Tuya Cloud API** — using your Tuya IoT Platform Access ID/Secret,
  pulls your full device list (names, categories, and local_keys) and
  matches it against what's on the LAN.

One click ("Sync devices") runs both and merges the results, so you get
IP + local_key + version for every switch in one table — everything
Home Assistant's Tuya Local integration needs, and enough to flip
switches on/off right from this page.

## Important: this must run on your home LAN

Discovery relies on UDP broadcast packets, which don't cross subnets,
VLANs, or the internet. Run this on a machine on the **same network** as
your Tuya devices (e.g. the same host running Home Assistant, a Raspberry
Pi on your LAN, or your own computer at home) — not in a cloud VM or a
Docker network in bridge mode.

## Getting your Tuya Cloud Access ID/Secret (optional but recommended)

Local-only scanning finds devices but usually can't get their local_key
(Tuya only reveals it through the cloud once a device is paired to your
account). To auto-fill names and keys:

1. Go to https://iot.tuya.com and create a free developer account.
2. Create a **Cloud Project** (any plan works, incl. Trial).
3. Under the project's **Devices** tab, choose "Link Tuya App Account"
   and scan the QR code with your Smart Life / Tuya Smart app to link
   the account your switches are registered to.
4. Copy the project's **Access ID/Client ID** and **Access Secret/Client
   Secret** from the Overview tab.
5. Paste them into this dashboard's "Cloud API settings".

If you skip this, the dashboard still works — it'll show devices found
on the LAN, and you can paste in an IP/local_key manually via "Edit" if
you already have them from elsewhere (e.g. `tinytuya wizard`, or an
existing Home Assistant `.storage` file).

## Running it

### Option A: Python directly

```bash
cd tuya-dashboard
pip install -r requirements.txt
python app.py
```

Then open `http://<this-machine's-ip>:8080`.

### Option B: Docker

Because discovery needs to see LAN broadcast traffic, run the container
with **host networking** (bridge mode will not see the broadcasts):

```bash
cd tuya-dashboard
docker build -t tuya-dashboard .
docker run -d --name tuya-dashboard \
  --network host \
  -v tuya-dashboard-data:/data \
  tuya-dashboard
```

Then open `http://<host-ip>:8080` (host networking means it binds
directly to port 8080 on the host).

## Using it

1. Click **Cloud API settings** and enter your Access ID/Secret (optional).
2. Click **Sync devices**. This takes ~15 seconds — it queries the cloud
   (if configured) then listens on the LAN for broadcasts, matching them
   up by device ID.
3. Each row shows name, online status, IP, device ID, local key,
   protocol version and category. Click the eye icon to reveal a key,
   the clipboard icon to copy it, and the toggle to turn a switch on/off.
4. Use the ✎ edit icon to fix an IP that changed, paste in a local_key
   you already have, or set which DP index controls the switch (most
   single switches use DP `1`; multi-gang switches use `1`, `2`, `3`…).

Copy the IP + Device ID + Local Key straight into Home Assistant's
**Settings → Devices & Services → Add Integration → Tuya Local** flow
for each switch.

## Notes & limitations

- Not every Tuya device broadcasts continuously, and some protocol 3.4/3.5
  devices are quieter — if a device doesn't show up, try Sync again, or
  check the device is on and connected to Wi-Fi.
- If a device is missing from the LAN scan but is in your Cloud account,
  it'll still show up in the table (with its name/key) but marked
  Offline / no IP, until it's seen on the network.
- This is an independent tool built on the [tinytuya](https://github.com/jasonacox/tinytuya)
  library; it is not affiliated with Tuya, Home Assistant, or TasmoAdmin.

## Credential storage

Your Tuya Access Secret and every device's `local_key` are sensitive —
they grant control over physical devices in your home. They are:

- Encrypted at rest with [Fernet](https://cryptography.io/en/latest/fernet/)
  (AES-128-CBC + HMAC) before being written to `data/config.json` and
  `data/devices.json`. The API also never echoes the raw access_secret
  back to the browser.
- Decrypted only in memory, when the app needs to call the Tuya Cloud API
  or talk to a device on your LAN, and when the dashboard displays a key
  for you to copy into Home Assistant.

The encryption key itself comes from the `APP_SECRET_KEY` environment
variable. If you don't set one, the app generates and persists a key to
`data/secret.key` on first run so restarts keep working — fine for a
quick local test, but for any real deployment you should set
`APP_SECRET_KEY` explicitly (e.g. `openssl rand -base64 32` to generate
one) via your platform's secrets manager, and back it up. If that key is
ever lost, every stored secret becomes unreadable and you'll need to
re-enter your Access Secret and re-sync devices.

`data/` (config, devices, and the local key file) is already in
`.gitignore` — never commit it.

## Production notes: making this available to other people

The discovery and control features in this app depend on being on the
same LAN as your Tuya devices — UDP broadcast and the local device
protocol (TCP port 6668) don't route over the internet. That shapes how
"productionizing" this can work:

- **Self-hosted (recommended, matches how TasmoAdmin/most HA-adjacent
  tools distribute)**: publish the code as an open-source repo. Anyone
  who wants to use it clones/Docker-runs their *own* instance on their
  *own* network, using their *own* Tuya credentials. No user accounts or
  multi-tenant data store needed — each install is single-user by
  design, which is also why the credential storage above is deliberately
  simple (one config file, not a database of everyone's secrets).
- **Centrally hosted for many users**: only works for the Cloud API
  parts (device listing/naming), not LAN discovery or local on/off
  control, since a remote server can't reach into someone else's home
  network. You'd need real user accounts, per-user encrypted secrets in
  a database (not flat files), HTTPS, and switching device control to
  Tuya's Cloud API device-control endpoints instead of the local
  protocol — a meaningfully bigger project, and it gives up the "local"
  part of "Tuya Local" that this was built around.
