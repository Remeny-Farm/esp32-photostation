// Tag table and identification. Pure C++17, no Arduino headers.
#pragma once
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <string>
#include <vector>

struct TagSample {
  uint32_t ms;
  int8_t rssi;
};

struct Candidate {
  std::string mac;
  std::string name;
  int median;
  int count;
  int min;
  int max;
};

struct Decision {
  bool known = false;
  std::string mac;
  std::string name;
  std::vector<Candidate> candidates;  // sorted by median desc, ties by count desc
};

// Odd count: middle value. Even count: floor((a+b)/2.0) of the two middle values.
// Empty input returns -128 (weakest possible int8 RSSI).
int medianRssi(std::vector<int8_t> v);

class TagTable {
 public:
  static constexpr size_t kMaxTags = 32;
  static constexpr size_t kMaxSamplesPerTag = 1024;

  // A sample for a new tag is ignored while kMaxTags tags are held.
  // Beyond kMaxSamplesPerTag samples for one tag the oldest is dropped.
  void add(const std::string& mac, const std::string& name, uint32_t ms, int8_t rssi, int vbatMv);
  // Drops samples with (int32_t)(ms - keepFromMs) < 0; tags left empty are removed.
  void prune(uint32_t keepFromMs);
  // Per-tag stats over the wrap-safe window [fromMs, toMs]; tags with no sample are omitted.
  std::vector<Candidate> summarize(uint32_t fromMs, uint32_t toMs) const;
  size_t tagCount() const { return tags_.size(); }

 private:
  struct Tag {
    std::string name;
    int vbatMv = 0;
    std::deque<TagSample> samples;
  };
  std::map<std::string, Tag> tags_;
};

// Known only if the strongest candidate has median >= thresholdDbm, count >= minCount,
// and leads the runner-up (if any) by at least marginDb.
Decision identify(const std::vector<Candidate>& c, int thresholdDbm = -60, int marginDb = 8,
                  int minCount = 3);
