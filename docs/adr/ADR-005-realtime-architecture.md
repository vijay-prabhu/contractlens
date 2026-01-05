# ADR-005: Real-time Update Architecture

## Status
Proposed

## Date
2026-01-04

## Context

ContractLens currently uses HTTP polling to update the UI during document processing. This approach has several limitations:

### Current Implementation
- Frontend polls `/api/v1/documents/{id}` every 1.5 seconds during processing
- Document processing involves multiple stages: upload → extracting → analyzing → completed
- Analysis phase processes 50-100 clauses sequentially via OpenAI API (~2-3 minutes)
- No granular progress indication ("Analyzing clause 15/69")

### Problems with Polling
1. **Inefficient**: ~40 requests/minute during processing, most return unchanged data
2. **Delayed updates**: Up to 1.5s latency between actual state change and UI update
3. **No granular progress**: Cannot show clause-by-clause progress without constant polling
4. **Scalability**: More users = more polling requests = higher server load
5. **Poor UX**: Progress bar jumps between stages rather than smooth progression

### Requirements
- Real-time status updates (< 100ms latency)
- Granular progress during analysis phase
- Scalable to 100+ concurrent users
- Minimal infrastructure changes
- Works with existing Supabase + FastAPI stack

## Decision

Implement a **hybrid approach** using:
1. **Supabase Realtime** for document status changes (CDC-based)
2. **Server-Sent Events (SSE)** for granular analysis progress

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
├─────────────────────────────────────────────────────────────────┤
│  useDocumentRealtime()     │    useProgressStream()             │
│  - Subscribes to doc       │    - SSE connection during         │
│    status changes          │      analysis phase                │
│  - PostgreSQL CDC          │    - Clause-level progress         │
└──────────────┬─────────────┴──────────────┬────────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│    Supabase Realtime     │   │      FastAPI SSE Endpoint        │
│    (PostgreSQL CDC)      │   │      /documents/{id}/progress    │
├──────────────────────────┤   ├──────────────────────────────────┤
│  - Listens to WAL        │   │  - Streams progress events       │
│  - Broadcasts on UPDATE  │   │  - In-memory or Redis store      │
│  - Built-in reconnection │   │  - Auto-closes on completion     │
└──────────────┬───────────┘   └──────────────┬───────────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL (Supabase)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  documents  │  │   clauses   │  │  document_versions      │  │
│  │  - status   │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Why Supabase Realtime for Status Changes

Supabase Realtime uses PostgreSQL's Write-Ahead Log (WAL) for Change Data Capture:

```sql
-- Automatic: When backend updates document status
UPDATE documents SET status = 'analyzing' WHERE id = '...';

-- Supabase broadcasts to all subscribers
-- Frontend receives instantly via WebSocket
```

**Benefits:**
- Zero backend code changes for status updates
- Automatic reconnection handling
- Works with existing auth
- Already paying for Supabase

### Why SSE for Granular Progress

Server-Sent Events are ideal for unidirectional progress updates:

