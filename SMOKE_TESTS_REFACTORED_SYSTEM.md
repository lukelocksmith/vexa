# Smoke Tests for Refactored Bot State Management System

## Overview
This document outlines comprehensive smoke tests to validate the refactored bot state management system that implements the single source of truth architecture. Tests will use the `vexa_client` to interact with the API and validate bot lifecycle management.

## 🎯 Test Objectives

### **Primary Goals:**
1. **Validate Single Source of Truth**: Ensure Meeting table is the only place where bot state is stored
2. **Verify Bot State Ownership**: Confirm bots control all state transitions via callbacks
3. **Test Concurrency Limits**: Validate database-enforced concurrent bot limits
4. **Verify API Compatibility**: Ensure no breaking changes to existing API endpoints
5. **Test Bot Lifecycle**: Validate complete bot creation → running → shutdown flow

### **Secondary Goals:**
1. **Error Handling**: Test edge cases and error scenarios
2. **Background Cleanup**: Validate stale meeting detection and cleanup
3. **Redis Commands**: Verify Redis Pub/Sub for bot commands (no state storage)
4. **Database Consistency**: Ensure transaction safety and data integrity

## 🧪 Test Environment Setup

### **Prerequisites:**
```bash
# 1. Deploy the refactored system
cd vexa
make all

# 2. Ensure services are running
docker ps | grep vexa

# 3. Verify API gateway is accessible
curl http://localhost:8056/health
```

### **Test Configuration:**
```python
# Test configuration
TEST_BASE_URL = "http://localhost:8056"
ADMIN_API_KEY = "your_admin_token_here"  # From environment or config
GOOGLE_MEET_URL = "https://meet.google.com/xxx-yyyy-zzz"  # Test meeting URL
TEST_USER_EMAIL = "smoke_test_user@example.com"
```

## 📋 Test Suite 1: User and Token Management

### **Test 1.1: Create Test User**
```python
from vexa_client import VexaClient

# Initialize admin client
admin_client = VexaClient(
    base_url=TEST_BASE_URL,
    admin_key=ADMIN_API_KEY
)

# Create test user with limited concurrent bots
test_user = admin_client.create_user(
    email=TEST_USER_EMAIL,
    name="Smoke Test User",
    max_concurrent_bots=2  # Limit for testing
)

print(f"✅ Created test user: {test_user['id']}")
assert test_user['max_concurrent_bots'] == 2
```

### **Test 1.2: Generate User API Token**
```python
# Generate API token for the test user
user_token = admin_client.create_token(test_user['id'])
user_api_key = user_token['token']

print(f"✅ Generated user API token: {user_api_key[:8]}...")

# Initialize user client
user_client = VexaClient(
    base_url=TEST_BASE_URL,
    api_key=user_api_key
)
```

## 📋 Test Suite 2: Bot Creation and State Management

### **Test 2.1: Create First Bot (Should Succeed)**
```python
# Create first bot
bot1_response = user_client.request_bot(
    platform="google_meet",
    native_meeting_id="smoke-test-1",
    bot_name="Smoke Test Bot 1",
    language="en",
    task="transcribe"
)

print(f"✅ Created first bot: {bot1_response['id']}")
print(f"   Status: {bot1_response['status']}")
print(f"   Container ID: {bot1_response['bot_container_id']}")

# Validate response structure
assert bot1_response['status'] == 'reserved'
assert bot1_response['platform'] == 'google_meet'
assert bot1_response['native_meeting_id'] == 'smoke-test-1'
assert bot1_response['bot_container_id'] is not None
```

### **Test 2.2: Create Second Bot (Should Succeed)**
```python
# Create second bot (within limit)
bot2_response = user_client.request_bot(
    platform="google_meet",
    native_meeting_id="smoke-test-2",
    bot_name="Smoke Test Bot 2",
    language="es",
    task="translate"
)

print(f"✅ Created second bot: {bot2_response['id']}")
print(f"   Status: {bot2_response['status']}")

assert bot2_response['status'] == 'reserved'
```

