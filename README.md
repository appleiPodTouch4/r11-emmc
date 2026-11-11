# r11-emmc-test

Fast, XNU-free eMMC probe for OPPO R11 (CPH1707, SDM660).

The normal R11 test cycle boots XNU and waits 300+ seconds for the panel. This
repository contains a UEFI DXE driver that runs before the storage stack, prints
the SDCC1 state and the first bytes of LBA1 on the UEFI console, then halts in
`CpuDeadLoop()`.

## What it tests

Read-only first:

- SDHCI `PRESENT_STATE`, `HOST_CONTROL`, `HOST_CONTROL2`,
  `CAPABILITIES`, `CORE_VENDOR_SPEC`
- CMD13 on RCA 1..8 in the state left by the bootloader
- CMD17 at LBA1 with PIO, prints `d1` and the first 8 bytes
- Does **not** reset the card, change clocks or change voltage

This distinguishes:

- no CMD response / RCA not found
- CMD response but data phase wrong (`d1=4546492045464920`, `EFI EFI `)
- a valid `EFI PART`

## Expected output

```text
[R11EMMC] fast probe, no XNU
[R11EMMC] ps=01f800f0 hc1=38 hc2=0003 caps=742dc8b2 vs=00240a0e
[R11EMMC] cmd13 rca=1 st=00000900
[R11EMMC] cmd17 err=Success d1=4546492045464920 st=00000900
[R11EMMC] bytes: 45 46 49 20 45 46 49 20
```

Success is:

```text
d1=4546492050415254
bytes: 45 46 49 20 50 41 52 54
```

## Build integration

The driver is not a standalone EDK2 platform. It is copied into the existing
R11 UEFI package, added to `APRIORI.inc` before `ClockDxe`, and built with the
normal `build-r11.sh` wrapper.

```sh
export UNIXNU_ROOT=/Users/mry0000/Desktop/unixnu_r11
./scripts/install.sh "$UNIXNU_ROOT"

cd "$UNIXNU_ROOT"
./build-r11.sh firmware
./build-r11.sh bootimg
```

After the test, remove it from the normal build:

```sh
./scripts/uninstall.sh "$UNIXNU_ROOT"
```

Then boot manually:

```sh
fastboot boot boot-control/boot-r11-emmc-test.img
```

Do **not** flash. The driver halts, so XNU is never entered.

## Why a DXE driver

- Automatically dispatched from `APRIORI.inc`
- No UEFI Shell, menu or payload needed
- Runs in seconds instead of waiting for the XNU panel
- `CpuDeadLoop()` keeps the result visible for a photograph

## Status

- Driver source and integration script: compiled into a UEFI FD
- UEFI FD: `b550d702f5d0dc94065a7d772b66d6386a50c6dae611793bc79175a254defd78`
- Test boot image: `boot-control/boot-r11-emmc-test.img`
  - 8,634,368 bytes
  - sha256 `2ac0af395f317e45b17a243db7b0173a0233a6e0307276ecd79748eb4cf55e04`
- Not yet tested on hardware
- The test driver was removed from the normal UEFI build after this image was
  produced, so ordinary builds do not halt in `CpuDeadLoop()`
- Next step: boot the test image and photograph the `[R11EMMC]` lines
- Cold-start test (CMD0/CMD1/CMD2/CMD3/CMD7/CMD16) comes only after the
  read-only probe is stable
