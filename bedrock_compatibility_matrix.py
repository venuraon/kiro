#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bedrock Model Compatibility Matrix Generator

Discovers all available Bedrock models from bedrock-runtime and bedrock-mantle,
tests their compatibility across inference profiles and API endpoints,
and generates a CSV compatibility matrix.
"""

import boto3
import json
import csv
import sys
import argparse
from typing import Dict, List, Tuple
from botocore.exceptions import ClientError
from openai import OpenAI
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Constants
REGION = 'us-east-1'
TEST_PROMPT = "Hi"
TIMEOUT = 30

class AWSBedrockMantleAuth(httpx.Auth):
    """Custom authentication for bedrock-mantle using AWS SigV4"""
    def __init__(self, service: str, region: str, credentials):
        self.service = service
        self.region = region
        self.credentials = credentials

    def auth_flow(self, request: httpx.Request):
        headers_to_sign = {
            'host': request.url.host,
            'x-amz-date': None,
        }
        
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers_to_sign
        )
        
        signer = SigV4Auth(self.credentials, self.service, self.region)
        signer.add_auth(aws_request)
        
        for key, value in aws_request.headers.items():
            request.headers[key] = value
        
        yield request


def discover_runtime_models(bedrock_client) -> List[Dict]:
    """Discover models from bedrock-runtime service"""
    print("Discovering models from bedrock-runtime...")
    try:
        response = bedrock_client.list_foundation_models()
        models = response.get('modelSummaries', [])
        print(f"Found {len(models)} models in bedrock-runtime")
        return [{'modelId': m['modelId'], 'service': 'bedrock-runtime'} for m in models]
    except Exception as e:
        print(f"Error discovering bedrock-runtime models: {e}")
        return []


def discover_mantle_models(session) -> List[Dict]:
    """Discover models from bedrock-mantle service"""
    print("Discovering models from bedrock-mantle...")
    try:
        credentials = session.get_credentials().get_frozen_credentials()
        client = OpenAI(
            api_key="dummy",
            base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1",
            http_client=httpx.Client(
                auth=AWSBedrockMantleAuth("bedrock-mantle", REGION, credentials),
                timeout=TIMEOUT
            )
        )
        models = client.models.list()
        model_list = [{'modelId': m.id, 'service': 'bedrock-mantle'} for m in models.data]
        print(f"Found {len(model_list)} models in bedrock-mantle")
        return model_list
    except Exception as e:
        print(f"Error discovering bedrock-mantle models: {e}")
        return []


def discover_inference_profiles(bedrock_client) -> Dict[str, str]:
    """Discover inference profiles and categorize them"""
    print("Discovering inference profiles...")
    try:
        response = bedrock_client.list_inference_profiles()
        profiles = response.get('inferenceProfileSummaries', [])
        
        profile_map = {}
        for profile in profiles:
            profile_id = profile.get('inferenceProfileId', '')
            if profile_id.startswith('us.') or profile_id.startswith('eu.') or profile_id.startswith('ap.'):
                profile_type = 'regional-cross-region'
            elif profile_id.startswith('global.'):
                profile_type = 'global-cross-region'
            else:
                profile_type = 'in-region'
            profile_map[profile_id] = profile_type
        
        print(f"Found {len(profile_map)} inference profiles")
        return profile_map
    except Exception as e:
        print(f"Error discovering inference profiles: {e}")
        return {}


def test_invoke_api(bedrock_runtime, model_id: str) -> str:
    """Test invoke_model API"""
    try:
        # Try standard format first
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": TEST_PROMPT}]}],
            "inferenceConfig": {"max_new_tokens": 10}
        })
        bedrock_runtime.invoke_model(modelId=model_id, body=body)
        return "✓"
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        # If it's a validation error, try alternative format
        if 'Validation' in error_code:
            try:
                # Try Anthropic format
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": TEST_PROMPT}]
                })
                bedrock_runtime.invoke_model(modelId=model_id, body=body)
                return "✓"
            except Exception:
                pass
        return "✗"
    except Exception:
        return "✗"


def test_converse_api(bedrock_runtime, model_id: str) -> str:
    """Test converse API"""
    try:
        bedrock_runtime.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": TEST_PROMPT}]}],
            inferenceConfig={"maxTokens": 10}
        )
        return "✓"
    except Exception:
        return "✗"


def test_chat_completions_api(session, model_id: str) -> str:
    """Test chat completions API via OpenAI SDK"""
    try:
        credentials = session.get_credentials().get_frozen_credentials()
        client = OpenAI(
            api_key="dummy",
            base_url=f"https://bedrock-runtime.{REGION}.amazonaws.com/openai/v1",
            http_client=httpx.Client(
                auth=AWSBedrockMantleAuth("bedrock-runtime", REGION, credentials),
                timeout=TIMEOUT
            )
        )
        client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=10
        )
        return "✓"
    except Exception:
        return "✗"


def test_responses_api(session, model_id: str) -> str:
    """Test responses API via OpenAI SDK"""
    try:
        credentials = session.get_credentials().get_frozen_credentials()
        client = OpenAI(
            api_key="dummy",
            base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1",
            http_client=httpx.Client(
                auth=AWSBedrockMantleAuth("bedrock-mantle", REGION, credentials),
                timeout=TIMEOUT
            )
        )
        client.responses.create(
            model=model_id,
            input=[{"role": "user", "content": TEST_PROMPT}]
        )
        return "✓"
    except Exception:
        return "✗"


def main():
    parser = argparse.ArgumentParser(description='Generate Bedrock model compatibility matrix')
    parser.add_argument('--output', default='bedrock_compatibility_matrix.csv', 
                       help='Output CSV filename')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of models to test (for quick testing)')
    parser.add_argument('--error-log', default='bedrock_errors.log',
                       help='Error log filename')
    args = parser.parse_args()
    
    # Initialize AWS clients
    session = boto3.Session(region_name=REGION)
    bedrock_client = session.client('bedrock')
    bedrock_runtime = session.client('bedrock-runtime')
    
    # Open error log
    error_log = open(args.error_log, 'w', encoding='utf-8')
    
    # Task 1: Discover models
    runtime_models = discover_runtime_models(bedrock_client)
    mantle_models = discover_mantle_models(session)
    
    all_models = runtime_models + mantle_models
    
    if args.limit:
        all_models = all_models[:args.limit]
        print(f"\nLimiting to {len(all_models)} models for testing")
    
    print(f"\nTotal models to test: {len(all_models)}")
    
    # Task 2: Discover inference profiles
    inference_profiles = discover_inference_profiles(bedrock_client)
    
    print("\n=== Discovery Complete ===")
    print(f"Models from bedrock-runtime: {len([m for m in all_models if m['service'] == 'bedrock-runtime'])}")
    print(f"Models from bedrock-mantle: {len([m for m in all_models if m['service'] == 'bedrock-mantle'])}")
    print(f"Inference profiles: {len(inference_profiles)}")
    
    # Task 4: Generate compatibility matrix
    print("\n=== Testing API Compatibility ===")
    results = []
    total_tests = len(all_models)
    
    for idx, model in enumerate(all_models, 1):
        model_id = model['modelId']
        service = model['service']
        
        print(f"\n[{idx}/{total_tests}] Testing {model_id} ({service})")
        error_log.write(f"\n[{idx}/{total_tests}] {model_id} ({service})\n")
        
        # Determine profile type for this model
        profile_type = inference_profiles.get(model_id, 'in-region')
        
        # Test all 4 APIs
        print(f"  Testing invoke_model...", end=' ')
        invoke_result = test_invoke_api(bedrock_runtime, model_id)
        print(invoke_result)
        error_log.write(f"  invoke_model: {invoke_result}\n")
        
        print(f"  Testing converse...", end=' ')
        converse_result = test_converse_api(bedrock_runtime, model_id)
        print(converse_result)
        error_log.write(f"  converse: {converse_result}\n")
        
        print(f"  Testing chat_completions...", end=' ')
        chat_result = test_chat_completions_api(session, model_id)
        print(chat_result)
        error_log.write(f"  chat_completions: {chat_result}\n")
        
        print(f"  Testing responses...", end=' ')
        responses_result = test_responses_api(session, model_id)
        print(responses_result)
        error_log.write(f"  responses: {responses_result}\n")
        
        results.append({
            'Model': model_id,
            'Service': service,
            'Profile_Type': profile_type,
            'Invoke_API': invoke_result,
            'Converse_API': converse_result,
            'ChatCompletions_API': chat_result,
            'Responses_API': responses_result
        })
    
    error_log.close()
    
    # Task 5: Write CSV output
    print(f"\n=== Writing Results to {args.output} ===")
    with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Model', 'Service', 'Profile_Type', 'Invoke_API', 'Converse_API', 
                     'ChatCompletions_API', 'Responses_API']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    # Summary statistics
    total_supported = sum(
        1 for r in results 
        for api in ['Invoke_API', 'Converse_API', 'ChatCompletions_API', 'Responses_API']
        if r[api] == '✓'
    )
    total_combinations = len(results) * 4
    
    print(f"\n=== Summary ===")
    print(f"Total models tested: {len(results)}")
    print(f"Total API combinations: {total_combinations}")
    print(f"Supported combinations: {total_supported}")
    print(f"Success rate: {total_supported/total_combinations*100:.1f}%")
    print(f"\nResults saved to: {args.output}")
    print(f"Error log saved to: {args.error_log}")


if __name__ == "__main__":
    main()
