#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"

target="${1:-}"
if [[ -z "$target" ]]; then
  printf 'Usage: %s WINDOWS_USER@%s\n' "${0##*/}" "$WINDOWS_ENDPOINT_IP" >&2
  exit 2
fi
require_command ssh
require_command scp
require_command base64
require_command iconv

# Windows OpenSSH can use either cmd.exe or PowerShell as its default shell.
# Passing a nested -Command string lets the outer shell expand variables such
# as $root prematurely. PowerShell -EncodedCommand receives UTF-16LE and keeps
# the command opaque until the intended PowerShell process decodes it.
remote_command='$root = Join-Path $env:USERPROFILE "SanoliFood-Endpoint"; $config = Join-Path $root "config"; New-Item -ItemType Directory -Force -Path $root,$config | Out-Null'
encoded_command="$(
  printf '%s' "$remote_command" \
    | iconv -f UTF-8 -t UTF-16LE \
    | base64 -w 0
)"

ssh "$target" \
  "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded_command"

scp \
  "$endpoints_dir/windows/Install-SanoliFoodEndpoint.ps1" \
  "$endpoints_dir/windows/Test-SanoliFoodEndpoint.ps1" \
  "${target}:SanoliFood-Endpoint/"
scp \
  "$endpoints_dir/config/windows/sysmonconfig.xml" \
  "$endpoints_dir/config/windows/quality-policy.json" \
  "${target}:SanoliFood-Endpoint/config/"

printf 'OK   Windows bundle staged for %s\n' "$target"
printf 'Open an elevated PowerShell in the Windows VM and run:\n'
printf '  Set-ExecutionPolicy -Scope Process Bypass\n'
printf '  & "$env:USERPROFILE\\SanoliFood-Endpoint\\Install-SanoliFoodEndpoint.ps1"\n'
