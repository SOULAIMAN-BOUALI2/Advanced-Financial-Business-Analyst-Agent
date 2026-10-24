import pandas as pd
import plotly.graph_objects as go
import pytest

from data_engineering import analytics as an


@pytest.fixture
def df():
    return pd.DataFrame({
        "order_id": ["A1", "A1", "A2", "A3"],
        "date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10", "2024-03-01"]),
        "client_id": ["C1", "C1", "C2", "C3"],
        "region": ["West", "West", "East", "East"],
        "category": ["Tech", "Tech", "Furniture", "Tech"],
        "sales_amount": [100.0, 50.0, 200.0, 150.0],
        "profit": [20.0, 10.0, -5.0, 30.0],
        "quantity": [1, 2, 3, 1],
    })


def test_kpi_summary(df):
    k = an.get_kpi_summary(df)
    assert k["total_sales"] == 500.0
    assert k["total_profit"] == 55.0
    assert k["total_orders"] == 3
    assert k["profit_margin_pct"] == 11.0
    assert k["best_region"] == "East"


def test_kpi_empty():
    k = an.get_kpi_summary(pd.DataFrame(columns=["sales_amount"]))
    assert k["total_sales"] == 0.0


def test_monthly_revenue(df):
    m = an.monthly_revenue(df)
    assert len(m) == 3
    assert m.iloc[0]["sales_amount"] == 150.0


def test_aggregate_sorted(df):
    out = an.aggregate(df, "region")
    assert out.iloc[0]["region"] == "East"


def test_forecast_returns_float(df):
    assert isinstance(an.forecast_next_month(an.monthly_revenue(df)), float)


@pytest.mark.parametrize("func,kwargs", [
    (an.plot_line_chart, dict(x="date", y="sales_amount")),
    (an.plot_bar_chart, dict(x="region", y="sales_amount")),
    (an.plot_pie_chart, dict(labels="category", values="sales_amount")),
])
def test_charts_return_figure(df, func, kwargs):
    assert isinstance(func(df, **kwargs), go.Figure)


def test_missing_column_raises(df):
    with pytest.raises(ValueError):
        an.plot_bar_chart(df, x="nope", y="sales_amount")


def test_empty_df_returns_figure(df):
    assert isinstance(an.plot_bar_chart(df.iloc[0:0], "region", "sales_amount"), go.Figure)
