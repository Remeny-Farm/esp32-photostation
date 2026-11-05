// SD card (SPI, FAT32): verified writes, queue listing, moves, pruning.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include <functional>
#include <string>

bool storageInit();   // mounts the card, creates /q /sent /bad /log, removes stale *.tmp in /q
bool storageReady();  // true after a successful storageInit()
// Recursive lock around every SD access (several tasks use the card).
void storageLock();
void storageUnlock();

// Writes to "<path>.tmp", reads it back and compares byte by byte, then renames to <path>.
// On any failure the temporary file is removed and false is returned.
bool storageWriteVerified(const char* path, const uint8_t* buf, size_t len);
bool storageWriteText(const char* path, const std::string& s);
// One pass over dir (getNextFileName: no per-entry open, no stored list). Calls fn with the bare
// name of each regular file; directories are skipped. Holds the storage lock for the pass and
// yields one tick every 32 entries. Returns the number of regular files (0 when dir is missing).
size_t storageForEach(const char* dir, const std::function<void(const std::string&)>& fn);
int64_t storageFileSize(const char* path);  // -1 when missing
// Reads at most maxBytes from the end of the file. False when the file is missing.
bool storageReadTail(const char* path, std::string& out, size_t maxBytes);
// Creates dir with its parents when missing. False when the card is not ready or mkdir fails.
bool storageEnsureDir(const char* dir);
// Moves a file into toDir (created with parents), keeping its bare name.
bool storageMove(const char* from, const char* toDir);
// Above 80 % card usage removes the single oldest /sent day directory (one day per call), taking
// the storage lock per batch of 32 files, not for the whole day. Never touches /q.
void storagePruneSent();
// Removes dir and everything below it (batched, the lock is taken per batch). True when dir is gone.
// Only /benchls and paths below it are accepted; null or any other path returns false and touches nothing.
bool storageRemoveTree(const char* dir);
uint8_t storageUsedPct();
uint64_t storageSizeMb();
