"""Auto data visualization from CSV/JSON data"""
import json
import csv
import io
from pathlib import Path


def auto_visualize(data_text: str, chart_type: str = "auto") -> str:
    """Generate Plotly chart code from data"""
    try:
        # Try JSON first
        data = json.loads(data_text)
        if isinstance(data, list) and len(data) > 0:
            # Array of objects - good for charts
            keys = list(data[0].keys())
            numeric_keys = [k for k in keys if isinstance(data[0].get(k), (int, float))]
            categorical_keys = [k for k in keys if k not in numeric_keys]

            if not numeric_keys:
                return "No numeric columns found for visualization."

            x_key = categorical_keys[0] if categorical_keys else numeric_keys[0]
            y_key = numeric_keys[0] if numeric_keys else keys[0]

            chart_code = f"""import plotly.express as px
import json

data = {json.dumps(data, indent=2)}

fig = px.{chart_type if chart_type != "auto" else "bar"}(
    data,
    x="{x_key}",
    y="{y_key}",
    title="Data Visualization",
    template="plotly_dark"
)
fig.show()
"""
            return chart_code
    except json.JSONDecodeError:
        pass

    # Try CSV
    try:
        reader = csv.DictReader(io.StringIO(data_text))
        rows = list(reader)
        if rows:
            headers = reader.fieldnames or []
            numeric = []
            for h in headers:
                try:
                    float(rows[0].get(h, 0))
                    numeric.append(h)
                except:
                    pass

            if not numeric:
                return "No numeric columns found for visualization."

            x_key = [h for h in headers if h not in numeric][0] if [h for h in headers if h not in numeric] else numeric[0]
            y_key = numeric[0]

            chart_code = f"""import plotly.express as px
import csv
from io import StringIO

csv_data = """{data_text[:2000]}"""
reader = csv.DictReader(StringIO(csv_data))
data = list(reader)

fig = px.{chart_type if chart_type != "auto" else "bar"}(
    data,
    x="{x_key}",
    y="{y_key}",
    title="Data Visualization",
    template="plotly_dark"
)
fig.show()
"""
            return chart_code
    except Exception as e:
        return f"Could not auto-visualize: {e}"

    return "Could not parse data. Provide JSON array or CSV."
