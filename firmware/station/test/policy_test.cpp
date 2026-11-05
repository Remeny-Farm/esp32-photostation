#include <string>
#include <vector>

#include "check.h"
#include "core/policy.h"

using std::string;
using std::vector;

static std::ostream& operator<<(std::ostream& os, UploadOutcome o) {
  return os << static_cast<int>(o);
}

TEST(classify_statuses) {
  CHECK_EQ(classify(200), UploadOutcome::Sent);
  CHECK_EQ(classify(201), UploadOutcome::Sent);
  CHECK_EQ(classify(400), UploadOutcome::Bad);
  CHECK_EQ(classify(413), UploadOutcome::Bad);
  CHECK_EQ(classify(415), UploadOutcome::Bad);
  CHECK_EQ(classify(422), UploadOutcome::Bad);
  CHECK_EQ(classify(401), UploadOutcome::AuthStop);
  CHECK_EQ(classify(403), UploadOutcome::AuthStop);
  CHECK_EQ(classify(429), UploadOutcome::Retry);
  CHECK_EQ(classify(500), UploadOutcome::Retry);
  CHECK_EQ(classify(503), UploadOutcome::Retry);
  CHECK_EQ(classify(-1), UploadOutcome::Retry);
  CHECK_EQ(classify(0), UploadOutcome::Retry);
  CHECK_EQ(classify(302), UploadOutcome::Retry);
}

TEST(backoff_caps) {
  CHECK_EQ(backoffMs(0), 5000u);
  CHECK_EQ(backoffMs(1), 10000u);
  CHECK_EQ(backoffMs(6), 320000u);
  CHECK_EQ(backoffMs(7), 600000u);
  CHECK_EQ(backoffMs(31), 600000u);
  CHECK_EQ(backoffMs(32), 600000u);
  CHECK_EQ(backoffMs(1000), 600000u);
  CHECK_EQ(backoffMs(0xFFFFFFFFu), 600000u);
}

TEST(order_photos_before_json) {
  vector<string> in = {"v1.json", "v1_2.jpg", "v1_10.jpg", "v1_1.jpg"};
  vector<string> want = {"v1_1.jpg", "v1_2.jpg", "v1_10.jpg", "v1.json"};
  CHECK(uploadOrder(in) == want);
}

TEST(order_oldest_visit_first) {
  const string a = "ps-01-20261103T101500Z-0001";
  const string b = "ps-01-20261103T091500Z-0001";
  vector<string> in = {a + ".json", a + "_1.jpg", b + ".json", b + "_2.jpg", b + "_1.jpg"};
  vector<string> want = {b + "_1.jpg", b + "_2.jpg", b + ".json", a + "_1.jpg", a + ".json"};
  CHECK(uploadOrder(in) == want);
}

TEST(order_visit_ids_with_dashes_and_digits) {
  // unsynced id; photo number is split on the last '_'
  vector<string> in = {"ps-01-B0007-0042.json", "ps-01-B0007-0042_3.jpg", "ps-01-B0007-0042_12.jpg"};
  vector<string> want = {"ps-01-B0007-0042_3.jpg", "ps-01-B0007-0042_12.jpg", "ps-01-B0007-0042.json"};
  CHECK(uploadOrder(in) == want);
}

TEST(order_drops_junk) {
  vector<string> in = {"notes.txt", "v1.json", "v1_1.jpg", "v1_x.jpg", "v1_.jpg", "_1.jpg",
                       ".json", "v1_1.png", "v1_-1.jpg", "v1_1.jpg.tmp", ""};
  vector<string> want = {"v1_1.jpg", "v1.json"};
  CHECK(uploadOrder(in) == want);
  CHECK(uploadOrder({"notes.txt"}).empty());
  CHECK(uploadOrder({}).empty());
}

TEST(parse_quoted) {
  Command c = parseCommand("set wifi \"Home WiFi\" pw123");
  CHECK_EQ(c.name, string("set"));
  vector<string> want = {"wifi", "Home WiFi", "pw123"};
  CHECK(c.args == want);
}

TEST(parse_trim_and_empty) {
  Command c = parseCommand("  status \r\n");
  CHECK_EQ(c.name, string("status"));
  CHECK(c.args.empty());
  Command e = parseCommand("   ");
  CHECK(e.name.empty());
  CHECK(e.args.empty());
  Command m = parseCommand("a   b\tc");
  CHECK_EQ(m.name, string("a"));
  vector<string> want = {"b", "c"};
  CHECK(m.args == want);
}

TEST(parse_quote_edges) {
  Command u = parseCommand("set wifi \"Home WiFi");  // unterminated: rest is the argument
  vector<string> wantU = {"wifi", "Home WiFi"};
  CHECK(u.args == wantU);
  Command q = parseCommand("set pw \"\"");
  vector<string> wantQ = {"pw", ""};
  CHECK(q.args == wantQ);
}

TEST(mask) {
  CHECK_EQ(maskSecret("abcdef123456"), string("****3456"));
  CHECK_EQ(maskSecret("abc"), string("****"));
  CHECK_EQ(maskSecret("abcd"), string("****"));
  CHECK_EQ(maskSecret("abcde"), string("****bcde"));
  CHECK_EQ(maskSecret(""), string("****"));
}

CHECK_MAIN()
