#! /usr/bin/make -f

PACKAGENAME ?= depthcharge-tools
VERSION ?= 0.3.1-dev
DESTDIR ?=

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
SBINDIR ?= $(PREFIX)/sbin
DATADIR ?= $(PREFIX)/share
SYSCONFDIR ?= $(PREFIX)/etc
LOCALSTATEDIR ?= $(PREFIX)/var
LIBDIR ?= $(PREFIX)/lib
MANDIR ?= $(DATADIR)/man
BASHCOMPDIR ?= ${DATADIR}/bash-completion/completions
ZSHCOMPDIR ?= ${DATADIR}/zsh/site-functions

vars := PACKAGENAME VERSION
vars += PREFIX BINDIR SBINDIR DATADIR SYSCONFDIR LOCALSTATEDIR LIBDIR
vars += BASHCOMPDIR

# Default values for depthchargectl configuration.
# These don't affect mkdepthcharge.
DEFAULT_FORMAT ?= fit
DEFAULT_CMDLINE ?= console=tty0 quiet splash
DEFAULT_COMPRESS ?= none lz4 lzma
DEFAULT_MAX_SIZE ?= 33554432
DEFAULT_DTB_NAME ?=
DEFAULT_NOINITRAMFS ?= no

# These are paths for Debian.
DEFAULT_VBOOT_DEVKEYS ?= /usr/share/vboot/devkeys
DEFAULT_VBOOT_KEYBLOCK ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel.keyblock
DEFAULT_VBOOT_SIGNPUBKEY ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel_subkey.vbpubk
DEFAULT_VBOOT_SIGNPRIVATE ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel_data_key.vbprivk

d_vars := FORMAT CMDLINE COMPRESS MAX_SIZE DTB_NAME NOINITRAMFS
d_vars += VBOOT_DEVKEYS VBOOT_KEYBLOCK VBOOT_SIGNPUBKEY VBOOT_SIGNPRIVATE
vars += $(foreach var,$(d_vars),DEFAULT_$(var))

# Search lines of 'VAR="value"' and replace them with ours.
pattern = 's|^$(var)=".*"$$|$(var)="$(call $(var))"|1'
patterns := $(foreach var,$(vars),-e $(pattern))
sh_substvars := sed $(patterns)

