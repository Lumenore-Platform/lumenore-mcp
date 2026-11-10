from fastmcp import FastMCP
from core.middleware import RawMiddleware

mcp = FastMCP(
    name="Lumenore-Analytics-MCP",
    website_url="https://lumenore.com/",
    instructions=(
        "When a user attaches a file and asks to upload it to Lumenore, upload the "
        "complete file using the upload tools; do not summarize, trim, clean, or "
        "drop columns unless the user explicitly asks. Use upload_file only when "
        "the decoded file is at most 102400 bytes (100 KiB). For larger files, "
        "use create_upload_link when the file is attached in the chat and give the "
        "user its upload_page_url. The page uploads and completes the file in the "
        "browser; do not suggest terminal commands or network allowlist changes "
        "unless the user asks or the page cannot be used. Use upload_file_from_url "
        "when the client provides a temporary HTTPS file URL; only use "
        "start_chunked_upload/upload_chunk directly for scripts or agents that can "
        "supply bytes without model-generated tool payloads, and finally "
        "complete_upload. For chunked uploads, split the raw bytes into chunks no "
        "larger than 30000 bytes, calculate total_chunks from the file size, use "
        "zero-based chunk numbers starting at 0, and provide the file's sha256 "
        "when available. Do not tell the user that a large file is too big to send "
        "when the attached file is available; use the browser upload page instead. "
        "'Lumenore' means the standard Lumenore file storage and does not require "
        "a workspace, dataset, folder, or other destination. Do not ask for a more "
        "specific location unless the user explicitly requests one. Confirm the "
        "uploaded file name after completion."
    ),
)
mcp.add_middleware(RawMiddleware())
