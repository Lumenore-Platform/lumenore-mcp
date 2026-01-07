import json
from typing import Annotated
from pydantic import Field
from core.lumenore_analytics import get_lumenore_client
from utils.logger import get_logger
from mcp_instance import mcp

logger = get_logger()


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Analyze Trend Data"
    }
)
async def get_trend_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query describing the trend analysis needed (e.g., 'show sales trends over time', 'what are the growth patterns')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Performs trend analysis to identify temporal patterns and directional changes in data.

    This tool analyzes time-based patterns, growth trends, seasonal behaviors, and
    directional changes in the specified dataset. It can identify increasing/decreasing
    trends, calculate growth rates, and detect cyclical patterns over time.

    Returns analysis results containing trend information, growth rates, seasonal patterns,
    and time series data in JSON format.
    """

    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-trend-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        # Return MCP-compliant content format
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Trend analysis failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Generate Prediction Analysis"
    }
)
async def get_prediction_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query for prediction analysis (e.g., 'predict next quarter sales', 'forecast customer growth')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Generates predictive insights and forecasts based on historical data patterns.

    This tool uses machine learning algorithms to predict future values, trends,
    and outcomes. It provides forecasts, scenario analysis, and confidence intervals
    for predictions based on historical data patterns.

    Returns prediction results including forecasts, confidence intervals, scenario analyses,
    and model insights in JSON format.
    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-prediction-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Prediction analysis failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Perform Pareto Analysis"
    }
)
async def get_pareto_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query for Pareto analysis (e.g., 'top 20% products driving revenue', 'identify key contributors')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Performs Pareto (80/20) analysis to identify the most significant contributing factors.

    This tool applies the Pareto principle to identify the vital few factors that
    contribute to the majority of results. Useful for prioritization, resource
    allocation decisions, and identifying the most impactful elements.

    Returns Pareto analysis results showing 80/20 distribution, impact rankings,
    contribution percentages, and prioritized factor lists.

    Example:
        result = await get_pareto_data(ctx, "which customers drive most revenue", 35403)

    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-pareto-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Pareto analysis failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Detect Outliers"
    }
)
async def get_outlier_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query for outlier detection (e.g., 'find unusual sales patterns', 'detect anomalies in orders')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Detects anomalies, outliers, and unusual patterns in the dataset.

    This tool identifies unusual data points, anomalies, and outliers that deviate
    significantly from normal patterns. Useful for fraud detection, quality control,
    identifying exceptional cases, and anomaly discovery.

    Returns outlier detection results including anomaly scores, outlier rankings,
    pattern summaries, and identified unusual data points.
    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-outlier-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Outlier detection failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Analyze Correlations"
    }
)
async def get_correlation_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query for correlation analysis (e.g., 'correlation between price and sales', 'relationship between marketing and revenue')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Analyzes correlations and relationships between variables in the dataset.

    This tool identifies statistical relationships, dependencies, and correlations
    between different variables. Useful for understanding which factors influence
    each other, feature selection, and relationship discovery.

    Returns correlation analysis results including correlation coefficients,
    relationship strengths, dependency mappings, and statistical insights.
    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-correlation-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Correlation analysis failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Detect Changes"
    }
)
async def get_change_data(
    userQuery: Annotated[
        str,
        Field(
            description="Natural language query for change detection (e.g., 'detect shifts in customer behavior', 'identify pattern changes')",
            min_length=1,
            max_length=5000
        )
    ],
    schemaId: Annotated[
        int,
        Field(
            description="Integer identifier for the dataset schema to analyze. Must be a positive integer.",
            gt=0
        )
    ]
):
    """
    Detects and analyzes changes, shifts, and pattern transitions in the dataset.

    This tool identifies significant changes, pattern shifts, and temporal changes
    in data over time. Useful for monitoring performance, detecting drifts,
    identifying when patterns change, and tracking behavioral shifts.

    Returns change detection results including shift points, pattern changes,
    timeline analysis, and change magnitude assessments.
    """
    try:
        client = get_lumenore_client()

        result = await client.call_endpoint(
            endpoint_name="get-change-data",
            userQuery=userQuery,
            schemaId=schemaId
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if isinstance(result, dict) else str(result)
                }
            ]
        }

    except ValueError as e:
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Change detection failed: {str(e)}",
                        "status": "error",
                        "query": userQuery,
                        "schema_id": schemaId,
                    })
                }
            ],
            "isError": True
        }
