# Code Duplication Checks

Use PMD CPD for C/C++ duplication checks. It tokenizes C-like code and gives
useful reports for copy-paste refactoring work in `src/_goi`.

## Local install

PMD needs Java. The repo has been tested with OpenJDK 27-ea, but any current
PMD-supported Java should work.

Install PMD locally under `.tools/`:

```sh
mkdir -p .tools
wget -O /tmp/pmd-dist-7.24.0-bin.zip \
  https://github.com/pmd/pmd/releases/download/pmd_releases%2F7.24.0/pmd-dist-7.24.0-bin.zip
unzip -q -o /tmp/pmd-dist-7.24.0-bin.zip -d .tools
```

Verify:

```sh
.tools/pmd-bin-7.24.0/bin/pmd --version
```

## Run CPD

Start with the cleaner report:

```sh
.tools/pmd-bin-7.24.0/bin/pmd cpd \
  --minimum-tokens 100 \
  --language cpp \
  --dir src/_goi \
  --format text
```

For smaller marshalling/container duplicates, lower the threshold:

```sh
.tools/pmd-bin-7.24.0/bin/pmd cpd \
  --minimum-tokens 80 \
  --language cpp \
  --dir src/_goi \
  --format text
```

PMD exits with code `4` when duplication is found. That is expected and does
not mean the command failed.

## Current useful targets

After the `strv` and `invoke/return.c` tuple cleanups, the remaining useful
hits at `--minimum-tokens 80` include:

- `src/_goi/invoke/jit/plan.c` and `src/_goi/runtime/callable.c`: duplicated
  `GITypeTag` to JIT type mapping.
- `src/_goi/GObject/Boxed-class.c` and `src/_goi/marshal/marshal.c`:
  duplicated zero-terminated string-array field handling.
- `src/_goi/jit/arch/*`: repeated backend epilogue/error-exit code.

