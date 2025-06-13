// AWS Configuration for Transcribe Service
// Replace these values with your actual AWS configuration

export const REGION = process.env.REACT_APP_AWS_REGION || 'us-east-1';
export const IDENTITY_POOL_ID = process.env.REACT_APP_AWS_IDENTITY_POOL_ID || 'YOUR_IDENTITY_POOL_ID';

// You can also export additional configuration if needed
export const AWS_CONFIG = {
  region: REGION,
  identityPoolId: IDENTITY_POOL_ID
};