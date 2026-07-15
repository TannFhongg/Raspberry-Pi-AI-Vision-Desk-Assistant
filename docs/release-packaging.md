# VisionDesk release packaging

This document defines the appliance update package for VisionDesk 1.0.2. It is
separate from GitHub's generated **Source code.zip** and **Source code.tar.gz**:
those source snapshots do not contain the package manifest and checksum file
required by `update.sh`.

## `update.sh` archive contract

The updater extracts the archive into a staging directory, then identifies the
release root as either:

1. the extraction root when it contains `visiondesk/version.py`; or
2. the first immediate child directory that contains `visiondesk/version.py`.

For that release root, the updater requires:

- `manifest.json` at the release root;
- a non-empty `manifest.version`, converted to text by the updater;
- `manifest.checksums_file` when supplied, otherwise `checksums.sha256`;
- the declared checksum file at the release root (or its declared relative path);
- checksum lines accepted by `sha256sum -c`, executed from the release root;
- source `visiondesk/version.py` whose `__version__` exactly matches the
  requested `--version` (when supplied) and `manifest.version`;
- `qt_app/main.py`, `deployment/visiondesk-launch.sh`, and
  `deployment/visiondesk.service`;
- either `requirements.txt` or `requirements.lock`.

`update.sh` does not define a general file blacklist or require checksum coverage
for every file. The official VisionDesk package intentionally uses a stricter,
single-root layout and the verifier rejects unsafe paths, symlinks, `.env`, Git
metadata, virtual environments, data, logs, caches, tests, and unchecksummed
files.

## Official package layout

```text
visiondesk-1.0.2/
├── manifest.json
├── checksums.sha256
├── .env.example
├── requirements.txt
├── install.sh
├── update.sh
├── uninstall.sh
├── factory-reset.sh
├── ai/ camera/ config/ deployment/ gpio/ hardware/
├── pipeline/ qt_app/ system/ vision/ visiondesk/
└── ...runtime source and QML assets only
```

The generated manifest is deliberately minimal and matches the current updater:

```json
{
  "version": "1.0.2",
  "checksums_file": "checksums.sha256"
}
```

`checksums.sha256` contains one GNU `sha256sum -c` compatible line for every
regular file except itself, including `manifest.json`:

```text
<64 lowercase hexadecimal SHA-256>  ./relative/path
```

## Build the v1.0.2 package

Run the build utility from a clean maintenance checkout that contains `scripts/`.
It exports source only from the named Git ref, so the package content comes from
the tag rather than the current working tree.

```bash
git fetch --tags origin
git status --short
scripts/build-release.sh --git-ref v1.0.2
```

The command requires the source version, requested version, and exact tag to
agree after normalizing `v1.0.2` to application version `1.0.2`. It writes:

```text
dist/visiondesk-1.0.2.tar.gz
```

The build is deterministic to a reasonable extent: it uses the tagged commit's
timestamp, sorted archive members, normalized numeric owner/group, and `gzip
-n`. It prints the archive path, byte size, archive SHA-256, source version,
commit, and tag.

`--allow-dirty` is explicit and should be used only when the maintenance
checkout contains uncommitted packaging-tool changes. The source payload still
comes from `--git-ref`; do not use this bypass for a normal client release.
`--allow-untagged` is for non-production builds only.

## Verify before upload

```bash
scripts/verify-release.sh dist/visiondesk-1.0.2.tar.gz --expected-version 1.0.2
sha256sum dist/visiondesk-1.0.2.tar.gz
```

Verification does not install the archive or modify `/opt`, `/etc`, systemd, or
NetworkManager. It rejects path traversal, absolute paths, symlinks/hard links,
special files, `.env`, forbidden development/runtime data, malformed manifests,
checksum errors, missing release files, and version mismatches.

## Upload to GitHub Release

Create or open the GitHub Release tagged `v1.0.2`, then attach the verified
`dist/visiondesk-1.0.2.tar.gz`. With GitHub CLI installed and authenticated:

```bash
gh release upload v1.0.2 dist/visiondesk-1.0.2.tar.gz
```

Record the SHA-256 printed by the build in the release notes. Do not upload a
package containing client configuration, `/etc/visiondesk/visiondesk.env`, API
keys, Wi-Fi credentials, captured media, or data directories.

## Install and update on Raspberry Pi

For a fresh appliance, clone the fixed release tag and run the installer:

```bash
git clone --depth 1 --branch v1.0.2 \
  https://github.com/TannFhongg/Raspberry-Pi-AI-Vision-Desk-Assistant.git \
  ~/visiondesk
cd ~/visiondesk
git describe --tags --exact-match
chmod +x install.sh
sudo ./install.sh
```

For an already installed appliance, verify the archive on the maintenance
workstation, copy that exact verified archive to the Pi, then run the updater
from the checked source tree:

```bash
sudo ./update.sh --local /path/to/visiondesk-1.0.2.tar.gz --version 1.0.2 --dry-run
sudo ./update.sh --local /path/to/visiondesk-1.0.2.tar.gz --version 1.0.2
```

The updater dry-run validates the archive, manifest, and checksums but does not
build a virtual environment, switch `/opt/visiondesk/current`, or restart the
service. A full update also runs migrations and diagnostics, then requires the
restarted service to publish a matching readiness marker and remain stable.

Rollback is available only after a successful update has recorded rollback
metadata:

```bash
sudo ./update.sh --rollback
```

The release tag is for production deployment. Developers may work from `master`,
but `master` must not be used as the production clone target.
