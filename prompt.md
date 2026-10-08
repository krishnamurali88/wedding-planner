Act as a Principal AI Engineer specializing in multi-agent autonomous systems, CrewAI, and LangChain.

Write a complete, modular, and functional Python implementation for an autonomous multi-agent wedding planning platform called "AisleOrchestrator". 

### Architectural Requirements:
1. Frameworks: CrewAI (`crewai`) paired with LangChain tools (`langchain-core`, `langchain-community`, or custom BaseTool subclasses).
2. LLM Setup: Use `ChatOpenAI(model="gpt-4o")` or an equivalent model configured for structured output and tool execution.
3. Architecture Pattern: Hierarchical or sequential multi-agent orchestration managed by a Master Coordinator.
4. Robust Data Structures: Use Pydantic models for structured agent outputs and validation.

### Agents to Implement:
1. Vendor Coordinator Agent:
   - Role: Lead Vendor Negotiator & Contract Auditor.
   - Goal: Extract contract restrictions, flag conflicts against venue policies, track payment milestones, and build standardized vendor comparison sheets.
   - Backstory: Seasoned event operations director with deep knowledge of hospitality contracts, noise ordinances, and fee structures.

2. Guest Experience & RSVP Agent:
   - Role: Guest Logistics & Seating Strategist.
   - Goal: Ingest unstructured guest messages, update dietary/allergy tables, parse plus-one changes, and recommend conflict-free table arrangements.
   - Backstory: Highly empathetic hospitality concierge focused on guest accommodations, accessibility constraints, and table dynamics.

3. Day-Of Execution Agent:
   - Role: Real-Time Timeline Controller.
   - Goal: Build the master run-of-show, detect schedule delay cascades, recalculate dependent time blocks, and generate vendor broadcast alerts.
   - Backstory: Veteran stage manager and on-site director with real-time incident response skills.

### Custom Tools to Implement:
Provide full code for at least 3 custom tools using LangChain's `@tool` decorator or `BaseTool`:
1. `audit_contract_clause(contract_text: str, venue_rules: str) -> str`: Compares curfew, noise decibels, and load-in timing between contract and venue.
2. `solve_seating_arrangement(guest_data_json: str, table_capacity: int) -> str`: Allocates guests while respecting relationship tags and dietary/mobility needs.
3. `recalculate_timeline(current_timeline_json: str, delay_minutes: int, delayed_event_name: str) -> str`: Adjusts downstream events without moving fixed landmarks (e.g., hard venue curfew).

### Tasks to Define:
- Task 1: Vendor contract verification and milestone scheduling.
- Task 2: RSVP natural language processing and guest constraint cataloging.
- Task 3: Dynamic day-of contingency planning and run-of-show generation.

### Output Deliverable:
- Provide clean, commented Python code in a single executable script or clean module structure.
- Include a simulated `main()` execution block with sample wedding inputs (couple preferences, mock contract snippet, raw RSVP text, and an unexpected 40-minute caterer delay) showing the agents collaborating and printing final execution results.