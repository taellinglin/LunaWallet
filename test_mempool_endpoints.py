#!/usr/bin/env python3
"""
Test script to find the correct mempool broadcast endpoint and diagnose transaction failures.
Run this to identify which API endpoint accepts transactions.
"""

import requests
import json
import sys
from datetime import datetime

# Test configuration
BASE_URL = "https://bank.linglin.art"
TIMEOUT = 10

# Test transaction (using valid Luna address format)
TEST_TRANSACTION = {
    "type": "transfer",
    "from": "LUN_C7UBynkoMnaYGUMSy8AB9MZE12VYZPyt17",
    "to": "LUN_Bv1GCRCd5G95J3CDjWasmjHKuqxL1F7Rrt",
    "amount": 1.0,
    "fee": 0.001,
    "timestamp": int(datetime.now().timestamp()),
    "memo": "Test transaction from diagnostic script",
    "hash": "test_hash_123456789",
    "signature": "test_signature"
}

# Endpoints to test
BROADCAST_ENDPOINTS = [
    "/api/transactions/broadcast",
    "/api/transactions/submit",
    "/api/mempool/add",
    "/api/mempool/broadcast",
    "/api/v1/transactions/broadcast",
    "/api/v1/mempool/add",
    "/broadcast",
    "/mempool/add",
    "/submit",
    "/transactions",
    "/mempool",
    "/api/broadcast",
    "/rpc",
]

def test_endpoint(url, endpoint, tx_data):
    """Test a single endpoint"""
    full_url = url + endpoint
    print(f"\n{'='*70}")
    print(f"Testing: {full_url}")
    print(f"{'='*70}")
    
    try:
        # Try POST with JSON
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            full_url,
            json=tx_data,
            headers=headers,
            timeout=TIMEOUT,
            verify=True
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'Not specified')}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body (first 500 chars):\n{response.text[:500]}")
        
        # Check if response is JSON
        is_json = response.headers.get('content-type', '').startswith('application/json')
        print(f"Is JSON Response: {is_json}")
        
        # Try to parse JSON
        try:
            json_response = response.json()
            print(f"JSON Parsed Successfully: {json.dumps(json_response, indent=2)[:300]}")
        except:
            print("Could not parse JSON response")
        
        # Check for success indicators
        success_indicators = ["success", "accepted", "added", "broadcasted", "hash", "txid"]
        found_indicators = []
        response_text_lower = response.text.lower()
        for indicator in success_indicators:
            if indicator in response_text_lower:
                found_indicators.append(indicator)
        
        if found_indicators:
            print(f"Found success indicators: {found_indicators}")
        
        return {
            'endpoint': endpoint,
            'status': response.status_code,
            'is_json': is_json,
            'success': response.status_code == 200 and is_json,
            'response': response.text[:200]
        }
        
    except requests.exceptions.Timeout:
        print(f"TIMEOUT after {TIMEOUT}s")
        return {'endpoint': endpoint, 'status': 'TIMEOUT', 'success': False}
    except requests.exceptions.ConnectionError as e:
        print(f"CONNECTION ERROR: {e}")
        return {'endpoint': endpoint, 'status': 'CONNECTION_ERROR', 'success': False}
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {'endpoint': endpoint, 'status': 'ERROR', 'success': False, 'error': str(e)}

def main():
    """Run all endpoint tests"""
    print("\n" + "="*70)
    print("LUNA WALLET MEMPOOL ENDPOINT DIAGNOSTIC TEST")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print(f"Testing {len(BROADCAST_ENDPOINTS)} endpoints")
    print(f"Transaction: {json.dumps(TEST_TRANSACTION, indent=2)}")
    
    results = []
    
    for endpoint in BROADCAST_ENDPOINTS:
        result = test_endpoint(BASE_URL, endpoint, TEST_TRANSACTION)
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\nSuccessful endpoints (JSON + status 200):")
    successful = [r for r in results if r.get('success')]
    if successful:
        for r in successful:
            print(f"  ✓ {r['endpoint']}")
    else:
        print("  None found")
    
    print("\nJSON endpoints (non-HTML):")
    json_endpoints = [r for r in results if r.get('is_json')]
    if json_endpoints:
        for r in json_endpoints:
            print(f"  ✓ {r['endpoint']} - Status: {r['status']}")
    else:
        print("  None found")
    
    print("\nAll tested endpoints:")
    for r in results:
        status = r.get('status', 'UNKNOWN')
        is_json = r.get('is_json', False)
        endpoint = r['endpoint']
        json_indicator = "[JSON]" if is_json else "[HTML/TEXT]"
        print(f"  {endpoint:<40} {json_indicator:<12} Status: {status}")
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    if successful:
        print(f"✓ Found working endpoint(s): {[r['endpoint'] for r in successful]}")
        print("  Update your TransactionManager network_endpoints with this path")
    else:
        json_found = [r for r in results if r.get('is_json')]
        if json_found:
            print(f"✓ Found JSON-responding endpoints: {[r['endpoint'] for r in json_found]}")
            print("  These might work if they accept transaction data")
        else:
            print("✗ No JSON endpoints found")
            print("  The API might be using a different format or location")
            print("  Check with your server administrator for the correct endpoint")
    
    print("\nTo use the discovered endpoint, update page_send.py:")
    if successful:
        endpoint = successful[0]['endpoint']
        print(f"  network_endpoints = [\"https://bank.linglin.art{endpoint}\"]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
