// SD card health check + FAT32 format on the XIAO ESP32S3 Sense (SPI mode).
// Serial commands (newline-terminated):
//   i  = card registers, filesystem info, root listing   (read-only)
//   T  = raw write/verify test across the whole card     (DESTROYS DATA)
//   F  = format FAT32 (32 KB clusters) + file write/read check (DESTROYS DATA)

#include <dirent.h>
#include <sys/stat.h>
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "diskio_impl.h"
#include "diskio_sdmmc.h"
#include "ff.h"
#include "esp_heap_caps.h"

#define SD_CS   21
#define SD_SCK  7
#define SD_MISO 8
#define SD_MOSI 9
#define MOUNT   "/sd"

static sdmmc_card_t *card = nullptr;
static sdmmc_host_t host = SDSPI_HOST_DEFAULT();

static sdspi_dev_handle_t devh = -1;
static bool mounted = false;

static void busInit() {
  spi_bus_config_t bus = {};
  bus.mosi_io_num = SD_MOSI;
  bus.miso_io_num = SD_MISO;
  bus.sclk_io_num = SD_SCK;
  bus.quadwp_io_num = -1;
  bus.quadhd_io_num = -1;
  bus.max_transfer_sz = 32 * 1024;
  spi_bus_initialize((spi_host_device_t)host.slot, &bus, SDSPI_DEFAULT_DMA);  // INVALID_STATE = already up
}

static sdspi_device_config_t slotCfg() {
  sdspi_device_config_t slot = SDSPI_DEVICE_CONFIG_DEFAULT();
  slot.gpio_cs = (gpio_num_t)SD_CS;
  slot.host_id = SPI2_HOST;
  return slot;
}

// Raw card access without any filesystem (works for exFAT / unformatted cards too).
static bool rawInit() {
  busInit();
  host.max_freq_khz = 20000;
  esp_err_t e = sdspi_host_init();
  if (e != ESP_OK && e != ESP_ERR_INVALID_STATE) { Serial.printf("ERR sdspi_host_init 0x%x\n", e); return false; }
  sdspi_device_config_t slot = slotCfg();
  e = sdspi_host_init_device(&slot, &devh);
  if (e != ESP_OK) { Serial.printf("ERR init_device 0x%x\n", e); return false; }
  host.slot = devh;
  card = (sdmmc_card_t *)calloc(1, sizeof(sdmmc_card_t));
  e = sdmmc_card_init(&host, card);
  if (e != ESP_OK) {
    Serial.printf("ERR sdmmc_card_init 0x%x (%s)\n", e, esp_err_to_name(e));
    free(card); card = nullptr;
    sdspi_host_remove_device(devh); devh = -1;
    return false;
  }
  return true;
}

static void rawDeinit() {
  if (devh >= 0) sdspi_host_remove_device(devh);
  devh = -1;
  sdspi_host_deinit();
  free(card);
  card = nullptr;
}

// Mount FAT (format if no FS found). Replaces the raw handle with the VFS-owned one.
static bool mountFat() {
  rawDeinit();
  sdmmc_host_t h = SDSPI_HOST_DEFAULT();
  h.max_freq_khz = 20000;
  host = h;
  sdspi_device_config_t slot = slotCfg();
  esp_vfs_fat_sdmmc_mount_config_t mc = {};
  mc.format_if_mount_failed = true;
  mc.max_files = 4;
  mc.allocation_unit_size = 32 * 1024;
  esp_err_t e = esp_vfs_fat_sdspi_mount(MOUNT, &host, &slot, &mc, &card);
  if (e != ESP_OK) { Serial.printf("ERR mount 0x%x (%s)\n", e, esp_err_to_name(e)); card = nullptr; return false; }
  mounted = true;
  return true;
}

static void printPartitions() {
  uint8_t *b = (uint8_t *)heap_caps_malloc(512, MALLOC_CAP_DMA);
  if (sdmmc_read_sectors(card, b, 0, 1) != ESP_OK) { Serial.println("MBR read_fail"); free(b); return; }
  bool sig = b[510] == 0x55 && b[511] == 0xAA;
  if (memcmp(b + 3, "EXFAT   ", 8) == 0 || memcmp(b + 0x52, "FAT32", 5) == 0 || memcmp(b + 0x36, "FAT", 3) == 0) {
    Serial.printf("MBR none (superfloppy) boot_sig=%d oem=%.8s\n", sig, b + 3);
    free(b); return;
  }
  Serial.printf("MBR boot_sig=%d\n", sig);
  for (int i = 0; i < 4; i++) {
    uint8_t *pe = b + 0x1BE + 16 * i;
    uint8_t type = pe[4];
    uint32_t lba = pe[8] | pe[9] << 8 | pe[10] << 16 | (uint32_t)pe[11] << 24;
    uint32_t n = pe[12] | pe[13] << 8 | pe[14] << 16 | (uint32_t)pe[15] << 24;
    if (!type) continue;
    uint8_t *vb = (uint8_t *)heap_caps_malloc(512, MALLOC_CAP_DMA);
    char oem[9] = {0}, label[12] = {0};
    if (sdmmc_read_sectors(card, vb, lba, 1) == ESP_OK) {
      memcpy(oem, vb + 3, 8);
      if (memcmp(oem, "EXFAT", 5) != 0) memcpy(label, vb + (memcmp(vb + 0x52, "FAT32", 5) == 0 ? 0x47 : 0x2B), 11);
    }
    Serial.printf("PART %d type=0x%02x start=%u sectors=%u (%.2f GB) fs_oem=%s label=%s\n", i, type, lba, n,
                  n * 512.0 / 1e9, oem, label);
    free(vb);
  }
  free(b);
}

