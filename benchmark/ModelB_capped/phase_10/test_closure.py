#!/usr/bin/env python3

from tinylang.evaluator import evaluate
from tinylang.environment import Environment
from tinylang.parser import parse

# Test the closure behavior
source = '''
let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let c = make_counter();
print(c());
print(c());
print(c());
'''

try:
    env = Environment()
    program = parse(source)
    result = evaluate(program, env)
    print('Evaluation completed')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()