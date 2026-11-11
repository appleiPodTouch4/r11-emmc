# r11-emmc

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
R11 UEFI package, added to `DXE.inc` before the XNU-driving modules, and built with the
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
fastboot boot boot-control/boot-r11-emmc-qr3.img
```

Do **not** flash. The driver halts, so XNU is never entered.

## Why a DXE driver

- Automatically dispatched from `DXE.inc` before XNU drivers
- No UEFI Shell, menu or payload needed
- Runs in seconds instead of waiting for the XNU panel
- `CpuDeadLoop()` keeps the result visible for a photograph

## Status

- Driver source and integration script: compiled into a UEFI FD
- UEFI FD: `67c98da047c01f65f9b15bd246c97637104faae518b7bd4adb6a639cccb38f8d`
- Test boot image: `boot-control/boot-r11-emmc-qr3.img`
  - 8,642,560 bytes
  - sha256 `029ee3d864906da162dee09d1936804d90673ef464fb4cd0f4621fbb259988a8`
  - `R11EmmcTestDxe` is after `SimpleFbDxe`, so `EFI_GRAPHICS_OUTPUT_PROTOCOL` exists
  - The result QR is drawn after a 20 s wait and stays visible for 20 s
  - `R11EmmcTestDxe` is in `DXE.inc`, before the XNU-driving modules
  - Displays the result as a QR code before the 20 s countdown/reset
- Not yet tested on hardware
- The test driver was removed from the normal UEFI build after this image was
  produced, so ordinary builds do not halt in `CpuDeadLoop()`
- Next step: boot the test image and photograph the `[R11EMMC]` lines
- Cold-start test (CMD0/CMD1/CMD2/CMD3/CMD7/CMD16) comes only after the
  read-only probe is stable

## Automation log

| round | time | status | conclusion |
|---|---|---|---|
| 1 | 2026-11-11 21:24:07 | ok | CMD0=unknown CMD1_timeouts=0 never_ready=no ps=? int=? |
| 2 | 2026-11-11 21:26:09 | ok | CMD0=unknown CMD1_timeouts=0 never_ready=no ps=? int=? |
| 3 | 2026-11-11 21:28:11 | ok | CMD0=unknown CMD1_timeouts=0 never_ready=no ps=? int=? |
| 1 | 2026-11-11 21:39:59 | ok | CMD0=unknown CMD1_timeouts=0 never_ready=no ps=? int=? |
| 2 | 2026-11-11 21:42:53 | ok | CMD0=unknown CMD1_timeouts=0 never_ready=no ps=? int=? |
| 1 | 2026-11-11 22:02:23 | ok | QR R11|stage=cmd1|ps=01F800F1|int=00018000|c0=1|c1=3|never=1 |
| 2 | 2026-11-11 22:04:19 | ok | QR R11|stage=cmd1|ps=01F800F1|int=00018000|c0=1|c1=3|never=1 |
| 3 | 2026-11-11 22:05:56 | ok | QR R11|stage=cmd1|ps=01F800F1|int=00018000|c0=1|c1=3|never=1 |
| 4 | 2026-11-11 22:07:23 | ok | QR R11|stage=cmd1|ps=01F800F1|int=00018000|c0=1|c1=3|never=1 |
| 5 | 2026-11-11 22:08:52 | ok | QR R11|stage=cmd1|ps=01F800F1|int=00018000|c0=1|c1=3|never=1 |
| cmdreset | 2026-11-11 | QR R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1 |
