"""Auto data visualization from CSV/JSON data."""
import csv
import io
import json


def auto_visualize(data_text: str, chart_type: str = "auto") -> str:
    """Generate Plotly chart code from JSON or CSV data."""
    plot_type = chart_type if chart_type != "auto" else "bar"

    try:
        data = json.loads(data_text)
        if isinstance(data, list) and data:
            keys = list(data[0].keys())
            numeric_keys = [k for k in keys if isinstance(data[0].get(k), (int, float))]
            categorical_keys = [k for k in keys if k not in numeric_keys]

            if not numeric_keys:
                return "No numeric columns found for visualization."

            x_key = categorical_keys[0] if categorical_keys else numeric_keys[0]
            y_key = numeric_keys[0]

            chart_code = f"""import plotly.express as px
import json

data = {json.dumps(data, indent=2)}

fig = px.{plot_type}(
    data,
    x={json.dumps(x_key)},
    y={json.dumps(y_key)},
    title="Data Visualization",
    template="plotly_dark"
)
fig.show()
"""
            return chart_code
    except json.JSONDecodeError:
        pass

    try:
        reader = csv.DictReader(io.StringIO(data_text))
        rows = list(reader)
        if rows:
            headers = reader.fieldnames or []
            numeric = []
            for header in headers:
                try:
                    float(rows[0].get(header, 0))
                    numeric.append(header)
                except (TypeError, ValueError):
                    pass

            if not numeric:
                return "No numeric columns found for visualization."

            non_numeric = [header for header in headers if header not in numeric]
            x_key = non_numeric[0] if non_numeric else numeric[0]
            y_key = numeric[0]
            csv_literal = json.dumps(data_text[:2000])

            chart_code = f"""import plotly.express as px
import csv
from io import StringIO

csv_data = {csv_literal}
reader = csv.DictReader(StringIO(csv_data))
data = list(reader)

fig = px.{plot_type}(
    data,
    x={json.dumps(x_key)},
    y={json.dumps(y_key)},
    title="Data Visualization",
    template="plotly_dark"
)
fig.show()
"""
            return chart_code
    except Exception as e:
        return f"Could not auto-visualize: {e}"

    return "Could not parse data. Provide JSON array or CSV."