static int fatInfo(uint64_t *total, uint64_t *freeb) {
  if (esp_vfs_fat_info(MOUNT, total, freeb) != ESP_OK) return -1;
  BYTE pdrv = ff_diskio_get_pdrv_card(card);
  char drv[3] = {(char)('0' + pdrv), ':', 0};
  DWORD nclst;
  FATFS *fs;
  if (f_getfree(drv, &nclst, &fs) != FR_OK) return -1;
  Serial.printf("FS type=%s cluster_bytes=%u\n",
                fs->fs_type == FS_FAT32 ? "FAT32" : fs->fs_type == FS_FAT16 ? "FAT16"
                : fs->fs_type == FS_FAT12 ? "FAT12" : fs->fs_type == FS_EXFAT ? "exFAT" : "?",
                (unsigned)fs->csize * 512);
  return 0;
}

static void listDir(const char *path, int depth, int *files, uint64_t *bytes) {
  DIR *d = opendir(path);
  if (!d) return;
  struct dirent *de;
  while ((de = readdir(d))) {
    char p[300];
    snprintf(p, sizeof(p), "%s/%s", path, de->d_name);
    struct stat st;
    if (stat(p, &st) != 0) continue;
    if (S_ISDIR(st.st_mode)) {
      if (depth < 2) Serial.printf("LS  [dir] %s\n", p);
      listDir(p, depth + 1, files, bytes);
    } else {
      (*files)++;
      *bytes += st.st_size;
      if (*files <= 40) Serial.printf("LS  %10ld %s\n", (long)st.st_size, p);
    }
  }
  closedir(d);
}

static void cmdInfo() {
  Serial.printf("CARD name=%.8s mfg_id=0x%02x oem_id=0x%04x serial=0x%08x date=%d-%02d\n",
                card->cid.name, card->cid.mfg_id, card->cid.oem_id, (unsigned)card->cid.serial,
                2000 + (card->cid.date >> 4), card->cid.date & 0xF);
  uint64_t capB = (uint64_t)card->csd.capacity * card->csd.sector_size;
  Serial.printf("CARD type=%s sectors=%d sector_size=%d capacity_bytes=%llu (%.2f GB)\n",
                (card->ocr & SD_OCR_SDHC_CAP) ? "SDHC/SDXC" : "SDSC", card->csd.capacity,
                card->csd.sector_size, capB, capB / 1e9);
  Serial.printf("CARD csd_ver=%d tr_speed=%d bus_khz=%d\n", card->csd.csd_ver, card->csd.tr_speed,
                card->max_freq_khz);
  printPartitions();
  uint64_t total, freeb;
  if (mounted && fatInfo(&total, &freeb) == 0) {
    Serial.printf("FS total=%llu free=%llu\n", total, freeb);
    int files = 0;
    uint64_t bytes = 0;
    listDir(MOUNT, 0, &files, &bytes);
    Serial.printf("LS_SUMMARY files=%d bytes=%llu\n", files, bytes);
  } else {
    Serial.println("FS not_mounted (raw mode)");
  }
}

// Deterministic per-sector pattern; first word = sector number so wrap-around (fake capacity) shows.
static void fillPattern(uint32_t *w, uint32_t sector, uint32_t seed) {
  w[0] = sector;
  w[1] = ~sector;
  uint32_t x = sector * 2654435761u ^ seed ^ 0x9E3779B9u;
  for (int i = 2; i < 128; i++) {
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    w[i] = x;
  }
}

