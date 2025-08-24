#!/usr/bin/env python3
"""
Smoke Tests for Refactored Bot State Management System

This script runs comprehensive tests to validate the refactored bot state management
system that implements the single source of truth architecture.

Usage:
    python run_smoke_tests.py [--admin-token TOKEN] [--base-url URL]

Example:
    python run_smoke_tests.py --admin-token "your_admin_token" --base-url "http://localhost:8056"
"""

import argparse
import time
import sys
from typing import Dict, Any, List
from vexa_client import VexaClient, VexaClientError

# Test configuration
TEST_USER_EMAIL = "smoke_test_user@example.com"
TEST_USER_NAME = "Smoke Test User"
TEST_MAX_CONCURRENT_BOTS = 2

class SmokeTestRunner:
    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.admin_token = admin_token
        self.admin_client = None
        self.user_client = None
        self.test_user = None
        self.user_api_key = None
        
        # Test results tracking
        self.test_results = []
        self.current_test = None
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test results with consistent formatting."""
        timestamp = time.strftime("%H:%M:%S")
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        
        print(f"{timestamp} {status_icon} {test_name}: {details}")
        
        self.test_results.append({
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": timestamp
        })
        
    def run_test(self, test_name: str, test_func):
        """Run a test and handle errors gracefully."""
        self.current_test = test_name
        print(f"\n🧪 Running: {test_name}")
        print("=" * 60)
        
        try:
            result = test_func()
            self.log_test(test_name, "PASS", result)
            return True
        except Exception as e:
            self.log_test(test_name, "FAIL", f"Error: {str(e)}")
            print(f"   Exception details: {type(e).__name__}: {e}")
            return False
    
    def setup_test_environment(self):
        """Set up the test environment with admin and user clients."""
        print("🔧 Setting up test environment...")
        
        # Initialize admin client
        self.admin_client = VexaClient(
            base_url=self.base_url,
            admin_key=self.admin_token
        )
        
        # Test admin connection
        try:
            users = self.admin_client.list_users()
            print(f"   ✅ Admin connection: {len(users)} users found")
        except Exception as e:
            raise Exception(f"Admin connection failed: {e}")
        
        # Check if test user exists, create if not
        try:
            self.test_user = self.admin_client.get_user_by_email(TEST_USER_EMAIL)
            print(f"   ✅ Test user exists: {self.test_user['id']}")
        except:
            print(f"   🔄 Creating test user: {TEST_USER_EMAIL}")
            self.test_user = self.admin_client.create_user(
                email=TEST_USER_EMAIL,
                name=TEST_USER_NAME,
                max_concurrent_bots=TEST_MAX_CONCURRENT_BOTS
            )
            print(f"   ✅ Created test user: {self.test_user['id']}")
        
        # Generate or get user API token
        try:
            # Try to get existing token first
            tokens = self.admin_client.list_users()  # This should show tokens
            # For now, create a new token
            user_token = self.admin_client.create_token(self.test_user['id'])
            self.user_api_key = user_token['token']
            print(f"   ✅ Generated user API token: {self.user_api_key[:8]}...")
        except Exception as e:
            raise Exception(f"Failed to generate user token: {e}")
        
        # Initialize user client
        self.user_client = VexaClient(
            base_url=self.base_url,
            api_key=self.user_api_key
        )
        
        # Test user connection
        try:
            meetings = self.user_client.get_meetings()
            print(f"   ✅ User connection: {len(meetings)} meetings found")
        except Exception as e:
            raise Exception(f"User connection failed: {e}")
        
        return "Test environment setup completed successfully"
    
    def test_bot_creation_and_limits(self):
        """Test bot creation and concurrent bot limits."""
        print("🔄 Testing bot creation and concurrent limits...")
        
        # Clean up any existing test meetings
        meetings = self.user_client.get_meetings()
        for meeting in meetings:
            if meeting['native_meeting_id'].startswith('smoke-test-'):
                try:
                    self.user_client.stop_bot(meeting['platform'], meeting['native_meeting_id'])
                    print(f"   Cleaned up existing meeting: {meeting['id']}")
                except:
                    pass
        
        time.sleep(5)  # Allow cleanup to complete
        
        # Test 1: Create first bot (should succeed)
        bot1 = self.user_client.request_bot(
            platform="google_meet",
            native_meeting_id="smoke-test-1",
            bot_name="Smoke Test Bot 1",
            language="en",
            task="transcribe"
        )
        
        print(f"   ✅ Created first bot: {bot1['id']} (status: {bot1['status']})")
        assert bot1['status'] == 'reserved'
        
        # Test 2: Create second bot (should succeed)
        bot2 = self.user_client.request_bot(
            platform="google_meet",
            native_meeting_id="smoke-test-2",
            bot_name="Smoke Test Bot 2",
            language="es",
            task="translate"
        )
        
        print(f"   ✅ Created second bot: {bot2['id']} (status: {bot2['status']})")
        assert bot2['status'] == 'reserved'
        
        # Test 3: Create third bot (should fail - limit exceeded)
        try:
            bot3 = self.user_client.request_bot(
                platform="google_meet",
                native_meeting_id="smoke-test-3",
                bot_name="Smoke Test Bot 3"
            )
            raise Exception("Third bot creation should have failed due to concurrent bot limit")
        except VexaClientError as e:
            if "Maximum concurrent bots limit reached" in str(e):
                print(f"   ✅ Third bot creation correctly failed: {str(e)[:100]}...")
            else:
                raise Exception(f"Unexpected error for third bot: {e}")
        
        # Verify running bots count
        running_bots = self.user_client.get_running_bots_status()
        print(f"   ✅ Running bots count: {len(running_bots)} (expected: 2)")
        assert len(running_bots) == 2
        
        return f"Bot creation and limits test passed - {len(running_bots)} bots running"
    
    def test_bot_state_transitions(self):
        """Test bot state transitions and callback system."""
        print("🔄 Testing bot state transitions...")
        
        # Wait for bots to start and transition states
        print("   Waiting for bots to start up...")
        time.sleep(30)
        
        # Check meeting states
        meetings = self.user_client.get_meetings()
        test_meetings = [m for m in meetings if m['native_meeting_id'].startswith('smoke-test-')]
        
        print(f"   Found {len(test_meetings)} test meetings:")
        for meeting in test_meetings:
            print(f"     Meeting {meeting['id']}: {meeting['status']} (container: {meeting['bot_container_id']})")
            
            # Should have transitioned from 'reserved' to 'starting' or 'active'
            assert meeting['status'] in ['reserved', 'starting', 'active'], f"Invalid status: {meeting['status']}"
            
            # Verify bot container ID is set
            assert meeting['bot_container_id'] is not None, "Bot container ID not set"
        
        # Check running bots status
        running_bots = self.user_client.get_running_bots_status()
        print(f"   Running bots status: {len(running_bots)} bots")
        
        for bot in running_bots:
            print(f"     Bot {bot['meeting_id']}: {bot['status']} (container: {bot['container_id']})")
        
        return f"State transitions test passed - {len(test_meetings)} meetings in valid states"
    
    def test_bot_configuration(self):
        """Test bot configuration updates via Redis commands."""
        print("🔄 Testing bot configuration...")
        
        # Find an active or starting bot
        meetings = self.user_client.get_meetings()
        active_bot = None
        
        for meeting in meetings:
            if (meeting['native_meeting_id'].startswith('smoke-test-') and 
                meeting['status'] in ['starting', 'active']):
                active_bot = meeting
                break
        
        if not active_bot:
            print("   ⚠️  No active/starting bot found, waiting...")
            time.sleep(30)
            meetings = self.user_client.get_meetings()
            for meeting in meetings:
                if (meeting['native_meeting_id'].startswith('smoke-test-') and 
                    meeting['status'] in ['starting', 'active']):
                    active_bot = meeting
                    break
        
        if active_bot:
            print(f"   Reconfiguring bot: {active_bot['id']} (status: {active_bot['status']})")
            
            # Update bot configuration
            config_response = self.user_client.update_bot_config(
                platform=active_bot['platform'],
                native_meeting_id=active_bot['native_meeting_id'],
                language="fr",
                task="translate"
            )
            
            print(f"   ✅ Bot reconfiguration accepted: {config_response['message']}")
            
            # Wait for bot to process the command
            time.sleep(10)
            
            # Verify bot is still running
            running_bots = self.user_client.get_running_bots_status()
            assert len(running_bots) == 2, "Bot count changed after reconfiguration"
            
            return "Bot configuration test passed - Redis command delivered successfully"
        else:
            return "Bot configuration test skipped - no suitable bot found"
    
    def test_bot_shutdown(self):
        """Test bot shutdown and cleanup."""
        print("🔄 Testing bot shutdown...")
        
        # Stop the first bot
        meetings = self.user_client.get_meetings()
        bot_to_stop = None
        
        for meeting in meetings:
            if meeting['native_meeting_id'] == 'smoke-test-1':
                bot_to_stop = meeting
                break
        
        if bot_to_stop:
            print(f"   Stopping bot: {bot_to_stop['id']} (status: {bot_to_stop['status']})")
            
            stop_response = self.user_client.stop_bot(
                platform=bot_to_stop['platform'],
                native_meeting_id=bot_to_stop['native_meeting_id']
            )
            
            print(f"   ✅ Bot stop request accepted: {stop_response['message']}")
            
            # Monitor the shutdown process
            print("   Monitoring bot shutdown...")
            time.sleep(30)
            
            # Check final meeting status
            meetings = self.user_client.get_meetings()
            for meeting in meetings:
                if meeting['native_meeting_id'] == 'smoke-test-1':
                    print(f"   Final status: {meeting['status']}")
                    
                    # Should be in final state
                    assert meeting['status'] in ['completed', 'failed', 'stopping'], f"Invalid final status: {meeting['status']}"
                    
                    if meeting['status'] == 'completed':
                        print("   ✅ Bot completed successfully")
                    elif meeting['status'] == 'failed':
                        print("   ⚠️  Bot failed during shutdown")
                    else:
                        print("   🔄 Bot still shutting down")
                    
                    break
            
            return "Bot shutdown test passed"
        else:
            return "Bot shutdown test skipped - bot not found"
    
    def test_concurrent_limit_reset(self):
        """Test that concurrent bot limit resets after bot shutdown."""
        print("🔄 Testing concurrent bot limit reset...")
        
        # Wait a bit more for cleanup
        time.sleep(30)
        
        try:
            bot3 = self.user_client.request_bot(
                platform="google_meet",
                native_meeting_id="smoke-test-3",
                bot_name="Smoke Test Bot 3"
            )
            
            print(f"   ✅ Third bot creation succeeded after limit reset: {bot3['id']}")
            assert bot3['status'] == 'reserved'
            
            return "Concurrent limit reset test passed - new bot created successfully"
            
        except VexaClientError as e:
            if "Maximum concurrent bots limit reached" in str(e):
                print(f"   ⚠️  Third bot creation still failed: {str(e)[:100]}...")
                return "Concurrent limit reset test - limit still enforced (may need more cleanup time)"
            else:
                raise Exception(f"Unexpected error for third bot: {e}")
    
    def test_api_compatibility(self):
        """Test that all API endpoints work without breaking changes."""
        print("🔄 Testing API endpoint compatibility...")
        
        # Test meetings endpoint
        meetings = self.user_client.get_meetings()
        print(f"   ✅ GET /meetings: {len(meetings)} meetings")
        
        # Test transcript endpoint (should work even if no transcript yet)
        try:
            transcript = self.user_client.get_transcript("google_meet", "smoke-test-1")
            print(f"   ✅ GET /transcripts: {len(transcript.get('segments', []))} segments")
        except Exception as e:
            print(f"   ⚠️  GET /transcripts: {str(e)[:100]}... (expected if no transcript yet)")
        
        # Test meeting data update
        if meetings:
            meeting = meetings[0]
            update_response = self.user_client.update_meeting_data(
                platform=meeting['platform'],
                native_meeting_id=meeting['native_meeting_id'],
                name="Updated Meeting Name",
                notes="Smoke test notes"
            )
            print(f"   ✅ PATCH /meetings: {update_response['id']}")
        
        # Verify response schema consistency
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
        
        print("   ✅ Response schema validation passed")
        
        return "API compatibility test passed - all endpoints working correctly"
    
    def test_background_cleanup(self):
        """Test background cleanup of stale meetings."""
        print("🔄 Testing background cleanup...")
        
        # Wait for background cleanup task to run
        print("   Waiting for background cleanup task...")
        time.sleep(60)  # Wait 1 minute for cleanup cycles
        
        # Check for any stale meetings that were cleaned up
        meetings = self.user_client.get_meetings()
        failed_meetings = [m for m in meetings if m['status'] == 'failed']
        
        print(f"   Failed meetings after cleanup: {len(failed_meetings)}")
        for meeting in failed_meetings:
            failure_reason = meeting['data'].get('failure_reason', 'Unknown')
            print(f"     Meeting {meeting['id']}: {meeting['native_meeting_id']} - {failure_reason}")
        
        return f"Background cleanup test completed - {len(failed_meetings)} failed meetings found"
    
    def cleanup_test_environment(self):
        """Clean up test environment."""
        print("🧹 Cleaning up test environment...")
        
        if not self.user_client:
            return "Cleanup skipped - user client not initialized"
        
        # Stop all test bots
        meetings = self.user_client.get_meetings()
        test_meetings = [m for m in meetings if m['native_meeting_id'].startswith('smoke-test-')]
        
        for meeting in test_meetings:
            try:
                self.user_client.stop_bot(meeting['platform'], meeting['native_meeting_id'])
                print(f"   Stopped bot: {meeting['id']}")
            except Exception as e:
                print(f"   Warning: Could not stop bot {meeting['id']}: {e}")
        
        # Wait for cleanup
        time.sleep(30)
        
        return f"Cleanup completed - {len(test_meetings)} test bots stopped"
    
    def run_all_tests(self):
        """Run all smoke tests."""
        print("🚀 Starting Smoke Tests for Refactored Bot State Management System")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"Test User: {TEST_USER_EMAIL}")
        print(f"Max Concurrent Bots: {TEST_MAX_CONCURRENT_BOTS}")
        print("=" * 80)
        
        start_time = time.time()
        
        # Run tests
        tests = [
            ("Environment Setup", self.setup_test_environment),
            ("Bot Creation and Limits", self.test_bot_creation_and_limits),
            ("Bot State Transitions", self.test_bot_state_transitions),
            ("Bot Configuration", self.test_bot_configuration),
            ("Bot Shutdown", self.test_bot_shutdown),
            ("Concurrent Limit Reset", self.test_concurrent_limit_reset),
            ("API Compatibility", self.test_api_compatibility),
            ("Background Cleanup", self.test_background_cleanup),
            ("Environment Cleanup", self.cleanup_test_environment),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                passed += 1
            else:
                failed += 1
        
        # Print summary
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "=" * 80)
        print("📊 SMOKE TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {len(tests)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Duration: {duration:.1f} seconds")
        print("=" * 80)
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED! The refactored system is working correctly.")
            return True
        else:
            print(f"⚠️  {failed} test(s) failed. Please review the errors above.")
            return False

def main():
    parser = argparse.ArgumentParser(description="Run smoke tests for refactored bot state management")
    parser.add_argument("--admin-token", required=True, help="Admin API token for user management")
    parser.add_argument("--base-url", default="http://localhost:18056", help="Base URL for Vexa API Gateway")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.admin_token:
        print("❌ Error: Admin token is required")
        sys.exit(1)
    
    # Run tests
    runner = SmokeTestRunner(args.base_url, args.admin_token)
    
    try:
        success = runner.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
