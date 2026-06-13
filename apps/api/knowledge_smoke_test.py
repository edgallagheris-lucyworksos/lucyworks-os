from app.knowledge_routes import AGENTS, SOURCES

print("\n--- RUNNING KNOWLEDGE REGISTRY SMOKE TEST ---\n")

assert any(source["id"] == "hospital-sop" for source in SOURCES)
assert any(source["id"] == "business-training" for source in SOURCES)
assert any(agent["id"] == "lucy-ops-agent" for agent in AGENTS)
assert any(agent["id"] == "lucy-gov-agent" for agent in AGENTS)

print("\n--- KNOWLEDGE REGISTRY TEST PASSED ---\n")
