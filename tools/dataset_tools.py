import json
from mcp_instance import mcp
from typing import Annotated
from pydantic import Field
from core.lumenore_analytics import get_lumenore_client


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Get Dataset Metadata",
    }
)
async def get_dataset_metadata():
    """
    Fetches all available datasets with comprehensive metadata.

    This tool retrieves comprehensive information about all datasets available
    in the Lumenore platform, including dataset names, IDs, timestamps, and types.

    Returns JSON containing all available dataset metadata with headers and resultset
    containing dataset information including domain_id, domain_name, and domain_timestamp
    in MCP-compliant format.
    """
    try:
        client = get_lumenore_client()
        response = await client.call_endpoint(
            endpoint_name="get-domain",
            method="GET"
        )

        datasets = response.get("data", {})

        # Return MCP-compliant content format
        return {"content": [{"type": "text", "text": json.dumps(datasets, indent=2)}]}

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Failed to get dataset metadata: {str(e)}",
                            "status": "error",
                            "available": False,
                        },
                        indent=2,
                    ),
                }
            ],
            "isError": True,
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Get Metadata Details",
    }
)
async def get_metadata_info(
    schemaId: Annotated[
        int,
        Field(
            description="Unique Schema/Domain ID used to retrieve column metadata. Must be a positive integer.",
            gt=0,
        ),
    ],
):
    """
    Fetches detailed column metadata for a specific dataset schema.

    This tool retrieves all available column-level details for the given
    Schema/Domain ID within the Lumenore platform. The response includes
    essential information such as column names, aliases, descriptions,
    data types, date formats, and associated units.

    The metadata returned helps users understand the purpose, meaning, and
    structure of fields inside a dataset, enabling effective data exploration,
    modeling, and transformation.

    Returns JSON in MCP-compliant format containing a resultSet of column
    attributes mapped to the provided schemaId, including:
        - column_name
        - column_alias
        - description
        - column_datatype_name
        - column_type
        - unit
        - date_format
    """

    columns = [
        "description",
        "column_name",
        "column_alias",
        "column_type",
        "unit",
        "column_datatype_name",
        "date_format",
    ]

    try:
        client = get_lumenore_client()
        response = await client.call_endpoint(
            endpoint_name=f"metadata/get/{schemaId}",
            method="POST",
            data={
                "columns": columns,
                "domainId": schemaId,
            }
        )

        datasets = response.get("data", {})

        return {
            "content": [
                {
                    "type": "text",
                    "text": {
                        "columns": columns,
                        "data": json.dumps(
                            datasets.get("result", {}).get("resultSet", {}), indent=2
                        ),
                    },
                }
            ]
        }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Unable to fetch metadata for Schema/Domain ID {schemaId}: {str(e)}",
                            "status": "failed",
                            "success": False,
                        },
                        indent=2,
                    ),
                }
            ],
            "isError": True,
        }
