# Lumenore Analytics MCP Server

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-Code%20of%20Conduct-ff69b4.svg)](CODE_OF_CONDUCT.md)

A Model Context Protocol (MCP) server that provides AI assistants with access to Lumenore's analytics and natural language query capabilities. Built with FastMCP and Python 3.13 for scalable data analytics integration.

## Quick Start

**1. Install & Run**
```bash
git clone https://github.com/Lumenore-Platform/lumenore-mcp.git
cd lumenore-mcp
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your client credentials (LUMENORE_CLIENT_ID and LUMENORE_SECRET)
python main.py
```

**2. Connect Your AI Assistant**
- **URL**: `http://localhost:8080/mcp`
- **Transport**: Streamable HTTP

**3. Start Analyzing**
```python
# Example: Get sales insights
result = await client.call_tool("nlq_to_data", {
    "userQuery": "Top 5 sales regions last month",
    "schemaId": 123
})
```

[📖 Full Documentation](#table-of-contents) | [🐛 Report Issues](#support) | [🔒 Privacy Policy](PRIVACY.md)

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Authentication](#authentication)
- [Security & Privacy](#security--privacy)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

## Overview

This MCP server provides AI assistants with access to Lumenore's powerful analytics capabilities:

- **Natural Language Queries**: Convert questions to data insights
- **Advanced Analytics**: Trends, predictions, correlations, outliers, changes, Pareto analysis
- **Real-time Processing**: Stream responses for large datasets
- **Zero Data Storage**: In-memory processing with no persistent logging. When the MCP Server forwards requests to Lumenore's backend, Lumenore's privacy policies apply

## Installation

### Prerequisites
- Python 3.13+
- Lumenore client credentials (client ID and secret)
- Access to Lumenore server instance

### Setup
```bash
git clone https://github.com/Lumenore-Platform/lumenore-mcp.git
cd lumenore-mcp
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with your credentials. You can use `.env.example` as a template:

```bash
cp .env.example .env
```

Then edit `.env` with your configuration:

### Using Client Credentials
```bash
LUMENORE_CLIENT_ID="your_client_id_here"
LUMENORE_SECRET="your_secret_here"
SERVER_URL="https://preview.lumenore.com"
```

### Configuration Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `LUMENORE_CLIENT_ID` | Yes | Client ID for client credentials authentication | None |
| `LUMENORE_SECRET` | Yes | Client secret for client credentials authentication | None |
| `SERVER_URL` | No | Lumenore server URL | `https://preview.lumenore.com` |

## Running the Server

Start the MCP server:
```bash
python main.py
```

The server runs on `http://0.0.0.0:8080` with SSE transport for real-time streaming.

## Connecting Your AI Assistant

### Claude for Desktop
1. Settings → MCP Servers
2. Add Server with:
   ```
   Name: Lumenore Analytics
   URL: http://localhost:8080/mcp
   Transport: Streamable HTTP
   ```

### Programmatic Access (Python)
```python
from mcp.client import MCPClient

client = MCPClient("http://localhost:8080/mcp", transport="streamable_http")
tools = await client.list_tools()
result = await client.call_tool("nlq_to_data", {
    "userQuery": "Top 5 sales regions last month",
    "schemaId": 123
})
```

**Connection Details**:
- **Protocol**: MCP 2024-11-05+
- **Transport**: Streamable HTTP (SSE)
- **Port**: 8080 (default)
- **Auth**: No MCP-level auth required

**Test Connection**:
```bash
curl -I http://localhost:8080  # Should return HTTP/1.1 200 OK
```

## Authentication

### Getting Your Credentials

**Client Credentials**
1. Contact Lumenore support to obtain client credentials
2. Receive your `LUMENORE_CLIENT_ID` and `LUMENORE_SECRET`
3. Store securely in your `.env` file

See the [Configuration](#configuration) section for detailed setup instructions.

### Security Best Practices
<!-- Add security best practices here by refering the code -->

### Troubleshooting Authentication Issues

**"Authorization token missing or invalid"**:
- Verify credentials are set in `.env` file:
  - For client credentials: Check both `LUMENORE_CLIENT_ID` and `LUMENORE_SECRET` are set
- Ensure Lumenore AI credits are available
- Check `SERVER_URL` points to correct Lumenore instance

## Available Tools

The server provides 8 powerful tools for data analysis:

### Dataset Management
**`get_dataset_metadata`** - Lists available datasets and schema IDs

### Natural Language Queries
**`nlq_to_data`** - Converts questions to structured data
```python
{
  "userQuery": "Top 5 sales regions last month",
  "schemaId": 123
}
```

### Advanced Analytics
**`get_trend_data`** - Identifies temporal patterns and trends
**`get_prediction_data`** - Generates forecasts and predictions
**`get_outlier_data`** - Detects anomalies and unusual patterns
**`get_correlation_data`** - Analyzes variable relationships
**`get_change_data`** - Detects pattern shifts and transitions
**`get_pareto_data`** - Performs 80/20 impact analysis

### Error Handling
All tools return standardized responses:
- **Success**: `{"data": {...}, "status": "success"}`
- **Validation Error**: `{"error": "...", "status": "validation_error"}`
- **Service Error**: `{"error": "...", "status": "error"}`

### Performance
- **Response Time**: 1-7 seconds
- **Timeout**: 60 seconds
- **Concurrency**: Multiple simultaneous requests supported

### Best Practices
1. Start with `get_dataset_metadata` to find schema IDs
2. Be specific in natural language queries
3. Always check the `status` field in responses
4. Cache frequent queries for better performance

## Usage Examples

Here are three realistic examples showing how AI assistants can interact with the Lumenore Analytics MCP Server:

### Example 1: Sales Performance Analysis

**Scenario**: A business analyst wants to understand sales performance for the last quarter.

**AI Assistant Interaction**:
```python
# Step 1: Get available datasets
metadata = await client.call_tool("get_dataset_metadata", {})

# Step 2: Query sales data
sales_data = await client.call_tool("nlq_to_data", {
    "userQuery": "Show me total sales by region for Q4 2024, sorted by highest sales",
    "schemaId": 35403
})

# Step 3: Analyze trends
trend_analysis = await client.call_tool("get_trend_data", {
    "userQuery": "What are the monthly sales trends for Q4 2024?",
    "schemaId": 35403
})

# Step 4: Identify top performers
pareto_analysis = await client.call_tool("get_pareto_data", {
    "userQuery": "Which products contribute to 80% of our sales?",
    "schemaId": 35403
})
```

**Expected Insights**:
- Regional sales breakdown with totals
- Monthly trend visualization showing growth/decline
- Product contribution analysis highlighting key revenue drivers

---

### Example 2: Customer Behavior Analysis

**Scenario**: A marketing team wants to understand customer purchasing patterns and detect anomalies.

**AI Assistant Interaction**:
```python
# Step 1: Get customer dataset information
metadata = await client.call_tool("get_dataset_metadata", {})

# Step 2: Analyze customer segments
customer_data = await client.call_tool("nlq_to_data", {
    "userQuery": "Show customer demographics and average order value by age group",
    "schemaId": 35404
})

# Step 3: Detect unusual patterns
anomaly_detection = await client.call_tool("get_outlier_data", {
    "userQuery": "Find customers with unusually high order values or frequency",
    "schemaId": 35404
})

# Step 4: Understand correlations
correlation_analysis = await client.call_tool("get_correlation_data", {
    "userQuery": "What factors correlate with customer lifetime value?",
    "schemaId": 35404
})
```

**Expected Insights**:
- Customer segmentation by demographics and spending
- Identification of potential fraud or VIP customers
- Key drivers of customer value for targeted marketing

---

### Example 3: Inventory Optimization

**Scenario**: An operations manager needs to optimize inventory levels based on demand patterns and forecasts.

**AI Assistant Interaction**:
```python
# Step 1: Get inventory dataset
metadata = await client.call_tool("get_dataset_metadata", {})

# Step 2: Analyze historical demand
demand_data = await client.call_tool("nlq_to_data", {
    "userQuery": "Show monthly demand for each product category over the past year",
    "schemaId": 35405
})

# Step 3: Identify trends
trend_analysis = await client.call_tool("get_trend_data", {
    "userQuery": "What are the demand trends for each product category?",
    "schemaId": 35405
})

# Step 4: Generate forecasts
forecast = await client.call_tool("get_prediction_data", {
    "userQuery": "Predict demand for next 3 months by product category",
    "schemaId": 35405
})

# Step 5: Detect demand changes
change_detection = await client.call_tool("get_change_data", {
    "userQuery": "Have there been any significant changes in demand patterns recently?",
    "schemaId": 35405
})
```

**Expected Insights**:
- Historical demand patterns by category
- Future demand forecasts with confidence intervals
- Early warning of demand pattern shifts
- Data-driven inventory optimization recommendations

---


**Benefits**:
- Automated data refresh without manual intervention
- Real-time insights for operational decision-making
- Reduced load on backend systems through efficient caching

---

### Best Practices from Examples

1. **Start with Metadata**: Always use `get_dataset_metadata` to understand available datasets
2. **Combine Tools**: Use multiple tools together for comprehensive analysis
3. **Specific Queries**: Be clear and specific in natural language queries
4. **Error Handling**: Always check response status before processing results
5. **Performance**: Cache frequently accessed data to improve response times

### Claude Prompts

Here are example prompts you can use with Claude when connected to this MCP server:

**For Sales Analysis**:
> "Use the Lumenore Analytics tools to analyze our Q4 sales performance. I need to see regional breakdowns, identify top-performing products, and understand sales trends."

**For Customer Insights**:
> Analyze customer demographics, find any unusual purchasing patterns, and identify what factors drive customer value. Use the available analytics tools to provide comprehensive insights."

**For Inventory Management**:
> "generate forecasts for next quarter, and identify any recent changes in demand behavior using the predictive and trend analysis tools."

---



## Error Handling

All tools implement comprehensive error handling with specific error types:

```python
# Validation errors
{
    "error": "Invalid request parameters: <details>",
    "status": "validation_error",
    "query": "<user_query>",
    "schema_id": <schema_id>
}

# Service errors
{
    "error": "<Operation> failed: <details>",
    "status": "error",
    "query": "<user_query>",
    "schema_id": <schema_id>
}
```

### Testing the Server

You can test the MCP server using any MCP-compatible client or by making HTTP requests to the SSE endpoint:

```bash
# Example: Testing with curl (adjust based on MCP protocol)
curl -N http://localhost:8080
```


## Security & Privacy

### Security Overview

The Lumenore Analytics MCP Server implements multiple layers of security to protect your data and API credentials:

#### Data Protection
- **In-Memory Processing**: All data is processed in-memory and immediately discarded after response generation
- **No Data Storage**: The MCP server does not store or log any user queries, schema IDs, or response data
- **Secure Communication**: All backend API requests use HTTPS encryption
- **Credentials Security**: Client credentials are never logged, stored, or exposed in responses

#### Authentication Security
- **Client Credentials Flow**: Industry-standard authentication using client ID and secret
- **Session Management**: Secure cookie-based session handling with automatic token refresh
- **No MCP-Level Auth**: MCP connection doesn't require authentication (backend auth is handled server-side)
- **Security Monitoring**: Failed authentication attempts are logged for security analysis

#### Credentials Best Practices
- **Environment Variables**: Store credentials in environment variables or `.env` files (never in code)
- **Regular Rotation**: Rotate credentials every 90 days or as needed
- **Scope Limitation**: Use credentials with minimal required permissions
- **Separate Environments**: Use different credentials for development, staging, and production

### Privacy Policy

For detailed information about how Lumenore handles your data, please see our [Privacy Policy](PRIVACY.md).

#### Key Privacy Principles
- **Minimal Data Processing**: Only processes queries and schema IDs provided by users
- **No Conversation History**: Does not store or log conversation history
- **User Control**: Users control what data is queried and analyzed
- **Compliance**: Designed to comply with data protection regulations (GDPR, CCPA)

#### Data Flow Privacy
```
User Query → MCP Server → Lumenore Backend → Results → User
             (No storage)   (Lumenore's privacy policy applies)
```

#### Privacy Considerations
- The MCP server acts as a secure proxy between AI assistants and Lumenore's backend
- All privacy and data handling policies of Lumenore's backend API apply to your data
- The server itself does not retain any user data beyond the immediate request processing
- Users are responsible for ensuring their queries comply with applicable data protection laws

### Compliance

#### Regulatory Compliance
- **GDPR**: Compliant with General Data Protection Regulation
- **CCPA**: Compliant with California Consumer Privacy Act
- **SOC 2**: Backend services follow SOC 2 security standards
- **ISO 27001**: Information security management best practices

#### Data Residency
- Data processing occurs in Lumenore's cloud infrastructure
- Data residency requirements should be discussed with Lumenore sales team
- Enterprise deployments may support private cloud or on-premise options

### Security Configuration

#### Environment Security
```bash
# Secure credentials management
export LUMENORE_CLIENT_ID="your_client_id"
export LUMENORE_SECRET="your_secret"

# Restrict file permissions
chmod 600 .env
chmod 700 /path/to/server/directory

# Use secure network connections only
# Avoid using public Wi-Fi for sensitive operations
```

#### Production Security
- Use dedicated client credentials for production environments
- Implement credential rotation automation
- Monitor API usage and set up alerts for unusual activity
- Consider implementing IP allowlisting for API access
- Use VPN or private networks for server communication

### Vulnerability Management

#### Reporting Security Issues
We take security seriously. If you find a vulnerability:
1. Email: [askme@lumenore.com](mailto:askme@lumenore.com)
2. Include vulnerability details and reproduction steps
3. We will acknowledge within 24 hours
4. Work with us to resolve the issue before public disclosure

#### Security Updates
- Security patches are prioritized and deployed quickly
- Subscribe to security notifications via our support channels
- Regular security assessments are performed on the infrastructure

### Data Encryption

#### In Transit
- All API communications use TLS 1.2+ encryption
- HTTPS is enforced for all backend connections
- Certificate pinning can be implemented for enhanced security

#### At Rest
- Backend data storage uses encryption at rest
- Database encryption protects stored analytics data
- Key management follows industry best practices

### Access Control

#### Principle of Least Privilege
- Client credentials should have minimal required permissions
- Separate credentials for different applications and environments
- Regular review of credential permissions and usage

#### Network Security
- Firewall rules restrict access to necessary ports only
- Consider implementing VPN access for server management
- Use network segmentation for production deployments

---

## Troubleshooting

### Quick Diagnostic Steps

1. **Check server is running**: `curl -I http://localhost:8080`
2. **Verify token is loaded**: Check server startup logs for "No authorization token" warning
3. **Test backend connectivity**: `curl -I https://preview.lumenore.com`
4. **Check MCP protocol**: Ensure client is using Streamable HTTP transport




**Example client configuration**:
```json
{
    "server": {
        "lumenore-server": {
            "type": "streamable-http",
            "url": "http://localhost:8080/mcp",
        }
    }
}
```

**Manual testing with Python**:
```python
from config import config
from core.lumenore_analytics import LumenoreAnalytics
import asyncio

async def test():
    client = LumenoreAnalytics()
    result = await client.make_request('get-domain', method='GET')
    print(result)

asyncio.run(test())
```

### Getting Help

If you've tried the above steps and still have issues:

1. **Check server logs** for detailed error messages
2. **Verify token validity** and permissions
3. **Test backend API directly** to isolate MCP vs backend issues
4. **Review MCP client configuration** for transport and URL settings
5. **Contact support** with logs and error messages (see [Support](#support) section)

## Contributing

We welcome contributions to the Lumenore Analytics MCP Server! Please follow these guidelines:

### Code of Conduct
Please note that this project is released with a [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

### How to Contribute
1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup
```bash
# Clone your fork
git clone <your-fork-url>
cd lumenore-mcp

# Install development dependencies
pip install -r requirements.txt

# Run tests (if available)
python -m pytest
```

### Reporting Bugs
Use the [issue tracker](https://github.com/lumenore/analytics-mcp-server/issues) to report bugs. Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS)

### Feature Requests
We welcome feature requests through GitHub Issues. Please:
- Search existing issues first
- Provide clear use cases
- Explain the desired functionality

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

### Contact Information

For technical support and inquiries:

- **Email**: askme@lumenore.com
- **Website**: [https://lumenore.com/](https://lumenore.com/)
- **Documentation**: [Lumenore Analytics Docs](https://help.lumenore.com/knowledge-base/lumenore_ask_me/)

---

**Version**: 1.0.0  
**Last Updated**: January 2026  
**Python**: 3.13+  
**MCP Protocol**: Compatible with MCP 2024-11-05 specification
