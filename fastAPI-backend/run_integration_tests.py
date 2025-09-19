#!/usr/bin/env python3
"""
Integration test runner for the LLM Summariser Service.

This script runs integration tests that require Redis and Ollama to be running.
Make sure to start the services using docker-compose before running this script.

Usage:
    python run_integration_tests.py

Prerequisites:
    1. Start Redis and Ollama services:
       docker-compose up redis ollama ollama-init
    2. Start the API service:
       docker-compose up api
    3. Run this script:
       python run_integration_tests.py
"""

import subprocess
import sys
import time
import requests
from pathlib import Path


def check_service_health(service_name: str, url: str, max_retries: int = 30) -> bool:
    """Check if a service is healthy and responding."""
    print(f"Checking {service_name} health at {url}...")
    
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✓ {service_name} is healthy")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if i < max_retries - 1:
            print(f"  Waiting for {service_name}... ({i+1}/{max_retries})")
            time.sleep(2)
    
    print(f"✗ {service_name} is not responding after {max_retries} attempts")
    return False


def main():
    """Run the integration tests."""
    print("🚀 LLM Summariser Service - Integration Test Runner")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("tests/test_integration_concurrency.py").exists():
        print("❌ Error: test_integration_concurrency.py not found")
        print("Please run this script from the fastAPI-backend directory")
        sys.exit(1)
    
    # Check service health
    print("\n📋 Checking service health...")
    
    services_healthy = True
    
    # Check API health
    if not check_service_health("API", "http://localhost:8000/health"):
        services_healthy = False
    
    # Check Ollama health
    if not check_service_health("Ollama", "http://localhost:11434/api/tags"):
        services_healthy = False
    
    if not services_healthy:
        print("\n❌ Some services are not healthy. Please check:")
        print("   1. Start Redis and Ollama: docker-compose up redis ollama ollama-init")
        print("   2. Start the API: docker-compose up api")
        print("   3. Wait for all services to be ready")
        sys.exit(1)
    
    print("\n✅ All services are healthy!")
    
    # Run the integration tests
    print("\n🧪 Running integration tests...")
    print("-" * 40)
    
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_integration_concurrency.py",
            "-v", "-s", "--tb=short"
        ], cwd=Path.cwd())
        
        if result.returncode == 0:
            print("\n✅ All integration tests passed!")
        else:
            print("\n❌ Some integration tests failed!")
            sys.exit(result.returncode)
            
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
