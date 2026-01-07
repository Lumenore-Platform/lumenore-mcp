# Lumenore Analytics MCP Server Privacy Policy

## Overview

This Privacy Policy explains how the Lumenore Analytics MCP Server handles user data and privacy. The Lumenore Analytics MCP Server acts as a bridge between AI assistants and Lumenore's analytics backend, providing access to powerful data analysis capabilities while maintaining strict privacy standards.

## What Data We Collect

### Data Processed by the MCP Server

The Lumenore Analytics MCP Server processes the following types of data:

1. **User Queries**: Natural language questions and requests for data analysis
2. **Schema IDs**: Numeric identifiers that reference specific datasets in Lumenore
3. **Tool Parameters**: Input parameters required for analytics tools

### Data NOT Collected or Stored

The MCP Server does **NOT** collect, store, or log:

- User identities or personal information
- Conversation history or chat logs
- Raw dataset contents
- User credentials or authentication details (beyond the API token)
- Any persistent user data

## How We Use Your Data

### Data Processing

All data processed by the MCP Server is handled as follows:

1. **In-Memory Processing**: Data is processed entirely in memory without persistent storage
2. **Immediate Discard**: All user data is discarded immediately after generating a response
3. **No Logging**: User queries and responses are not logged or recorded
4. **Real-time Processing**: Data flows through the system in real-time without retention

### Data Flow

```
User → MCP Server → Lumenore Backend → Analytics Processing → Response → User
       (In-Memory)   (Data Storage)    (Analysis)         (No Retention)
```

## Data Security

### Encryption and Protection

- **Transport Security**: All communications use HTTPS/TLS encryption
- **Token Security**: API tokens are handled securely and never exposed in logs
- **Memory Management**: Data is securely managed in application memory
- **No Persistent Storage**: No data is written to disk or databases

### Access Control

- **Minimal Access**: Only necessary data is accessed for processing requests
- **Token-Based Authentication**: Secure OAuth 2.0 Bearer token authentication
- **No Unauthorized Access**: Strict controls prevent unauthorized data access

## Third-Party Data Processing

### Lumenore Backend Services

When the MCP Server processes your requests, data is forwarded to Lumenore's backend services for analysis. Lumenore's privacy policies apply to data processed by their systems:

- **Backend Privacy**: [Lumenore Privacy Policy](https://lumenore.com/privacy-statement/)
- **Data Processing**: Backend services may store and process data according to their policies
- **Compliance**: Lumenore backend services comply with relevant data protection regulations

### Your Responsibility

Users are responsible for:

- Ensuring queries comply with applicable data protection laws
- Understanding Lumenore's backend privacy policies
- Using appropriate data handling practices in their organization

## User Rights and Control

### Data Control

Users maintain full control over their data:

- **Query Control**: Users control what questions are asked and what data is analyzed
- **No Data Retention**: Since no data is stored, there's no need for data deletion requests
- **Real-time Processing**: Data is processed immediately and not retained

### Compliance with Regulations

The MCP Server is designed to support compliance with major data protection regulations:

#### General Data Protection Regulation (GDPR)

- **Data Minimization**: Only processes necessary data for analysis
- **Purpose Limitation**: Data is used solely for analytics purposes
- **Storage Limitation**: No persistent data storage
- **Accountability**: Transparent data processing practices

#### California Consumer Privacy Act (CCPA)

- **No Data Sale**: User data is never sold or shared for commercial purposes
- **Data Access**: Users control what data is analyzed
- **Opt-out Rights**: Users can stop using the service at any time

## Data Retention

### MCP Server Retention Policy

- **Zero Retention**: The MCP Server does not retain any user data
- **Real-time Processing**: All data is processed and immediately discarded
- **No Logs**: User queries and responses are not logged or recorded
- **Memory Only**: Data exists only in application memory during processing

### Lumenore Backend Retention

Data retention for Lumenore's backend services follows their separate privacy policy and terms of service.

## Security Measures

### Technical Safeguards

- **Secure Communication**: All API calls use encrypted HTTPS connections
- **Token Management**: Secure handling of authentication tokens
- **Input Validation**: Robust validation of all user inputs
- **Error Handling**: Secure error handling that doesn't expose sensitive information

### Operational Safeguards

- **No Data Logging**: User data is never written to log files
- **Memory Management**: Secure handling of data in application memory
- **Access Controls**: Strict access controls for system components

## International Data Transfers

### Cross-Border Data Flow

Data may be transferred across international borders when:

- Connecting to Lumenore's global infrastructure
- Using distributed analytics services
- Accessing cloud-based backend services

### Data Protection

International data transfers are protected by:

- **Standard Contractual Clauses**: Where applicable, standard contractual clauses
- **Adequate Protection**: Transfers to countries with adequate data protection
- **User Consent**: Where required, explicit user consent for data transfers

## Children's Privacy

### Age Restrictions

The Lumenore Analytics MCP Server is not intended for use by children under the age of 16. We do not knowingly collect data from children.

### Parental Guidance

If the service is used by minors under appropriate supervision:

- Parental/guardian oversight is recommended
- Educational use should be monitored
- Data processing follows the same privacy standards

## Changes to This Privacy Policy

### Policy Updates

We may update this Privacy Policy from time to time. Changes will be:

- **Posted Here**: Updated policy will be posted on this page
- **Version Tracked**: Version number and date will be updated
- **User Notification**: Significant changes may be communicated through support channels

### Your Responsibility

Users should:

- **Review Periodically**: Check this policy periodically for updates
- **Understand Changes**: Review any changes before continuing to use the service
- **Contact Support**: Ask questions about policy changes through support channels

## Contact Information

### Privacy Questions

For questions about this Privacy Policy or data handling practices:

- **Email**: [askme@lumenore.com](mailto:askme@lumenore.com)
- **Support**: [Lumenore Support](https://lumenore.com/contact/)
- **Mail**: Lumenore Inc., Attn: Privacy Officer, [Company Address]


## Additional Privacy Resources

### Related Documents

- **Terms of Service**: [Lumenore Terms](https://lumenore.com/terms)
- **Cookie Policy**: [Lumenore Cookie Policy](https://lumenore.com/cookies)
- **Security Documentation**: [Lumenore Security](https://lumenore.com/security)
- **Compliance Certifications**: Available through Lumenore support


---

**Service Version**: Lumenore Analytics MCP Server v1.0.0  
**Policy Version**: 1.0  
**Effective Date**: November 2025