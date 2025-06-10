import sqlite3
import json
import os
from typing import List, Dict, Any
from datetime import datetime

class FHIRDatabase:
    def __init__(self, db_path: str = 'fhir_data.db'):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        
    def create_connection(self) -> None:
        """Create a database connection"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.create_tables()
        except sqlite3.Error as e:
            print(f"Error creating database connection: {e}")
            
    def create_tables(self) -> None:
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.conn.cursor()
            
            # Create resources table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    content JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create resource type index
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_resource_type 
                ON resources (resource_type)
            ''')
            
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
            
    def load_from_json(self, json_path: str) -> None:
        """Load FHIR data from JSON file into database"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            cursor = self.conn.cursor()
            
            for item in data:
                resource_id = item['resource_id']
                resource_type = item['resource_type']
                content = json.dumps(item['json'])
                
                cursor.execute('''
                    INSERT OR REPLACE INTO resources (id, resource_type, content)
                    VALUES (?, ?, ?)
                ''', (resource_id, resource_type, content))
                
            self.conn.commit()
            print(f"Successfully loaded {len(data)} resources into database")
            
        except sqlite3.Error as e:
            print(f"Error loading data: {e}")
            
    def search_by_type(self, resource_type: str) -> List[Dict[str, Any]]:
        """Search for resources by type"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = ?
        ''', (resource_type,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results
        
    def search_by_id(self, resource_id: str) -> Dict[str, Any]:
        """Search for a specific resource by ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE id = ?
        ''', (resource_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            }
        return None
        
    def search_by_text(self, query: str) -> List[Dict[str, Any]]:
        """Search for resources containing specific text"""
        cursor = self.conn.cursor()
        
        # Using LIKE with wildcards for basic text search
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE content LIKE ?
            LIMIT 100
        ''', ('%' + query + '%',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results
        
    def get_all_resources(self) -> List[Dict[str, Any]]:
        """Get all resources in the database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def find_patient(self, query: str) -> List[Dict[str, Any]]:
        """Search for a patient by name, DOB, or other identifiers"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'Patient'
        ''')
        
        results = []
        for row in cursor.fetchall():
            patient = json.loads(row[2])
            if (query.lower() in str(patient.get('name', '')).lower() or
                query.lower() in str(patient.get('birthDate', '')).lower() or
                query.lower() in str(patient.get('identifier', '')).lower()):
                results.append({
                    'id': row[0],
                    'resource_type': row[1],
                    'content': patient
                })
        
        return results

    def get_patient_observations(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve patient observations/vital signs"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'Observation' AND 
                  json_extract(content, '$.subject.reference') = ?
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's active conditions"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'Condition' AND 
                  json_extract(content, '$.subject.reference') = ? AND 
                  json_extract(content, '$.clinicalStatus.coding[0].code') = 'active'
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's current medications"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'MedicationStatement' AND 
                  json_extract(content, '$.subject.reference') = ? AND 
                  json_extract(content, '$.status') = 'active'
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_encounters(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's clinical encounters"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'Encounter' AND 
                  json_extract(content, '$.subject.reference') = ?
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_allergies(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's allergies and intolerances"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'AllergyIntolerance' AND 
                  json_extract(content, '$.patient.reference') = ?
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_procedures(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's procedures"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'Procedure' AND 
                  json_extract(content, '$.subject.reference') = ?
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_careteam(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's care team members"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'CareTeam' AND 
                  json_extract(content, '$.subject.reference') = ?
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def get_patient_careplans(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's active care plans"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = 'CarePlan' AND 
                  json_extract(content, '$.subject.reference') = ? AND 
                  json_extract(content, '$.status') = 'active'
        ''', (f'Patient/{patient_id}',))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'resource_type': row[1],
                'content': json.loads(row[2])
            })
        
        return results

    def clinical_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute custom FHIR queries"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, resource_type, content 
            FROM resources 
            WHERE resource_type = ?
        ''', (query.split(':')[0],))
        
        results = []
        for row in cursor.fetchall():
            resource = json.loads(row[2])
            if query.lower() in str(resource).lower():
                results.append({
                    'id': row[0],
                    'resource_type': row[1],
                    'content': resource
                })
        
        return results
        
    def get_resource_types(self) -> List[str]:
        """Get all available resource types"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT resource_type 
            FROM resources
        ''')
        
        return [row[0] for row in cursor.fetchall()]
        
    def close(self) -> None:
        """Close the database connection"""
        if self.conn:
            self.conn.close()

def main():
    # Initialize database
    db = FHIRDatabase()
    
    # Load data from JSON file if it exists
    if os.path.exists('processed_data.json'):
        db.load_from_json('processed_data.json')
    
    while True:
        print("\nFHIR Database Operations:")
        print("1. Search by Resource Type")
        print("2. Search by Resource ID")
        print("3. Search by Text")
        print("4. List All Resource Types")
        print("5. List All Resources")
        print("6. Quit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            resource_type = input("Enter resource type (e.g., Patient, Encounter): ")
            results = db.search_by_type(resource_type)
            print(f"\nFound {len(results)} {resource_type} resources:")
            for i, result in enumerate(results[:10], 1):
                print(f"\nResource {i}:")
                print(f"ID: {result['id']}")
                print(f"Content: {json.dumps(result['content'], indent=2)}")
        
        elif choice == '2':
            resource_id = input("Enter resource ID: ")
            result = db.search_by_id(resource_id)
            if result:
                print("\nFound resource:")
                print(f"Type: {result['resource_type']}")
                print(f"ID: {result['id']}")
                print(f"Content: {json.dumps(result['content'], indent=2)}")
            else:
                print("\nResource not found")
        
        elif choice == '3':
            query = input("Enter search text: ")
            results = db.search_by_text(query)
            print(f"\nFound {len(results)} matching resources:")
            for i, result in enumerate(results[:10], 1):
                print(f"\nResult {i}:")
                print(f"Type: {result['resource_type']}")
                print(f"ID: {result['id']}")
                print(f"Content: {json.dumps(result['content'], indent=2)}")
        
        elif choice == '4':
            resource_types = db.get_resource_types()
            print("\nAvailable Resource Types:")
            for i, resource_type in enumerate(resource_types, 1):
                print(f"{i}. {resource_type}")
        
        elif choice == '5':
            resources = db.get_all_resources()
            print(f"\nTotal resources: {len(resources)}")
            for i, resource in enumerate(resources[:10], 1):
                print(f"\nResource {i}:")
                print(f"Type: {resource['resource_type']}")
                print(f"ID: {resource['id']}")
        
        elif choice == '6':
            db.close()
            break
            
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main()