```python
# Backend emits progress during processing
@router.get("/documents/{id}/progress")
async def stream_progress(id: str):
    async def generate():
        while processing:
            progress = get_progress(id)  # From Redis/memory
            yield f"data: {json.dumps(progress)}\n\n"
            await asyncio.sleep(0.3)
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Benefits over WebSocket:**
- Simpler implementation (no bidirectional protocol)
- Automatic reconnection in browsers
- Works through HTTP/1.1 proxies
- Lower overhead for one-way updates

## Alternatives Considered

### Option 1: Pure Polling (Current)
**Pros:** Simple, no infrastructure changes
**Cons:** Inefficient, delayed, not scalable
**Verdict:** ❌ Not suitable for production

### Option 2: Full WebSocket Implementation
```
Frontend ←──WebSocket──→ FastAPI ←──Redis Pub/Sub──→ Workers
```
**Pros:** Bidirectional, full control
**Cons:** Complex connection management, need Redis, more code
**Verdict:** ❌ Over-engineered for our needs

### Option 3: Supabase Realtime Only
**Pros:** Simplest, zero backend changes
**Cons:** Can't easily send granular progress (not in DB)
**Verdict:** ⚠️ Good for status, but need SSE for progress

### Option 4: Supabase Realtime + SSE (Selected)
**Pros:** Best of both worlds, minimal infrastructure
**Cons:** Two subscription mechanisms to manage
**Verdict:** ✅ Right balance of simplicity and capability

### Option 5: GraphQL Subscriptions
**Pros:** Type-safe, single protocol
**Cons:** Major refactor, new stack to learn
**Verdict:** ❌ Too much change for this benefit

## Implementation Plan

### Phase 1: Supabase Realtime (Low Risk)
1. Enable Realtime on `documents` table in Supabase dashboard
2. Create `useDocumentRealtime` React hook
3. Replace polling with subscription in document detail page
4. Keep polling as fallback for connection issues

### Phase 2: SSE Progress Endpoint (Medium Risk)
1. Add progress tracking to document processor
2. Create in-memory progress store (upgrade to Redis later)
3. Implement SSE endpoint with proper cleanup
4. Create `useProgressStream` React hook

### Phase 3: UI Enhancement (Low Risk)
1. Show "Analyzing clause X of Y" during analysis
2. Smooth progress bar animation
3. Stage transition animations

### Phase 4: Production Hardening
1. Add Redis for progress store (multi-instance support)
2. Implement connection retry logic
3. Add monitoring/metrics for real-time connections
4. Load testing with concurrent users

## Consequences

### Positive
- **Instant updates**: < 100ms latency vs 1.5s polling
- **Better UX**: Granular progress, smooth animations
- **Efficient**: ~95% reduction in HTTP requests during processing
- **Scalable**: Event-driven scales better than polling
- **Maintainable**: Clear separation of concerns

### Negative
- **Complexity**: Two subscription mechanisms instead of simple polling
- **Debugging**: Harder to debug real-time connections than request/response
- **State management**: Need to handle reconnection and state sync

### Risks
1. **Supabase Realtime limits**: Free tier has connection limits
   - Mitigation: Upgrade plan or implement connection pooling

2. **SSE connection limits**: Browsers limit concurrent SSE connections
   - Mitigation: Close connection when not on processing page

3. **Progress store memory**: In-memory store lost on restart
   - Mitigation: Use Redis in production, TTL on entries

## Migration Strategy

### Backward Compatibility
- Keep polling code during transition (feature flag)
- Graceful degradation if WebSocket fails
- No database schema changes required

### Rollout Plan
1. Deploy Supabase Realtime (server-side only)
2. Enable for 10% of users via feature flag
3. Monitor error rates and latency
4. Gradually increase to 100%
5. Remove polling code after 2 weeks stable

## Metrics to Track

| Metric | Current | Target |
|--------|---------|--------|
| Status update latency | 1500ms | < 100ms |
| Requests during processing | ~40/min | ~2/min |
| User-perceived progress | 4 stages | Clause-level |
| Server load (processing) | High | Low |

## References

- [Supabase Realtime Documentation](https://supabase.com/docs/guides/realtime)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
- [Server-Sent Events MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [Event-Driven Architecture Patterns](https://martinfowler.com/articles/201701-event-driven.html)

## Decision Outcome

**Decision**: Implement Option 4 (Supabase Realtime + SSE)

**Rationale**: This approach provides the best balance of:
- Minimal infrastructure changes (leverages existing Supabase)
- Real-time capability for both status and progress
- Clear upgrade path to full WebSocket if needed
- Reasonable implementation complexity

**Next Steps**:
1. Create implementation tickets for each phase
2. Set up monitoring for real-time connections
3. Document fallback behavior for offline scenarios
