#!/bin/bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/scripts" "$tmp/src/os-skills/ai/sample"
cp "$root/scripts/rpm-build.sh" "$tmp/scripts/"
cp "$root/src/os-skills/os-skills.spec.in" "$tmp/src/os-skills/"
printf '[component]\nname = "os-skills"\nversion = "7.8.9"\n' > "$tmp/src/os-skills/component.toml"
printf 'test skill\n' > "$tmp/src/os-skills/ai/sample/SKILL.md"
printf 'license\n' > "$tmp/src/os-skills/LICENSE"
cat > "$tmp/rpmbuild" <<'MOCK'
#!/bin/bash
set -euo pipefail
spec=${@: -1}
grep -Eq "^Version:[[:space:]]+${EXPECTED_VERSION}$" "$spec"
tar -tzf "$(dirname "$(dirname "$spec")")/SOURCES/os-skills-${EXPECTED_VERSION}.tar.gz" | grep -q '^os-skills-.*/component.toml$'
MOCK
chmod +x "$tmp/rpmbuild"
EXPECTED_VERSION=7.8.9 RPMBUILD="$tmp/rpmbuild" bash "$tmp/scripts/rpm-build.sh" os-skills
EXPECTED_VERSION=9.9.9 VERSION=9.9.9 RPMBUILD="$tmp/rpmbuild" bash "$tmp/scripts/rpm-build.sh" os-skills
cp "$root/src/os-skills/component.toml" "$tmp/src/os-skills/component.toml"
component_version=$(python3 - "$root/scripts/check-component-versions.py" <<'PY'
import runpy
import sys

checker = runpy.run_path(sys.argv[1])
print(checker["read_version"]("src/os-skills/component.toml"))
PY
)
EXPECTED_VERSION="$component_version" RPMBUILD="$tmp/rpmbuild" bash "$tmp/scripts/rpm-build.sh" os-skills

# --help must print usage and exit 0 without requiring or invoking rpmbuild.
cat > "$tmp/rpmbuild-should-not-run" <<'MOCK'
#!/bin/bash
touch "${RPMBUILD_MARKER:?}"
exit 99
MOCK
chmod +x "$tmp/rpmbuild-should-not-run"
RPMBUILD_MARKER="$tmp/rpmbuild-invoked" RPMBUILD="$tmp/rpmbuild-should-not-run" \
    bash "$tmp/scripts/rpm-build.sh" --help > "$tmp/help.out" 2>&1
grep -q '^Usage: .*rpm-build\.sh <package|all>$' "$tmp/help.out"
grep -q 'os-skills' "$tmp/help.out"
if [ -e "$tmp/rpmbuild-invoked" ]; then
    echo "rpmbuild was invoked for --help" >&2
    exit 1
fi
