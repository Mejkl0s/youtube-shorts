#!/usr/bin/env bash
# Install the basic Czech male voice locally, preserving APT signature/hash checks.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v espeak-ng >/dev/null && exit 0
speech_root="$PWD/.runtime/tools/espeak"
if [ -x "$speech_root/usr/bin/espeak-ng" ]; then exit 0; fi
speech_apt="$PWD/.runtime/apt"
mkdir -p "$speech_apt/lists/partial" "$speech_apt/cache/archives/partial" "$PWD/.runtime/tools/debs"
. /etc/os-release
printf '%s\n' "deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian $VERSION_CODENAME main" > "$speech_apt/sources.list"
speech_opts=(-o Dir::Etc::parts=- -o "Dir::Etc::sourcelist=$speech_apt/sources.list" -o Dir::Etc::sourceparts=- -o "Dir::State::lists=$speech_apt/lists" -o "Dir::Cache=$speech_apt/cache")
apt-get "${speech_opts[@]}" -o APT::Update::Error-Mode=any update
cd .runtime/tools/debs
apt-get "${speech_opts[@]}" download espeak-ng espeak-ng-data libespeak-ng1 libpcaudio0 libsonic0
mkdir -p "$speech_root"
for speech_deb in ./*.deb; do dpkg-deb -x "$speech_deb" "$speech_root"; done
