# Next steps before publishing this more formally

Everything built so far has been verified structurally (syntax, API
contracts, the merge/encryption logic, the start/stop lifecycle) but has
**not** been exercised end to end against real Tuya devices or a real
network - that testing has to happen on an actual LAN, which it now is.

## 1. Real-device testing

- [ ] Run **Sync** and confirm real switches show up with correct IP,
      name, local_key, and protocol version (LAN broadcast scan).
- [ ] Add Tuya Cloud Access ID/Secret in **Cloud API settings** and
      confirm the device list, names, categories, and local_keys pull in
      correctly.
- [ ] Confirm the **MAC/ARP sweep** resolves the IP for a device that the
      broadcast scan misses (its row should show `origin: mac_sweep`
      internally, and it should get an IP without a broadcast hit).
- [ ] **Toggle a real switch on/off** from the dashboard and confirm it
      physically switches. If any device is multi-gang, check that the
      DP index (Edit -> Switch DP) controls the right gang.
- [ ] **Restart the app** and confirm devices, local_keys, and cloud
      credentials all survive correctly (encrypted store round-trip -
      `data/config.json` / `data/devices.json` should still decrypt fine
      after a restart).
- [ ] Test **both install paths** on real hardware: the plain-Python
      `start.sh`/`stop.sh` flow, and `docker compose up -d` with host
      networking - confirm Docker's host networking actually sees LAN
      broadcasts too (this is the part most likely to behave differently
      machine to machine).

## 2. Security decision: dashboard has no login

Right now the app binds to all interfaces with **no authentication** -
anyone on the same LAN/Wi-Fi can open the dashboard, reveal local_keys,
and toggle switches. That may be a perfectly reasonable choice for a
single-user home network, but it should be a conscious decision, not a
default that ships silently once other people start running this on
networks that aren't fully trusted (shared housing, small office Wi-Fi,
etc.).

Options if it needs hardening before wider release:
- Simple HTTP Basic Auth (username/password) gate in front of the whole app.
- A "setup password" prompted on first run, stored (hashed) alongside
  the existing config.
- Leave as-is, but call it out loudly in the README as a LAN-only,
  trusted-network tool (similar posture to a lot of other home-network
  dashboards).

## 3. Scope of "publishing more formally"

Still to decide - this changes what "ready" means:
- **Private share** (send the repo link to a few people) - current state
  is basically enough once real-device testing passes.
- **Public post** (r/homeassistant, HA community forum, etc.) - add a
  LICENSE file, a screenshot/GIF in the README, and probably the auth
  decision above resolved one way or the other.
- **Versioned release / prebuilt image** - tag releases on GitHub, build
  and publish a Docker image to a registry (Docker Hub or GHCR) so people
  don't have to `docker build` themselves, and consider a CHANGELOG.
- **Home Assistant add-on** - a bigger step: package this to install
  straight from HA's Supervisor/Add-on store instead of as a separate
  process/container.

## Status

- [x] Core app built: LAN scan, Cloud API sync, MAC/ARP sweep, on/off
      control, encrypted credential storage.
- [x] Modern dashboard UI (sidebar, stat cards, table/grid views,
      dark/light theme).
- [x] start/stop/restart/status scripts + docker-compose.yml.
- [x] Repo published (public) at github.com/sajid2310/tuya-dashboard.
- [ ] Real-device testing (section 1 above) - **in progress**.
- [ ] Auth decision (section 2).
- [ ] Publishing scope decision (section 3).
