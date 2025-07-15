# Claude LAD Workflow Design

## Practical Usage Model

**User Interaction:**
1. User: "Use LAD to implement [feature description]"
2. I read `.lad/claude_prompts/00_feature_kickoff.md` and execute setup
3. I read `.lad/claude_prompts/01_autonomous_context_planning.md` and execute Phase 1
4. **Return to user** for plan review
5. User: "Continue to validation" or "Proceed with implementation"
6. I read appropriate next prompt and continue
7. **Return to user** between each phase for review/approval

## Resumability Requirements

**Cross-Session State:**
- TodoWrite integration for task tracking
- Plan files in `docs/` track validation status
- Implementation can resume from any pending task
- Works across different machines

**Phase 2 Resumability (like Copilot step 04):**
- Check TodoWrite for current state
- Run tests to see what's passing/failing
- Resume from next pending task
- User can say "start" or "continue" and it works

## Missing Steps to Implement

### 1. Feature Kickoff (00_feature_kickoff.md)
- Setup `.flake8` and `.coveragerc` if missing
- Verify `.lad` folder structure
- Establish baseline coverage/quality metrics
- Initialize development environment

### 2. ChatGPT Review Process (01c_chatgpt_review.md)
- Take plan to ChatGPT for independent assessment
- Structured format for external review
- True multi-model validation

### 3. Integration Phase (01d_integrate_reviews.md)
- Incorporate feedback from both Claude and ChatGPT
- Reconcile conflicting suggestions
- Update implementation plan
- User decision-making on suggestions

### 4. Enhanced Implementation Resumability
- Better state checking in Phase 2
- Automatic resume from pending tasks
- Cross-session compatibility

## File Structure Rules
- **NEVER write to `.lad/` folder** - contains framework prompts
- **Always write to `docs/` folder** - working directory
- **Preserve `.lad/` integrity** - framework, not workspace