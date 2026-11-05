#include "ident.h"

#include <algorithm>
#include <cmath>

int medianRssi(std::vector<int8_t> v) {
  if (v.empty()) return -128;
  std::sort(v.begin(), v.end());
  size_t n = v.size();
  if (n % 2 == 1) return v[n / 2];
  int a = v[n / 2 - 1];
  int b = v[n / 2];
  return static_cast<int>(std::floor((a + b) / 2.0));
}

void TagTable::add(const std::string& mac, const std::string& name, uint32_t ms, int8_t rssi,
                   int vbatMv) {
  auto it = tags_.find(mac);
  if (it == tags_.end()) {
    if (tags_.size() >= kMaxTags) return;
    it = tags_.emplace(mac, Tag{}).first;
  }
  Tag& t = it->second;
  if (!name.empty()) t.name = name;
  t.vbatMv = vbatMv;
  t.samples.push_back({ms, rssi});
  while (t.samples.size() > kMaxSamplesPerTag) t.samples.pop_front();
}

void TagTable::prune(uint32_t keepFromMs) {
  for (auto it = tags_.begin(); it != tags_.end();) {
    std::deque<TagSample>& s = it->second.samples;
    s.erase(std::remove_if(s.begin(), s.end(),
                           [keepFromMs](const TagSample& x) {
                             return static_cast<int32_t>(x.ms - keepFromMs) < 0;
                           }),
            s.end());
    if (s.empty()) {
      it = tags_.erase(it);
    } else {
      ++it;
    }
  }
}

static bool better(const Candidate& a, const Candidate& b) {
  if (a.median != b.median) return a.median > b.median;
  if (a.count != b.count) return a.count > b.count;
  return a.mac < b.mac;  // deterministic
}

std::vector<Candidate> TagTable::summarize(uint32_t fromMs, uint32_t toMs) const {
  std::vector<Candidate> out;
  const uint32_t span = toMs - fromMs;
  for (const auto& kv : tags_) {
    std::vector<int8_t> v;
    for (const TagSample& s : kv.second.samples) {
      if (static_cast<uint32_t>(s.ms - fromMs) <= span) v.push_back(s.rssi);
    }
    if (v.empty()) continue;
    Candidate c;
    c.mac = kv.first;
    c.name = kv.second.name;
    c.count = static_cast<int>(v.size());
    c.min = *std::min_element(v.begin(), v.end());
    c.max = *std::max_element(v.begin(), v.end());
    c.median = medianRssi(v);
    out.push_back(c);
  }
  std::sort(out.begin(), out.end(), better);
  return out;
}

Decision identify(const std::vector<Candidate>& c, int thresholdDbm, int marginDb, int minCount) {
  Decision d;
  d.candidates = c;
  std::sort(d.candidates.begin(), d.candidates.end(), better);
  if (d.candidates.empty()) return d;
  const Candidate& top = d.candidates[0];
  if (top.median < thresholdDbm) return d;
  if (top.count < minCount) return d;
  if (d.candidates.size() > 1 && top.median - d.candidates[1].median < marginDb) return d;
  d.known = true;
  d.mac = top.mac;
  d.name = top.name;
  return d;
}
