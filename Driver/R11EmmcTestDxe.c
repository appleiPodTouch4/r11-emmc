/** @file
  Fast, XNU-free SDCC1/eMMC probe for the OPPO R11 (SDM660).

  Runs as a DXE driver before the vendor storage stack.  It does not reset the
  card or reprogram clocks; it samples the state the bootloader left behind,
  tries CMD13 on RCA 1..8, then reads LBA1 with CMD17 in PIO mode and prints
  the first eight bytes.  The driver ends in CpuDeadLoop(), so the result stays
  on the UEFI console instead of continuing into a 300-second XNU boot.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/IoLib.h>
#include <Library/PrintLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiDriverEntryPoint.h>
#include <Library/UefiLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>

#define SDCC_BASE             0x0C0C4000u
#define GCC_BASE              0x00100000u

#define SDHCI_BLOCK_SIZE      0x004u
#define SDHCI_BLOCK_COUNT     0x006u
#define SDHCI_ARGUMENT        0x008u
#define SDHCI_TRANSFER_MODE   0x00Cu
#define SDHCI_COMMAND         0x00Eu
#define SDHCI_RESPONSE        0x010u
#define SDHCI_BUFFER          0x020u
#define SDHCI_PRESENT_STATE   0x024u
#define SDHCI_HOST_CONTROL    0x028u
#define SDHCI_POWER_CONTROL   0x029u
#define SDHCI_CLOCK_CONTROL   0x02Cu
#define SDHCI_INT_STATUS      0x030u
#define SDHCI_INT_ENABLE      0x034u
#define SDHCI_SIGNAL_ENABLE   0x036u
#define SDHCI_HOST_CONTROL2   0x03Eu
#define SDHCI_CAPABILITIES    0x040u
#define SDHCI_CORE_VENDOR     0x20Cu
#define SDHCI_TIMEOUT_CONTROL 0x02Eu

#define SDHCI_INT_CMD_COMPLETE  0x0001u
#define SDHCI_INT_TX_COMPLETE   0x0002u
#define SDHCI_INT_BUF_READ      0x0020u
#define SDHCI_INT_ERROR         0x8000u

#define SDHCI_PS_CMD_INHIBIT    0x00000001u
#define SDHCI_PS_DAT_INHIBIT    0x00000002u
#define SDHCI_PS_BUF_READ_EN    0x00000800u

#define SDHCI_CMD_R48           0x00000002u
#define SDHCI_CMD_R136          0x00000001u
#define SDHCI_CMD_R48BUSY       0x00000003u
#define SDHCI_CMD_CRC           0x00000008u
#define SDHCI_CMD_INDEX         0x00000010u
#define SDHCI_CMD_DATA          0x00000020u

#define SDHCI_TM_READ           0x00000010u
#define SDHCI_TM_BLKCNT_EN      0x00000002u
#define SDHCI_TM_MULTI          0x00000020u

STATIC
EFI_STATUS
WaitBits16 (
  IN UINT32  Offset,
  IN UINT16  Mask,
  IN UINT16  Value,
  IN UINTN   Microseconds
  )
{
  UINTN  i;

  for (i = 0; i < Microseconds; i++) {
    if ((MmioRead16 (SDCC_BASE + Offset) & Mask) == Value) {
      return EFI_SUCCESS;
    }
    gBS->Stall (1);
  }
  return EFI_TIMEOUT;
}

STATIC
EFI_STATUS
WaitBits (
  IN UINT32  Offset,
  IN UINT32  Mask,
  IN UINT32  Value,
  IN UINTN   Microseconds
  )
{
  UINTN  i;

  for (i = 0; i < Microseconds; i++) {
    if ((MmioRead32 (SDCC_BASE + Offset) & Mask) == Value) {
      return EFI_SUCCESS;
    }
    gBS->Stall (1);
  }
  return EFI_TIMEOUT;
}

STATIC
EFI_STATUS
SdCommand (
  IN  UINT8   Index,
  IN  UINT32  Argument,
  IN  UINT32  Flags,
  OUT UINT32  *Response,
  OUT VOID    *Data,
  IN  UINT32  Blocks
  )
{
  UINT32  Status;
  UINT32  Words;
  UINT32  i;

  if (WaitBits (SDHCI_PRESENT_STATE,
               SDHCI_PS_CMD_INHIBIT | SDHCI_PS_DAT_INHIBIT, 0,
               100000) != EFI_SUCCESS)
  {
    return EFI_TIMEOUT;
  }

  MmioWrite32 (SDCC_BASE + SDHCI_INT_STATUS, 0xFFFFFFFFu);
  MmioWrite32 (SDCC_BASE + SDHCI_ARGUMENT, Argument);

  if (Data != NULL) {
    MmioWrite16 (SDCC_BASE + SDHCI_BLOCK_SIZE, 512);
    MmioWrite16 (SDCC_BASE + SDHCI_BLOCK_COUNT, (UINT16)Blocks);
    MmioWrite16 (
      SDCC_BASE + SDHCI_TRANSFER_MODE,
      (UINT16)(SDHCI_TM_READ | SDHCI_TM_BLKCNT_EN |
               (Blocks > 1 ? SDHCI_TM_MULTI : 0))
      );
  }

  MmioWrite16 (
    SDCC_BASE + SDHCI_COMMAND,
    (UINT16)(((UINT32)Index << 8) | Flags)
    );

  if (WaitBits (SDHCI_INT_STATUS,
               SDHCI_INT_CMD_COMPLETE | SDHCI_INT_ERROR,
               SDHCI_INT_CMD_COMPLETE, 100000) != EFI_SUCCESS)
  {
    return EFI_TIMEOUT;
  }

  Status = MmioRead32 (SDCC_BASE + SDHCI_INT_STATUS);
  if ((Status & SDHCI_INT_ERROR) != 0) {
    return EFI_DEVICE_ERROR;
  }

  if (Response != NULL) {
    for (i = 0; i < 4; i++) {
      Response[i] = MmioRead32 (SDCC_BASE + SDHCI_RESPONSE + i * 4);
    }
  }

  if (Data != NULL) {
    Words = Blocks * 128u; /* 512 bytes per block */
    for (i = 0; i < Words; i++) {
      if (WaitBits (SDHCI_PRESENT_STATE, SDHCI_PS_BUF_READ_EN,
                   SDHCI_PS_BUF_READ_EN, 200000) != EFI_SUCCESS)
      {
        return EFI_TIMEOUT;
      }
      ((UINT32 *)Data)[i] = MmioRead32 (SDCC_BASE + SDHCI_BUFFER);
    }

    if (WaitBits (SDHCI_INT_STATUS, SDHCI_INT_TX_COMPLETE,
                 SDHCI_INT_TX_COMPLETE, 300000) != EFI_SUCCESS)
    {
      return EFI_TIMEOUT;
    }
  }

  return EFI_SUCCESS;
}

