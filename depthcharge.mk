#! /usr/bin/make -f

all: kernel.img

keys := kernel.keyblock kernel_data_key.vbprivk

kernel.img: kernel.itb kernel.args bootloader.bin $(keys)
	vbutil_kernel \
		--version 1 \
		--arch aarch64 \
		--pack $@ \
		--vmlinuz kernel.itb \
		--config kernel.args \
		--bootloader bootloader.bin \
		--keyblock kernel.keyblock \
		--signprivate kernel_data_key.vbprivk
	test "$$(stat -c '%s' $@)" -lt 33554432

kernel.itb: vmlinuz.lz4 initrd.img rk3399-gru-kevin.dtb
	mkimage \
		-D "-I dts -O dtb -p 2048" \
		-f auto \
		-A arm64 \
		-O linux \
		-T kernel \
		-C lz4 \
		-a 0 \
		-d vmlinuz.lz4 \
		-i initrd.img \
		-b rk3399-gru-kevin.dtb \
		$@

kernel.args: initrd.args
	@echo 'root=PARTUUID=4f7a82a0-1e9a-47fd-83b5-73847350f068' > $@
	@echo 'console=tty1' >> $@
	@echo 'rootwait' >> $@
	@echo 'rw' >> $@

vmlinuz.lz4: vmlinuz
	lz4 -12 $< $@

bootloader.bin:
	dd if=/dev/zero of=$@ count=1

clean:
	rm kernel.img

.PHONY: clean
