#!/usr/bin/env python3

# Simple test to verify closure behavior
# This is more about understanding the logic than running

# The key insight from the brief:
# let make_counter = fn() {
#   let n = 0;
#   return fn() { n = n + 1; return n; };
# };
# let c = make_counter();
# print(c()); // Should print 1
# print(c()); // Should print 2

# The inner function (the one returned) should:
# 1. Capture the environment where it was defined (including n=0)
# 2. When called, it should be able to access and modify n
# 3. Multiple calls should share the same n value

# This means the Function class should:
# - Store the closure_env (the environment where it was defined)
# - When called, create a new environment that inherits from closure_env
# - Access to variables in closure_env should work correctly

print("Testing closure logic understanding...")
print("If a function captures an environment by reference,")
print("then multiple closures sharing that environment")
print("should be able to mutate the same variables.")