# Search lines of '. "${FUNCTIONS_DIR}/func.sh"' and replace them with the
# content of the script at "lib/func.sh".
functions := $(foreach f, $(wildcard lib/*.sh), $(basename $(notdir $(f))))
pattern = '\|^\. "$${FUNCTIONS_DIR}/$(f)\.sh"$$| r lib/$(f).sh'
patterns := $(foreach f, $(functions),-e $(pattern))
sh_includelibs := sed $(patterns) -e 's|^\. "$${FUNCTIONS_DIR}/.*\.sh"$$|\n|1'

# Search lines of '.. |var| replace:: value' and replace them with ours.
pattern = 's|^.. \|$(var)\| replace:: .*|.. \|$(var)\| replace:: $(subst $${,\|,$(subst },\|,$(call $(var))))|1'
patterns := $(foreach var,$(vars),-e $(pattern))
rst_substvars := sed $(patterns)

all: bin/depthchargectl bin/depthchargectl.8
all: bin/mkdepthcharge bin/mkdepthcharge.1
all: bin/mkdepthcharge-standalone

bin/depthchargectl: depthchargectl
	mkdir -p bin
	$(sh_substvars) <"$<" >"$@"

bin/mkdepthcharge: mkdepthcharge
	mkdir -p bin
	$(sh_substvars) <"$<" >"$@"

# This builds mkdepthcharge into a single file.
bin/mkdepthcharge-standalone: mkdepthcharge
	mkdir -p bin
	$(sh_substvars) <"$<" | $(sh_includelibs) >"$@"

bin/depthchargectl.8: depthchargectl.rst
	mkdir -p bin
	$(rst_substvars) <"$<" | rst2man >"$@"

bin/mkdepthcharge.1: mkdepthcharge.rst
	mkdir -p bin
	$(rst_substvars) <"$<" | rst2man >"$@"

install: bin/mkdepthcharge bin/depthchargectl
	install -d '$(DESTDIR)$(BINDIR)'
	install -d '$(DESTDIR)$(SBINDIR)'
	install -d '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'
	install -d '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'/depthchargectl
	install -d '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'
	install -d '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'/config.d
	install -d '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'/userdb.d
	install -d '$(DESTDIR)$(LOCALSTATEDIR)/$(PACKAGENAME)'
	install -d '$(DESTDIR)$(LOCALSTATEDIR)/$(PACKAGENAME)'/images
	install -d '$(DESTDIR)$(LOCALSTATEDIR)/$(PACKAGENAME)'/images
	install -m 0755 bin/mkdepthcharge '$(DESTDIR)$(BINDIR)'
	install -m 0755 bin/depthchargectl '$(DESTDIR)$(SBINDIR)'
	install -m 0644 lib/*.sh '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'
	install -m 0644 lib/depthchargectl/*.sh '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'/depthchargectl
	install -m 0644 conf/db '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'
	install -m 0644 conf/userdb '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'
	install -m 0644 conf/config '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'

install-man: bin/mkdepthcharge.1 bin/depthchargectl.8
	install -d '$(DESTDIR)$(MANDIR)'/man1
	install -d '$(DESTDIR)$(MANDIR)'/man8
	install -m 0644 bin/mkdepthcharge.1 '$(DESTDIR)$(MANDIR)'/man1
	install -m 0644 bin/depthchargectl.8 '$(DESTDIR)$(MANDIR)'/man8

install-systemd: systemd/depthchargectl-set-good.service
	install -d '$(DESTDIR)$(LIBDIR)/systemd/system'
	install -m 0644 systemd/depthchargectl-set-good.service '$(DESTDIR)$(LIBDIR)/systemd/system'
	@echo "This target only installs the service, does not enable it."
	@echo "You might want to run:"
	@echo "  systemctl daemon-reload"
	@echo "  systemctl --enable depthchargectl-set-good"

install-init: init.d/depthchargectl-set-good
	install -d '$(DESTDIR)$(SYSCONFDIR)/init.d'
	install -m 0644 init.d/depthchargectl-set-good '$(DESTDIR)$(SYSCONFDIR)/init.d'
	@echo "This target only installs the service, does not enable it."
	@echo "You might want to run:"
	@echo "  ln -s ../init.d/S02depthchargectl-set-good $(DESTDIR)$(SYSCONFDIR)/rc2.d/depthchargectl-set-good"
	@echo "  ln -s ../init.d/S03depthchargectl-set-good $(DESTDIR)$(SYSCONFDIR)/rc3.d/depthchargectl-set-good"
	@echo "  ln -s ../init.d/S04depthchargectl-set-good $(DESTDIR)$(SYSCONFDIR)/rc4.d/depthchargectl-set-good"
	@echo "  ln -s ../init.d/S05depthchargectl-set-good $(DESTDIR)$(SYSCONFDIR)/rc5.d/depthchargectl-set-good"

install-bash: completions/_mkdepthcharge.bash completions/_depthchargectl.bash
	install -d '$(DESTDIR)$(BASHCOMPDIR)'
	install -m 0644 completions/_mkdepthcharge.bash '$(DESTDIR)$(BASHCOMPDIR)'/mkdepthcharge
	install -m 0644 completions/_depthchargectl.bash '$(DESTDIR)$(BASHCOMPDIR)'/depthchargectl

install-zsh: completions/_mkdepthcharge.zsh completions/_depthchargectl.zsh
	install -d '$(DESTDIR)$(ZSHCOMPDIR)'
	install -m 0644 completions/_mkdepthcharge.zsh '$(DESTDIR)$(ZSHCOMPDIR)'/_mkdepthcharge
	install -m 0644 completions/_depthchargectl.zsh '$(DESTDIR)$(ZSHCOMPDIR)'/_depthchargectl

uninstall:
	rm -f '$(DESTDIR)$(BINDIR)'/mkdepthcharge
	rm -f '$(DESTDIR)$(SBINDIR)'/depthchargectl
	rm -rf '$(DESTDIR)$(DATADIR)/$(PACKAGENAME)'
	rm -rf '$(DESTDIR)$(SYSCONFDIR)/$(PACKAGENAME)'
	rm -rf '$(DESTDIR)$(LOCALSTATEDIR)/$(PACKAGENAME)'
	rm -f '$(DESTDIR)$(MANDIR)'/man1/mkdepthcharge.1
	rm -f '$(DESTDIR)$(MANDIR)'/man8/depthchargectl.8
	rm -f '$(DESTDIR)$(LIBDIR)'/systemd/system/depthchargectl-set-good.service
	rm -f '$(DESTDIR)$(SYSCONFDIR)'/init.d/depthchargectl-set-good
	rm -f '$(DESTDIR)$(BASHCOMPDIR)'/mkdepthcharge
	rm -f '$(DESTDIR)$(BASHCOMPDIR)'/depthchargectl
	rm -f '$(DESTDIR)$(ZSHCOMPDIR)'/_mkdepthcharge
	rm -f '$(DESTDIR)$(ZSHCOMPDIR)'/_depthchargectl

install-standalone: bin/mkdepthcharge-standalone
	install -d '$(DESTDIR)$(BINDIR)'
	install -m 0755 bin/mkdepthcharge-standalone -T '$(DESTDIR)$(BINDIR)'/mkdepthcharge

clean:
	rm -f bin/depthchargectl bin/depthchargectl.8
	rm -f bin/mkdepthcharge bin/mkdepthcharge.1
	rm -f bin/mkdepthcharge-standalone
	[ ! -d bin ] || rmdir bin

.PHONY: all install install-man install-systemd install-init install-bash install-zsh install-standalone uninstall clean