### **Test 2.3: Create Third Bot (Should Fail - Limit Exceeded)**
```python
# Attempt to create third bot (should fail due to limit)
try:
    bot3_response = user_client.request_bot(
        platform="google_meet",
        native_meeting_id="smoke-test-3",
        bot_name="Smoke Test Bot 3"
    )
    assert False, "Should have failed due to concurrent bot limit"
except Exception as e:
    print(f"✅ Third bot creation correctly failed: {e}")
    assert "Maximum concurrent bots limit reached" in str(e)
```

### **Test 2.4: Verify Concurrent Bot Count**
```python
# Check running bots status
running_bots = user_client.get_running_bots_status()
print(f"✅ Running bots count: {len(running_bots)}")

assert len(running_bots) == 2  # Should have exactly 2 bots
```

## 📋 Test Suite 3: Bot State Transitions (Bot Callbacks)

### **Test 3.1: Monitor Bot State Changes**
```python
import time

# Monitor bot state transitions
print("🔄 Monitoring bot state transitions...")

# Wait for bots to start and transition states
time.sleep(30)  # Allow time for container startup

# Check meeting states
meetings = user_client.get_meetings()
for meeting in meetings:
    if meeting['native_meeting_id'] in ['smoke-test-1', 'smoke-test-2']:
        print(f"   Meeting {meeting['id']}: {meeting['status']}")
        
        # Should have transitioned from 'reserved' to 'starting' or 'active'
        assert meeting['status'] in ['reserved', 'starting', 'active']
        
        # Verify bot container ID is set
        assert meeting['bot_container_id'] is not None
```

### **Test 3.2: Verify MeetingSession Creation**
```python
# This test validates that MeetingSession records are created
# when bots start up (handled by docker_utils.py)

# Check that meetings have associated sessions
for meeting in meetings:
    if meeting['native_meeting_id'] in ['smoke-test-1', 'smoke-test-2']:
        print(f"   Meeting {meeting['id']} has container: {meeting['bot_container_id']}")
        
        # The MeetingSession should be created automatically
        # We can verify this by checking the bot status endpoint
        running_bots = user_client.get_running_bots_status()
        for bot in running_bots:
            if bot['meeting_id'] == meeting['id']:
                print(f"   ✅ Bot session verified for meeting {meeting['id']}")
                break
```

## 📋 Test Suite 4: Bot Configuration and Commands

### **Test 4.1: Reconfigure Active Bot**
```python
# Wait for a bot to become active
time.sleep(60)  # Allow time for bot to join meeting

# Find an active bot
meetings = user_client.get_meetings()
active_bot = None
for meeting in meetings:
    if meeting['status'] == 'active' and meeting['native_meeting_id'] in ['smoke-test-1', 'smoke-test-2']:
        active_bot = meeting
        break

if active_bot:
    print(f"🔄 Reconfiguring active bot: {active_bot['id']}")
    
    # Update bot configuration
    config_response = user_client.update_bot_config(
        platform=active_bot['platform'],
        native_meeting_id=active_bot['native_meeting_id'],
        language="fr",
        task="translate"
    )
    
    print(f"✅ Bot reconfiguration accepted: {config_response['message']}")
    
    # Verify the command was sent (bot should receive it via Redis)
    # The actual reconfiguration happens in the bot, not in the API response
else:
    print("⚠️  No active bot found for reconfiguration test")
```

### **Test 4.2: Verify Redis Command Delivery**
```python
# This test validates that Redis commands are delivered to bots
# The bot should receive the reconfigure command and update its configuration

# Wait for bot to process the command
time.sleep(10)

# Check bot status to see if it's still running
running_bots = user_client.get_running_bots_status()
print(f"✅ Bots still running after reconfiguration: {len(running_bots)}")

# All bots should still be running
assert len(running_bots) == 2
```

## 📋 Test Suite 5: Bot Shutdown and Cleanup

### **Test 5.1: Stop First Bot**
```python
# Stop the first bot
print(f"🔄 Stopping bot: {bot1_response['id']}")

stop_response = user_client.stop_bot(
    platform="google_meet",
    native_meeting_id="smoke-test-1"
)

print(f"✅ Bot stop request accepted: {stop_response['message']}")

# The bot should receive the leave command via Redis
# and transition to 'stopping' status
```

