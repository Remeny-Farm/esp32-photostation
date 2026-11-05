#include "check.h"
#include "core/ident.h"

static Candidate cand(const char* mac, int median, int count) {
  return Candidate{mac, mac, median, count, median, median};
}

TEST(median_odd) {
  CHECK_EQ(medianRssi({-50, -40, -45}), -45);
}

TEST(median_even_negative) {
  CHECK_EQ(medianRssi({-48, -51}), -50);
}

TEST(ident_clear_winner) {
  Decision d = identify({cand("A", -48, 12), cand("B", -61, 5)});
  CHECK(d.known);
  CHECK_EQ(d.mac, std::string("A"));
}

TEST(ident_margin_too_small) {
  Decision d = identify({cand("A", -50, 10), cand("B", -55, 10)});
  CHECK(!d.known);
}

TEST(ident_below_threshold) {
  Decision d = identify({cand("A", -65, 10)});
  CHECK(!d.known);
}

TEST(ident_too_few_packets) {
  Decision d = identify({cand("A", -45, 2)});
  CHECK(!d.known);
}

TEST(ident_single_tag_ok) {
  Decision d = identify({cand("A", -50, 3)});
  CHECK(d.known);
  CHECK_EQ(d.mac, std::string("A"));
}

TEST(ident_empty) {
  Decision d = identify({});
  CHECK(!d.known);
  CHECK(d.candidates.empty());
}

TEST(table_summarize_window) {
  TagTable t;
  t.add("A", "hen", 1000, -50, 3000);
  t.add("A", "hen", 2000, -50, 3000);
  t.add("A", "hen", 9000, -50, 3000);
  std::vector<Candidate> c = t.summarize(1500, 8000);
  CHECK_EQ(c.size(), (size_t)1);
  CHECK_EQ(c[0].count, 1);
}

TEST(ident_window_across_wrap) {
  TagTable t;
  t.add("A", "hen", 0xFFFFFF00u, -50, 3000);
  t.add("A", "hen", 0x00000100u, -52, 3000);
  std::vector<Candidate> c = t.summarize(0xFFFFF000u, 0x00001000u);
  CHECK_EQ(c.size(), (size_t)1);
  CHECK_EQ(c[0].count, 2);
}

TEST(table_cap_samples) {
  TagTable t;
  for (uint32_t i = 0; i < 1100; i++) t.add("A", "hen", i, -50, 3000);
  std::vector<Candidate> c = t.summarize(0, 0xFFFFFFFFu);
  CHECK_EQ(c.size(), (size_t)1);
  CHECK_EQ(c[0].count, 1024);
}

TEST(table_cap_tags) {
  TagTable t;
  for (int i = 0; i < 40; i++) t.add("T" + std::to_string(i), "n", 100, -50, 3000);
  CHECK_EQ(t.tagCount(), (size_t)32);
}

TEST(table_prune_wrap_safe) {
  TagTable t;
  t.add("A", "hen", 0xFFFFFF00u, -50, 3000);
  t.add("A", "hen", 0x00000100u, -50, 3000);
  t.prune(0x00000000u);  // drops the pre-wrap sample only
  std::vector<Candidate> c = t.summarize(0xFFFFF000u, 0x00001000u);
  CHECK_EQ(c.size(), (size_t)1);
  CHECK_EQ(c[0].count, 1);
  t.prune(0x00000200u);
  CHECK_EQ(t.tagCount(), (size_t)0);
}

TEST(summarize_sorted_and_stats) {
  TagTable t;
  t.add("A", "a", 10, -70, 3000);
  t.add("B", "b", 10, -40, 3000);
  t.add("B", "b", 11, -50, 3000);
  t.add("C", "c", 10, -40, 3000);
  std::vector<Candidate> c = t.summarize(0, 100);
  CHECK_EQ(c.size(), (size_t)3);
  CHECK_EQ(c[0].mac, std::string("C"));  // -40, count 1
  CHECK_EQ(c[1].mac, std::string("B"));  // median -45
  CHECK_EQ(c[2].mac, std::string("A"));
  CHECK_EQ(c[1].min, -50);
  CHECK_EQ(c[1].max, -40);
  CHECK_EQ(c[1].median, -45);
}

CHECK_MAIN()