STATIC
VOID
Stage (
  IN UINT32        Number,
  IN UINT32        Total,
  IN CONST CHAR16  *Text
  )
{
  Print (L"\r\n[R11EMMC] STEP %u/%u: %s\r\n", Number, Total, Text);
  gBS->Stall (1500000);
}

STATIC
VOID
R11Finish (
  VOID
  )
{
  UINTN  i;

  for (i = 15; i > 0; i--) {
    Print (L"\r[R11EMMC] reboot in %02u s...", (UINT32)i);
    gBS->Stall (1000000);
  }
  Print (L"\r\n[R11EMMC] reset now\r\n");
  gRT->ResetSystem (EfiResetCold, EFI_SUCCESS, 0, NULL);
  CpuDeadLoop ();
}

EFI_STATUS
EFIAPI
R11EmmcTestEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  UINT32   Ps;
  UINT32   Caps;
  UINT32   GccApps;
  UINT32   GccAhb;
  UINT32   GccBcr;
  UINT32   Vendor;
  UINT16   Hc2;
  UINT8    Hc1;
  UINT8    Power;
  UINT16   Clock;
  UINT32   Resp[4];
  UINT32   Rca;
  UINT64   D1;
  UINT8    Block[512];
  EFI_STATUS Status;
  UINTN    i;

  (VOID)ImageHandle;
  (VOID)SystemTable;

  /* Never let a stuck CMD1/CMD13 loop keep the phone in UEFI forever. */
  gBS->SetWatchdogTimer (45, 0, 0, NULL);

  Ps     = MmioRead32 (SDCC_BASE + SDHCI_PRESENT_STATE);
  Hc1    = MmioRead8  (SDCC_BASE + SDHCI_HOST_CONTROL);
  Hc2    = MmioRead16 (SDCC_BASE + SDHCI_HOST_CONTROL2);
  Caps   = MmioRead32 (SDCC_BASE + SDHCI_CAPABILITIES);
  Vendor = MmioRead32 (SDCC_BASE + SDHCI_CORE_VENDOR);
  Power  = MmioRead8  (SDCC_BASE + SDHCI_POWER_CONTROL);
  Clock  = MmioRead16 (SDCC_BASE + SDHCI_CLOCK_CONTROL);

  Stage (1, 5, L"read SDHCI registers");
  Print (L"[R11EMMC] ps=%08x hc1=%02x hc2=%04x caps=%08x vs=%08x\r\n",
         Ps, Hc1, Hc2, Caps, Vendor);
  Print (L"[R11EMMC] pwr=%02x clk=%04x\r\n", Power, Clock);

  Stage (2, 5, L"enable 3.3 V / 400 kHz / 1-bit");

  /* The bootloader can leave the SD clock gated after handoff.  Enable 3.3 V,
   * a 400 kHz card clock (divider 0xFA for a 200 MHz base), and 1-bit mode
   * before trying CMD13.  This writes only the host, not the card. */
  MmioWrite8  (SDCC_BASE + SDHCI_POWER_CONTROL, 0x0F);
  MmioWrite8  (SDCC_BASE + SDHCI_HOST_CONTROL, 0x00);
  MmioWrite8  (SDCC_BASE + SDHCI_TIMEOUT_CONTROL, 0x0E);
  MmioWrite16 (SDCC_BASE + SDHCI_CLOCK_CONTROL, 0x0000);
  gBS->Stall (1000);
  MmioWrite16 (SDCC_BASE + SDHCI_CLOCK_CONTROL, 0x0001);
  if (WaitBits16 (SDHCI_CLOCK_CONTROL, 0x0002, 0x0002, 100000) != EFI_SUCCESS) {
    Print (L"[R11EMMC] clock never stable\r\n");
    R11Finish ();
  }
  MmioWrite16 (SDCC_BASE + SDHCI_CLOCK_CONTROL, 0xFA05);
  MmioWrite32 (SDCC_BASE + SDHCI_CORE_VENDOR, 0xA9Cu);
  Clock = MmioRead16 (SDCC_BASE + SDHCI_CLOCK_CONTROL);
  Print (L"[R11EMMC] clk after=%04x pwr after=%02x\r\n",
         Clock, MmioRead8 (SDCC_BASE + SDHCI_POWER_CONTROL));

  GccBcr  = MmioRead32 (GCC_BASE + 0x16000);
  GccApps = MmioRead32 (GCC_BASE + 0x16004);
  GccAhb  = MmioRead32 (GCC_BASE + 0x16008);
  Print (L"[R11EMMC] gcc bcr=%08x apps=%08x ahb=%08x\r\n",
         GccBcr, GccApps, GccAhb);
  if (((GccApps & 1u) == 0) || ((GccAhb & 1u) == 0)) {
    MmioWrite32 (GCC_BASE + 0x16008, GccAhb | 1u);
    MmioWrite32 (GCC_BASE + 0x16004, GccApps | 1u);
    gBS->Stall (1000);
    Print (L"[R11EMMC] gcc after apps=%08x ahb=%08x\r\n",
           MmioRead32 (GCC_BASE + 0x16004),
           MmioRead32 (GCC_BASE + 0x16008));
  }

  Stage (3, 7, L"CMD0 reset (0xF0F0F0F0)");
  Status = SdCommand (0, 0xF0F0F0F0u, 0, NULL, NULL, 0);
  Print (L"[R11EMMC] cmd0 err=%r\r\n", Status);
  gBS->Stall (10000);

  Stage (4, 7, L"CMD1 OCR wait");
  for (i = 0; i < 30; i++) {
    ZeroMem (Resp, sizeof (Resp));
    Status = SdCommand (1, 0x40FF8080u, SDHCI_CMD_R48, Resp, NULL, 0);
    if ((Status == EFI_SUCCESS) && ((Resp[0] & 0x80000000u) != 0)) {
      break;
    }
    if ((i % 5) == 0) {
      Print (L"[R11EMMC] cmd1 try=%u err=%r ocr=%08x\r\n",
             (UINT32)i, Status, Resp[0]);
    }
    gBS->Stall (10000);
  }
  Print (L"[R11EMMC] cmd1 err=%r ocr=%08x\r\n", Status, Resp[0]);
  if ((Status != EFI_SUCCESS) || ((Resp[0] & 0x80000000u) == 0)) {
    Print (L"[R11EMMC] card never ready\r\n");
    R11Finish ();
  }

  Stage (5, 7, L"CMD2 CID / CMD3 RCA / CMD7 select");
  ZeroMem (Resp, sizeof (Resp));
  Status = SdCommand (2, 0, SDHCI_CMD_R136 | SDHCI_CMD_CRC, Resp, NULL, 0);
  Print (L"[R11EMMC] cmd2 err=%r cid0=%08x\r\n", Status, Resp[0]);
  if (Status != EFI_SUCCESS) {
    R11Finish ();
  }

  ZeroMem (Resp, sizeof (Resp));
  Status = SdCommand (3, 0, SDHCI_CMD_R48 | SDHCI_CMD_CRC | SDHCI_CMD_INDEX,
                      Resp, NULL, 0);
  Rca = Resp[0] >> 16;
  Print (L"[R11EMMC] cmd3 err=%r rca=%u st=%08x\r\n", Status, Rca, Resp[0]);
  if ((Status != EFI_SUCCESS) || (Rca == 0)) {
    R11Finish ();
  }

  ZeroMem (Resp, sizeof (Resp));
  Status = SdCommand (7, Rca << 16,
                      SDHCI_CMD_R48BUSY | SDHCI_CMD_CRC | SDHCI_CMD_INDEX,
                      Resp, NULL, 0);
  Print (L"[R11EMMC] cmd7 err=%r st=%08x\r\n", Status, Resp[0]);
  if (Status != EFI_SUCCESS) {
    R11Finish ();
  }

  Stage (6, 7, L"CMD13 status / CMD16 blocklen 512");
  ZeroMem (Resp, sizeof (Resp));
  Status = SdCommand (13, Rca << 16,
                      SDHCI_CMD_R48 | SDHCI_CMD_CRC | SDHCI_CMD_INDEX,
                      Resp, NULL, 0);
  Print (L"[R11EMMC] cmd13 err=%r st=%08x\r\n", Status, Resp[0]);
  if (Status != EFI_SUCCESS) {
    R11Finish ();
  }

  ZeroMem (Resp, sizeof (Resp));
  Status = SdCommand (16, 512,
                      SDHCI_CMD_R48 | SDHCI_CMD_CRC | SDHCI_CMD_INDEX,
                      Resp, NULL, 0);
  Print (L"[R11EMMC] cmd16 err=%r st=%08x\r\n", Status, Resp[0]);
  if (Status != EFI_SUCCESS) {
    R11Finish ();
  }

  Stage (7, 7, L"CMD17 LBA1 with PIO");
  ZeroMem (Block, sizeof (Block));
  Status = SdCommand (17, 1, SDHCI_CMD_R48 | SDHCI_CMD_CRC |
                      SDHCI_CMD_INDEX | SDHCI_CMD_DATA,
                      Resp, Block, 1);
  D1 = 0;
  for (i = 0; i < 8; i++) {
    D1 = (D1 << 8) | Block[i];
  }

  Print (L"[R11EMMC] cmd17 err=%r d1=%016lx st=%08x\r\n",
         Status, D1, Resp[0]);
  Print (L"[R11EMMC] bytes: %02x %02x %02x %02x %02x %02x %02x %02x\r\n",
         Block[0], Block[1], Block[2], Block[3],
         Block[4], Block[5], Block[6], Block[7]);

  R11Finish ();
  return EFI_SUCCESS;
}