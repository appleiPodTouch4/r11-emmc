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
| cmd0zero | 2026-11-11 | QR R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1 |
| 1v8 | 2026-11-11 | QR R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1 |
| pwrcycle | 2026-11-11 | QR R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1 |
| corevendor | 2026-11-11 | QR R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1 |

## eMMC results (2026-11-13)

All variants below produced the same QR result:

```text
R11|stage=cmd1|ps=01F800F0|int=00000000|c0=1|c1=3|never=1
```

| variant | change | result |
|---|---|---|
| cmdreset | CMD1 timeout -> SWRST_CMD -> retry | CMD1 3x timeout, card never ready |
| cmd0zero | CMD0 argument 0 | same |
| 1v8 | POWER_CONTROL 1.8 V | same |
| pwrcycle | power off/on before CMD1 | same |
| corevendor | keep bootloader CORE_VENDOR_SPEC | same |
| gccroot | program GCC sdcc1_apps root to 400 kHz | same |
| vendorstack | vendor stock ClockDxe + SdccDxe | same |
| cmd1arg | CMD1 OCR argument 0x00FF8080 | same |
| swreset | SWRST_ALL | hung before QR; not viable |

### Images

| variant | image | sha256 |
|---|---|---|
| cmdreset | `boot-control/boot-r11-emmc-cmdreset.img` | `9f86ab43a4047a51679f5dc4f22e30264cff1746a33e8c03bca22b8f89e07f2b` |
| cmd0zero | `boot-control/boot-r11-emmc-cmd0zero.img` | `eebd87aed489edd0ba1d79db15d745ae841ba9ef7ca8eb2509afe1b9c31bd295` |
| 1v8 | `boot-control/boot-r11-emmc-1v8.img` | `cbaeed13c03dfa63561275f77b6943aae97391c5d8313793c9d0fdc6badf15ed` |
| pwrcycle | `boot-control/boot-r11-emmc-pwrcycle.img` | `d121ca8974a04ed21a8868818adfc92f8efcf8a17ce0232802fc654af250b134` |
| corevendor | `boot-control/boot-r11-emmc-corevendor.img` | `064902bc64934a384d140eb63c97ea7550fc910c797bd24025daacad757650ce` |
| gccroot | `boot-control/boot-r11-emmc-gccroot.img` | `6263454caefa95095d4fb3256060c76530c7f2397a7be87257d7d4895fa96208` |
| vendorstack | `boot-control/boot-r11-emmc-vendorstack.img` | `3e060e23876d99838ea485364da38b02c89ff985187fe3604dd3dcd08e64300b` |
| cmd1arg | `boot-control/boot-r11-emmc-cmd1arg.img` | `9860663d0bccdbb537f934c5858f641e37b376a39fe0042b0914d7779cc2f63f` |
| QR baseline | `boot-control/boot-r11-emmc-qr3.img` | `029ee3d864906da162dee09d1936804d90673ef464fb4cd0f4621fbb259988a8` |

### Conclusion

- CMD0 completes.
- CMD1 never gets a response from the card.
- CMD inhibit cleanup works: `ps=01F800F0`, `int=00000000`.
- Host SDHCI clock, GCC gates/root, CMD0 argument, 1.8 V signalling, power register cycle,
  CORE_VENDOR_SPEC, CMD1 OCR argument and the vendor ClockDxe/SdccDxe stack do not change the result.
- The remaining blocker is the card-side power/reset/CMD-line state: eMMC VCC/VCCQ
  (PM660L L4 / PM660 L8), reset, or CMD-line pull-up.

### Current state

- Normal UEFI configuration restored; test driver removed from the normal build.
- Device returns to Fastboot after each test.
- Camera: `http://192.168.31.195:8080/`
- No automatic loop is running after this suite completed.
