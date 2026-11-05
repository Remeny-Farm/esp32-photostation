#include "policy.h"

#include <algorithm>
#include <cctype>
#include <tuple>

UploadOutcome classify(int status) {
  switch (status) {
    case 200:
    case 201:
      return UploadOutcome::Sent;
    case 400:
    case 413:
    case 415:
    case 422:
      return UploadOutcome::Bad;
    case 401:
    case 403:
      return UploadOutcome::AuthStop;
    default:
      return UploadOutcome::Retry;
  }
}

uint32_t backoffMs(uint32_t attempt) {
  const uint32_t base = 5000;
  const uint32_t cap = 600000;
  if (attempt >= 7) return cap;  // 5000 * 128 = 640000 > cap; also avoids shift overflow
  uint32_t v = base << attempt;
  return v < cap ? v : cap;
}

namespace {

struct Entry {
  std::string visit;
  int kind;  // 0 = photo, 1 = json
  uint32_t n;
  std::string name;
};

bool endsWith(const std::string& s, const char* suffix) {
  size_t len = std::char_traits<char>::length(suffix);
  return s.size() >= len && s.compare(s.size() - len, len, suffix) == 0;
}

bool parseName(const std::string& name, Entry& out) {
  if (endsWith(name, ".json")) {
    std::string visit = name.substr(0, name.size() - 5);
    if (visit.empty()) return false;
    out = {visit, 1, 0, name};
    return true;
  }
  if (endsWith(name, ".jpg")) {
    std::string stem = name.substr(0, name.size() - 4);
    size_t us = stem.rfind('_');
    if (us == std::string::npos || us == 0) return false;
    std::string digits = stem.substr(us + 1);
    if (digits.empty() || digits.size() > 9) return false;
    uint32_t n = 0;
    for (char c : digits) {
      if (!std::isdigit(static_cast<unsigned char>(c))) return false;
      n = n * 10 + static_cast<uint32_t>(c - '0');
    }
    out = {stem.substr(0, us), 0, n, name};
    return true;
  }
  return false;
}

}  // namespace

std::vector<std::string> uploadOrder(std::vector<std::string> names) {
  std::vector<Entry> entries;
  for (const std::string& name : names) {
    Entry e;
    if (parseName(name, e)) entries.push_back(std::move(e));
  }
  std::stable_sort(entries.begin(), entries.end(), [](const Entry& a, const Entry& b) {
    return std::tie(a.visit, a.kind, a.n) < std::tie(b.visit, b.kind, b.n);
  });
  std::vector<std::string> out;
  out.reserve(entries.size());
  for (Entry& e : entries) out.push_back(std::move(e.name));
  return out;
}

Command parseCommand(const std::string& line) {
  std::vector<std::string> tokens;
  size_t i = 0;
  const size_t n = line.size();
  auto isSpace = [](char c) { return std::isspace(static_cast<unsigned char>(c)) != 0; };
  while (i < n) {
    while (i < n && isSpace(line[i])) i++;
    if (i >= n) break;
    std::string tok;
    if (line[i] == '"') {
      i++;
      while (i < n && line[i] != '"') tok += line[i++];
      if (i < n) i++;  // closing quote; unterminated quote takes the rest
    } else {
      while (i < n && !isSpace(line[i])) tok += line[i++];
    }
    tokens.push_back(std::move(tok));
  }
  Command c;
  if (!tokens.empty()) {
    c.name = tokens.front();
    c.args.assign(tokens.begin() + 1, tokens.end());
  }
  return c;
}

std::string maskSecret(const std::string& s) {
  if (s.size() <= 4) return "****";
  return "****" + s.substr(s.size() - 4);
}
