// Upload status policy, queue order and serial console parsing.
// Pure C++17, no Arduino headers.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

enum class UploadOutcome { Sent, Bad, AuthStop, Retry };

// 200/201 Sent; 400/413/415/422 Bad; 401/403 AuthStop; everything else
// (429, 5xx, status <= 0 for network errors, unknown codes) Retry.
UploadOutcome classify(int status);

// min(5000 * 2^attempt, 600000) ms. Safe for any attempt.
uint32_t backoffMs(uint32_t attempt);

// Bare file names in /q: "<visit>_<n>.jpg" and "<visit>.json".
// Grouped by visit id ascending, photos by numeric n, then the JSON.
// Names matching neither pattern are dropped.
std::vector<std::string> uploadOrder(std::vector<std::string> names);

struct Command {
  std::string name;
  std::vector<std::string> args;
};

// Trims, splits on whitespace. A double-quoted argument may contain spaces.
Command parseCommand(const std::string& line);

// "****" + last 4 chars; "****" alone when length <= 4.
std::string maskSecret(const std::string& s);
