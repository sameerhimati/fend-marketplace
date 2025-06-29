#!/usr/bin/env python
"""
Test script to verify Digital Ocean Spaces configuration without running Django.
This script checks the basic connection and configuration.
"""
import os
import sys
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / '.env.prod'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded environment from {env_file}")
    else:
        print("✗ .env.prod file not found")
        sys.exit(1)
except ImportError:
    print("✗ python-dotenv not installed")
    sys.exit(1)

# Test basic connectivity
def test_boto3_connection():
    """Test basic boto3 connection to Digital Ocean Spaces"""
    try:
        import boto3
        from botocore.exceptions import ClientError, EndpointConnectionError
        
        # Get configuration from environment
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
        endpoint_url = os.getenv('AWS_S3_ENDPOINT_URL')
        region = os.getenv('AWS_S3_REGION_NAME', 'sfo3')
        
        print("\n" + "="*50)
        print("TESTING DIGITAL OCEAN SPACES CONNECTION")
        print("="*50)
        
        # Validate configuration
        missing_vars = []
        for var_name, var_value in [
            ('AWS_ACCESS_KEY_ID', access_key),
            ('AWS_SECRET_ACCESS_KEY', secret_key),
            ('AWS_STORAGE_BUCKET_NAME', bucket_name),
            ('AWS_S3_ENDPOINT_URL', endpoint_url)
        ]:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
            return False
        
        # Mask sensitive information for display
        print(f"Access Key: {access_key[:4]}...{access_key[-4:]}")
        print(f"Secret Key: {secret_key[:4]}...{secret_key[-4:]}")
        print(f"Bucket: {bucket_name}")
        print(f"Endpoint: {endpoint_url}")
        print(f"Region: {region}")
        
        # Create boto3 client
        print("\n1. Creating boto3 client...")
        session = boto3.session.Session()
        client = session.client(
            's3',
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        print("✓ Boto3 client created successfully")
        
        # Test bucket access
        print("\n2. Testing bucket access...")
        try:
            response = client.head_bucket(Bucket=bucket_name)
            print("✓ Bucket access successful")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"✗ Bucket '{bucket_name}' not found")
            elif error_code == '403':
                print(f"✗ Access denied to bucket '{bucket_name}'")
            else:
                print(f"✗ Error accessing bucket: {error_code}")
            return False
        
        # Test file upload
        print("\n3. Testing file upload...")
        test_key = 'test/config_test.txt'
        test_content = b'Digital Ocean Spaces configuration test'
        
        try:
            client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content,
                ACL='public-read'
            )
            print("✓ File upload successful")
        except Exception as e:
            print(f"✗ File upload failed: {e}")
            return False
        
        # Test file retrieval
        print("\n4. Testing file retrieval...")
        try:
            response = client.get_object(Bucket=bucket_name, Key=test_key)
            retrieved_content = response['Body'].read()
            if retrieved_content == test_content:
                print("✓ File retrieval successful")
            else:
                print("✗ Retrieved content doesn't match uploaded content")
                return False
        except Exception as e:
            print(f"✗ File retrieval failed: {e}")
            return False
        
        # Test public URL
        print("\n5. Testing public URL generation...")
        try:
            cdn_domain = os.getenv('AWS_S3_CUSTOM_DOMAIN')
            if cdn_domain:
                public_url = f"https://{cdn_domain}/{test_key}"
                print(f"CDN URL: {public_url}")
            
            # Direct endpoint URL
            direct_url = f"{endpoint_url}/{test_key}"
            print(f"Direct URL: {direct_url}")
            print("✓ URL generation successful")
        except Exception as e:
            print(f"✗ URL generation failed: {e}")
        
        # Clean up test file
        print("\n6. Cleaning up test file...")
        try:
            client.delete_object(Bucket=bucket_name, Key=test_key)
            print("✓ Test file deleted")
        except Exception as e:
            print(f"⚠ Failed to delete test file: {e}")
        
        print("\n" + "="*50)
        print("✓ ALL TESTS PASSED - Digital Ocean Spaces is configured correctly!")
        print("="*50)
        return True
        
    except ImportError:
        print("✗ boto3 not installed. Run: pip install boto3")
        return False
    except EndpointConnectionError:
        print("✗ Cannot connect to Digital Ocean Spaces endpoint")
        print("  Check your internet connection and endpoint URL")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_django_storages():
    """Test if django-storages is properly configured"""
    try:
        import storages
        print(f"✓ django-storages version: {storages.__version__}")
        return True
    except ImportError:
        print("✗ django-storages not installed. Run: pip install django-storages")
        return False


def main():
    print("Digital Ocean Spaces Configuration Test")
    print("This script tests your DO Spaces setup before deploying")
    
    # Test dependencies
    if not test_django_storages():
        return
    
    # Test connection
    if not test_boto3_connection():
        print("\n" + "="*50)
        print("CONFIGURATION ISSUES DETECTED")
        print("="*50)
        print("Please check:")
        print("1. Environment variables in .env.prod")
        print("2. Digital Ocean Spaces access keys")
        print("3. Bucket name and permissions")
        print("4. Internet connectivity")
        return
    
    print("\nConfiguration test completed successfully!")
    print("You can now deploy with confidence.")


if __name__ == '__main__':
    main()