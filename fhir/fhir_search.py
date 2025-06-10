import json
from typing import List, Dict, Any
from fhir_db import FHIRDatabase

class FHIRSearch:
    def __init__(self, db_path: str = 'fhir_data.db'):
        self.db = FHIRDatabase(db_path)
        
    def search_by_type(self, resource_type: str) -> List[Dict[str, Any]]:
        """Search for resources by type"""
        return self.db.search_by_type(resource_type)
        
    def search_by_id(self, resource_id: str) -> Dict[str, Any]:
        """Search for a specific resource by ID"""
        return self.db.search_by_id(resource_id)
        
    def search_by_text(self, query: str) -> List[Dict[str, Any]]:
        """Search for resources containing specific text"""
        return self.db.search_by_text(query)

    def find_patient(self, query: str) -> List[Dict[str, Any]]:
        """Search for a patient by name, DOB, or other identifiers"""
        return self.db.find_patient(query)

    def get_patient_observations(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve patient observations/vital signs"""
        return self.db.get_patient_observations(patient_id)

    def get_patient_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's active conditions"""
        return self.db.get_patient_conditions(patient_id)

    def get_patient_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's current medications"""
        return self.db.get_patient_medications(patient_id)

    def get_patient_encounters(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's clinical encounters"""
        return self.db.get_patient_encounters(patient_id)

    def get_patient_allergies(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's allergies and intolerances"""
        return self.db.get_patient_allergies(patient_id)

    def get_patient_procedures(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's procedures"""
        return self.db.get_patient_procedures(patient_id)

    def get_patient_careteam(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's care team members"""
        return self.db.get_patient_careteam(patient_id)

    def get_patient_careplans(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's active care plans"""
        return self.db.get_patient_careplans(patient_id)

    def get_vital_signs(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's vital signs"""
        observations = self.get_patient_observations(patient_id)
        return [obs for obs in observations if obs['code'] in ['BP', 'HR', 'RR', 'Temp', 'O2Sat', 'Height', 'Weight', 'BMI']]

    def get_lab_results(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's laboratory results"""
        observations = self.get_patient_observations(patient_id)
        return [obs for obs in observations if obs.get('category') == 'laboratory']

    def get_medications_history(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's medication history"""
        return self.db.get_patient_medications(patient_id)

    def clinical_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute custom FHIR queries"""
        return self.db.clinical_query(query)
        
    def get_resource_by_type_and_id(self, resource_type: str, resource_id: str) -> Dict[str, Any]:
        """Get a specific resource by type and ID"""
        resources = self.search_by_type(resource_type)
        for resource in resources:
            if resource['id'] == resource_id:
                return resource
        return None
        
    def get_all_resources(self) -> List[Dict[str, Any]]:
        """Get all resources in the data"""
        return self.db.get_all_resources()
        
    def get_resource_types(self) -> List[str]:
        """Get all available resource types"""
        return self.db.get_resource_types()

    def close(self) -> None:
        """Close the database connection"""
        self.db.close()
        
def main():
    # Initialize search
    search = FHIRSearch()
    
    try:
        while True:
            print("\nFHIR Search Options:")
            print("1. Search by Resource Type")
            print("2. Search by Resource ID")
            print("3. Search by Text")
            print("4. Find Patient")
            print("5. Get Patient Observations")
            print("6. Get Patient Conditions")
            print("7. Get Patient Medications")
            print("8. Get Patient Encounters")
            print("9. Get Patient Allergies")
            print("10. Get Patient Procedures")
            print("11. Get Patient Care Team")
            print("12. Get Patient Care Plans")
            print("13. Get Vital Signs")
            print("14. Get Lab Results")
            print("15. Get Medication History")
            print("16. Execute Custom Query")
            print("17. List All Resource Types")
            print("18. List All Resources")
            print("19. Quit")
            
            choice = input("\nEnter your choice (1-19): ")
            
            if choice == '1':
                resource_type = input("Enter resource type (e.g., Patient, Encounter): ")
                results = search.search_by_type(resource_type)
                print(f"\nFound {len(results)} {resource_type} resources:")
                for i, result in enumerate(results[:10], 1):
                    print(f"\nResource {i}:")
                    print(f"ID: {result['id']}")
                    print(f"Content: {json.dumps(result['content'], indent=2)}")
            
            elif choice == '2':
                resource_id = input("Enter resource ID: ")
                result = search.search_by_id(resource_id)
                if result:
                    print("\nFound resource:")
                    print(f"Type: {result['resource_type']}")
                    print(f"ID: {result['id']}")
                    print(f"Content: {json.dumps(result['content'], indent=2)}")
                else:
                    print("\nResource not found")
            
            elif choice == '3':
                query = input("Enter search text: ")
                results = search.search_by_text(query)
                print(f"\nFound {len(results)} matching resources:")
                for i, result in enumerate(results[:10], 1):
                    print(f"\nResult {i}:")
                    print(f"Type: {result['resource_type']}")
                    print(f"ID: {result['id']}")
                    print(f"Content: {json.dumps(result['content'], indent=2)}")
            
            elif choice == '4':
                query = input("Enter patient search query (name, DOB, etc.): ")
                patients = search.find_patient(query)
                print(f"\nFound {len(patients)} matching patients:")
                for i, patient in enumerate(patients, 1):
                    print(f"\nPatient {i}:")
                    print(f"ID: {patient['id']}")
                    print(f"Name: {patient.get('name', 'N/A')}")
                    print(f"Birth Date: {patient.get('birthDate', 'N/A')}")
            
            elif choice == '5':
                patient_id = input("Enter patient ID: ")
                observations = search.get_patient_observations(patient_id)
                print(f"\nFound {len(observations)} observations for patient {patient_id}:")
                for i, obs in enumerate(observations[:10], 1):
                    print(f"\nObservation {i}:")
                    print(f"Code: {obs.get('code', 'N/A')}")
                    print(f"Value: {obs.get('value', 'N/A')}")
                    print(f"Date: {obs.get('date', 'N/A')}")
            
            elif choice == '6':
                patient_id = input("Enter patient ID: ")
                conditions = search.get_patient_conditions(patient_id)
                print(f"\nFound {len(conditions)} conditions for patient {patient_id}:")
                for i, cond in enumerate(conditions, 1):
                    print(f"\nCondition {i}:")
                    print(f"Code: {cond.get('code', 'N/A')}")
                    print(f"Onset Date: {cond.get('onsetDateTime', 'N/A')}")
                    print(f"Status: {cond.get('status', 'N/A')}")
            
            elif choice == '7':
                patient_id = input("Enter patient ID: ")
                medications = search.get_patient_medications(patient_id)
                print(f"\nFound {len(medications)} medications for patient {patient_id}:")
                for i, med in enumerate(medications, 1):
                    print(f"\nMedication {i}:")
                    print(f"Code: {med.get('code', 'N/A')}")
                    print(f"Status: {med.get('status', 'N/A')}")
                    print(f"Dosage: {med.get('dosage', 'N/A')}")
            
            elif choice == '8':
                patient_id = input("Enter patient ID: ")
                encounters = search.get_patient_encounters(patient_id)
                print(f"\nFound {len(encounters)} encounters for patient {patient_id}:")
                for i, enc in enumerate(encounters, 1):
                    print(f"\nEncounter {i}:")
                    print(f"Type: {enc.get('type', 'N/A')}")
                    print(f"Start: {enc.get('start', 'N/A')}")
                    print(f"End: {enc.get('end', 'N/A')}")
            
            elif choice == '9':
                patient_id = input("Enter patient ID: ")
                allergies = search.get_patient_allergies(patient_id)
                print(f"\nFound {len(allergies)} allergies for patient {patient_id}:")
                for i, allergy in enumerate(allergies, 1):
                    print(f"\nAllergy {i}:")
                    print(f"Code: {allergy.get('code', 'N/A')}")
                    print(f"Status: {allergy.get('status', 'N/A')}")
                    print(f"Criticality: {allergy.get('criticality', 'N/A')}")
            
            elif choice == '10':
                patient_id = input("Enter patient ID: ")
                procedures = search.get_patient_procedures(patient_id)
                print(f"\nFound {len(procedures)} procedures for patient {patient_id}:")
                for i, proc in enumerate(procedures, 1):
                    print(f"\nProcedure {i}:")
                    print(f"Code: {proc.get('code', 'N/A')}")
                    print(f"Date: {proc.get('date', 'N/A')}")
                    print(f"Status: {proc.get('status', 'N/A')}")
            
            elif choice == '11':
                patient_id = input("Enter patient ID: ")
                careteam = search.get_patient_careteam(patient_id)
                print(f"\nFound {len(careteam)} care team members for patient {patient_id}:")
                for i, member in enumerate(careteam, 1):
                    print(f"\nCare Team Member {i}:")
                    print(f"Name: {member.get('name', 'N/A')}")
                    print(f"Role: {member.get('role', 'N/A')}")
            
            elif choice == '12':
                patient_id = input("Enter patient ID: ")
                careplans = search.get_patient_careplans(patient_id)
                print(f"\nFound {len(careplans)} care plans for patient {patient_id}:")
                for i, plan in enumerate(careplans, 1):
                    print(f"\nCare Plan {i}:")
                    print(f"Title: {plan.get('title', 'N/A')}")
                    print(f"Status: {plan.get('status', 'N/A')}")
                    print(f"Period: {plan.get('period', 'N/A')}")
            
            elif choice == '13':
                patient_id = input("Enter patient ID: ")
                vitals = search.get_vital_signs(patient_id)
                print(f"\nFound {len(vitals)} vital signs for patient {patient_id}:")
                for i, vital in enumerate(vitals, 1):
                    print(f"\nVital Sign {i}:")
                    print(f"Code: {vital.get('code', 'N/A')}")
                    print(f"Value: {vital.get('value', 'N/A')}")
                    print(f"Date: {vital.get('date', 'N/A')}")
            
            elif choice == '14':
                patient_id = input("Enter patient ID: ")
                labs = search.get_lab_results(patient_id)
                print(f"\nFound {len(labs)} lab results for patient {patient_id}:")
                for i, lab in enumerate(labs, 1):
                    print(f"\nLab Result {i}:")
                    print(f"Code: {lab.get('code', 'N/A')}")
                    print(f"Value: {lab.get('value', 'N/A')}")
                    print(f"Date: {lab.get('date', 'N/A')}")
            
            elif choice == '15':
                patient_id = input("Enter patient ID: ")
                history = search.get_medications_history(patient_id)
                print(f"\nFound {len(history)} medication history entries for patient {patient_id}:")
                for i, entry in enumerate(history, 1):
                    print(f"\nMedication History {i}:")
                    print(f"Code: {entry.get('code', 'N/A')}")
                    print(f"Status: {entry.get('status', 'N/A')}")
                    print(f"Date: {entry.get('date', 'N/A')}")
            
            elif choice == '16':
                query = input("Enter custom FHIR query: ")
                results = search.clinical_query(query)
                print(f"\nFound {len(results)} results:")
                for i, result in enumerate(results[:10], 1):
                    print(f"\nResult {i}:")
                    print(f"Type: {result.get('resource_type', 'N/A')}")
                    print(f"ID: {result.get('id', 'N/A')}")
                    print(f"Content: {json.dumps(result, indent=2)}")
            
            elif choice == '17':
                resource_types = search.get_resource_types()
                print("\nAvailable Resource Types:")
                for i, resource_type in enumerate(resource_types, 1):
                    print(f"{i}. {resource_type}")
            
            elif choice == '18':
                resources = search.get_all_resources()
                print(f"\nTotal resources: {len(resources)}")
                for i, resource in enumerate(resources[:10], 1):
                    print(f"\nResource {i}:")
                    print(f"Type: {resource['resource_type']}")
                    print(f"ID: {resource['id']}")
            
            elif choice == '6':
                break
                
            else:
                print("\nInvalid choice. Please try again.")
    
    finally:
        search.close()

if __name__ == "__main__":
    main()