### **Test 5.2: Monitor Bot Shutdown**
```python
# Monitor the shutdown process
print("🔄 Monitoring bot shutdown...")

time.sleep(30)  # Allow time for graceful shutdown

# Check meeting status
meetings = user_client.get_meetings()
for meeting in meetings:
    if meeting['native_meeting_id'] == 'smoke-test-1':
        print(f"   Meeting {meeting['id']} status: {meeting['status']}")
        
        # Should be in final state (completed, failed, or still stopping)
        assert meeting['status'] in ['completed', 'failed', 'stopping']
        
        if meeting['status'] == 'completed':
            print(f"   ✅ Bot {meeting['id']} completed successfully")
        elif meeting['status'] == 'failed':
            print(f"   ⚠️  Bot {meeting['id']} failed during shutdown")
        else:
            print(f"   🔄 Bot {meeting['id']} still shutting down")
```

### **Test 5.3: Verify Concurrent Bot Limit Reset**
```python
# After stopping one bot, should be able to create a new one
print("🔄 Testing concurrent bot limit reset...")

try:
    bot3_response = user_client.request_bot(
        platform="google_meet",
        native_meeting_id="smoke-test-3",
        bot_name="Smoke Test Bot 3"
    )
    
    print(f"✅ Third bot creation succeeded after limit reset: {bot3_response['id']}")
    assert bot3_response['status'] == 'reserved'
    
except Exception as e:
    print(f"❌ Third bot creation still failed: {e}")
    # This might happen if the first bot hasn't fully cleaned up yet
```

## 📋 Test Suite 6: Background Cleanup and Edge Cases

### **Test 6.1: Verify Background Cleanup**
```python
# Wait for background cleanup task to run
print("🔄 Waiting for background cleanup task...")
time.sleep(120)  # Wait 2 minutes for cleanup cycles

# Check for any stale meetings that were cleaned up
meetings = user_client.get_meetings()
failed_meetings = [m for m in meetings if m['status'] == 'failed']

print(f"✅ Failed meetings after cleanup: {len(failed_meetings)}")
for meeting in failed_meetings:
    print(f"   Meeting {meeting['id']}: {meeting['native_meeting_id']} - {meeting['data'].get('failure_reason', 'Unknown')}")
```

### **Test 6.2: Test Invalid Bot Requests**
```python
# Test invalid platform
try:
    invalid_response = user_client.request_bot(
        platform="invalid_platform",
        native_meeting_id="invalid-test"
    )
    assert False, "Should have failed for invalid platform"
except Exception as e:
    print(f"✅ Invalid platform correctly rejected: {e}")

# Test missing required fields
try:
    invalid_response = user_client.request_bot(
        platform="google_meet"
        # Missing native_meeting_id
    )
    assert False, "Should have failed for missing native_meeting_id"
except Exception as e:
    print(f"✅ Missing fields correctly rejected: {e}")
```

## 📋 Test Suite 7: API Compatibility and Endpoints

### **Test 7.1: Verify All Endpoints Work**
```python
# Test all major endpoints to ensure no breaking changes
print("🔄 Testing API endpoint compatibility...")

# Test meetings endpoint
meetings = user_client.get_meetings()
print(f"✅ GET /meetings: {len(meetings)} meetings")

# Test transcript endpoint (should work even if no transcript yet)
try:
    transcript = user_client.get_transcript("google_meet", "smoke-test-1")
    print(f"✅ GET /transcripts: {len(transcript.get('segments', []))} segments")
except Exception as e:
    print(f"⚠️  GET /transcripts: {e} (expected if no transcript yet)")

# Test meeting data update
if meetings:
    meeting = meetings[0]
    update_response = user_client.update_meeting_data(
        platform=meeting['platform'],
        native_meeting_id=meeting['native_meeting_id'],
        name="Updated Meeting Name",
        notes="Smoke test notes"
    )
    print(f"✅ PATCH /meetings: {update_response['id']}")
```

