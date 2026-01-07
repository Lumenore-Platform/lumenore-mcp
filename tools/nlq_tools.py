import json
from typing import Annotated
from mcp_instance import mcp
from pydantic import Field
from core.lumenore_analytics import get_lumenore_client


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Natural Language Query to Data"
    }
)
async def nlq_to_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language question to convert into structured data query (e.g., 'show me top 10 customers by revenue')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to query against. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Converts natural language queries into structured data analysis results.

    This tool processes user queries expressed in plain English and transforms
    them into appropriate analytical operations on the specified dataset schema.
    The system can handle various types of analytical questions including
    sales analysis, trend identification, aggregations, and data insights.

    Returns structured data with analysis results including headers and data rows.
    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="nlq-to-data",
            stream=True,
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        # Return MCP-compliant content format
        return {
            "content": [
                {
                    "type": "text",
                    "text": result if isinstance(result, str) else json.dumps(result)
                }
            ]
        }

    except ValueError as e:
        # Return MCP-compliant error content
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Invalid request parameters: {str(e)}",
                        "status": "validation_error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }

    except Exception as e:
        # Return MCP-compliant error content
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Analysis failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                        "suggestion": "Check that you have valid authorization and schema ID",
                    })
                }
            ],
            "isError": True
        }
