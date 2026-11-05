// Tiny host test harness. One test file = one executable.
//   TEST(name) { CHECK(x); CHECK_EQ(a, b); }
//   CHECK_MAIN()   // once, at the end of the test file
#pragma once
#include <cstdio>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

namespace check {

struct Case {
  const char* name;
  void (*fn)();
};

inline std::vector<Case>& registry() {
  static std::vector<Case> r;
  return r;
}

inline int& failuresInCurrent() {
  static int n = 0;
  return n;
}

struct Registrar {
  Registrar(const char* name, void (*fn)()) { registry().push_back({name, fn}); }
};

inline int runAll() {
  int failedTests = 0;
  for (const Case& c : registry()) {
    failuresInCurrent() = 0;
    c.fn();
    if (failuresInCurrent() == 0) {
      std::printf("PASS %s\n", c.name);
    } else {
      std::printf("FAIL %s\n", c.name);
      failedTests++;
    }
  }
  std::printf("%zu tests, %d failed\n", registry().size(), failedTests);
  return failedTests == 0 ? 0 : 1;
}

}  // namespace check

#define TEST(name)                                                    \
  static void test_##name();                                          \
  static check::Registrar registrar_##name(#name, &test_##name);      \
  static void test_##name()

#define CHECK(cond)                                                              \
  do {                                                                           \
    if (!(cond)) {                                                               \
      std::printf("  %s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond);     \
      check::failuresInCurrent()++;                                              \
    }                                                                            \
  } while (0)

#define CHECK_EQ(a, b)                                                           \
  do {                                                                           \
    auto&& va_ = (a);                                                            \
    auto&& vb_ = (b);                                                            \
    if (!(va_ == vb_)) {                                                         \
      std::cout << "  " << __FILE__ << ":" << __LINE__ << ": CHECK_EQ failed: "  \
                << #a << " == " << #b << " (" << va_ << " vs " << vb_ << ")\n";  \
      check::failuresInCurrent()++;                                              \
    }                                                                            \
  } while (0)

#define CHECK_MAIN() \
  int main() { return check::runAll(); }
