# MIMIC HealthLake Debug Test Suite
# Comprehensive testing for MIMIC-IV FHIR data in AWS HealthLake

import os
import json
import boto3
import requests
import asyncio
from datetime import datetime
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError, NoCredentialsError
import pandas as pd
import time

class MimicHealthLakeDebugger:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.datastore_id = os.getenv('HEALTHLAKE_DATASTORE_ID', '86d0ba828f546e2bd3521a04f5fd3052')
        self.endpoint_url = os.getenv('HEALTHLAKE_ENDPOINT_URL')
        self.session = None
        self.auth = None
        self.healthlake_client = None
        
        # Known MIMIC patient IDs from your sample
        self.sample_patient_ids = [
            "0a8eebfd-a352-522e-89f0-1d4a13abdebc",
            "0c2243d2-987b-5cbd-8eb1-170a80647693", 
            "13df78e7-150e-5eb7-be5f-5f62b2baee87",
            "158f3a39-e3d7-5e7a-93aa-57af894aadd9"
        ]
        
        # Known MIMIC identifiers
        self.sample_identifiers = ["10000032", "10005866", "10022880", "10005909"]
        
    def setup_authentication(self):
        """Setup AWS authentication for HealthLake"""
        print("=== Step 1: AWS Authentication ===")
        try:
            self.session = boto3.Session(region_name=self.region)
            
            # Test basic AWS connectivity
            sts = self.session.client('sts')
            identity = sts.get_caller_identity()
            print(f"✅ AWS Authentication successful")
            print(f"   Account: {identity['Account']}")
            print(f"   User/Role: {identity['Arn']}")
            print(f"   Region: {self.region}")
            
            # Setup AWS4Auth for FHIR API calls
            creds = self.session.get_credentials().get_frozen_credentials()
            self.auth = AWS4Auth(
                creds.access_key,
                creds.secret_key,
                self.region,
                'healthlake',
                session_token=creds.token,
            )
            
            # Create HealthLake client
            self.healthlake_client = self.session.client('healthlake')
            return True
            
        except NoCredentialsError:
            print("❌ AWS credentials not found")
            print("   Please run: aws configure")
            return False
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def validate_datastore(self):
        """Validate HealthLake datastore and get endpoint"""
        print(f"\n=== Step 2: Datastore Validation ===")
        try:
            response = self.healthlake_client.describe_fhir_datastore(
                DatastoreId=self.datastore_id
            )
            
            datastore = response['DatastoreProperties']
            print(f"✅ Datastore found: {datastore['DatastoreName']}")
            print(f"   Status: {datastore['DatastoreStatus']}")
            print(f"   Type: {datastore['DatastoreTypeVersion']}")
            print(f"   Created: {datastore['CreatedAt']}")
            
            # Get the correct endpoint
            if not self.endpoint_url:
                self.endpoint_url = datastore['DatastoreEndpoint'].rstrip('/')
            
            print(f"   Endpoint: {self.endpoint_url}")
            
            if datastore['DatastoreStatus'] != 'ACTIVE':
                print(f"⚠️  Datastore is {datastore['DatastoreStatus']}, not ACTIVE")
                return False
                
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                print(f"❌ Datastore not found: {self.datastore_id}")
                print("   Check your HEALTHLAKE_DATASTORE_ID")
            elif error_code == 'AccessDeniedException':
                print(f"❌ Access denied to datastore")
                print("   Check IAM permissions for healthlake:DescribeFHIRDatastore")
            else:
                print(f"❌ Error: {e}")
            return False
    
    def test_fhir_capability(self):
        """Test FHIR capability statement"""
        print(f"\n=== Step 3: FHIR Capability Test ===")
        try:
            metadata_url = f"{self.endpoint_url}/metadata"
            print(f"Testing: {metadata_url}")
            
            response = requests.get(
                metadata_url,
                auth=self.auth,
                headers={
                    'Accept': 'application/fhir+json',
                    'Content-Type': 'application/fhir+json'
                },
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
            
            if response.status_code == 200:
                capability = response.json()
                print(f"✅ FHIR Capability Statement retrieved")
                print(f"   FHIR Version: {capability.get('fhirVersion', 'Unknown')}")
                print(f"   Publisher: {capability.get('publisher', 'Unknown')}")
                
                # Check for supported resources
                if 'rest' in capability:
                    resources = capability['rest'][0].get('resource', [])
                    resource_types = [r['type'] for r in resources]
                    print(f"   Supported Resources: {len(resource_types)}")
                    if 'Patient' in resource_types:
                        print(f"   ✅ Patient resource supported")
                    else:
                        print(f"   ❌ Patient resource not found in capability")
                
                return True
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_patient_count(self):
        """Test getting patient count"""
        print(f"\n=== Step 4: Patient Count Test ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient"
            
            # Test with summary=count to get total count
            response = requests.get(
                patient_url,
                auth=self.auth,
                params={'_summary': 'count'},
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            print(f"URL: {patient_url}?_summary=count")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                bundle = response.json()
                total = bundle.get('total', 0)
                print(f"✅ Total patients in datastore: {total:,}")
                
                if total == 0:
                    print("⚠️  No patients found - check import status")
                    return False
                else:
                    return True
            else:
                print(f"❌ HTTP {response.status_code}")
                try:
                    error = response.json()
                    print(f"Error: {json.dumps(error, indent=2)}")
                except:
                    print(f"Error body: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_patient_search_basic(self):
        """Test basic patient search"""
        print(f"\n=== Step 5: Basic Patient Search ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient"
            
            response = requests.get(
                patient_url,
                auth=self.auth,
                params={'_count': 5},
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            print(f"URL: {patient_url}?_count=5")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                bundle = response.json()
                entries = bundle.get('entry', [])
                total = bundle.get('total', 0)
                
                print(f"✅ Retrieved {len(entries)} patients (total: {total:,})")
                
                if entries:
                    # Analyze first patient
                    patient = entries[0]['resource']
                    print(f"\n   Sample Patient Analysis:")
                    print(f"   ID: {patient.get('id', 'N/A')}")
                    print(f"   Resource Type: {patient.get('resourceType', 'N/A')}")
                    
                    # Check MIMIC-specific fields
                    if 'meta' in patient and 'profile' in patient['meta']:
                        profiles = patient['meta']['profile']
                        print(f"   MIMIC Profile: {profiles[0] if profiles else 'None'}")
                    
                    # Check identifier
                    if 'identifier' in patient:
                        identifiers = patient['identifier']
                        for ident in identifiers:
                            if 'mimic' in ident.get('system', ''):
                                print(f"   MIMIC ID: {ident.get('value', 'N/A')}")
                    
                    # Check name
                    if 'name' in patient and patient['name']:
                        name = patient['name'][0]
                        print(f"   Name: {name.get('family', 'N/A')}")
                    
                    # Check dates
                    print(f"   Birth Date: {patient.get('birthDate', 'N/A')}")
                    print(f"   Gender: {patient.get('gender', 'N/A')}")
                    
                    if 'deceasedDateTime' in patient:
                        print(f"   Deceased: {patient['deceasedDateTime']}")
                    
                    return True, entries
                else:
                    print("❌ No patient entries found in bundle")
                    return False, None
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False, None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, None
    
    def test_specific_patient_by_id(self, patient_id):
        """Test retrieving a specific MIMIC patient by ID"""
        print(f"\n=== Step 6: Specific Patient Test ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient/{patient_id}"
            print(f"Testing: {patient_url}")
            
            response = requests.get(
                patient_url,
                auth=self.auth,
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                patient = response.json()
                print(f"✅ Successfully retrieved patient: {patient_id}")
                
                # Detailed analysis
                print(f"\n   Detailed Patient Info:")
                print(f"   Resource Type: {patient.get('resourceType')}")
                print(f"   ID: {patient.get('id')}")
                
                # Meta information
                if 'meta' in patient:
                    meta = patient['meta']
                    print(f"   Version: {meta.get('versionId')}")
                    print(f"   Last Updated: {meta.get('lastUpdated')}")
                    if 'profile' in meta:
                        print(f"   Profile: {meta['profile'][0]}")
                
                # MIMIC identifier
                if 'identifier' in patient:
                    for ident in patient['identifier']:
                        if 'mimic' in ident.get('system', ''):
                            print(f"   MIMIC ID: {ident['value']}")
                
                # Demographics
                if 'name' in patient:
                    name = patient['name'][0]
                    print(f"   Family Name: {name.get('family')}")
                
                print(f"   Gender: {patient.get('gender')}")
                print(f"   Birth Date: {patient.get('birthDate')}")
                
                if 'deceasedDateTime' in patient:
                    print(f"   Deceased: {patient['deceasedDateTime']}")
                
                # Extensions (race, ethnicity, birth sex)
                if 'extension' in patient:
                    for ext in patient['extension']:
                        url = ext.get('url', '')
                        if 'us-core-race' in url:
                            race_ext = ext.get('extension', [])
                            for race in race_ext:
                                if race.get('url') == 'text':
                                    print(f"   Race: {race.get('valueString')}")
                        elif 'us-core-ethnicity' in url:
                            eth_ext = ext.get('extension', [])
                            for eth in eth_ext:
                                if eth.get('url') == 'text':
                                    print(f"   Ethnicity: {eth.get('valueString')}")
                        elif 'us-core-birthsex' in url:
                            print(f"   Birth Sex: {ext.get('valueCode')}")
                
                return True, patient
            elif response.status_code == 404:
                print(f"❌ Patient not found: {patient_id}")
                return False, None
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False, None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, None
    
    def test_patient_search_by_identifier(self, mimic_id):
        """Test searching for patient by MIMIC identifier"""
        print(f"\n=== Step 7: Patient Search by MIMIC ID ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient"
            
            # Search by identifier
            response = requests.get(
                patient_url,
                auth=self.auth,
                params={
                    'identifier': f"http://fhir.mimic.mit.edu/identifier/patient|{mimic_id}",
                    '_count': 10
                },
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            print(f"Searching for MIMIC ID: {mimic_id}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                bundle = response.json()
                entries = bundle.get('entry', [])
                
                if entries:
                    print(f"✅ Found {len(entries)} patient(s) with MIMIC ID {mimic_id}")
                    patient = entries[0]['resource']
                    print(f"   Patient ID: {patient.get('id')}")
                    print(f"   Name: {patient['name'][0].get('family') if patient.get('name') else 'N/A'}")
                    return True, entries
                else:
                    print(f"❌ No patients found with MIMIC ID: {mimic_id}")
                    return False, None
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False, None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, None
    
    def test_patient_search_by_name(self):
        """Test searching patients by name pattern"""
        print(f"\n=== Step 8: Patient Search by Name ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient"
            
            # Search for MIMIC patients (they all have "Patient_" prefix)
            response = requests.get(
                patient_url,
                auth=self.auth,
                params={
                    'name': 'Patient_10000032',
                    '_count': 5
                },
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            print(f"Searching for name: Patient_10000032")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                bundle = response.json()
                entries = bundle.get('entry', [])
                
                if entries:
                    print(f"✅ Found {len(entries)} patient(s) with name search")
                    for entry in entries:
                        patient = entry['resource']
                        print(f"   Patient ID: {patient.get('id')}")
                        if 'name' in patient:
                            print(f"   Name: {patient['name'][0].get('family')}")
                    return True, entries
                else:
                    print(f"❌ No patients found with name search")
                    return False, None
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False, None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, None
    
    def test_import_job_status(self):
        """Check import job status to see if data was loaded properly"""
        print(f"\n=== Step 9: Import Job Status ===")
        try:
            response = self.healthlake_client.list_fhir_import_jobs(
                DatastoreId=self.datastore_id,
                MaxResults=10
            )
            
            import_jobs = response.get('ImportJobPropertiesList', [])
            
            if import_jobs:
                print(f"✅ Found {len(import_jobs)} import job(s)")
                
                for i, job in enumerate(import_jobs):
                    print(f"\n   Job {i+1}:")
                    print(f"   ID: {job['JobId']}")
                    print(f"   Status: {job['JobStatus']}")
                    print(f"   Submit Time: {job['SubmitTime']}")
                    
                    if 'EndTime' in job:
                        print(f"   End Time: {job['EndTime']}")
                    
                    if 'JobProgressReport' in job:
                        progress = job['JobProgressReport']
                        print(f"   Files Imported: {progress.get('TotalNumberOfImportedFiles', 0)}")
                        print(f"   Resources Imported: {progress.get('TotalNumberOfResourcesImported', 0)}")
                        print(f"   Files with Errors: {progress.get('TotalNumberOfFilesWithCustomerError', 0)}")
                        print(f"   Resources with Errors: {progress.get('TotalNumberOfResourcesWithCustomerError', 0)}")
                
                # Check if any jobs are still running
                running_jobs = [j for j in import_jobs if j['JobStatus'] in ['SUBMITTED', 'IN_PROGRESS']]
                if running_jobs:
                    print(f"\n⚠️  {len(running_jobs)} job(s) still running - data may not be fully loaded")
                
                return True
            else:
                print(f"❌ No import jobs found")
                print("   This might explain why no data is returned")
                return False
                
        except Exception as e:
            print(f"❌ Error checking import jobs: {e}")
            return False
    
    def test_raw_request_debug(self):
        """Debug raw HTTP request/response"""
        print(f"\n=== Step 10: Raw Request Debug ===")
        try:
            patient_url = f"{self.endpoint_url}/Patient"
            
            print(f"Making raw request to: {patient_url}")
            print(f"Auth type: {type(self.auth)}")
            print(f"Region: {self.region}")
            
            # Make request with detailed logging
            import logging
            import http.client
            
            # Enable HTTP debugging
            http.client.HTTPConnection.debuglevel = 1
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
            
            response = requests.get(
                patient_url,
                auth=self.auth,
                params={'_count': 1},
                headers={'Accept': 'application/fhir+json'},
                timeout=30
            )
            
            # Disable debugging
            http.client.HTTPConnection.debuglevel = 0
            
            print(f"\nResponse Analysis:")
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Content Length: {len(response.content)}")
            print(f"Content Type: {response.headers.get('content-type')}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"JSON Parse: Success")
                    print(f"Resource Type: {data.get('resourceType', 'Unknown')}")
                    print(f"Total: {data.get('total', 'Unknown')}")
                    print(f"Entry Count: {len(data.get('entry', []))}")
                except Exception as e:
                    print(f"JSON Parse Error: {e}")
                    print(f"Raw content (first 1000 chars): {response.text[:1000]}")
            else:
                print(f"Error Response: {response.text[:1000]}")
                
        except Exception as e:
            print(f"❌ Error in raw debug: {e}")
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("=" * 80)
        print("MIMIC HEALTHLAKE COMPREHENSIVE DEBUG TEST")
        print("=" * 80)
        
        print(f"Configuration:")
        print(f"  Datastore ID: {self.datastore_id}")
        print(f"  Region: {self.region}")
        print(f"  Endpoint URL: {self.endpoint_url or 'Auto-detect'}")
        print(f"  Sample Patient IDs: {len(self.sample_patient_ids)}")
        
        # Step 1: Authentication
        if not self.setup_authentication():
            print("\n❌ FAILED: Cannot proceed without authentication")
            return False
        
        # Step 2: Datastore validation
        if not self.validate_datastore():
            print("\n❌ FAILED: Cannot access datastore")
            return False
        
        # Step 3: FHIR capability
        if not self.test_fhir_capability():
            print("\n❌ FAILED: FHIR endpoint not responding")
            return False
        
        # Step 4: Patient count
        if not self.test_patient_count():
            print("\n❌ FAILED: No patients found")
            # Continue to check import status
        
        # Step 5: Basic patient search
        success, patients = self.test_patient_search_basic()
        if not success:
            print("\n❌ FAILED: Cannot retrieve patients")
            # Check import status
            self.test_import_job_status()
            return False
        
        # Step 6: Test specific patient
        if patients:
            patient_id = patients[0]['resource']['id']
            self.test_specific_patient_by_id(patient_id)
        else:
            # Try with known patient ID
            self.test_specific_patient_by_id(self.sample_patient_ids[0])
        
        # Step 7: Search by MIMIC ID
        self.test_patient_search_by_identifier(self.sample_identifiers[0])
        
        # Step 8: Search by name
        self.test_patient_search_by_name()
        
        # Step 9: Import job status
        self.test_import_job_status()
        
        # Step 10: Raw debug if needed
        # Uncomment if you need detailed HTTP debugging
        # self.test_raw_request_debug()
        
        print("\n" + "=" * 80)
        print("✅ COMPREHENSIVE TEST COMPLETED")
        print("=" * 80)
        print("\nIf you're still having issues:")
        print("1. Check that import jobs completed successfully")
        print("2. Verify the datastore has data using AWS CLI")
        print("3. Check CloudWatch logs for detailed errors")
        print("4. Ensure your IAM permissions include FHIR read access")
        
        return True

# Usage example
if __name__ == "__main__":
    # Set up environment variables if not already set
    os.environ.setdefault('AWS_REGION', 'us-east-1')
    os.environ.setdefault('HEALTHLAKE_DATASTORE_ID', '86d0ba828f546e2bd3521a04f5fd3052')
    
    # Run the test
    debugger = MimicHealthLakeDebugger()
    debugger.run_comprehensive_test()