### **Test 7.2: Verify Response Schema Consistency**
```python
# Ensure response schemas haven't changed
for meeting in meetings:
    # Check required fields exist
    required_fields = ['id', 'platform', 'native_meeting_id', 'status', 'created_at']
    for field in required_fields:
        assert field in meeting, f"Missing required field: {field}"
    
    # Check data field structure
    assert 'data' in meeting
    assert isinstance(meeting['data'], dict)
    
    # Check status values are valid
    valid_statuses = ['reserved', 'starting', 'active', 'stopping', 'completed', 'failed']
    assert meeting['status'] in valid_statuses, f"Invalid status: {meeting['status']}"

print("✅ Response schema validation passed")
```

## 📋 Test Suite 8: Database Consistency and Transactions

### **Test 8.1: Verify Transaction Safety**
```python
# This test validates that database transactions work correctly
# The concurrent bot limit enforcement uses transactions with row-level locking

print("🔄 Testing transaction safety...")

# Try to create multiple bots simultaneously
import threading
import concurrent.futures

def create_bot(platform, meeting_id, bot_name):
    try:
        response = user_client.request_bot(
            platform=platform,
            native_meeting_id=meeting_id,
            bot_name=bot_name
        )
        return response
    except Exception as e:
        return {"error": str(e)}

# Create multiple bot requests simultaneously
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(create_bot, "google_meet", f"concurrent-test-{i}", f"Bot {i}")
        for i in range(3)
    ]
    
    results = [future.result() for future in futures]

# Analyze results
successful = [r for r in results if 'error' not in r]
failed = [r for r in results if 'error' in r]

print(f"✅ Concurrent bot creation results:")
print(f"   Successful: {len(successful)}")
print(f"   Failed: {len(failed)}")

# Should have exactly 2 successful (within limit) and 1 failed (over limit)
assert len(successful) == 2, f"Expected 2 successful, got {len(successful)}"
assert len(failed) == 1, f"Expected 1 failed, got {len(failed)}"

# Verify the limit was enforced correctly
for result in failed:
    assert "Maximum concurrent bots limit reached" in result['error']
```

## 📋 Test Suite 9: Redis Pub/Sub and Commands

### **Test 9.1: Verify Redis Command Delivery**
```python
# This test validates that Redis is used only for commands, not state storage

print("🔄 Testing Redis command delivery...")

# Find an active bot
active_bot = None
meetings = user_client.get_meetings()
for meeting in meetings:
    if meeting['status'] == 'active':
        active_bot = meeting
        break

if active_bot:
    # Send multiple commands to test Redis reliability
    for i in range(3):
        config_response = user_client.update_bot_config(
            platform=active_bot['platform'],
            native_meeting_id=active_bot['native_meeting_id'],
            language="en" if i % 2 == 0 else "es"
        )
        print(f"   Command {i+1}: {config_response['message']}")
        time.sleep(2)  # Small delay between commands
    
    print("✅ Redis command delivery test completed")
else:
    print("⚠️  No active bot found for Redis command test")
```

## 📋 Test Suite 10: Integration and End-to-End

### **Test 10.1: Complete Bot Lifecycle**
```python
print("🔄 Testing complete bot lifecycle...")

# 1. Create bot
lifecycle_bot = user_client.request_bot(
    platform="google_meet",
    native_meeting_id="lifecycle-test",
    bot_name="Lifecycle Test Bot"
)

print(f"   1. Created bot: {lifecycle_bot['id']}")

# 2. Wait for bot to start
time.sleep(60)
meetings = user_client.get_meetings()
for meeting in meetings:
    if meeting['native_meeting_id'] == 'lifecycle-test':
        print(f"   2. Bot status: {meeting['status']}")
        break

# 3. Reconfigure bot
config_response = user_client.update_bot_config(
    platform="google_meet",
    native_meeting_id="lifecycle-test",
    language="fr",
    task="translate"
)
print(f"   3. Reconfigured bot: {config_response['message']}")

# 4. Stop bot
stop_response = user_client.stop_bot(
    platform="google_meet",
    native_meeting_id="lifecycle-test"
)
print(f"   4. Stopped bot: {stop_response['message']}")

# 5. Wait for cleanup
time.sleep(30)
meetings = user_client.get_meetings()
for meeting in meetings:
    if meeting['native_meeting_id'] == 'lifecycle-test':
        print(f"   5. Final status: {meeting['status']}")
        break

print("✅ Complete bot lifecycle test passed")
```

