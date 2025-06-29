"""Response formatting utilities for consistent MCP responses."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import csv
import io


@dataclass
class MCPResponse:
    """Structured MCP response."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "timestamp": self.timestamp
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class TableFormatter:
    """Format table data for different output formats."""
    
    @staticmethod
    def to_csv(columns: List[str], rows: List[List[Any]]) -> str:
        """Format as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)
        return output.getvalue()
    
    @staticmethod
    def to_json(columns: List[str], rows: List[List[Any]]) -> str:
        """Format as JSON."""
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
        return json.dumps(data, indent=2, default=str)
    
    @staticmethod
    def to_markdown(columns: List[str], rows: List[List[Any]], max_rows: int = 50) -> str:
        """Format as Markdown table."""
        if not rows:
            return "No data available."
        
        # Limit rows for readability
        display_rows = rows[:max_rows]
        
        # Build markdown table
        lines = []
        
        # Header
        lines.append("| " + " | ".join(str(col) for col in columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        
        # Data rows
        for row in display_rows:
            row_str = " | ".join(str(cell) if cell is not None else "" for cell in row)
            lines.append(f"| {row_str} |")
        
        if len(rows) > max_rows:
            lines.append(f"\n*Showing {max_rows} of {len(rows)} rows*")
        
        return "\n".join(lines)
    
    @staticmethod
    def to_table(columns: List[str], rows: List[List[Any]], max_rows: int = 50) -> str:
        """Format as ASCII table."""
        return TableFormatter.to_markdown(columns, rows, max_rows)
