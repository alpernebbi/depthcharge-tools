#! /usr/bin/make -f

PACKAGENAME ?= depthcharge-tools
DESTDIR ?=

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
SBINDIR ?= $(PREFIX)/sbin
DATADIR ?= $(PREFIX)/share
SYSCONFDIR ?= $(PREFIX)/etc
LOCALSTATEDIR ?= $(PREFIX)/var

dirs := PREFIX BINDIR SBINDIR DATADIR SYSCONFDIR LOCALSTATEDIR

# Default values for depthchargectl configuration.
# These don't affect mkdepthcharge.
DEFAULT_CMDLINE ?= quiet splash
DEFAULT_COMPRESS ?= none lz4 lzma
DEFAULT_MAX_SIZE ?= 33554432
DEFAULT_DTB_NAME ?=

# These are paths for Debian.
DEFAULT_VBOOT_DEVKEYS ?= /usr/share/vboot/devkeys
DEFAULT_VBOOT_KEYBLOCK ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel.keyblock
DEFAULT_VBOOT_SIGNPUBKEY ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel_subkey.vbpubk
DEFAULT_VBOOT_SIGNPRIVATE ?= $${DEFAULT_VBOOT_DEVKEYS}/kernel_data_key.vbprivk

vars := CMDLINE COMPRESS MAX_SIZE DTB_NAME
vars += VBOOT_DEVKEYS VBOOT_KEYBLOCK VBOOT_SIGNPUBKEY VBOOT_SIGNPRIVATE
vars := $(foreach var,$(vars),DEFAULT_$(var))

# Search lines of 'VAR="value"' and replace them with ours.
pattern = 's|^$(var)=".*"$$|$(var)="$(call $(var))"|1'
patterns := $(foreach var, $(dirs) $(vars),-e $(pattern))
substvars := sed $(patterns)

all:
	mkdir -p bin
	$(substvars) <mkdepthcharge >bin/mkdepthcharge
	$(substvars) <depthchargectl >bin/depthchargectl