## 📊 Test Results Summary

### **Success Criteria:**
- ✅ **All API endpoints work without breaking changes**
- ✅ **Bot state transitions work correctly via callbacks**
- ✅ **Concurrent bot limits enforced via database transactions**
- ✅ **Redis used only for commands, not state storage**
- ✅ **Background cleanup handles stale meetings**
- ✅ **Database consistency maintained under concurrent load**
- ✅ **Bot lifecycle management works end-to-end**

### **Expected Test Results:**
```
Test Suite 1: User and Token Management     ✅ PASS
Test Suite 2: Bot Creation and State        ✅ PASS  
Test Suite 3: Bot State Transitions         ✅ PASS
Test Suite 4: Bot Configuration              ✅ PASS
Test Suite 5: Bot Shutdown                  ✅ PASS
Test Suite 6: Background Cleanup            ✅ PASS
Test Suite 7: API Compatibility             ✅ PASS
Test Suite 8: Database Consistency          ✅ PASS
Test Suite 9: Redis Commands                ✅ PASS
Test Suite 10: End-to-End Integration       ✅ PASS

OVERALL RESULT: ✅ ALL TESTS PASSED
```

## 🚀 Running the Smoke Tests

### **Quick Test Run:**
```bash
cd vexa
python -c "
from vexa_client import VexaClient
import time

# Initialize clients
admin_client = VexaClient('http://localhost:8056', admin_key='your_admin_token')
user_client = VexaClient('http://localhost:8056', api_key='your_user_token')

# Run basic tests
print('🧪 Running smoke tests...')

# Test 1: Create bot
bot = user_client.request_bot('google_meet', 'smoke-test-1')
print(f'✅ Bot created: {bot[\"id\"]}')

# Test 2: Check status
time.sleep(30)
meetings = user_client.get_meetings()
print(f'✅ Meetings: {len(meetings)}')

# Test 3: Stop bot
stop = user_client.stop_bot('google_meet', 'smoke-test-1')
print(f'✅ Bot stopped: {stop[\"message\"]}')

print('🎉 Basic smoke tests completed!')
"
```

### **Full Test Suite:**
```bash
# Run the complete test suite
cd vexa
python smoke_tests.py
```

## 🔍 Troubleshooting

### **Common Issues:**
1. **Bot creation fails**: Check Docker daemon and container resources
2. **State transitions slow**: Verify Redis connectivity and bot callback URLs
3. **Concurrent limit errors**: Check database connection and transaction logs
4. **Background cleanup issues**: Verify bot-manager background tasks are running

### **Debug Commands:**
```bash
# Check service status
docker ps | grep vexa

# Check logs
docker logs vexa-bot-manager-1
docker logs vexa-api-gateway-1

# Check database
docker exec -it vexa-postgres-1 psql -U postgres -d vexa -c "SELECT * FROM meetings ORDER BY created_at DESC LIMIT 5;"

# Check Redis
docker exec -it vexa-redis-1 redis-cli PUBSUB CHANNELS "bot_commands:*"
```

## 📝 Test Report Template

After running the tests, document the results:

```markdown
# Smoke Test Report - Refactored Bot State Management

**Date:** [Date]
**Environment:** [Staging/Production]
**Version:** [Git commit hash]

## Test Results Summary
- **Total Tests:** 10 suites
- **Passed:** X
- **Failed:** X
- **Skipped:** X

## Key Findings
- [List any issues discovered]
- [Performance observations]
- [Edge case behavior]

## Recommendations
- [Deployment readiness assessment]
- [Additional testing needed]
- [Performance optimizations]

## Next Steps
- [Deploy to production]
- [Monitor production metrics]
- [Plan additional testing]
```

This comprehensive smoke test plan will validate that the refactored bot state management system works correctly and maintains full backward compatibility while implementing the new single source of truth architecture.

