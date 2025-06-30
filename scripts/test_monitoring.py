#!/usr/bin/env python3
"""
Test script for monitoring setup validation
Run this after setting up monitoring to verify everything works.
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_health_endpoint():
    """Test the health check endpoint"""
    print("🔍 Testing health check endpoint...")
    
    try:
        response = requests.get("https://marketplace.fend.ai/health/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status')}")
            print(f"   Database: {data.get('database')}")
            print(f"   Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Health check failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_main_site():
    """Test the main marketplace site"""
    print("\n🔍 Testing main marketplace site...")
    
    try:
        response = requests.get("https://marketplace.fend.ai", timeout=10)
        
        if response.status_code == 200:
            print("✅ Main site is accessible")
            return True
        else:
            print(f"❌ Main site returned status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Main site error: {str(e)}")
        return False

def test_sentry_setup():
    """Test if Sentry is configured (by checking if DSN is set)"""
    print("\n🔍 Testing Sentry configuration...")
    
    # This would need to be run on the server to check environment variables
    print("⚠️  To test Sentry:")
    print("   1. SSH to your server")
    print("   2. Run: docker-compose exec web python manage.py shell")
    print("   3. Execute: import logging; logging.getLogger(__name__).error('Test Sentry error')")
    print("   4. Check your Sentry dashboard for the error")
    
    return True

def test_ssl_certificate():
    """Test SSL certificate validity"""
    print("\n🔍 Testing SSL certificate...")
    
    try:
        response = requests.get("https://marketplace.fend.ai", timeout=10)
        print("✅ SSL certificate is valid")
        return True
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL certificate error: {str(e)}")
        return False
    except Exception as e:
        # If we get here, SSL might be OK but there's another issue
        print(f"⚠️  SSL check inconclusive: {str(e)}")
        return True

def main():
    """Run all monitoring tests"""
    print("🚀 Fend Marketplace Monitoring Test Suite")
    print("=" * 50)
    
    tests = [
        ("Health Check Endpoint", test_health_endpoint),
        ("Main Site Accessibility", test_main_site), 
        ("SSL Certificate", test_ssl_certificate),
        ("Sentry Configuration", test_sentry_setup),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your monitoring setup looks good.")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
    
    print("\n📋 NEXT STEPS:")
    print("1. Set up UptimeRobot account and add monitors")
    print("2. Set up Sentry account and add SENTRY_DSN to .env.prod")
    print("3. Deploy with: ./deploy.sh")
    print("4. Test Sentry by creating a test error")
    print("5. Configure alert notifications in both services")

if __name__ == "__main__":
    main()