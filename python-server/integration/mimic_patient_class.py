import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
import warnings
import logging

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Demographics:
    """Patient demographic information"""
    patient_id: str = ""
    mimic_id: str = ""
    name: str = ""
    gender: str = ""
    birth_date: str = ""
    deceased_date: Optional[str] = None
    marital_status: str = ""
    race: str = ""
    ethnicity: str = ""
    birth_sex: str = ""
    age_at_admission: Optional[int] = None
    is_deceased: bool = False

@dataclass
class ClinicalData:
    """Clinical data containers"""
    observations: List[Dict] = field(default_factory=list)
    conditions: List[Dict] = field(default_factory=list)
    medications: List[Dict] = field(default_factory=list)
    medication_administrations: List[Dict] = field(default_factory=list)
    medication_requests: List[Dict] = field(default_factory=list)
    encounters: List[Dict] = field(default_factory=list)
    procedures: List[Dict] = field(default_factory=list)
    locations: List[Dict] = field(default_factory=list)
    specimens: List[Dict] = field(default_factory=list)
    
    # Organized clinical data
    vital_signs: List[Dict] = field(default_factory=list)
    lab_results: List[Dict] = field(default_factory=list)
    microbiology: List[Dict] = field(default_factory=list)
    
    # Analysis containers
    timeline: List[Dict] = field(default_factory=list)

