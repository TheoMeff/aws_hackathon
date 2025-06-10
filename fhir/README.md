# FHIR Search System

A powerful FHIR search system that provides both traditional and semantic search capabilities for medical records, with support for AWS S3 storage.

## Features

- Traditional text-based search
- Patient-specific search capabilities:
  - Find patients by name, DOB, or identifiers
  - Retrieve patient observations and vital signs
  - Get patient conditions and medications
  - View patient encounters and procedures
  - Access care team and care plan information
- Command-line interface for easy interaction

## Prerequisites

1. Python 3.8+
4. Required Python packages (see `requirements.txt`)

## Setup Instructions

### 1. Create Project Structure

First, create the required directory structure:

```bash
mkdir -p data
```

The `data` folder will be used for:
- Local SQLite database storage
- Temporary files during processing

### 2. Set Up Virtual Environment

We recommend using uv (uvenv) for managing the virtual environment:

```bash
# Install uv if not already installed
pip install uv

# Create virtual environment
uv venv .venv

# Activate virtual environment
uv activate .venv
```

### 3. Install Dependencies

Install the required packages:

Run the search interface:

```bash
python fhir_search.py
```

The interface provides several options:

1. Search by Resource Type
2. Search by Resource ID
3. Search by Text
4. Find Patient
5. Get Patient Observations
6. Get Patient Conditions
7. Get Patient Medications
8. Get Patient Encounters
9. Get Patient Allergies
10. Get Patient Procedures
11. Get Patient Care Team
12. Get Patient Care Plans
13. Get Vital Signs
14. Get Lab Results
15. Get Medication History
16. Execute Custom Query
17. List All Resource Types
18. List All Resources
19. Quit

### Example Usage

1. Find a patient:
   ```bash
   Enter your choice (1-19): 4
   Enter patient search query (name, DOB, etc.): John Smith
   ```

2. Get patient observations:
   ```bash
   Enter your choice (1-19): 5
   Enter patient ID: 12345
   ```

3. Execute custom FHIR query:
   ```bash
   Enter your choice (1-19): 16
   Enter custom FHIR query: Condition?patient=12345&status=active
   ```

## Database Structure

The system uses a SQLite database with the following structure:

```sql
CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    content JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository.