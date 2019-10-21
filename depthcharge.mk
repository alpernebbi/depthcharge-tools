#! /usr/bin/make -f

dirs = $(wildcard */)
kernel-initrd = $(addsuffix kernel-initrd.img, $(dirs))
kernel-noinitrd = $(addsuffix kernel-noinitrd.img, $(dirs))
all: $(kernel-initrd) $(kernel-noinitrd)

keys := kernel.keyblock kernel_data_key.vbprivk

%.img: %.itb %.args bootloader.bin $(keys)
	vbutil_kernel \
		--version 1 \
		--arch aarch64 \
		--pack $@ \
		--vmlinuz $*.itb \
		--config $*.args \
		--bootloader bootloader.bin \
		--keyblock kernel.keyblock \
		--signprivate kernel_data_key.vbprivk

%/kernel-initrd.itb: %/vmlinuz.lz4 %/initrd.img %/rk3399-gru-kevin.dtb
	mkimage \
		-D "-I dts -O dtb -p 2048" \
		-f auto \
		-A arm64 \
		-O linux \
		-T kernel \
		-C lz4 \
		-a 0 \
		-d $*/vmlinuz.lz4 \
		-i $*/initrd.img \
		-b $*/rk3399-gru-kevin.dtb \
		$@

%/kernel-noinitrd.itb: %/vmlinuz.lz4 %/rk3399-gru-kevin.dtb
	mkimage \
		-D "-I dts -O dtb -p 2048" \
		-f auto \
		-A arm64 \
		-O linux \
		-T kernel \
		-C lz4 \
		-a 0 \
		-d $*/vmlinuz.lz4 \
		-b $*/rk3399-gru-kevin.dtb \
		$@

%/kernel-initrd.args: initrd.args
	cat $< | tr "\n" " " > $@

%/kernel-noinitrd.args: noinitrd.args
	cat $< | tr "\n" " " > $@

%.lz4: %
	lz4 -12 $< $@

initrd.args:
	@echo 'root=PARTUUID=4f7a82a0-1e9a-47fd-83b5-73847350f068' > $@
	@echo 'console=tty1' >> $@
	@echo 'rootwait' >> $@
	@echo 'rw' >> $@

noinitrd.args: initrd.args
	@cp $< $@
	@echo 'noinitrd' >> $@

bootloader.bin:
	dd if=/dev/zero of=$@ count=1

clean:
	rm $(kernel-initrd) $(kernel-noinitrd)

.PHONY: clean
