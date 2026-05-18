from tinylang.environment import Environment

# Test basic environment functionality
env = Environment()
env.define("x", 10)
print("x =", env.get("x"))

# Test child environment
child_env = env.child()
child_env.define("y", 20)
print("y =", child_env.get("y"))
print("x from child =", child_env.get("x"))

# Test assignment
child_env.assign("x", 15)
print("x after assignment =", child_env.get("x"))
print("x in parent =", env.get("x"))