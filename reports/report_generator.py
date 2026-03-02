import os
import datetime
from typing import Optional
import pandas as pd
from jinja2 import Environment, FileSystemLoader, Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UDS Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }
        h1 { color: #333; }
        .summary { margin-bottom: 30px; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .sequence { margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        .sequence-header { background: #e9ecef; padding: 10px 15px; font-weight: bold; cursor: pointer; }
        .sequence-body { padding: 15px; background: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .pass { color: #28a745; font-weight: bold; }
        .fail { color: #dc3545; font-weight: bold; }
        .row-pass { background-color: #d4edda; }
        .row-fail { background-color: #f8d7da; }
        .log-container { background: #2b2b2b; color: #f8f8f2; padding: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>UDS Simulation Test Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Timestamp:</strong> {{ timestamp }}</p>
        <p><strong>ECU Configuration:</strong> ID: 0x7E0 (RX), 0x7E8 (TX)</p>
        <table>
            <tr>
                <th>Total Tests</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Pass Rate</th>
            </tr>
            <tr>
                <td>{{ total }}</td>
                <td>{{ passed }}</td>
                <td>{{ failed }}</td>
                <td>{{ pass_rate }}%</td>
            </tr>
        </table>
    </div>

    <h2>Test Sequences</h2>
    {% for seq in sequences %}
    <div class="sequence">
        <div class="sequence-header">{{ seq.name }} - <span class="{{ 'pass' if seq.success else 'fail' }}">{{ 'PASSED' if seq.success else 'FAILED' }}</span></div>
        <div class="sequence-body">
            <p>{{ seq.description }}</p>
            <div class="log-container">
{{ seq.logs }}
            </div>
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""


class ReportGenerator:
    """
    Generates HTML test reports after test execution.
    """

    def __init__(self, results_df: Optional[pd.DataFrame] = None) -> None:
        self.results = results_df if results_df is not None else pd.DataFrame()

    def generate(self, output_path: str, sequences_data: list) -> None:
        """Generate HTML report."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total = len(sequences_data)
        passed = sum(1 for s in sequences_data if s["success"])
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        template = Template(HTML_TEMPLATE)
        html_content = template.render(
            timestamp=timestamp,
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=round(pass_rate, 1),
            sequences=sequences_data,
        )

        with open(output_path, "w") as f:
            f.write(html_content)

        print(f"Report generated: {output_path}")


if __name__ == "__main__":
    # Example usage for standalone testing
    gen = ReportGenerator()
    data = [
        {
            "name": "Sequence 1",
            "description": "Happy Path",
            "success": True,
            "logs": "[10:00:01] TX: 10 03\n[10:00:01] RX: 50 03 ...",
        },
        {
            "name": "Sequence 2",
            "description": "Security Lockout",
            "success": False,
            "logs": "[10:00:05] TX: 27 01\n[10:00:05] RX: 7F 27 36",
        },
    ]
    gen.generate("reports/sample_report.html", data)
