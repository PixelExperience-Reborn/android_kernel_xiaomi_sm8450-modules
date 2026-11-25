#!/usr/bin/env bash
# Limit LLD thread memory during the real Full LTO link on ephemeral CI runners.
# Source this file in the same shell as the kernel make command.
set -euo pipefail
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
test -d "$RUNNER_TEMP"
real_lld="/tmp/google-clang/clang-r614150/bin/ld.lld"
test -x "$real_lld" || { echo "::error::Pinned Google LLVM23 linker missing"; return 1; }
lld_help="$("$real_lld" --help)"
if [[ "$lld_help" != *"--threads="* ]]; then
  echo "::error::Pinned ld.lld does not advertise supported --threads option"
  return 1
fi
wrapper_dir="$RUNNER_TEMP/mondrian-lld-wrapper"
mkdir -p "$wrapper_dir"
cat > "$wrapper_dir/ld.lld" <<'LLD_WRAPPER'
#!/usr/bin/env bash
exec /tmp/google-clang/clang-r614150/bin/ld.lld --threads=1 "$@"
LLD_WRAPPER
chmod 755 "$wrapper_dir/ld.lld"
export PATH="$wrapper_dir:$PATH"
test "$(command -v ld.lld)" = "$wrapper_dir/ld.lld"
echo "[INFO] Bounded real Google LLVM23 ld.lld to one linker thread; Full LTO/CFI/SCS/HW-tag KASAN remain selected"
