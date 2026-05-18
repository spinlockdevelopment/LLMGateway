// Test dict functionality
let d = {"a": 1, "b": 2};
print(d["a"]);          // 1
d["c"] = 3;
print(d["c"]);          // 3
print(keys(d));         // ["a", "b", "c"]
print(values(d));       // [1, 2, 3]
print(has(d, "a"), has(d, "z"));   // true false
del(d, "b");
print(d);               // {"a": 1, "c": 3}

// Test for loops
let xs = [10, 20, 30];
for (x) in xs { print(x); }                // 10 20 30
for (i, x) in xs { print(i, x); }          // 0 10 / 1 20 / 2 30
for (k, v) in d { print(k, v); }           // a 1 / c 3