static void cmdTest() {
  const uint32_t CH = 64;  // sectors per chunk (32 KB)
  const uint32_t REG = 256;
  uint32_t total = card->csd.capacity;
  uint32_t seed = esp_random();
  uint8_t *buf = (uint8_t *)heap_caps_malloc(CH * 512, MALLOC_CAP_DMA);
  uint8_t *exp = (uint8_t *)malloc(512);
  if (!buf || !exp) { Serial.println("ERR alloc"); return; }

  // Phase 1: write REG chunks spread over the whole card (last one ends at the final sector).
  uint32_t werr = 0, rerr = 0, bad = 0, wrapped = 0;
  uint32_t t0 = millis();
  for (uint32_t r = 0; r < REG; r++) {
    uint32_t start = (uint32_t)(((uint64_t)(total - CH) * r) / (REG - 1));
    for (uint32_t s = 0; s < CH; s++) fillPattern((uint32_t *)(buf + s * 512), start + s, seed);
    if (sdmmc_write_sectors(card, buf, start, CH) != ESP_OK) werr++;
    if (r % 32 == 31) Serial.printf("TEST write %u/%u\n", r + 1, REG);
  }
  // Phase 2: read everything back after all writes, verify.
  for (uint32_t r = 0; r < REG; r++) {
    uint32_t start = (uint32_t)(((uint64_t)(total - CH) * r) / (REG - 1));
    if (sdmmc_read_sectors(card, buf, start, CH) != ESP_OK) { rerr++; continue; }
    for (uint32_t s = 0; s < CH; s++) {
      fillPattern((uint32_t *)exp, start + s, seed);
      if (memcmp(buf + s * 512, exp, 512) != 0) {
        bad++;
        uint32_t got = *(uint32_t *)(buf + s * 512);
        if (got != start + s && got < total) wrapped++;
        if (bad <= 5) Serial.printf("TEST BAD sector=%u first_word=%u\n", start + s, got);
      }
    }
  }
  Serial.printf("TEST spread regions=%u sectors_checked=%u write_err=%u read_err=%u bad_sectors=%u wrapped=%u ms=%u\n",
                REG, REG * CH, werr, rerr, bad, wrapped, millis() - t0);

  // Phase 3: sequential speed, 16 MB in the middle of the card.
  const uint32_t N = 512;  // 512 x 32 KB = 16 MB
  uint32_t base = total / 2;
  uint32_t sbad = 0;
  t0 = millis();
  for (uint32_t i = 0; i < N; i++) {
    for (uint32_t s = 0; s < CH; s++) fillPattern((uint32_t *)(buf + s * 512), base + i * CH + s, seed);
    if (sdmmc_write_sectors(card, buf, base + i * CH, CH) != ESP_OK) werr++;
  }
  uint32_t wms = millis() - t0;
  t0 = millis();
  for (uint32_t i = 0; i < N; i++) {
    if (sdmmc_read_sectors(card, buf, base + i * CH, CH) != ESP_OK) { rerr++; continue; }
    for (uint32_t s = 0; s < CH; s++) {
      fillPattern((uint32_t *)exp, base + i * CH + s, seed);
      if (memcmp(buf + s * 512, exp, 512) != 0) sbad++;
    }
  }
  uint32_t rms = millis() - t0;  // includes verify time
  Serial.printf("TEST seq bytes=%u write_ms=%u (%.2f MB/s) read+verify_ms=%u (%.2f MB/s) bad_sectors=%u\n",
                N * CH * 512, wms, N * CH * 512 / 1e3 / wms, rms, N * CH * 512 / 1e3 / rms, sbad);
  Serial.printf("TEST_DONE %s\n", (werr || rerr || bad || sbad) ? "FAIL" : "PASS");
  free(buf);
  free(exp);
}

static void cmdFormat() {
  uint32_t t0 = millis();
  if (!mounted && !mountFat()) { Serial.println("FORMAT_FAIL mount"); return; }
  esp_err_t e = esp_vfs_fat_sdcard_format(MOUNT, card);
  if (e != ESP_OK) {
    Serial.printf("FORMAT_FAIL 0x%x (%s)\n", e, esp_err_to_name(e));
    return;
  }
  Serial.printf("FORMAT ok ms=%u\n", millis() - t0);
  uint64_t total, freeb;
  if (fatInfo(&total, &freeb) == 0) Serial.printf("FS total=%llu free=%llu\n", total, freeb);

  // File-level check: write 1 MB, read back, compare.
  const size_t SZ = 1024 * 1024;
  uint8_t *b = (uint8_t *)malloc(4096);
  FILE *f = fopen(MOUNT "/health.bin", "wb");
  bool ok = f != nullptr;
  for (size_t off = 0; ok && off < SZ; off += 4096) {
    for (int i = 0; i < 4096; i++) b[i] = (uint8_t)((off + i) * 31 + 7);
    ok = fwrite(b, 1, 4096, f) == 4096;
  }
  if (f) fclose(f);
  f = fopen(MOUNT "/health.bin", "rb");
  ok = ok && f != nullptr;
  for (size_t off = 0; ok && off < SZ; off += 4096) {
    ok = fread(b, 1, 4096, f) == 4096;
    for (int i = 0; ok && i < 4096; i++) ok = b[i] == (uint8_t)((off + i) * 31 + 7);
  }
  if (f) fclose(f);
  remove(MOUNT "/health.bin");
  free(b);
  Serial.printf("FILECHECK %s (1 MB write/read/compare, file removed)\n", ok ? "ok" : "FAIL");
}

void setup() {
  Serial.begin(115200);
  uint32_t t = millis();
  while (!Serial && millis() - t < 5000) delay(10);
  Serial.println(rawInit() ? "READY" : "NO_CARD");
}

void loop() {
  if (!Serial.available()) { delay(10); return; }
  String l = Serial.readStringUntil('\n');
  l.trim();
  if (!card) {
    Serial.println("NO_CARD, retrying mount");
    if (!rawInit()) { Serial.println("CMD_END"); return; }
    Serial.println("MOUNT_RETRY ok");
  }
  if (l == "i") cmdInfo();
  else if (l == "T") cmdTest();
  else if (l == "F") cmdFormat();
  Serial.println("CMD_END");
}
