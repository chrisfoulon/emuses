# Atomic Transaction Framework Architecture

## Current Task: 0A-Ext.2.a - Implement atomic transaction framework

### Requirements Analysis
From context and session handover:
- **Atomic Safety**: Registry operations must be transaction-safe
- **Multi-step Operations**: Model installation, deduplication, registry updates
- **Rollback Capability**: Restore registry state on operation failures
- **Concurrent Safety**: Handle multiple concurrent operations

### Current LocalModelRegistry Analysis
- Registry operations span multiple steps: file operations + index updates
- Current weakness: No transaction safety between file operations and index updates
- Failure points: Partial file copies, index corruption, concurrent access issues

### Design Approach

#### Transaction Framework Components
```python
class RegistryTransaction:
    transaction_id: UUID
    operations: List[RegistryOperation]
    rollback_data: Dict[str, Any]
    state: TransactionState  # PENDING, COMMITTED, ROLLED_BACK

class RegistryOperation:
    operation_type: str  # "create_file", "update_index", "delete_file"
    target_path: Path
    rollback_info: Dict[str, Any]

class LocalModelRegistry:
    def begin_transaction() -> RegistryTransaction
    def commit_transaction(transaction: RegistryTransaction) -> bool
    def rollback_transaction(transaction: RegistryTransaction) -> bool
```

#### Integration Strategy
- Extend existing `install_model()` method with transaction support
- Maintain backward compatibility with non-transactional calls
- Add transaction parameter: `install_model(..., transaction=None)`
- If transaction provided, defer commits until transaction.commit()

### Implementation Plan
1. **Create Transaction Classes**: RegistryTransaction, RegistryOperation
2. **Add Transaction Methods**: begin_transaction, commit_transaction, rollback_transaction
3. **Enhance install_model()**: Add optional transaction parameter
4. **Implement Rollback Logic**: File cleanup, index restoration
5. **Add Concurrent Safety**: File locking, atomic index updates

### Testing Strategy
- Test successful transaction commits
- Test rollback on various failure scenarios
- Test concurrent transaction safety
- Test backward compatibility (non-transactional calls)