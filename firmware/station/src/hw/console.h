// Line-based serial console. Handlers run on the task that calls consolePoll().
#pragma once
#include <functional>
#include <string>

#include "../core/policy.h"

void consoleRegister(const char* name, std::function<void(const Command&)> fn);
void consolePoll();  // non-blocking: reads available bytes, dispatches complete lines
// The raw text of the line now being dispatched (CR/LF stripped, nothing trimmed). Only valid
// inside a handler. Lets a handler take "the rest of the line" verbatim (e.g. `set pass`).
const std::string& consoleRawLine();
