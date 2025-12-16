#!/usr/bin/env python3
"""Quick test to check Account ID requirement"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)
print(f"Loading .env from: {env_path}")

async def test():
    from app.services.zoom_api import ZoomAPIService
    service = ZoomAPIService()
    print(f"Client ID: {os.getenv('ZOOM_CLIENT_ID', 'NOT SET')[:20]}...")
    print(f"Client Secret: {'SET' if os.getenv('ZOOM_CLIENT_SECRET') else 'NOT SET'}")
    print(f"Account ID: {os.getenv('ZOOM_ACCOUNT_ID', 'NOT SET')}")
    
    if not os.getenv('ZOOM_ACCOUNT_ID'):
        print("\n⚠ Account ID is required for Server-to-Server OAuth.")
        print("For User-managed apps, you may need to:")
        print("1. Check Zoom Account Settings -> Account Profile")
        print("2. Or use a different OAuth flow (user authorization)")
        return
    
    try:
        token = await service.get_access_token()
        print(f"\n✓ Success! Token: {token[:20]}...")
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())

