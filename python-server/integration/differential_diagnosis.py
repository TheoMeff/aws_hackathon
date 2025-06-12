"""differential_diagnosis.py

Provides helper for generating a differential diagnosis list for a patient
using Amazon Bedrock Claude Sonnet 4.

Why: Keep Bedrock invocation logic in one isolated place so other modules can
import and call it without duplicating code.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, Any

import boto3

logger = logging.getLogger(__name__)

# Bedrock model
DEFAULT_MODEL_ID = os.getenv(
    "CLAUDE_SONNET_MODEL_ID",
    "anthropic.claude-3-sonnet-20240229-v1:0",
)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

_bedrock_rt = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _build_prompt(symptoms: str, patient_summary: str) -> str:
    """Craft the Claude prompt for differential diagnosis.

    The prompt is deliberately concise and instructs the model to return a
    numbered list of diagnoses. We avoid including raw PHI and send only the
    minimal summary string derived from the patient object.
    """
    return (
        "You are a board-certified physician AI. Given the patient information "
        "and current symptoms, provide a differential diagnosis list ranked by "
        "likelihood with a brief rationale for each item.\n\n"  # noqa: E501
        "Patient information:\n"
        f"{patient_summary}\n\n"
        "Current symptoms:\n"
        f"{symptoms.strip()}\n\n"
        "Format your answer as:\n"
        "1. Diagnosis — Rationale\n2. …"
    )


def generate_differential_diagnosis(
    *,
    symptoms: str,
    patient_summary: str,
    model_id: str | None = None,
    max_tokens: int = 512,
) -> str:
    """Call Claude Sonnet via Bedrock and return the plain-text response.

    Raises whatever boto3 exceptions occur so the caller can handle them.
    """

    model_id = model_id or DEFAULT_MODEL_ID
    prompt = _build_prompt(symptoms, patient_summary)

    logger.info("Invoking Bedrock model %s for differential diagnosis", model_id)

    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    response = _bedrock_rt.invoke_model(
        body=json.dumps(body),
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    payload = json.loads(response["body"].read())
    # Claude Bedrock returns { "content": [ { "text": "…" } ], … }
    try:
        text = payload["content"][0]["text"]
    except (KeyError, IndexError):
        text = json.dumps(payload)
    return text
