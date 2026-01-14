#!/usr/bin/env python3
"""
Enhanced test to find which JSON endpoint actually accepts transaction broadcasts.
Tests only the JSON-responding endpoints discovered.
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://bank.linglin.art"
TIMEOUT = 10

# Test transaction with valid Luna addresses
TEST_TRANSACTION = {
    "type": "transfer",
    "from": "LUN_C7UBynkoMnaYGUMSy8AB9MZE12VYZPyt17",
    "to": "LUN_Bv1GCRCd5G95J3CDjWasmjHKuqxL1F7Rrt",
    "amount": 1.0,
    "fee": 0.001,
    "timestamp": int(datetime.now().timestamp()),
    "memo": "Test broadcast",
    "hash": "abc123def456",
    "signature": "sig123"
}

# JSON endpoints from previous scan
JSON_ENDPOINTS = [
    '/api/transactions/broadcast',
    '/api/transactions/submit',
    '/api/mempool/add',
    '/api/mempool/broadcast',
    '/api/v1/transactions/broadcast',
    '/api/v1/mempool/add',
    '/mempool/add',
    '/api/broadcast',
]

def test_json_endpoint(url, endpoint, tx_data):
    """Test a JSON endpoint for actual transaction acceptance"""
    full_url = url + endpoint
    print(f"\n{'='*70}")
    print(f"Testing JSON endpoint: {full_url}")
    print(f"{'='*70}")
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            full_url,
            json=tx_data,
            headers=headers,
            timeout=TIMEOUT,
            verify=True
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Body:")
        try:
            json_resp = response.json()
            print(json.dumps(json_resp, indent=2))
            response_data = json_resp
        except:
            print(f"{response.text[:1000]}")
            response_data = response.text
        
        # Analyze response
        success = False
        reason = ""
        
        if isinstance(response_data, dict):
            # Check for success indicators
            if response_data.get('success') or response_data.get('accepted'):
                success = True
                reason = "success/accepted flag"
            elif response_data.get('hash') or response_data.get('txid'):
                success = True
                reason = "transaction hash returned"
            elif 'error' in response_data or 'message' in response_data:
                reason = f"Error: {response_data.get('error', response_data.get('message'))}"
            elif response.status_code == 200:
                success = True
                reason = "Status 200 + JSON response"
        
        result = {
            'endpoint': endpoint,
            'url': full_url,
            'status': response.status_code,
            'success': success,
            'reason': reason,
            'response_type': 'JSON' if isinstance(response_data, dict) else 'TEXT'
        }
        
        return result
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'endpoint': endpoint,
            'url': full_url,
            'status': 'ERROR',
            'success': False,
            'reason': str(e),
            'response_type': 'NONE'
        }

def main():
    """Test all JSON endpoints"""
    print("\n" + "="*70)
    print("LUNA WALLET - JSON ENDPOINT BROADCAST TEST")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print(f"Testing {len(JSON_ENDPOINTS)} JSON-responding endpoints")
    print(f"\nTest Transaction:")
    print(json.dumps(TEST_TRANSACTION, indent=2))
    
    results = []
    for endpoint in JSON_ENDPOINTS:
        result = test_json_endpoint(BASE_URL, endpoint, TEST_TRANSACTION)
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    working = [r for r in results if r['success']]
    errors = [r for r in results if r['status'] == 'ERROR']
    responses = [r for r in results if r['status'] not in [200, 'ERROR']]
    
    print(f"\nWorking endpoints (accepted request): {len(working)}")
    for r in working:
        print(f"  ✓ {r['endpoint']}")
        print(f"    Reason: {r['reason']}")
        print(f"    Full URL: {r['url']}")
    
    print(f"\nEndpoints with responses:")
    for r in results:
        if r['status'] != 'ERROR':
            status_indicator = "✓" if r['success'] else "✗"
            print(f"  {status_indicator} {r['endpoint']:<40} Status: {r['status']:<5} Type: {r['response_type']}")
    
    print(f"\nEndpoints with errors: {len(errors)}")
    for r in errors:
        print(f"  ✗ {r['endpoint']}")
        print(f"    Error: {r['reason']}")
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    if working:
        print(f"\n✓ SUCCESS! Found working endpoint(s):")
        for r in working:
            print(f"  {r['endpoint']}")
        
        best = working[0]
        print(f"\nUse this endpoint in page_send.py:")
        print(f"  network_endpoints = [\"{best['url']}\" ]")
        
        print(f"\nOR shorter:")
        print(f"  network_endpoints = [\"{BASE_URL}{best['endpoint']}\"]")
    else:
        print(f"\n✗ No endpoints accepted the transaction")
        print(f"  Possible reasons:")
        print(f"  1. Transaction format is incorrect")
        print(f"  2. Server is rejecting all test transactions")
        print(f"  3. Additional authentication required")
        print(f"\n  Check with server administrator for correct endpoint and format")
    
    # Detail report
    print("\n" + "="*70)
    print("DETAILED RESULTS")
    print("="*70)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['endpoint']}")
        print(f"   URL: {r['url']}")
        print(f"   Status: {r['status']}")
        print(f"   Success: {r['success']}")
        print(f"   Response: {r['response_type']}")
        if r['reason']:
            print(f"   Details: {r['reason']}")

if __name__ == "__main__":
    try:
        main()
        print("\n" + "="*70)
        print("Test completed")
        print("="*70 + "\n")
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
