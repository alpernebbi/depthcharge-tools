#! /usr/bin/make -f

all: kernel.img

keyblock := /usr/share/vboot/devkeys/kernel.keyblock
vbprivk := /usr/share/vboot/devkeys/kernel_data_key.vbprivk

kversion := 5.3.0-trunk-arm64
vmlinuz := /boot/vmlinuz-$(kversion)
initramfs := /boot/initrd.img-$(kversion)
dtb := /usr/lib/linux-image-$(kversion)/rockchip/rk3399-gru-kevin.dtb

kernel.img: kernel.itb kernel.args bootloader.bin $(keyblock) $(vbprivk)
	vbutil_kernel \
		--version 1 \
		--arch aarch64 \
		--pack $@ \
		--vmlinuz kernel.itb \
		--config kernel.args \
		--bootloader bootloader.bin \
		--keyblock $(keyblock) \
		--signprivate $(vbprivk)
	test "$$(stat -c '%s' $@)" -lt 33554432

kernel.itb: vmlinuz.lz4 initrd.img rk3399-gru-kevin.dtb
	mkimage \
		-f auto \
		-A arm64 \
		-O linux \
		-C lz4 \
		-n "Debian kernel ${kversion}" \
		-d vmlinuz.lz4 \
		-i initrd.img \
		-b rk3399-gru-kevin.dtb \
		$@

kernel.args:
	@echo -n \
		'root=PARTUUID=4f7a82a0-1e9a-47fd-83b5-73847350f068' \
		'console=tty1' \
		'rootwait' \
		'rw' \
		>$@

vmlinuz.lz4: vmlinuz
	lz4 -12 $< $@

rk3399-gru-kevin.dtb: $(dtb)
	cp $< $@

initrd.img: $(initramfs)
	cp $< $@

vmlinuz: $(vmlinuz)
	cp $< $@

bootloader.bin:
	dd if=/dev/zero of=$@ count=1

flash: kernel.img
	notify-send 'depthcharge' 'enter sudo password'
	sudo -v
	sudo dd if=$< of=/dev/disk/by-partlabel/KERN-X
	sudo cgpt add -i 1 -P 15 -T 1 /dev/sda
	sudo cgpt show /dev/sda

clean:
	rm -f kernel.img
	rm -f kernel.itb
	rm -f kernel.args
	rm -f vmlinuz
	rm -f vmlinuz.lz4
	rm -f initrd.img
	rm -f kernel.args
	rm -f bootloader.bin
	rm -f rk3399-gru-kevin.dtb

.PHONY: all clean flash
