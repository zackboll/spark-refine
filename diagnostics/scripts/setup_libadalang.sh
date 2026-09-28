#!/usr/bin/env bash
# Task 009: build a relocatable Libadalang Python bundle for the OPTIONAL
# semantic enrichment (`spark-refine ... --semantic`).
#
#   diagnostics/scripts/setup_libadalang.sh [BUNDLE_DIR]
#
# Libadalang is not published on PyPI; the released crate is built from
# source with Alire (the same tool that pins the proof toolchain). This
# script:
#
#   1. `alr get libadalang=$LAL_VERSION` into BUNDLE_DIR/build (Alire picks
#      and downloads its own GNAT; the solution is printed and recorded);
#   2. `alr build` ("prod" mode via the crate's own externals, relocatable
#      libraries);
#   3. copies the Python binding plus libadalang.so and EVERY non-system
#      shared library it needs (per ldd) into BUNDLE_DIR/python/libadalang,
#      and rewrites their RUNPATH to $ORIGIN with patchelf, so the bundle
#      no longer depends on the Alire build tree (cacheable in CI);
#   4. writes BUNDLE_DIR/env.sh (sets PYTHONPATH) and BUNDLE_DIR/VERSION;
#   5. smoke-tests `import libadalang` from a clean environment.
#
# Default BUNDLE_DIR: ${XDG_CACHE_HOME:-$HOME/.cache}/spark-refine/libadalang-$LAL_VERSION
# Idempotent: an existing bundle that passes the smoke test is kept.
# Needs: alr (2.x), python3 (venv + pip, network for patchelf), ldd.
# The core spark-refine package never needs any of this.
set -euo pipefail

LAL_VERSION="26.0.0"
# the dependency solution observed and validated for libadalang=26.0.0
LAL_PINS="adasat=26.0.0 gnatcoll=26.0.0 gnatcoll_gmp=26.0.0
  gnatcoll_iconv=26.0.0 gnatcoll_minimal=26.0.0 gnatcoll_projects=26.0.0
  gprconfig_kb=26.0.0 langkit_support=26.0.0 libgpr=26.0.0 libgpr2=26.0.0
  prettier_ada=26.0.0 vss_text=26.2.0 xmlada=26.0.0"
LAL_TOOLS="gnat_native=15.3.1 gprbuild=26.0.1"
PATCHELF_VERSION="0.17.2.1"
BUNDLE="${1:-${XDG_CACHE_HOME:-$HOME/.cache}/spark-refine/libadalang-$LAL_VERSION}"
PKG="$BUNDLE/python/libadalang"

smoke() {
  env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONPATH="$BUNDLE/python" \
    python3 -c 'import libadalang as lal; lal.AnalysisContext(); print("libadalang import ok")'
}

if [ -f "$BUNDLE/VERSION" ] && smoke >/dev/null 2>&1; then
  echo "bundle already present and working: $BUNDLE"
  cat "$BUNDLE/VERSION"
  exit 0
fi

start=$(date +%s)
rm -rf "$BUNDLE/python" "$BUNDLE/VERSION" "$BUNDLE/env.sh"
mkdir -p "$BUNDLE/build"
cd "$BUNDLE/build"
if ! ls -d libadalang_"$LAL_VERSION"_* >/dev/null 2>&1; then
  alr -n get "libadalang=$LAL_VERSION"
fi
SRC=$(ls -d "$PWD"/libadalang_"$LAL_VERSION"_* | head -1)
cd "$SRC"
# Reproducibility: the crate accepts any ^26 dependency; pin the solution
# validated for Task 009 and make the build toolchain an explicit
# dependency (independent of the user's `alr toolchain` selection).
if ! grep -q '^\[\[pins\]\]' alire.toml; then
  for pin in $LAL_PINS; do alr -n pin "$pin" >/dev/null; done
  alr -n with $LAL_TOOLS >/dev/null
fi
echo "== Alire solution for libadalang=$LAL_VERSION"
alr -n show --solve | sed -n '/Dependencies (solution)/,/Dependencies (graph)/p' \
  | grep -v 'Dependencies (graph)' | tee "$BUNDLE/build/solution.txt"
# the crate's gpr-set-externals select LIBADALANG_BUILD_MODE=prod; the
# Python binding loads a shared library, so every crate is built
# relocatable (the default is static)
export LIBRARY_TYPE=relocatable
alr -n build
LIB="$SRC/lib/relocatable/prod/libadalang.so"
[ -f "$LIB" ] || { echo "error: $LIB not built" >&2; exit 1; }

python3 -m venv "$BUNDLE/build/venv"
"$BUNDLE/build/venv/bin/pip" install -q "patchelf==$PATCHELF_VERSION"
PATCHELF="$BUNDLE/build/venv/bin/patchelf"

mkdir -p "$BUNDLE/python"
cp -r "$SRC/python/libadalang" "$PKG"
rm -f "$PKG"/*.so*
cp -L "$LIB" "$PKG/libadalang.so"
# every dependency outside the system library directories goes into the
# bundle (Alire-built GNATcoll/GPR2/Langkit/... and the GNAT runtime)
ldd "$LIB" | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}' | while read -r soname path; do
  case "$path" in
    /lib/*|/lib64/*|/usr/lib/*|/usr/lib64/*) ;;
    *) cp -L "$path" "$PKG/$soname" ;;
  esac
done
# DT_RPATH (--force-rpath), not DT_RUNPATH: it takes precedence over
# LD_LIBRARY_PATH, so e.g. `alr exec` environments (GNAT 16 runtime on
# LD_LIBRARY_PATH) cannot substitute a library inside the bundle
for so in "$PKG"/*.so*; do
  chmod u+w "$so"
  "$PATCHELF" --force-rpath --set-rpath '$ORIGIN' "$so"
done
missing=$(cd "$PKG" && ldd ./libadalang.so | grep 'not found' || true)
[ -z "$missing" ] || { echo "error: unresolved libraries: $missing" >&2; exit 1; }
outside=$(cd "$PKG" && ldd ./libadalang.so | awk '$3 ~ /^\// {print $3}' \
          | grep -v -e '^/lib' -e '^/usr/lib' -e "^$PKG/" || true)
[ -z "$outside" ] || { echo "error: bundle still loads $outside" >&2; exit 1; }

cat > "$BUNDLE/env.sh" <<EOF
# source this file to enable spark-refine --semantic (Libadalang $LAL_VERSION)
export PYTHONPATH="$BUNDLE/python\${PYTHONPATH:+:\$PYTHONPATH}"
EOF
{
  echo "libadalang=$LAL_VERSION (Alire crate, built from source)"
  grep -E '^\s+gnat=' "$BUNDLE/build/solution.txt" | sed 's/^ */built with /'
  echo "bundle size: $(du -sh "$PKG" | cut -f1)"
} > "$BUNDLE/VERSION"
echo "$LAL_VERSION" > "$PKG/SPARK_REFINE_CRATE_VERSION"
smoke
echo "== bundle ready in $(( $(date +%s) - start ))s: $BUNDLE"
cat "$BUNDLE/VERSION"
echo "enable with: source $BUNDLE/env.sh"