class MimicPatient:
    """
    Comprehensive MIMIC Patient class for FHIR data management and analysis
    """
    
    def __init__(self, patient_id: Optional[str] = None):
        """Initialize patient with optional ID"""
        self.demographics = Demographics()
        self.clinical_data = ClinicalData()
        self.raw_resources = {}  # Store raw FHIR resources
        self.data_frames = {}    # Store pandas DataFrames
        self.analysis_cache = {} # Cache analysis results
        # Scheduled follow-up appointments
        self.follow_up_appointments: List[Dict[str, Any]] = []
        
        if patient_id:
            self.demographics.patient_id = patient_id
    
    # =============================================
    # FHIR Resource Parsing Methods
    # =============================================
    
    def parse_patient_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Patient resource"""
        if not resource or resource.get("resourceType") != "Patient":
            return
        
        self.raw_resources["patient"] = resource
        
        # Basic demographics
        self.demographics.patient_id = resource.get("id", "")
        self.demographics.gender = resource.get("gender", "")
        self.demographics.birth_date = resource.get("birthDate", "")
        self.demographics.deceased_date = resource.get("deceasedDateTime")
        self.demographics.is_deceased = bool(self.demographics.deceased_date)
        
        # Extract MIMIC identifier
        if "identifier" in resource:
            for identifier in resource["identifier"]:
                if "mimic" in identifier.get("system", "").lower():
                    self.demographics.mimic_id = identifier.get("value", "")
        
        # Extract name
        if "name" in resource and resource["name"]:
            name_obj = resource["name"][0]
            if "family" in name_obj:
                self.demographics.name = name_obj["family"]
        
        # Extract marital status
        if "maritalStatus" in resource:
            marital_coding = resource["maritalStatus"].get("coding", [])
            if marital_coding:
                self.demographics.marital_status = marital_coding[0].get("code", "")
        
        # Extract extensions (race, ethnicity, birth sex)
        if "extension" in resource:
            for ext in resource["extension"]:
                url = ext.get("url", "")
                if "us-core-race" in url:
                    race_ext = ext.get("extension", [])
                    for race in race_ext:
                        if race.get("url") == "text":
                            self.demographics.race = race.get("valueString", "")
                elif "us-core-ethnicity" in url:
                    eth_ext = ext.get("extension", [])
                    for eth in eth_ext:
                        if eth.get("url") == "text":
                            self.demographics.ethnicity = eth.get("valueString", "")
                elif "us-core-birthsex" in url:
                    self.demographics.birth_sex = ext.get("valueCode", "")
        
        logger.info(f"Parsed patient: {self.demographics.name} (MIMIC ID: {self.demographics.mimic_id})")
    
    def parse_observation_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Observation resource"""
        if not resource or resource.get("resourceType") != "Observation":
            return
        
        observation = self._extract_observation_data(resource)
        self.clinical_data.observations.append(observation)
        
        # Categorize observations
        category = self._get_observation_category(resource)
        if category == "vital-signs":
            self.clinical_data.vital_signs.append(observation)
        elif category == "laboratory":
            self.clinical_data.lab_results.append(observation)
        elif "micro" in resource.get("meta", {}).get("profile", [""])[0]:
            self.clinical_data.microbiology.append(observation)
        
        # Add to timeline
        self._add_to_timeline("observation", observation)
    
    def parse_condition_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Condition resource"""
        if not resource or resource.get("resourceType") != "Condition":
            return
        
        condition = {
            "id": resource.get("id"),
            "code": self._extract_code_display(resource.get("code", {})),
            "clinical_status": self._extract_coding_display(resource.get("clinicalStatus", {})),
            "verification_status": self._extract_coding_display(resource.get("verificationStatus", {})),
            "category": [self._extract_coding_display(cat) for cat in resource.get("category", [])],
            "onset_date": resource.get("onsetDateTime"),
            "recorded_date": resource.get("recordedDate"),
            "severity": self._extract_coding_display(resource.get("severity", {})),
            "raw_resource": resource
        }
        
        self.clinical_data.conditions.append(condition)
        self._add_to_timeline("condition", condition)
        logger.debug(f"Parsed condition: {condition['code']}")
    
    def parse_medication_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Medication-related resources"""
        resource_type = resource.get("resourceType")
        
        if resource_type == "MedicationRequest":
            self._parse_medication_request(resource)
        elif resource_type == "MedicationAdministration":
            self._parse_medication_administration(resource)
        elif resource_type == "MedicationDispense":
            self._parse_medication_dispense(resource)
        elif resource_type == "Medication":
            self._parse_medication_definition(resource)
    
    def _parse_medication_request(self, resource: Dict[str, Any]) -> None:
        """Parse MedicationRequest resource"""
        med_request = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "intent": resource.get("intent"),
            "medication": self._extract_medication_info(resource),
            "authored_on": resource.get("authoredOn"),
            "dosage_instructions": self._extract_dosage_instructions(resource.get("dosageInstruction", [])),
            "dispense_request": resource.get("dispenseRequest", {}),
            "type": "request",
            "raw_resource": resource
        }
        
        self.clinical_data.medication_requests.append(med_request)
        self.clinical_data.medications.append(med_request)
        self._add_to_timeline("medication_request", med_request)
    
    def _parse_medication_administration(self, resource: Dict[str, Any]) -> None:
        """Parse MedicationAdministration resource"""
        med_admin = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "medication": self._extract_medication_info(resource),
            "effective_date": resource.get("effectiveDateTime"),
            "dosage": self._extract_administration_dosage(resource.get("dosage", {})),
            "type": "administration",
            "raw_resource": resource
        }
        
        self.clinical_data.medication_administrations.append(med_admin)
        self.clinical_data.medications.append(med_admin)
        self._add_to_timeline("medication_administration", med_admin)
    
    def _parse_medication_dispense(self, resource: Dict[str, Any]) -> None:
        """Parse MedicationDispense resource"""
        med_dispense = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "medication": self._extract_medication_info(resource),
            "when_dispensed": resource.get("whenHandedOver"),
            "quantity": resource.get("quantity", {}),
            "dosage_instructions": self._extract_dosage_instructions(resource.get("dosageInstruction", [])),
            "type": "dispense",
            "raw_resource": resource
        }
        
        self.clinical_data.medications.append(med_dispense)
        self._add_to_timeline("medication_dispense", med_dispense)
    
    def _parse_medication_definition(self, resource: Dict[str, Any]) -> None:
        """Parse Medication definition resource"""
        # Store medication definitions for reference
        med_id = resource.get("id")
        if med_id:
            self.raw_resources[f"medication_{med_id}"] = resource
    
    def parse_encounter_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Encounter resource"""
        if not resource or resource.get("resourceType") != "Encounter":
            return
        
        encounter = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "class": self._extract_coding_display(resource.get("class", {})),
            "type": [self._extract_coding_display(t) for t in resource.get("type", [])],
            "service_type": self._extract_coding_display(resource.get("serviceType", {})),
            "priority": self._extract_coding_display(resource.get("priority", {})),
            "period": resource.get("period", {}),
            "length_of_stay": self._calculate_length_of_stay(resource.get("period", {})),
            "reason_codes": [self._extract_code_display(r) for r in resource.get("reasonCode", [])],
            "hospitalization": resource.get("hospitalization", {}),
            "locations": self._extract_encounter_locations(resource.get("location", [])),
            "raw_resource": resource
        }
        
        self.clinical_data.encounters.append(encounter)
        self._add_to_timeline("encounter", encounter)
        logger.debug(f"Parsed encounter: {encounter['class']} ({encounter['period']})")
    
    def parse_procedure_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Procedure resource"""
        if not resource or resource.get("resourceType") != "Procedure":
            return
        
        procedure = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "category": self._extract_coding_display(resource.get("category", {})),
            "code": self._extract_code_display(resource.get("code", {})),
            "performed_date": resource.get("performedDateTime"),
            "performed_period": resource.get("performedPeriod", {}),
            "raw_resource": resource
        }
        
        self.clinical_data.procedures.append(procedure)
        self._add_to_timeline("procedure", procedure)
    
    def parse_location_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Location resource"""
        if not resource or resource.get("resourceType") != "Location":
            return
        
        location = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "name": resource.get("name"),
            "physical_type": self._extract_coding_display(resource.get("physicalType", {})),
            "raw_resource": resource
        }
        
        self.clinical_data.locations.append(location)
    
    def parse_specimen_resource(self, resource: Dict[str, Any]) -> None:
        """Parse FHIR Specimen resource"""
        if not resource or resource.get("resourceType") != "Specimen":
            return
        
        specimen = {
            "id": resource.get("id"),
            "type": self._extract_coding_display(resource.get("type", {})),
            "collection_date": resource.get("collection", {}).get("collectedDateTime"),
            "raw_resource": resource
        }
        
        self.clinical_data.specimens.append(specimen)
    
    # =============================================
    # Batch Processing Methods
    # =============================================
    
    def parse_fhir_bundle(self, bundle: Dict[str, Any]) -> None:
        """Parse a complete FHIR Bundle"""
        if not bundle or bundle.get("resourceType") != "Bundle":
            return
        
        logger.info(f"Parsing FHIR bundle with {len(bundle.get('entry', []))} entries")
        
        for entry in bundle.get("entry", []):
            if "resource" not in entry:
                continue
            
            resource = entry["resource"]
            self.parse_resource(resource)
    
    def parse_resource(self, resource: Dict[str, Any]) -> None:
        """Parse any FHIR resource based on its type"""
        resource_type = resource.get("resourceType")
        
        parsers = {
            "Patient": self.parse_patient_resource,
            "Observation": self.parse_observation_resource,
            "Condition": self.parse_condition_resource,
            "MedicationRequest": self.parse_medication_resource,
            "MedicationAdministration": self.parse_medication_resource,
            "MedicationDispense": self.parse_medication_resource,
            "Medication": self.parse_medication_resource,
            "Encounter": self.parse_encounter_resource,
            "Procedure": self.parse_procedure_resource,
            "Location": self.parse_location_resource,
            "Specimen": self.parse_specimen_resource
        }
        
        parser = parsers.get(resource_type)
        if parser:
            parser(resource)
        else:
            logger.debug(f"No parser for resource type: {resource_type}")
    
    def parse_resource_list(self, resources: List[Dict[str, Any]]) -> None:
        """Parse a list of FHIR resources"""
        for resource in resources:
            self.parse_resource(resource)
    
    # =============================================
    # Data Organization Methods
    # =============================================
    
    def create_data_frames(self) -> Dict[str, pd.DataFrame]:
        """Create pandas DataFrames from parsed data"""
        dfs = {}
        
        # Demographics DataFrame
        demo_data = {
            'patient_id': [self.demographics.patient_id],
            'mimic_id': [self.demographics.mimic_id],
            'name': [self.demographics.name],
            'gender': [self.demographics.gender],
            'birth_date': [self.demographics.birth_date],
            'deceased_date': [self.demographics.deceased_date],
            'race': [self.demographics.race],
            'ethnicity': [self.demographics.ethnicity],
            'marital_status': [self.demographics.marital_status],
            'is_deceased': [self.demographics.is_deceased]
        }
        dfs['demographics'] = pd.DataFrame(demo_data)
        
        # Clinical DataFrames
        if self.clinical_data.vital_signs:
            dfs['vital_signs'] = pd.DataFrame(self.clinical_data.vital_signs)
            if 'effective_date' in dfs['vital_signs'].columns:
                dfs['vital_signs']['effective_date'] = pd.to_datetime(dfs['vital_signs']['effective_date'])
        
        if self.clinical_data.lab_results:
            dfs['lab_results'] = pd.DataFrame(self.clinical_data.lab_results)
            if 'effective_date' in dfs['lab_results'].columns:
                dfs['lab_results']['effective_date'] = pd.to_datetime(dfs['lab_results']['effective_date'])
        
        if self.clinical_data.medications:
            dfs['medications'] = pd.DataFrame(self.clinical_data.medications)
        
        if self.clinical_data.conditions:
            dfs['conditions'] = pd.DataFrame(self.clinical_data.conditions)
        
        if self.clinical_data.encounters:
            dfs['encounters'] = pd.DataFrame(self.clinical_data.encounters)
        
        if self.clinical_data.procedures:
            dfs['procedures'] = pd.DataFrame(self.clinical_data.procedures)
        
        # Timeline DataFrame
        if self.clinical_data.timeline:
            dfs['timeline'] = pd.DataFrame(self.clinical_data.timeline)
            if 'date' in dfs['timeline'].columns:
                dfs['timeline']['date'] = pd.to_datetime(dfs['timeline']['date'])
                dfs['timeline'] = dfs['timeline'].sort_values('date')
        
        self.data_frames = dfs
        logger.info(f"Created {len(dfs)} DataFrames")
        return dfs
    
    # =============================================
    # Analysis Methods
    # =============================================
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics for the patient"""
        if 'summary' in self.analysis_cache:
            return self.analysis_cache['summary']
        
        summary = {
            'patient_info': {
                'id': self.demographics.patient_id,
                'mimic_id': self.demographics.mimic_id,
                'name': self.demographics.name,
                'age': self._calculate_age(),
                'gender': self.demographics.gender,
                'is_deceased': self.demographics.is_deceased
            },
            'data_counts': {
                'observations': len(self.clinical_data.observations),
                'vital_signs': len(self.clinical_data.vital_signs),
                'lab_results': len(self.clinical_data.lab_results),
                'conditions': len(self.clinical_data.conditions),
                'medications': len(self.clinical_data.medications),
                'encounters': len(self.clinical_data.encounters),
                'procedures': len(self.clinical_data.procedures)
            },
            'date_range': self._get_data_date_range(),
            'key_conditions': self._get_key_conditions(),
            'recent_vitals': self._get_recent_vitals(),
            'medication_summary': self._get_medication_summary()
        }
        
        self.analysis_cache['summary'] = summary
        return summary
    
    # =============================================
    # Visualization Methods
    # =============================================
    
    def create_patient_dashboard(self, figsize=(20, 16)) -> plt.Figure:
        """Create comprehensive patient dashboard"""
        fig = plt.figure(figsize=figsize)
        
        # Set up the grid layout
        gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)
        
        # Patient info header
        ax_info = fig.add_subplot(gs[0, :])
        self._plot_patient_header(ax_info)
        
        # Vital signs over time
        ax_vitals = fig.add_subplot(gs[1, :2])
        self._plot_vital_signs_timeline(ax_vitals)
        
        # Lab results over time
        ax_labs = fig.add_subplot(gs[1, 2:])
        self._plot_lab_results_timeline(ax_labs)
        
        # Conditions summary
        ax_conditions = fig.add_subplot(gs[2, :2])
        self._plot_conditions_summary(ax_conditions)
        
        # Medications timeline
        ax_meds = fig.add_subplot(gs[2, 2:])
        self._plot_medications_timeline(ax_meds)
        
        # Encounters timeline
        ax_encounters = fig.add_subplot(gs[3, :2])
        self._plot_encounters_timeline(ax_encounters)
        
        # Overall timeline
        ax_timeline = fig.add_subplot(gs[3, 2:])
        self._plot_overall_timeline(ax_timeline)
        
        plt.suptitle(f'MIMIC Patient Dashboard: {self.demographics.name} (ID: {self.demographics.mimic_id})', 
                     fontsize=16, fontweight='bold')
        
        return fig
    
    def _plot_patient_header(self, ax):
        """Plot patient demographic information"""
        ax.axis('off')
        
        info_text = f"""
        Patient ID: {self.demographics.patient_id}
        MIMIC ID: {self.demographics.mimic_id}
        Name: {self.demographics.name}
        Age: {self._calculate_age()} years
        Gender: {self.demographics.gender}
        Race: {self.demographics.race}
        Birth Date: {self.demographics.birth_date}
        Status: {'Deceased' if self.demographics.is_deceased else 'Alive'}
        """
        
        ax.text(0.1, 0.5, info_text, fontsize=12, verticalalignment='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
        
        # Add summary statistics
        summary = self.get_summary_statistics()
        stats_text = f"""
        Total Observations: {summary['data_counts']['observations']:,}
        Vital Signs: {summary['data_counts']['vital_signs']:,}
        Lab Results: {summary['data_counts']['lab_results']:,}
        Conditions: {summary['data_counts']['conditions']}
        Medications: {summary['data_counts']['medications']}
        Encounters: {summary['data_counts']['encounters']}
        """
        
        ax.text(0.6, 0.5, stats_text, fontsize=12, verticalalignment='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))
    
    def _plot_vital_signs_timeline(self, ax):
        """Plot vital signs over time"""
        if not self.clinical_data.vital_signs:
            ax.text(0.5, 0.5, 'No vital signs data', ha='center', va='center')
            ax.set_title('Vital Signs Timeline')
            return
        
        df = pd.DataFrame(self.clinical_data.vital_signs)
        if 'effective_date' not in df.columns or df.empty:
            ax.text(0.5, 0.5, 'No temporal vital signs data', ha='center', va='center')
            ax.set_title('Vital Signs Timeline')
            return
        
        df['effective_date'] = pd.to_datetime(df['effective_date'])
        
        # Plot different vital signs
        vital_types = df['code_display'].value_counts().head(5).index
        colors = plt.cm.tab10(np.linspace(0, 1, len(vital_types)))
        
        for i, vital_type in enumerate(vital_types):
            vital_data = df[df['code_display'] == vital_type]
            if 'value_numeric' in vital_data.columns:
                ax.scatter(vital_data['effective_date'], vital_data['value_numeric'], 
                          label=vital_type, alpha=0.7, color=colors[i])
        
        ax.set_title('Vital Signs Over Time')
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def _plot_lab_results_timeline(self, ax):
        """Plot lab results over time"""
        if not self.clinical_data.lab_results:
            ax.text(0.5, 0.5, 'No lab results data', ha='center', va='center')
            ax.set_title('Lab Results Timeline')
            return
        
        df = pd.DataFrame(self.clinical_data.lab_results)
        if 'effective_date' not in df.columns or df.empty:
            ax.text(0.5, 0.5, 'No temporal lab data', ha='center', va='center')
            ax.set_title('Lab Results Timeline')
            return
        
        df['effective_date'] = pd.to_datetime(df['effective_date'])
        
        # Plot most common lab tests
        lab_types = df['code_display'].value_counts().head(5).index
        colors = plt.cm.viridis(np.linspace(0, 1, len(lab_types)))
        
        for i, lab_type in enumerate(lab_types):
            lab_data = df[df['code_display'] == lab_type]
            if 'value_numeric' in lab_data.columns:
                ax.scatter(lab_data['effective_date'], lab_data['value_numeric'], 
                          label=lab_type, alpha=0.7, color=colors[i])
        
        ax.set_title('Lab Results Over Time')
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def _plot_conditions_summary(self, ax):
        """Plot conditions summary"""
        if not self.clinical_data.conditions:
            ax.text(0.5, 0.5, 'No conditions data', ha='center', va='center')
            ax.set_title('Medical Conditions')
            return
        
        df = pd.DataFrame(self.clinical_data.conditions)
        condition_counts = df['code'].value_counts().head(10)
        
        if condition_counts.empty:
            ax.text(0.5, 0.5, 'No condition codes', ha='center', va='center')
            ax.set_title('Medical Conditions')
            return
        
        # Create horizontal bar chart
        y_pos = np.arange(len(condition_counts))
        ax.barh(y_pos, condition_counts.values, color='salmon', alpha=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([c[:30] + '...' if len(c) > 30 else c for c in condition_counts.index])
        ax.set_xlabel('Count')
        ax.set_title('Medical Conditions')
    
    def _plot_medications_timeline(self, ax):
        """Plot medications timeline"""
        if not self.clinical_data.medications:
            ax.text(0.5, 0.5, 'No medications data', ha='center', va='center')
            ax.set_title('Medications Timeline')
            return
        
        df = pd.DataFrame(self.clinical_data.medications)
        
        # Extract dates from different fields
        dates = []
        med_names = []
        types = []
        
        for _, row in df.iterrows():
            date = None
            if 'authored_on' in row and pd.notna(row['authored_on']):
                date = row['authored_on']
            elif 'effective_date' in row and pd.notna(row['effective_date']):
                date = row['effective_date']
            
            if date:
                dates.append(pd.to_datetime(date))
                med_names.append(row.get('medication', {}).get('display', 'Unknown'))
                types.append(row.get('type', 'unknown'))
        
        if not dates:
            ax.text(0.5, 0.5, 'No temporal medication data', ha='center', va='center')
            ax.set_title('Medications Timeline')
            return
        
        # Create timeline plot
        med_df = pd.DataFrame({'date': dates, 'medication': med_names, 'type': types})
        med_counts = med_df['medication'].value_counts().head(10)
        
        for i, (med, count) in enumerate(med_counts.items()):
            med_data = med_df[med_df['medication'] == med]
            ax.scatter(med_data['date'], [i] * len(med_data), 
                      label=med[:20], alpha=0.7, s=50)
        
        ax.set_title('Medications Timeline')
        ax.set_xlabel('Date')
        ax.set_ylabel('Medication')
        ax.set_yticks(range(len(med_counts)))
        ax.set_yticklabels([m[:20] + '...' if len(m) > 20 else m for m in med_counts.index])
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def _plot_encounters_timeline(self, ax):
        """Plot encounters timeline"""
        if not self.clinical_data.encounters:
            ax.text(0.5, 0.5, 'No encounters data', ha='center', va='center')
            ax.set_title('Hospital Encounters')
            return
        
        df = pd.DataFrame(self.clinical_data.encounters)
        
        # Extract encounter periods
        starts = []
        ends = []
        types = []
        
        for _, row in df.iterrows():
            period = row.get('period', {})
            if 'start' in period:
                start_date = pd.to_datetime(period['start'])
                end_date = pd.to_datetime(period.get('end', period['start']))
                starts.append(start_date)
                ends.append(end_date)
                types.append(row.get('class', 'Unknown'))
        
        if not starts:
            ax.text(0.5, 0.5, 'No encounter periods', ha='center', va='center')
            ax.set_title('Hospital Encounters')
            return
        
        # Create Gantt-style chart
        for i, (start, end, enc_type) in enumerate(zip(starts, ends, types)):
            duration = (end - start).days if end > start else 1
            ax.barh(i, duration, left=start, height=0.6, 
                   label=enc_type if enc_type not in [t for t in types[:i]] else "", 
                   alpha=0.7)
        
        ax.set_title('Hospital Encounters Timeline')
        ax.set_xlabel('Date')
        ax.set_ylabel('Encounter')
        if types:
            ax.legend()
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def _plot_overall_timeline(self, ax):
        """Plot overall clinical timeline"""
        if not self.clinical_data.timeline:
            ax.text(0.5, 0.5, 'No timeline data', ha='center', va='center')
            ax.set_title('Clinical Timeline')
            return
        
        df = pd.DataFrame(self.clinical_data.timeline)
        if 'date' not in df.columns:
            ax.text(0.5, 0.5, 'No temporal data', ha='center', va='center')
            ax.set_title('Clinical Timeline')
            return
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Group by event type and date
        event_types = df['event_type'].unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(event_types)))
        
        for i, event_type in enumerate(event_types):
            event_data = df[df['event_type'] == event_type]
            event_counts = event_data.groupby(event_data['date'].dt.date).size()
            
            ax.scatter(event_counts.index, [i] * len(event_counts), 
                      s=event_counts.values * 20, alpha=0.7, 
                      color=colors[i], label=event_type)
        
        ax.set_title('Clinical Activity Timeline')
        ax.set_xlabel('Date')
        ax.set_ylabel('Event Type')
        ax.set_yticks(range(len(event_types)))
        ax.set_yticklabels(event_types)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # =============================================
    # Helper Methods
    # =============================================
    
    def _extract_observation_data(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Extract observation data from FHIR resource"""
        observation = {
            "id": resource.get("id"),
            "status": resource.get("status"),
            "category": [self._extract_coding_display(cat) for cat in resource.get("category", [])],
            "code": resource.get("code", {}),
            "code_display": self._extract_code_display(resource.get("code", {})),
            "effective_date": resource.get("effectiveDateTime"),
            "issued_date": resource.get("issued"),
            "value_quantity": resource.get("valueQuantity"),
            "value_string": resource.get("valueString"),
            "value_codeable_concept": resource.get("valueCodeableConcept"),
            "value_boolean": resource.get("valueBoolean"),
            "components": self._extract_observation_components(resource.get("component", [])),
            "reference_range": resource.get("referenceRange", []),
            "raw_resource": resource
        }
        
        # Extract numeric value for plotting
        if observation["value_quantity"]:
            observation["value_numeric"] = observation["value_quantity"].get("value")
            observation["unit"] = observation["value_quantity"].get("unit")
        elif observation["components"]:
            # For multi-component observations, take first numeric component
            for comp in observation["components"]:
                if comp.get("value_numeric"):
                    observation["value_numeric"] = comp["value_numeric"]
                    observation["unit"] = comp.get("unit")
                    break
        
        return observation
    
    def _extract_observation_components(self, components: List[Dict]) -> List[Dict]:
        """Extract observation components"""
        comp_list = []
        for comp in components:
            comp_data = {
                "code": self._extract_code_display(comp.get("code", {})),
                "value_quantity": comp.get("valueQuantity"),
                "value_string": comp.get("valueString"),
                "value_codeable_concept": comp.get("valueCodeableConcept")
            }
            
            # Extract numeric value
            if comp_data["value_quantity"]:
                comp_data["value_numeric"] = comp_data["value_quantity"].get("value")
                comp_data["unit"] = comp_data["value_quantity"].get("unit")
            
            comp_list.append(comp_data)
        
        return comp_list
    
    def _get_observation_category(self, resource: Dict[str, Any]) -> str:
        """Determine observation category"""
        categories = resource.get("category", [])
        for cat in categories:
            codings = cat.get("coding", [])
            for coding in codings:
                code = coding.get("code", "").lower()
                if "vital" in code or "vital-signs" in code:
                    return "vital-signs"
                elif "laboratory" in code:
                    return "laboratory"
                elif "survey" in code:
                    return "survey"
        return "other"
    
    def _extract_code_display(self, code_obj: Dict[str, Any]) -> str:
        """Extract display text from CodeableConcept"""
        if not code_obj:
            return ""
        
        # Check for text first
        if "text" in code_obj:
            return code_obj["text"]
        
        # Check codings
        codings = code_obj.get("coding", [])
        for coding in codings:
            if "display" in coding:
                return coding["display"]
            elif "code" in coding:
                return coding["code"]
        
        return ""
    
    def _extract_coding_display(self, coding_obj: Dict[str, Any]) -> str:
        """Extract display text from Coding"""
        if not coding_obj:
            return ""
        
        codings = coding_obj.get("coding", [])
        if codings:
            coding = codings[0]
            return coding.get("display", coding.get("code", ""))
        
        return ""
    
    def _extract_medication_info(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Extract medication information"""
        medication = {}
        
        # Check for medicationCodeableConcept
        if "medicationCodeableConcept" in resource:
            medication["display"] = self._extract_code_display(resource["medicationCodeableConcept"])
            medication["coding"] = resource["medicationCodeableConcept"]
        
        # Check for medicationReference
        elif "medicationReference" in resource:
            medication["reference"] = resource["medicationReference"].get("reference")
            # Try to resolve reference if we have the medication resource
            if medication["reference"]:
                med_id = medication["reference"].replace("Medication/", "")
                if f"medication_{med_id}" in self.raw_resources:
                    med_resource = self.raw_resources[f"medication_{med_id}"]
                    medication["display"] = self._extract_code_display(med_resource.get("code", {}))
        
        return medication
    
    def _extract_dosage_instructions(self, dosage_list: List[Dict]) -> List[Dict]:
        """Extract dosage instructions"""
        instructions = []
        for dosage in dosage_list:
            instruction = {
                "text": dosage.get("text"),
                "route": self._extract_coding_display(dosage.get("route", {})),
                "timing": self._extract_timing(dosage.get("timing", {})),
                "dose_and_rate": []
            }
            
            # Extract dose and rate information
            for dose_rate in dosage.get("doseAndRate", []):
                dose_info = {}
                if "doseQuantity" in dose_rate:
                    dose_info["dose"] = dose_rate["doseQuantity"]
                if "rateQuantity" in dose_rate:
                    dose_info["rate"] = dose_rate["rateQuantity"]
                instruction["dose_and_rate"].append(dose_info)
            
            instructions.append(instruction)
        
        return instructions
    
    def _extract_administration_dosage(self, dosage: Dict[str, Any]) -> Dict[str, Any]:
        """Extract administration dosage"""
        return {
            "text": dosage.get("text"),
            "route": self._extract_coding_display(dosage.get("route", {})),
            "method": self._extract_coding_display(dosage.get("method", {})),
            "dose": dosage.get("dose", {})
        }
    
    def _extract_timing(self, timing: Dict[str, Any]) -> Dict[str, Any]:
        """Extract timing information"""
        timing_info = {}
        
        if "code" in timing:
            timing_info["code"] = self._extract_code_display(timing["code"])
        
        if "repeat" in timing:
            repeat = timing["repeat"]
            timing_info["frequency"] = repeat.get("frequency")
            timing_info["period"] = repeat.get("period")
            timing_info["period_unit"] = repeat.get("periodUnit")
            
            if timing_info["frequency"] and timing_info["period"] and timing_info["period_unit"]:
                timing_info["description"] = f"{timing_info['frequency']} time(s) per {timing_info['period']} {timing_info['period_unit']}"
        
        return timing_info
    
    def _extract_encounter_locations(self, locations: List[Dict]) -> List[Dict]:
        """Extract encounter location information"""
        location_list = []
        for loc in locations:
            location_info = {
                "location_reference": loc.get("location", {}).get("reference"),
                "period": loc.get("period", {}),
                "status": loc.get("status")
            }
            location_list.append(location_info)
        
        return location_list
    
    def _calculate_length_of_stay(self, period: Dict[str, Any]) -> Optional[int]:
        """Calculate length of stay in days"""
        if not period or "start" not in period:
            return None
        
        try:
            start = pd.to_datetime(period["start"])
            end = pd.to_datetime(period.get("end", datetime.now()))
            return (end - start).days
        except:
            return None
    
    def _add_to_timeline(self, event_type: str, data: Dict[str, Any]) -> None:
        """Add event to clinical timeline"""
        # Extract date from various possible fields
        date = None
        
        date_fields = [
            "effective_date", "effectiveDateTime", "authored_on", "recorded_date",
            "onset_date", "performed_date", "start", "collection_date"
        ]
        
        for field in date_fields:
            if field in data and data[field]:
                date = data[field]
                break
        
        # Check period start
        if not date and "period" in data and "start" in data["period"]:
            date = data["period"]["start"]
        
        if date:
            timeline_entry = {
                "date": date,
                "event_type": event_type,
                "id": data.get("id"),
                "description": self._get_event_description(event_type, data),
                "raw_data": data
            }
            self.clinical_data.timeline.append(timeline_entry)
    
    def _get_event_description(self, event_type: str, data: Dict[str, Any]) -> str:
        """Get description for timeline event"""
        if event_type == "observation":
            return data.get("code_display", "Observation")
        elif event_type == "condition":
            return data.get("code", "Condition")
        elif event_type in ["medication_request", "medication_administration", "medication_dispense"]:
            med_info = data.get("medication", {})
            return med_info.get("display", "Medication")
        elif event_type == "encounter":
            return data.get("class", "Encounter")
        elif event_type == "procedure":
            return data.get("code", "Procedure")
        else:
            return event_type.replace("_", " ").title()
    
    def _calculate_age(self) -> Optional[int]:
        """Calculate patient age"""
        if not self.demographics.birth_date:
            return None
        
        try:
            birth_date = pd.to_datetime(self.demographics.birth_date)
            if self.demographics.deceased_date:
                end_date = pd.to_datetime(self.demographics.deceased_date)
            else:
                end_date = pd.to_datetime("today")
            
            age = (end_date - birth_date).days // 365
            return max(0, age)  # Ensure non-negative age
        except:
            return None
    
    def _get_data_date_range(self) -> Dict[str, Optional[str]]:
        """Get the date range of clinical data"""
        all_dates = []
        
        for item in self.clinical_data.timeline:
            if item.get("date"):
                try:
                    all_dates.append(pd.to_datetime(item["date"]))
                except:
                    continue
        
        if not all_dates:
            return {"start": None, "end": None}
        
        return {
            "start": min(all_dates).strftime("%Y-%m-%d") if all_dates else None,
            "end": max(all_dates).strftime("%Y-%m-%d") if all_dates else None
        }
    
    def _get_key_conditions(self) -> List[str]:
        """Get key medical conditions"""
        if not self.clinical_data.conditions:
            return []
        
        conditions = [c["code"] for c in self.clinical_data.conditions if c.get("code")]
        return list(set(conditions))[:5]  # Top 5 unique conditions
    
    def _get_recent_vitals(self) -> Dict[str, Any]:
        """Get most recent vital signs"""
        if not self.clinical_data.vital_signs:
            return {}
        
        # Sort by date and get most recent
        vitals_with_dates = [v for v in self.clinical_data.vital_signs if v.get("effective_date")]
        if not vitals_with_dates:
            return {}
        
        recent_vitals = sorted(vitals_with_dates, 
                              key=lambda x: pd.to_datetime(x["effective_date"]), 
                              reverse=True)[:5]
        
        result = {}
        for vital in recent_vitals:
            code = vital.get("code_display", "Unknown")
            if vital.get("value_numeric"):
                result[code] = {
                    "value": vital["value_numeric"],
                    "unit": vital.get("unit", ""),
                    "date": vital["effective_date"]
                }
        
        return result
    
    def _get_medication_summary(self) -> Dict[str, int]:
        """Get medication summary statistics"""
        if not self.clinical_data.medications:
            return {}
        
        summary = {
            "total_medications": len(self.clinical_data.medications),
            "requests": len(self.clinical_data.medication_requests),
            "administrations": len(self.clinical_data.medication_administrations),
            "unique_medications": len(set(m.get("medication", {}).get("display", "") 
                                        for m in self.clinical_data.medications 
                                        if m.get("medication", {}).get("display")))
        }
        
        return summary
    
    # =============================================
    # Integration Methods for MIMIC Framework
    # =============================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert patient to dictionary for JSON serialization"""
        return {
            "demographics": {
                "patient_id": self.demographics.patient_id,
                "mimic_id": self.demographics.mimic_id,
                "name": self.demographics.name,
                "gender": self.demographics.gender,
                "birth_date": self.demographics.birth_date,
                "deceased_date": self.demographics.deceased_date,
                "race": self.demographics.race,
                "ethnicity": self.demographics.ethnicity,
                "marital_status": self.demographics.marital_status,
                "is_deceased": self.demographics.is_deceased,
                "age": self._calculate_age()
            },
            "encounters": self.clinical_data.encounters,
            "medications": self.clinical_data.medications,
            "lab_results": self.clinical_data.lab_results,
            "observations": self.clinical_data.observations,
            "conditions": self.clinical_data.conditions,
            "clinical_summary": self.get_summary_statistics(),
            "data_counts": {
                "observations": len(self.clinical_data.observations),
                "vital_signs": len(self.clinical_data.vital_signs),
                "lab_results": len(self.clinical_data.lab_results),
                "conditions": len(self.clinical_data.conditions),
                "medications": len(self.clinical_data.medications),
                "encounters": len(self.clinical_data.encounters),
                "procedures": len(self.clinical_data.procedures)
            },
            "follow_up_appointments": self.follow_up_appointments
        }
    
    def get_voice_summary(self) -> str:
        """Get a voice-friendly summary for speech synthesis"""
        summary = self.get_summary_statistics()
        
        age = self._calculate_age()
        age_str = f"{age} year old" if age else ""
        
        vital_count = len(self.clinical_data.vital_signs)
        lab_count = len(self.clinical_data.lab_results)
        condition_count = len(self.clinical_data.conditions)
        med_count = len(self.clinical_data.medications)
        
        voice_summary = f"""
        Patient {self.demographics.name}, MIMIC ID {self.demographics.mimic_id}, 
        is a {age_str} {self.demographics.gender} patient. 
        
        We have {vital_count} vital sign measurements, {lab_count} lab results, 
        {condition_count} medical conditions, and {med_count} medication records.
        """
        
        return voice_summary.strip()
    
    def search_data(self, query: str) -> List[Dict[str, Any]]:
        """Search through patient data"""
        results = []
        query_lower = query.lower()
        
        # Search conditions
        for condition in self.clinical_data.conditions:
            if query_lower in condition.get("code", "").lower():
                results.append({"type": "condition", "data": condition})
        
        # Search medications
        for medication in self.clinical_data.medications:
            med_name = medication.get("medication", {}).get("display", "")
            if query_lower in med_name.lower():
                results.append({"type": "medication", "data": medication})
        
        # Search observations
        for observation in self.clinical_data.observations:
            if query_lower in observation.get("code_display", "").lower():
                results.append({"type": "observation", "data": observation})
        
        return results
    
    def __str__(self) -> str:
        """String representation of patient"""
        return f"MimicPatient(id={self.demographics.patient_id}, name={self.demographics.name}, mimic_id={self.demographics.mimic_id})"
    
    def __repr__(self) -> str:
        """Detailed representation of patient"""
        summary = self.get_summary_statistics()
        return f"""MimicPatient(
    id={self.demographics.patient_id},
    mimic_id={self.demographics.mimic_id}, 
    name={self.demographics.name},
    observations={summary['data_counts']['observations']},
    conditions={summary['data_counts']['conditions']},
    medications={summary['data_counts']['medications']}
)"""
    
    # =============================================
    # Follow-up Appointment Utilities
    # =============================================
    
    def schedule_follow_up(self, scheduled_time: str, reason: str = "") -> None:
        """Save a follow-up appointment for the patient.
        
        Args:
            scheduled_time: ISO-8601 datetime string when appointment is scheduled.
            reason: Optional human-readable reason.
        """
        appointment = {
            "scheduled_time": scheduled_time,
            "reason": reason,
        }
        self.follow_up_appointments.append(appointment)
        logger.info(
            "Scheduled follow-up for %s at %s", self.demographics.patient_id, scheduled_time
        )
