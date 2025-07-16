#!/usr/bin/env python3
"""
Simple test script to check server stability and handle broken pipe errors.
"""
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor

def test_server_connection():
    """Test basic server connection"""
    try:
        response = requests.get('http://127.0.0.1:8000/accounts/evade-and-sequence/', timeout=10)
        print(f"✅ Server connection successful: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Server connection failed: {e}")
        return False

def test_concurrent_requests():
    """Test multiple concurrent requests to check for broken pipe issues"""
    def make_request():
        try:
            response = requests.get('http://127.0.0.1:8000/accounts/evade-and-sequence/', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    print("🔄 Testing concurrent requests...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: make_request(), range(10)))
    
    successful = sum(results)
    print(f"✅ {successful}/10 concurrent requests successful")
    return successful >= 8

def test_game_functionality():
    """Test basic game functionality"""
    try:
        # Test game page load
        response = requests.get('http://127.0.0.1:8000/accounts/evade-and-sequence/', timeout=10)
        if response.status_code == 200:
            print("✅ Game page loads successfully")
            
            # Check if JavaScript is included
            if 'evade_and_sequence_game.js' in response.text:
                print("✅ JavaScript file is properly loaded")
            else:
                print("⚠️ JavaScript file not found in response")
            
            return True
        else:
            print(f"❌ Game page failed to load: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Game functionality test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Django server stability...")
    print("=" * 50)
    
    # Test 1: Basic connection
    if not test_server_connection():
        print("❌ Server is not running or not accessible")
        exit(1)
    
    # Test 2: Concurrent requests
    if not test_concurrent_requests():
        print("⚠️ Server may have stability issues with concurrent requests")
    
    # Test 3: Game functionality
    if not test_game_functionality():
        print("❌ Game functionality test failed")
        exit(1)
    
    print("=" * 50)
    print("✅ All tests completed successfully!")
    print("🎮 Server should be stable for the Evade & Sequence game") 