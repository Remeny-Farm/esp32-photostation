#include "console.h"

#include <Arduino.h>
#include <map>
#include <string>

namespace {
std::map<std::string, std::function<void(const Command&)>> g_cmds;
std::string g_line;
std::string g_current;
constexpr size_t kMaxLine = 256;

void dispatch(const std::string& line) {
  g_current = line;
  Command c = parseCommand(line);
  if (c.name.empty()) return;
  auto it = g_cmds.find(c.name);
  if (it == g_cmds.end()) {
    Serial.printf("ERR unknown command '%s'\n", c.name.c_str());
    return;
  }
  it->second(c);
}
}  // namespace

void consoleRegister(const char* name, std::function<void(const Command&)> fn) {
  g_cmds[name] = std::move(fn);
}

const std::string& consoleRawLine() { return g_current; }

void consolePoll() {
  while (Serial.available()) {
    int ch = Serial.read();
    if (ch < 0) break;
    if (ch == '\n' || ch == '\r') {
      std::string line;
      line.swap(g_line);
      dispatch(line);
    } else if (g_line.size() < kMaxLine) {
      g_line += (char)ch;
    }
  }
}
